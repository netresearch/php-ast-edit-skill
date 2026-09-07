#!/usr/bin/env python3
"""Freeze and evaluate a separate 2x2 result-evidence and verification-guidance pilot."""

import argparse
import json
import random
import shlex
import shutil
import statistics
import subprocess
from collections import Counter
from pathlib import Path

import pilot
from lsp import require

EXPERIMENT = "postcheck-2x2-v1"
SIZES = (10, 50)
TREATMENTS = (
    (False, "current"),
    (True, "current"),
    (False, "scoped"),
    (True, "scoped"),
)
SCOPED = """
Use reported facts only for their stated scope. Do not repeat parser or lint checks,
edit counts or changed-file counts that the report already confirms as passed.
If the report explicitly confirms that actual file bytes match only its validated
Identifier replacements, do not reread files or inspect a diff solely to reconfirm
that byte-level fact. Trust no evidence that the report does not actually provide.
Still independently address reference completeness and relevant behavior using
available source information or appropriate project checks. Resolver completeness
remains unknown even when every returned edit and all syntax checks pass. Remaining
old-name text alone does not establish a failed rename; determine whether it belongs
to the requested symbol. Never treat failed, skipped or not-run checks as passed.
After addressing those obligations, finish without repeating established checks.
"""


def schedule():
    blocks = [(size, repeat) for size in SIZES for repeat in range(3)]
    # Reproducible trial order, never a secret or authorization decision.
    random.Random(20260908).shuffle(blocks)  # NOSONAR(S2245)
    rows = []
    for block, (size, repeat) in enumerate(blocks):
        rotation = block % len(TREATMENTS)
        for evidence, guidance in TREATMENTS[rotation:] + TREATMENTS[:rotation]:
            rows.append(
                {
                    "id": f"run{len(rows) + 1:03d}",
                    "size": size,
                    "repetition": repeat,
                    "evidence": evidence,
                    "guidance": guidance,
                    "arm": ("evidence" if evidence else "legacy") + "-" + guidance,
                }
            )
    return rows


def prompts(size, command, guidance):
    require(guidance in ("current", "scoped"), "Unknown guidance treatment")
    instruction = f"Use the experimental symbol-aware AST command for this rename: {shlex.quote(str(command))} --file Provider.php --select 'method:Provider::fetch' --to load. It resolves references, applies one guarded transaction and reports validation; completeness is unknown. It retains edits on verification failure (exit 1)."
    prompt = f"Rename Example\\Provider::fetch to load in Provider.php and all its PHP callers in this workspace ({size} PHP files). Preserve Other::fetch, its callers and unrelated fetch text.\n\n{instruction}"
    return pilot.COMMON + (SCOPED if guidance == "scoped" else ""), prompt


def cli_identity():
    executable = shutil.which("claude")
    require(executable is not None, "Claude CLI is unavailable")
    return executable, pilot.invoke([executable, "--version"]).stdout.strip()


def prepare(args):
    require(
        not pilot.invoke(["git", "status", "--porcelain"], pilot.SOURCE).stdout,
        "Commit source before preparation",
    )
    phar = args.phpactor.resolve(strict=True)
    require(pilot.sha(phar) == pilot.PHAR_SHA256, "Wrong pinned Phpactor PHAR")
    cli, cli_version = cli_identity()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    source = output / "source"
    source.mkdir()
    # Fixed local archive tools and operator-selected paths; see ../TRUST.md.
    archive = subprocess.check_output(  # NOSONAR(S2076, S6350)
        ["git", "archive", "HEAD"], cwd=pilot.SOURCE
    )
    subprocess.run(  # NOSONAR(S2076, S6350)
        ["tar", "-x", "-C", str(source)], input=archive, check=True
    )
    shutil.copytree(pilot.SOURCE / "vendor", source / "vendor")
    shutil.copyfile(phar, output / pilot.PHAR_FILE)
    rows = schedule()
    for row in rows:
        run = output / row["id"]
        run.mkdir()
        work = run / "work"
        pilot.save(run / pilot.EXPECTED_FILE, pilot.fixture(work, row["size"]))
        pilot.save(run / pilot.INITIAL_FILE, pilot.manifest(work))
        pilot.invoke(["git", "init", "-q"], work, env=pilot.environment())
        pilot.invoke(["git", "add", "--", "*.php"], work, env=pilot.environment())
        pilot.invoke(
            [
                "git",
                "-c",
                "user.name=Benchmark",
                "-c",
                "user.email=benchmark@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Initial fixture",
            ],
            work,
            env=pilot.environment(),
        )
        state = run / "state"
        state.mkdir()
        command = run / "rename-tool"
        argv = [
            "python3",
            str(source / "benchmarks/symbol-intent/symbol_intent.py"),
            "rename_method",
            "--root",
            str(work),
            "--state",
            str(state),
            "--phpactor",
            str(output / pilot.PHAR_FILE),
        ]
        if row["evidence"]:
            argv.append("--evidence")
        command.write_text(
            "#!/usr/bin/env python3\nimport os,sys\nos.execvp('python3', "
            + repr(argv)
            + " + sys.argv[1:])\n"
        )
        command.chmod(0o755)
        system, prompt = prompts(row["size"], command, row["guidance"])
        (run / pilot.SYSTEM_FILE).write_text(system)
        (run / pilot.PROMPT_FILE).write_text(prompt)
        row["frozen"] = {
            name: pilot.sha(run / name)
            for name in (
                pilot.EXPECTED_FILE,
                pilot.INITIAL_FILE,
                pilot.SYSTEM_FILE,
                pilot.PROMPT_FILE,
                "rename-tool",
            )
        }
    config = {
        "experiment": EXPERIMENT,
        "source_commit": pilot.invoke(
            ["git", "rev-parse", "HEAD"], pilot.SOURCE
        ).stdout.strip(),
        "source_manifest": pilot.manifest(source),
        "phpactor_sha256": pilot.sha(output / pilot.PHAR_FILE),
        "model": pilot.MODEL,
        "cli": cli,
        "cli_version": cli_version,
        "schedule": rows,
        "max_run_usd": 0.5,
        "campaign_usd": 4.0,
        "timeout_seconds": 120,
    }
    pilot.save(output / pilot.CONFIG_FILE, config)
    (output / "config.sha256").write_text(pilot.sha(output / pilot.CONFIG_FILE) + "\n")
    print(
        json.dumps(
            {
                "prepared": str(output),
                "source_commit": config["source_commit"],
                "candidates": len(rows),
                "model_calls": 0,
            }
        )
    )


