"""Verify published accounting and replay trusted fixtures; never call a model.

All files and commands are operator-selected local evidence. The pinned repository
grader executes repository-owned PHP oracles, as documented in README.md and TRUST.md.
"""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
REPO = BUNDLE.parents[3]


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv, cwd):
    # Fixed local evaluator argv; no shell or candidate-selected command. See README.md.
    return subprocess.run(  # NOSONAR(S6350)
        argv, cwd=cwd, capture_output=True, text=True, check=True, timeout=60
    ).stdout


def check(condition, message):
    if not condition:
        raise ValueError(message)


def check_native(run):
    events = [
        json.loads(line) for line in (run / "native.jsonl").read_text().splitlines()
    ]
    result = next(event for event in reversed(events) if event["type"] == "result")
    measured = load(run / "measurement.json")
    check(
        result["modelUsage"] == measured["all_model_usage"],
        "Native model usage differs",
    )
    counters = [
        "inputTokens",
        "outputTokens",
        "cacheReadInputTokens",
        "cacheCreationInputTokens",
        "thinkingTokens",
    ]
    totals = {
        key: sum(model[key] for model in result["modelUsage"].values())
        for key in counters
    }
    totals["totalInputTokens"] = sum(
        totals[key] for key in counters if key not in ["outputTokens", "thinkingTokens"]
    )
    totals["totalTokens"] = totals["totalInputTokens"] + totals["outputTokens"]
    check(totals == measured["all_model_tokens"], "Normalized totals differ")
    check(
        result["total_cost_usd"] == measured["native_list_price_usd"],
        "Native USD differs",
    )
    responses, tools, results = set(), {}, {}
    for event in events:
        message = event.get("message", {})
        if event["type"] == "assistant":
            responses.add(message["id"])
        for block in message.get("content", []):
            if block["type"] == "tool_use":
                tools[block["id"]] = block
            if block["type"] == "tool_result":
                results[block["tool_use_id"]] = block
    check(len(responses) == measured["primary_model_rounds"], "Response count differs")
    check(set(tools) == set(results), "Tool/result IDs differ")
    check(len(tools) == len(results) == measured["tool_calls"], "Tool coverage differs")
    check(
        sum(bool(item.get("is_error")) for item in results.values())
        == measured["failed_tool_calls"],
        "Tool failure count differs",
    )
    check(result["num_turns"] == measured["native_num_turns"], "CLI turn count differs")
    init = events[0]
    check(init["model"] == "claude-sonnet-4-6", "Unexpected model")
    check(init["tools"] == ["Bash", "Edit", "Read", "Write"], "Tool access differs")
    check(
        not any(init[key] for key in ["skills", "plugins", "mcp_servers"]),
        "Global context contamination",
    )
    return measured


def replay(run, measured, fixtures, temporary, grader, manifest_hash):
    work = temporary / run.name
    work.mkdir()
    for filename, content in fixtures[measured["task_id"]].items():
        target = work / filename
        target.write_text(content)
    baseline = {name: digest(work / name) for name in fixtures[measured["task_id"]]}
    check(baseline == load(run / "initial-hashes.json"), "Initial bytes differ")
    command(["git", "apply", "--check", str(run / "diff.patch")], work)
    command(["git", "apply", str(run / "diff.patch")], work)
    check(
        {name: digest(work / name) for name in baseline}
        == load(run / "final-hashes.json"),
        "Replayed bytes differ",
    )
    state = temporary / f"{run.name}.state.json"
    state.write_text(
        json.dumps(
            {
                "task_id": measured["task_id"],
                "work": str(work),
                "task_manifest_sha256": manifest_hash,
                "baseline": baseline,
            }
        )
    )
    output = temporary / f"{run.name}.oracle.json"
    command(
        [
            "python3",
            str(grader),
            "grade",
            measured["task_id"],
            "--work",
            str(work),
            "--state",
            str(state),
            "--output",
            str(output),
        ],
        REPO,
    )
    check(load(output) == load(run / "oracle.json"), "Replayed oracle differs")


def main():
    for line in (BUNDLE / "SHA256SUMS").read_text().splitlines():
        checksum, filename = line.split("  ", 1)
        check(digest(BUNDLE / filename) == checksum, f"Checksum mismatch: {filename}")
    provenance = load(BUNDLE / "source-provenance.json")
    commit = provenance["source_commit"]
    fixtures = load(BUNDLE / "initial-fixtures.json")
    runs = sorted((BUNDLE / "runs").iterdir())
    check(len(runs) == 12, "Expected twelve retained runs")
    measured = [check_native(run) for run in runs]
    summary = command(
        [
            "jq",
            "-s",
            "-f",
            str(BUNDLE / "summarize.jq"),
            *[str(run / "measurement.json") for run in runs],
        ],
        REPO,
    )
    check(
        json.loads(summary) == load(BUNDLE / "summary.json"),
        "Published summary differs",
    )
    with tempfile.TemporaryDirectory(prefix="php-ast-pilot-verify-") as scratch:
        temporary = Path(scratch)
        benchmarks = temporary / "benchmarks"
        benchmarks.mkdir()
        for filename, expected in [
            ("tasks.json", provenance["task_manifest_sha256"]),
            ("agent_benchmark.py", provenance["grader_sha256"]),
        ]:
            target = benchmarks / filename
            target.write_text(
                command(["git", "show", f"{commit}:benchmarks/{filename}"], REPO)
            )
            check(digest(target) == expected, "Pinned source differs")
        selected = [
            task
            for task in load(benchmarks / "tasks.json")["tasks"]
            if task["id"] in fixtures
        ]
        check(
            selected == load(BUNDLE / "task-source.json"),
            "Task excerpts differ from pinned source",
        )
        for run, row in zip(runs, measured):
            replay(
                run,
                row,
                fixtures,
                temporary,
                benchmarks / "agent_benchmark.py",
                provenance["task_manifest_sha256"],
            )
    print(
        "OK: published checksums, native accounting, 12 diffs and pinned runtime oracles; model calls: 0"
    )


if __name__ == "__main__":
    main()
