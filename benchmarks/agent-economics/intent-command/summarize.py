#!/usr/bin/env python3
"""Add direct intent-command accounting to the released offline reporter.

The v0.8 reporter remains the source of truth for evidence paths, native metrics,
correctness, cells and existing unknown handling.  This small layer only reads the
already validated evidence path in each reported run and pairs the proxy's
``engine_request``/``engine_result`` records for the direct ``rename`` command.
"""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PILOT_REPORTER_PATH = HERE.parent / "v080-pilot" / "summarize.py"
ENGINE_AUDIT_FILE = "engine-audit.jsonl"


def _load_pilot_reporter() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_economics_v080_summarize", PILOT_REPORTER_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load reporter: {PILOT_REPORTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PILOT = _load_pilot_reporter()


def _empty_intent(
    observation: str = "unknown_missing_audit",
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "intent_calls": None,
        "failed_intent_calls": None,
        "intent_observation": observation,
        "intent_unknown": True,
        "intent_records": [],
        "intent_errors": errors or [],
    }


def _rename_requests(requests: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [request for request in requests.values() if _is_rename_request(request)]


def _is_rename_request(request: dict[str, Any]) -> bool:
    argv = request.get("argv")
    return isinstance(argv, list) and bool(argv) and argv[0] == "rename"


def _collect_intent_records(
    requests: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
    errors: list[dict[str, Any]],
    complete: bool,
) -> tuple[list[dict[str, Any]], int, bool, bool]:
    records: list[dict[str, Any]] = []
    failed = 0
    malformed_pair = False
    for request in requests:
        call_id = request["id"]
        result = results.get(call_id)
        exit_code = result.get("exit_code") if result else None
        paired = type(exit_code) is int
        if not paired:
            complete = False
            malformed_pair = malformed_pair or result is not None
            errors.append(
                {
                    "file": ENGINE_AUDIT_FILE,
                    "id": call_id,
                    "error": "rename request has no paired integer exit_code",
                }
            )
        if paired and exit_code != 0:
            failed += 1
        records.append(
            {
                "call_id": call_id,
                "argv": request.get("argv"),
                "exit_code": exit_code,
                "paired": paired,
            }
        )
    return records, failed, complete, malformed_pair


def _append_orphan_errors(
    results: dict[str, dict[str, Any]],
    requests: dict[str, dict[str, Any]],
    errors: list[dict[str, Any]],
) -> bool:
    # Result records have no argv. Without their request we cannot know whether
    # an orphan belongs to apply or rename; retain intact pairs but leave totals
    # unknown rather than attributing the missing command by assumption.
    orphan_results = results.keys() - requests.keys()
    for call_id in sorted(orphan_results):
        errors.append(
            {
                "file": ENGINE_AUDIT_FILE,
                "id": call_id,
                "error": "engine result has no request",
            }
        )
    return not orphan_results


def _unknown_intent(
    empty: dict[str, Any],
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    malformed: bool,
    parser_errors: bool,
    malformed_pair: bool,
) -> dict[str, Any]:
    status = (
        "unknown_malformed"
        if malformed or parser_errors or malformed_pair
        else "unknown_unpaired"
    )
    return {
        **empty,
        "intent_observation": status,
        "intent_records": records,
        "intent_errors": errors,
    }


def _intent_summary(evidence: Path | None) -> dict[str, Any]:
    """Return independent direct-command counts, retaining incomplete evidence."""

    empty = _empty_intent()
    if evidence is None:
        return _empty_intent("unknown_missing_evidence")
    path = evidence / ENGINE_AUDIT_FILE
    if path.is_symlink():
        return _empty_intent(
            "unknown_malformed",
            [
                {
                    "file": ENGINE_AUDIT_FILE,
                    "error": "engine audit path is a symlink and was rejected",
                }
            ],
        )
    if not path.exists():
        return empty

    errors: list[dict[str, Any]] = []
    try:
        events, malformed = PILOT.read_jsonl(path)
    except OSError as error:
        return _empty_intent(
            "unknown_unreadable",
            [{"file": ENGINE_AUDIT_FILE, "error": str(error)}],
        )

    requests, results = PILOT.index_engine_events(events, malformed, errors)
    parser_errors = bool(errors)
    records, failed, complete, malformed_pair = _collect_intent_records(
        _rename_requests(requests), results, errors, not malformed and not errors
    )
    complete = complete and _append_orphan_errors(results, requests, errors)

    if not complete:
        return _unknown_intent(
            empty, records, errors, malformed, parser_errors, malformed_pair
        )
    return {
        "intent_calls": len(records),
        "failed_intent_calls": failed,
        "intent_observation": "known",
        "intent_unknown": False,
        "intent_records": records,
        "intent_errors": [],
    }


def _augment_run(run: dict[str, Any], campaign: Path) -> dict[str, Any]:
    evidence_value = run.get("evidence_path")
    evidence = Path(evidence_value) if isinstance(evidence_value, str) else None
    # The path has already been selected by the released reporter's containment
    # checks.  Refuse a surprising path if this wrapper is called with a modified
    # report record in an embedding process.
    if evidence is not None:
        try:
            resolved = evidence.resolve()
            base = campaign.resolve()
            if resolved != base and base not in resolved.parents:
                evidence = None
        except OSError:
            evidence = None
    return {**run, **_intent_summary(evidence)}


def _intent_metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [
        row[key]
        for row in rows
        if type(row.get(key)) in (int, float) and math.isfinite(row[key])
    ]
    return {
        "median": statistics.median(values) if values else None,
        "n": len(values),
        "denominator": len(rows),
    }


def _augment_cell(group: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = sum(row.get("intent_observation") == "known" for row in rows)
    return {
        **group,
        "intent_calls": _intent_metric(rows, "intent_calls"),
        "failed_intent_calls": _intent_metric(rows, "failed_intent_calls"),
        "intent_observations": {
            "known": known,
            "unknown": len(rows) - known,
            "denominator": len(rows),
        },
    }


def summarize_campaign(campaign: str | Path) -> dict[str, Any]:
    """Preserve the released report and add intent-command observations."""

    base = Path(campaign).resolve(strict=True)
    report = PILOT.summarize_campaign(base)
    runs = [_augment_run(run, base) for run in report["runs"]]
    cells = []
    for group in report["cells"]:
        selected = [
            run
            for run in runs
            if run.get("task_id") == group.get("task_id")
            and PILOT.row_arm(run) == group.get("arm")
        ]
        cells.append(_augment_cell(group, selected))
    return {**report, "runs": runs, "cells": cells}


summarize = summarize_campaign


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: summarize.py CAMPAIGN", file=sys.stderr)
        return 2
    try:
        report = summarize_campaign(args[0])
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"summarize.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
