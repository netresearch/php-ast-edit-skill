#!/usr/bin/env python3
"""Produce a descriptive, offline report for one prepared v0.8 campaign.

The campaign is an operator-selected evidence directory.  This program only reads
it; it never follows an arbitrary path from a schedule outside the campaign.
Missing observations stay in the report as scheduled rows with unknown metrics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any

RUN_ID = re.compile(r"run\d{3,}$", re.ASCII)
MEASUREMENT_FILE = "measurement.json"
RAW_FILE = "raw.jsonl"
DIFF_FILE = "diff.patch"
ENGINE_AUDIT_FILE = "engine-audit.jsonl"
OBSERVED_FILES = (
    MEASUREMENT_FILE,
    RAW_FILE,
    DIFF_FILE,
    ENGINE_AUDIT_FILE,
)
METRICS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "total_tokens",
    "visible_primary_rounds",
    "native_turns",
    "tool_calls",
    "failed_tool_calls",
    "wall_ms",
    "tool_execution_ms",
    "cost_usd",
    "diff_lines",
)
TOKEN_KEYS = {
    "input_tokens": "inputTokens",
    "output_tokens": "outputTokens",
    "cache_read_input_tokens": "cacheReadInputTokens",
    "cache_creation_input_tokens": "cacheCreationInputTokens",
}


def read_json(path: Path) -> Any:
    """Read operator-selected local evidence and retain parse errors for the caller."""

    return json.loads(path.read_text(encoding="utf-8"))  # NOSONAR(S2083, S8707)


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read every usable JSONL row while recording malformed present lines."""

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,  # NOSONAR(S2083, S8707)
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError("JSONL row is not an object")
            rows.append(value)
        except (ValueError, TypeError) as error:
            errors.append({"line": number, "error": str(error), "text": line})
    return rows, errors


def safe_path(value: Any, base: Path) -> Path | None:
    """Resolve a schedule path only when it is contained by the campaign."""

    if not isinstance(value, str):
        return None
    candidate = Path(value.replace("{PILOT_ROOT}", str(base))).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    return resolved if resolved == base or base in resolved.parents else None


def evidence_path(base: Path, row: dict[str, Any]) -> Path | None:
    """Prefer relocated evidence, then a schedule path inside this campaign."""

    run_id = row.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        return None
    relocated = (base / "runs" / run_id / "evidence").resolve()
    if relocated.is_dir() and base in relocated.parents:
        return relocated
    recorded = safe_path(row.get("evidence"), base)
    return recorded if recorded is not None and recorded.is_dir() else None


def present_evidence(evidence: Path | None) -> bool:
    """Prepared evidence directories exist for every slot; these files mark attempts."""

    if evidence is None:
        return False
    names = set(OBSERVED_FILES) | {
        "argv.json",
        "stderr.txt",
        "oracle.json",
        "final-hashes.json",
        "git-status.txt",
    }
    return any((evidence / name).exists() for name in names)


def number(value: Any) -> int | float | None:
    """Accept finite non-negative measurement numbers without turning unknown into 0."""

    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value


def integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def tokens(measurement: dict[str, Any]) -> dict[str, int | None]:
    usage = measurement.get("all_model_tokens")
    if not isinstance(usage, dict):
        usage = {}
    values = {name: integer(usage.get(key)) for name, key in TOKEN_KEYS.items()}
    complete = all(value is not None for value in values.values())
    total = integer(usage.get("totalTokens")) if complete else None
    if total is None and complete:
        total = sum(values.values())  # type: ignore[arg-type]
    values["total_tokens"] = total
    return values