def configuration(output):
    config = json.loads((output / pilot.CONFIG_FILE).read_text())
    pilot.validate(output, config)
    require(config.get("experiment") == EXPERIMENT, "Not this frozen experiment")
    require(
        [{k: v for k, v in row.items() if k != "frozen"} for row in config["schedule"]]
        == schedule(),
        "Unexpected experiment schedule",
    )
    return config


def run(args):
    output = args.output.resolve(strict=True)
    configuration(output)
    require(
        Path(__file__).resolve()
        == output / "source/benchmarks/symbol-intent/postcheck_pilot.py",
        "Run the controller inside the prepared source snapshot",
    )
    # The imported runner validates this entire frozen source tree around every call.
    # No original-campaign recovery or candidate replacement is enabled here.
    pilot.run_pilot(
        argparse.Namespace(
            output=output, execute_models=args.execute_models, resume_reviewed=False
        )
    )


def post_calls(events, command):
    """Observable later calls, not an automatic judgment of unnecessary checking."""
    calls = {}
    success_event = None
    for index, event in enumerate(events):
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                calls.setdefault(block["id"], (index, block))
            if block.get("type") != "tool_result" or success_event is not None:
                continue
            call = calls.get(block["tool_use_id"], (None, {}))[1]
            if call.get("name") != "Bash" or command not in call.get("input", {}).get(
                "command", ""
            ):
                continue
            content = block.get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    part.get("text", "")
                    for part in content
                    if part.get("type") == "text"
                )
            try:
                report = json.loads(content)
            except (TypeError, ValueError):
                continue
            if (
                isinstance(report, dict)
                and report.get("ok") is True
                and not block.get("is_error")
            ):
                success_event = index
    later = [
        block
        for index, block in calls.values()
        if success_event is not None and index > success_event
    ]
    return {
        "subsequent_tool_calls": len(later) if success_event is not None else None,
        "subsequent_tools": dict(Counter(block["name"] for block in later)),
        "boundary": "First parseable successful rename-tool result; work batched inside a shell call is not separated",
    }


def records(output, config):
    result = []
    for row in config["schedule"]:
        run_dir = output / row["id"]
        pilot.validate(output, config, row)
        measurement = run_dir / pilot.MEASUREMENT_FILE
        trace = run_dir / pilot.NATIVE_FILE
        if not any(
            path.exists() for path in (measurement, trace, run_dir / "process.json")
        ):
            continue
        record = {**row, "oracle": None, "postcheck": {"subsequent_tool_calls": None}}
        if measurement.exists():
            measured = json.loads(measurement.read_text())
            require(
                all(measured.get(k) == v for k, v in row.items()),
                "Measurement treatment drift",
            )
            record.update(measured)
        else:
            record["accounting_error"] = (
                "Attempt has no completed measurement; raw evidence retained"
            )
            process = run_dir / "process.json"
            if process.exists():
                captured = json.loads(process.read_text())
                require(
                    all(captured.get(k) == v for k, v in row.items()),
                    "Process treatment drift",
                )
                record.update(captured)
        if "native" in record:
            require(trace.is_file(), "Missing native trace for measured usage")
        if trace.exists():
            events, malformed = pilot.native.read_events(trace)
            if malformed:
                require("native" not in record, "Malformed trace for measured usage")
                record["accounting_error"] = (
                    "Malformed incomplete trace; raw evidence retained"
                )
            else:
                record["postcheck"] = post_calls(events, str(run_dir / "rename-tool"))
                if "native" in record:
                    require(
                        record["native"]
                        == pilot.accounting.summarize(events, config["model"]),
                        "Measurement no longer matches native accounting",
                    )
        result.append(record)
    return result


