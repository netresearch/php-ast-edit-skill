#!/usr/bin/env python3
"""Summarize the check arms: did the model run a check the tool had already run?

Reads one or more prepared campaign directories and reports, per arm, the manipulation
check first — an integrated run whose `apply` never carried `alreadyRun` received no
treatment and is counted, not dropped — then the primary outcome and the cost columns.

    python3 check_arms.py /tmp/campaign-a /tmp/campaign-b
"""

import json
import statistics
import sys
from pathlib import Path

ARMS = ("check_manual", "check_integrated")
CHECK = "check.php"


def load(path):
    # Campaign directories are operator-selected local evidence; see benchmarks/TRUST.md.
    return json.loads(Path(path).read_text())  # NOSONAR(S2083, S8707)


def lines(path):
    if not Path(path).exists():  # NOSONAR(S6549)
        return []
    return [
        json.loads(row)
        for row in Path(path).read_text().splitlines()  # NOSONAR(S2083, S8707)
        if row.strip()
    ]


def bash_commands(raw):
    """Every Bash command the model issued, in order."""
    commands = []
    for event in lines(raw):
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "Bash"
            ):
                commands.append(block.get("input", {}).get("command", ""))
    return commands


def engine_calls(audit):
    """(applies, applies whose report carried alreadyRun)."""
    events = lines(audit)
    applies = [
        event
        for event in events
        if event.get("event") == "engine_request"
        and event.get("argv")
        and event["argv"][0] == "apply"
    ]
    already = [
        event
        for event in events
        if event.get("event") == "engine_result"
        and "alreadyRun" in event.get("stdout", "")
    ]
    return len(applies), len(already)


def classify(commands):
    """How often the model ran the check itself, and whether after its last apply.

    A command that both applies and checks counts as a check after the apply: the
    check still ran on the tree the apply had just verified.
    """
    ran = [index for index, text in enumerate(commands) if CHECK in text]
    applied = [
        index
        for index, text in enumerate(commands)
        if "apply" in text and "php-ast-edit" in text
    ]
    after = [index for index in ran if applied and index >= max(applied)]
    return len(ran), bool(after)


def resolve_evidence(base, row):
    """Where this run's evidence is now, which is not always where it was written.

    The schedule records the absolute path the campaign ran at. An unpacked evidence
    archive sits somewhere else, so fall back to the layout the runner creates. Falling
    back silently to a directory that is not there would report a campaign as empty, so
    the missing path is raised rather than skipped.
    """
    # The schedule's own recorded path, and the campaign the operator named; both are
    # local evidence locations, not request input. See benchmarks/TRUST.md.
    recorded = Path(row["evidence"])
    if recorded.is_dir():  # NOSONAR(S6549)
        return recorded
    relocated = base / "runs" / row["run_id"] / "evidence"
    if relocated.is_dir():
        return relocated
    raise FileNotFoundError(
        f"{row['run_id']}: no evidence at {recorded} or {relocated}"
    )


def rows(campaigns):
    collected = []
    for campaign in campaigns:
        base = Path(campaign)
        config = load(base / "config.json")
        for row in load(base / "schedule.json"):
            if row["variant"] not in ARMS:
                continue
            evidence = resolve_evidence(base, row)
            measurement = load(evidence / "measurement.json")
            applies, already = engine_calls(evidence / "engine-audit.jsonl")
            total, after = classify(bash_commands(evidence / "raw.jsonl"))
            collected.append(
                {
                    "campaign": base.name,
                    "run_id": row["run_id"],
                    "arm": row["variant"],
                    "task": row["task_id"],
                    "model": row["model_key"],
                    "source_commit": config["source_commit"],
                    "oracle_passed": (measurement.get("oracle") or {}).get("passed"),
                    "applies": applies,
                    "already_run_reports": already,
                    "own_check_runs": total,
                    "checked_after_last_apply": after,
                    "rounds": measurement.get("primary_model_rounds"),
                    "total_tokens": measurement["all_model_tokens"]["totalTokens"],
                    "output_tokens": measurement["all_model_tokens"]["outputTokens"],
                    "wall_s": round(measurement["candidate_wall_ms"] / 1000, 1),
                    "usd": measurement["native_list_price_usd"],
                }
            )
    return collected


def median(values):
    return statistics.median(values) if values else None


def summarize(collected):
    report = {"runs": len(collected), "arms": {}}
    treated = [row for row in collected if row["arm"] == "check_integrated"]
    report["manipulation_check"] = {
        "integrated_runs": len(treated),
        "with_already_run": sum(1 for row in treated if row["already_run_reports"]),
        "untreated_run_ids": [
            row["run_id"] for row in treated if not row["already_run_reports"]
        ],
    }
    for arm in ARMS:
        selected = [row for row in collected if row["arm"] == arm]
        if not selected:
            continue
        report["arms"][arm] = {
            "n": len(selected),
            "checked_after_last_apply": sum(
                1 for row in selected if row["checked_after_last_apply"]
            ),
            "own_check_runs_total": sum(row["own_check_runs"] for row in selected),
            "oracle_passed": sum(1 for row in selected if row["oracle_passed"]),
            "median_rounds": median([row["rounds"] for row in selected]),
            "median_total_tokens": median([row["total_tokens"] for row in selected]),
            "median_output_tokens": median([row["output_tokens"] for row in selected]),
            "median_wall_s": median([row["wall_s"] for row in selected]),
            "median_usd": median([row["usd"] for row in selected]),
        }
    return report


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    collected = rows(sys.argv[1:])
    print(json.dumps({"summary": summarize(collected), "runs": collected}, indent=2))


if __name__ == "__main__":
    main()