def accounting_errors(measurement: dict[str, Any]) -> list[Any]:
    value = measurement.get(
        "accounting_errors", measurement.get("accounting_error", [])
    )
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def correctness(
    measurement: dict[str, Any], errors: list[dict[str, Any]]
) -> bool | None:
    """Return a verdict only when enough evidence exists to evaluate every condition."""

    if not measurement:
        return None
    native_error = measurement.get("native_is_error", None)
    if native_error is not None and type(native_error) is not bool:
        errors.append(
            {"file": MEASUREMENT_FILE, "error": "native_is_error is not boolean"}
        )
        return None
    exit_code = measurement.get("process_exit_code")
    timed_out = measurement.get("timed_out")
    oracle = measurement.get("oracle")
    passed = oracle.get("passed") if isinstance(oracle, dict) else None
    if (
        type(exit_code) is not int
        or type(timed_out) is not bool
        or type(passed) is not bool
    ):
        return None
    usage = measurement.get("all_model_tokens")
    if not isinstance(usage, dict) or any(
        integer(usage.get(key)) is None for key in TOKEN_KEYS.values()
    ):
        return None
    accounting = measurement.get("accounting_errors")
    if not isinstance(accounting, list):
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "accounting_errors is missing or not an array",
            }
        )
        return None
    if measurement.get("native_result_present") is False:
        return False
    if (
        measurement.get("native_subtype") is None
        or measurement.get("reported_model") is None
    ):
        return None
    if measurement.get("native_subtype") != "success":
        return False
    # An absent native flag means the native terminal was not marked as an error.
    native_ok = native_error is None or native_error is False
    return bool(
        native_ok and exit_code == 0 and passed and not accounting and not timed_out
    )


def diff_lines(path: Path | None, errors: list[dict[str, Any]]) -> int | None:
    if path is None or not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()  # NOSONAR(S2083, S8707)
    except OSError as error:
        errors.append({"file": DIFF_FILE, "error": str(error)})
        return None
    return sum(
        line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        for line in lines
    )


def remember_tool_block(
    block: dict[str, Any],
    calls: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
        call_id = block["id"]
        if call_id in calls:
            errors.append(
                {
                    "file": RAW_FILE,
                    "call_id": call_id,
                    "error": "duplicate tool call ID",
                }
            )
        calls.setdefault(call_id, block)
    if block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str):
        call_id = block["tool_use_id"]
        if call_id in results:
            errors.append(
                {
                    "file": RAW_FILE,
                    "call_id": call_id,
                    "error": "duplicate tool result ID",
                }
            )
        results.setdefault(call_id, block)


def collect_tool_blocks(
    events: list[dict[str, Any]], errors: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    calls: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}
    for event in events:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            remember_tool_block(block, calls, results, errors)
    return calls, results


def queue_tool_call(
    call_id: str,
    call: dict[str, Any],
    result: dict[str, Any] | None,
    errors: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    flag = result.get("is_error") if result else None
    valid_flag = flag is None or type(flag) is bool
    if not valid_flag:
        errors.append(
            {
                "file": RAW_FILE,
                "call_id": call_id,
                "error": "tool result is_error is not boolean",
            }
        )
    return (
        {
            "call_id": call_id,
            "id": call_id,
            "tool": call.get("name"),
            "command": (call.get("input") or {}).get("command")
            if isinstance(call.get("input"), dict)
            else None,
            "is_error": flag if valid_flag else None,
            "result_present": result is not None,
        },
        flag is True,
    )


def complete_tool_queue(
    calls: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, bool]:
    queue: list[dict[str, Any]] = []
    failed = 0
    complete = set(calls) == set(results)
    for call_id, call in calls.items():
        item, failed_call = queue_tool_call(call_id, call, results.get(call_id), errors)
        if failed_call:
            failed += 1
        queue.append(item)
    for call_id in results.keys() - calls.keys():
        errors.append(
            {
                "file": RAW_FILE,
                "call_id": call_id,
                "error": "tool result has no call",
            }
        )
    if not complete:
        errors.append(
            {"file": RAW_FILE, "error": "tool call/result linkage incomplete"}
        )
    return queue, failed, complete


def raw_call_queue(
    path: Path | None, errors: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int | None, bool]:
    """Build a review queue from tool IDs; malformed error flags remain visible."""

    if path is None or not path.exists():
        return [], None, False
    try:
        events, malformed = read_jsonl(path)
    except OSError as error:
        errors.append({"file": RAW_FILE, "error": str(error)})
        return [], None, False
    errors.extend({"file": RAW_FILE, **row} for row in malformed)
    calls, results = collect_tool_blocks(events, errors)
    queue, failed, complete = complete_tool_queue(calls, results, errors)
    return queue, failed if complete else None, complete and not malformed


def verify_raw_hash(
    path: Path | None, measurement: dict[str, Any], errors: list[dict[str, Any]]
) -> None:
    if not measurement:
        return
    expected = measurement.get("raw_sha256")
    if not isinstance(expected, str) or not re.fullmatch(
        r"[\da-fA-F]{64}", expected, flags=re.ASCII
    ):
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "raw_sha256 is not a SHA-256 hex string",
            }
        )
        return
    if path is None or not path.exists():
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "raw_sha256 cannot be verified without raw.jsonl",
            }
        )
        return
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()  # NOSONAR(S2083, S8707)
    except OSError as error:
        errors.append({"file": RAW_FILE, "error": str(error)})
        return
    if expected.lower() != actual:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "raw_sha256 differs from raw.jsonl bytes",
                "expected": expected,
                "actual": actual,
            }
        )