def metrics(record):
    native = record.get("native", {}) if not record.get("accounting_error") else {}
    return {
        "tokens": native.get("all_model_tokens", {}).get("totalTokens"),
        "calls": native.get("tool_calls"),
        "rounds": native.get("primary_model_rounds"),
        "wall_ms": record.get("wall_time_ms"),
        "usd": native.get("native_list_price_usd"),
        "post_calls": record.get("postcheck", {}).get("subsequent_tool_calls"),
    }


def distributions(values, prefix=""):
    result = {}
    for key, data in values.items():
        result[prefix + key] = data
        result["median_" + prefix + key] = statistics.median(data) if data else None
    return result


def summarize_records(attempts):
    cells, effects = [], []
    for size in SIZES:
        for evidence, guidance in TREATMENTS:
            group = [
                r
                for r in attempts
                if (r["size"], r["evidence"], r["guidance"])
                == (size, evidence, guidance)
            ]
            values = {
                key: [metrics(r)[key] for r in group if metrics(r)[key] is not None]
                for key in metrics({})
            }
            cells.append(
                {
                    "size": size,
                    "evidence": evidence,
                    "guidance": guidance,
                    "attempts": len(group),
                    "successes": sum(
                        (r.get("oracle") or {}).get("success", False) for r in group
                    ),
                    "unknown_oracle": sum(r.get("oracle") is None for r in group),
                    "known_usage": len(values["tokens"]),
                    **distributions(values),
                }
            )
        for factor, controls in (
            ("evidence", ("current", "scoped")),
            ("guidance", (False, True)),
        ):
            for control in controls:
                deltas = {key: [] for key in metrics({})}
                pair_ids = []
                for repeat in range(3):
                    pair = []
                    for treatment in (
                        (False, True) if factor == "evidence" else ("current", "scoped")
                    ):
                        evidence, guidance = (
                            (treatment, control)
                            if factor == "evidence"
                            else (control, treatment)
                        )
                        pair.append(
                            next(
                                (
                                    r
                                    for r in attempts
                                    if (
                                        r["size"],
                                        r["repetition"],
                                        r["evidence"],
                                        r["guidance"],
                                    )
                                    == (size, repeat, evidence, guidance)
                                ),
                                None,
                            )
                        )
                    if any(r is None for r in pair):
                        continue
                    before, after = (metrics(r) for r in pair)
                    observed = {"ids": [r["id"] for r in pair]}
                    for key, values in deltas.items():
                        observed["delta_" + key] = None
                        if before[key] is not None and after[key] is not None:
                            difference = after[key] - before[key]
                            observed["delta_" + key] = difference
                            values.append(difference)
                    pair_ids.append(observed)
                effects.append(
                    {
                        "size": size,
                        "factor": factor,
                        "held_constant": control,
                        "pairs": pair_ids,
                        **distributions(deltas, "delta_"),
                    }
                )
    return {
        "experiment": EXPERIMENT,
        "planned_attempts": 24,
        "attempts": len(attempts),
        "known_usage": sum(metrics(r)["tokens"] is not None for r in attempts),
        "known_native_list_price_usd": sum(metrics(r)["usd"] or 0 for r in attempts),
        "cells": cells,
        "paired_effects": effects,
        "interpretation": "Only this 2x2 experiment is compared. Deltas are evidence-minus-legacy or scoped-minus-current. Subsequent calls can include necessary semantic checks; manual trace review is required. Three repetitions per cell do not establish general effects.",
    }


def summarize(args):
    output = args.output.resolve(strict=True)
    config = configuration(output)
    attempts = records(output, config)
    summary = summarize_records(attempts)
    summary["config_sha256"] = pilot.sha(output / pilot.CONFIG_FILE)
    pilot.save(output / "postcheck-runs.json", attempts)
    pilot.save(output / "postcheck-summary.json", summary)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("prepare", "run", "summarize"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--phpactor", type=Path, required=True)
        if name == "run":
            command.add_argument("--execute-models", action="store_true")
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "summarize": summarize}[args.action](args)


if __name__ == "__main__":
    main()