def index_engine_events(
    events: list[dict[str, Any]],
    malformed: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    errors.extend({"file": ENGINE_AUDIT_FILE, **row} for row in malformed)
    requests: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}
    for event in events:
        kind = event.get("event")
        if kind not in {"engine_request", "engine_result"}:
            errors.append(
                {
                    "file": ENGINE_AUDIT_FILE,
                    "error": "unknown engine audit event shape",
                }
            )
            continue
        call_id = event.get("id")
        if not isinstance(call_id, str):
            errors.append(
                {"file": ENGINE_AUDIT_FILE, "error": f"{kind} has no string ID"}
            )
            continue
        target = requests if kind == "engine_request" else results
        if call_id in target:
            errors.append(
                {
                    "file": ENGINE_AUDIT_FILE,
                    "id": call_id,
                    "error": f"duplicate {kind} ID",
                }
            )
        target.setdefault(call_id, event)
        if kind == "engine_request" and not isinstance(event.get("argv"), list):
            errors.append(
                {
                    "file": ENGINE_AUDIT_FILE,
                    "id": call_id,
                    "error": "engine request argv is not an array",
                }
            )
    return requests, results


def engine_apply_records(
    requests: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int | None]:
    applies = [
        row
        for row in requests.values()
        if isinstance(row.get("argv"), list)
        and row["argv"]
        and row["argv"][0] == "apply"
    ]
    records: list[dict[str, Any]] = []
    failed = 0
    complete_pairs = True
    for request in applies:
        call_id = request["id"]
        result = results.get(call_id)
        exit_code = result.get("exit_code") if result else None
        paired = type(exit_code) is int
        if not paired:
            complete_pairs = False
            errors.append(
                {
                    "file": ENGINE_AUDIT_FILE,
                    "id": call_id,
                    "error": "apply request has no paired integer exit_code",
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
                "capture_error": request.get("capture_error"),
            }
        )
    for call_id in results.keys() - requests.keys():
        errors.append(
            {
                "file": ENGINE_AUDIT_FILE,
                "id": call_id,
                "error": "engine result has no request",
            }
        )
    return records, failed if complete_pairs else None


def engine_apply_summary(
    path: Path | None, errors: list[dict[str, Any]]
) -> dict[str, Any]:
    """Pair engine request/result records by ID before counting failed applies."""

    empty = {
        "apply_calls": None,
        "failed_engine_apply": None,
        "records": [],
        "errors": [],
    }
    if path is None or not path.exists():
        empty["status"] = "missing"
        return empty
    error_start = len(errors)
    try:
        events, malformed = read_jsonl(path)
    except OSError as error:
        errors.append({"file": ENGINE_AUDIT_FILE, "error": str(error)})
        empty["status"] = "unreadable"
        return empty
    requests, results = index_engine_events(events, malformed, errors)
    records, failed = engine_apply_records(requests, results, errors)
    return {
        "status": "present",
        "apply_calls": len(records),
        "failed_engine_apply": failed,
        "records": records,
        "errors": errors[error_start:],
    }


def failed_tool_count(
    measurement: dict[str, Any],
    queue: list[dict[str, Any]],
    raw_failed: int | None,
    errors: list[dict[str, Any]],
) -> int | None:
    native_failed = integer(measurement.get("failed_tool_calls"))
    recorded_failed = measurement.get("failed_tool_calls")
    if recorded_failed is not None and native_failed is None:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "failed_tool_calls is not a non-negative integer",
            }
        )
    if queue and raw_failed is None:
        native_failed = None
    if native_failed is None and raw_failed is not None:
        native_failed = raw_failed
    if (
        native_failed is not None
        and raw_failed is not None
        and native_failed != raw_failed
    ):
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "native and raw failed tool call counts disagree",
            }
        )
    return native_failed


def measured_tool_calls(
    measurement: dict[str, Any],
    queue: list[dict[str, Any]],
    raw_complete: bool,
    errors: list[dict[str, Any]],
) -> int | None:
    measured = integer(measurement.get("tool_calls"))
    if measurement.get("tool_calls") is not None and measured is None:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "tool_calls is not a non-negative integer",
            }
        )
    if raw_complete and measured != len(queue):
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "measurement tool_calls differs from complete raw trace",
                "measured": measured,
                "raw": len(queue),
            }
        )
        return None
    return measured


def tool_duration(measurement: dict[str, Any]) -> tuple[Any, int | float | None]:
    timing_status = measurement.get("tool_timing_status")
    if timing_status is None:
        timing_status = measurement.get("tool_execution_coverage")
    if timing_status is True:
        timing_status = "complete_native_intervals"
    tool_ms = number(measurement.get("tool_execution_ms"))
    if timing_status != "complete_native_intervals":
        tool_ms = None
    return timing_status, tool_ms


def metric_row(
    measurement: dict[str, Any],
    raw_values: tuple[list[dict[str, Any]], int | None, bool],
    engine: dict[str, Any],
    errors: list[dict[str, Any]],
    evidence: Path | None,
) -> dict[str, Any]:
    values = tokens(measurement)
    queue, raw_failed, raw_complete = raw_values
    native_failed = failed_tool_count(measurement, queue, raw_failed, errors)
    timing_status, tool_ms = tool_duration(measurement)
    measured_calls = measured_tool_calls(measurement, queue, raw_complete, errors)
    metrics: dict[str, Any] = {
        **values,
        "visible_primary_rounds": integer(measurement.get("primary_model_rounds")),
        "native_turns": integer(measurement.get("native_num_turns")),
        "tool_calls": measured_calls,
        "failed_tool_calls": native_failed,
        "raw_failed_tool_calls": raw_failed,
        "wall_ms": number(measurement.get("candidate_wall_ms")),
        "tool_execution_ms": tool_ms,
        "cost_usd": number(measurement.get("native_list_price_usd")),
        "diff_lines": diff_lines(evidence / DIFF_FILE if evidence else None, errors),
    }
    metrics["tool_execution_coverage"] = timing_status
    return {
        "metrics": metrics,
        "native_is_error": measurement.get("native_is_error"),
        "native_result_present": measurement.get("native_result_present"),
        "native_subtype": measurement.get("native_subtype"),
        "reported_model": measurement.get("reported_model"),
        "native_duration_ms": number(measurement.get("native_duration_ms")),
        "native_duration_api_ms": number(measurement.get("native_duration_api_ms")),
        "primary_rounds_exact": measurement.get("primary_model_rounds_exact"),
        "response_input_coverage": measurement.get("response_input_coverage"),
        "tool_timing_status": timing_status,
        "all_model_usage": measurement.get("all_model_usage"),
        "review_queue": queue,
        "engine": {
            "apply_calls": engine["apply_calls"],
            "failed_engine_apply": engine["failed_engine_apply"],
            "apply_records": engine["records"],
            "errors": engine["errors"],
        },
    }


def expected_model(config: dict[str, Any] | None, row: dict[str, Any]) -> str | None:
    if not isinstance(config, dict):
        return None
    models = config.get("models")
    model_key = row.get("model_key")
    if isinstance(models, dict) and isinstance(models.get(model_key), dict):
        value = models[model_key].get("id")
        if isinstance(value, str):
            return value
    value = config.get("requested_model")
    return value if isinstance(value, str) else None


def validate_model_identity(
    measurement: dict[str, Any],
    expected: str | None,
    config: dict[str, Any] | None,
    errors: list[dict[str, Any]],
) -> None:
    if expected is None:
        return
    reported = measurement.get("reported_model")
    if reported != expected:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "reported model differs from campaign config",
                "expected": expected,
                "observed": reported,
            }
        )
    usage = measurement.get("all_model_usage")
    if not isinstance(usage, dict):
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "all_model_usage is missing or not an object",
            }
        )
        return
    configured_ids = {expected}
    if (
        isinstance(config, dict)
        and isinstance(config.get("model_keys"), list)
        and isinstance(config.get("models"), dict)
    ):
        configured_ids = {
            config["models"][key].get("id")
            for key in config["model_keys"]
            if isinstance(config["models"].get(key), dict)
            and isinstance(config["models"][key].get("id"), str)
        }
        configured_ids.add(expected)
    if expected not in usage:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "requested model missing from all_model_usage",
                "expected": expected,
            }
        )
    unexpected = sorted(set(usage) - configured_ids)
    if unexpected:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "unexpected all_model_usage model keys",
                "observed": unexpected,
            }
        )


def load_measurement(
    evidence: Path | None, errors: list[dict[str, Any]]
) -> tuple[dict[str, Any], bool]:
    if evidence is None:
        return {}, False
    path = evidence / MEASUREMENT_FILE
    if not path.exists():
        return {}, False
    try:
        loaded = read_json(path)
        if not isinstance(loaded, dict):
            raise TypeError("measurement is not an object")
        return loaded, True
    except (OSError, ValueError, TypeError) as error:
        errors.append({"file": MEASUREMENT_FILE, "error": str(error)})
        return {}, True


def check_schedule_identity(
    row: dict[str, Any],
    measurement: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    expected = {
        key: row.get(key)
        for key in ("run_id", "task_id", "variant", "arm", "repetition")
    }
    mismatches = {
        key: (expected[key], measurement[key])
        for key in expected
        if key in measurement and measurement[key] != expected[key]
    }
    if mismatches:
        errors.append(
            {
                "file": MEASUREMENT_FILE,
                "error": "schedule identity mismatch",
                "fields": mismatches,
            }
        )


def blocked_verdict(verdict: bool | None, errors: list[dict[str, Any]]) -> bool | None:
    blocking_errors = {MEASUREMENT_FILE, RAW_FILE}
    if any(item.get("file") in blocking_errors for item in errors):
        return None
    if any(item.get("error") == "schedule identity mismatch" for item in errors):
        return None
    return verdict


def run_record(
    base: Path, row: dict[str, Any], config: dict[str, Any] | None = None
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    evidence = evidence_path(base, row)
    attempted = present_evidence(evidence)
    measurement, measurement_file_present = load_measurement(evidence, errors)
    engine = engine_apply_summary(
        evidence / ENGINE_AUDIT_FILE if evidence else None, errors
    )
    raw_path = evidence / RAW_FILE if evidence else None
    raw_values = raw_call_queue(raw_path, errors)
    if attempted and (raw_path is None or not raw_path.exists()):
        errors.append({"file": RAW_FILE, "error": "raw trace is missing"})
    verify_raw_hash(raw_path, measurement, errors)
    check_schedule_identity(row, measurement, errors)
    validate_model_identity(measurement, expected_model(config, row), config, errors)
    verdict = correctness(measurement, errors)
    record: dict[str, Any] = {
        **row,
        "attempted": attempted,
        "arm": row_arm(row),
        "evidence_path": str(evidence) if evidence else None,
        "evidence_errors": errors,
        "correctness": verdict,
        "measurement_present": measurement_file_present,
        "raw_present": bool(evidence and (evidence / RAW_FILE).exists()),
        "engine_audit_present": bool(
            evidence and (evidence / ENGINE_AUDIT_FILE).exists()
        ),
        "accounting_errors": accounting_errors(measurement),
        "timed_out": measurement.get("timed_out"),
        "process_exit_code": measurement.get("process_exit_code"),
        "oracle_passed": (measurement.get("oracle") or {}).get("passed")
        if isinstance(measurement.get("oracle"), dict)
        else None,
    }
    record.update(metric_row(measurement, raw_values, engine, errors, evidence))
    record["correctness"] = blocked_verdict(verdict, errors)
    return record


def median_metric(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    values = [
        row.get("metrics", {}).get(metric)
        for row in rows
        if type(row.get("metrics", {}).get(metric)) in (int, float)
        and math.isfinite(row["metrics"][metric])
    ]
    return {
        "median": statistics.median(values) if values else None,
        "n": len(values),
        "denominator": len(rows),
    }


def cell(
    task_id: Any, arm: Any, rows: list[dict[str, Any]], scheduled: int
) -> dict[str, Any]:
    attempted = [row for row in rows if row["attempted"]]
    successful = [row for row in attempted if row["correctness"] is True]
    observed = {metric: median_metric(attempted, metric) for metric in METRICS}
    successful_observed = {
        metric: median_metric(successful, metric) for metric in METRICS
    }
    return {
        "task_id": task_id,
        "arm": arm,
        "scheduled": scheduled,
        "attempted": len(attempted),
        "unattempted": scheduled - len(attempted),
        "successful": len(successful),
        "all_observed": {"n": len(attempted), "medians": observed},
        "successful_observed": {"n": len(successful), "medians": successful_observed},
        "medians_all_observed": observed,
        "medians_successful": successful_observed,
    }


def row_arm(row: dict[str, Any]) -> Any:
    """Accept the runner's variant spelling and the report-facing arm spelling."""

    return row.get("variant", row.get("arm"))


def campaign_metadata(base: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        config = read_json(base / "config.json")
        schedule = read_json(base / "schedule.json")
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(f"Cannot read campaign metadata: {error}") from error
    if not isinstance(config, dict) or not isinstance(schedule, list):
        raise TypeError("Campaign config must be an object and schedule an array")
    return config, schedule


def validate_schedule_row(row: Any, identities: set[str]) -> str:
    if not isinstance(row, dict):
        raise TypeError("Schedule row is not an object")
    run_id = row.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError(f"Invalid run_id: {run_id!r}")
    if run_id in identities:
        raise ValueError(f"Duplicate run_id: {run_id}")
    identities.add(run_id)
    return run_id


def campaign_records(
    base: Path, schedule: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    identities: set[str] = set()
    for row in schedule:
        validate_schedule_row(row, identities)
        records.append(run_record(base, row, config))
    return records


def campaign_cells(
    schedule: list[dict[str, Any]], records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for task_id in dict.fromkeys(row.get("task_id") for row in schedule):
        for arm in dict.fromkeys(
            row_arm(row) for row in schedule if row.get("task_id") == task_id
        ):
            selected = [
                row
                for row in records
                if row.get("task_id") == task_id and row_arm(row) == arm
            ]
            groups.append(cell(task_id, arm, selected, len(selected)))
    return groups


def summarize_campaign(campaign: str | Path) -> dict[str, Any]:
    base = Path(campaign).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Campaign is not a directory")
    config, schedule = campaign_metadata(base)
    records = campaign_records(base, schedule, config)
    groups = campaign_cells(schedule, records)
    return {
        "schema_version": 1,
        "campaign": str(base),
        "scheduled": len(schedule),
        "attempted": sum(row["attempted"] for row in records),
        "unattempted": sum(not row["attempted"] for row in records),
        "unattempted_ids": [row["run_id"] for row in records if not row["attempted"]],
        "runs": records,
        "cells": groups,
        "config": {
            key: config.get(key)
            for key in (
                "source_commit",
                "requested_model",
                "models",
                "model_keys",
                "arms",
                "task_ids",
                "repetitions",
                "cache_condition",
                "cli_version",
            )
            if key in config
        },
        "interpretation": "Descriptive per-run and median observations only; unknown evidence remains null and no significance or universal claim is computed.",
    }


# Kept as a small import-friendly spelling for offline operators and tests.
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
