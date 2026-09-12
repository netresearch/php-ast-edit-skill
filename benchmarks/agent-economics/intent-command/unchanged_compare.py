#!/usr/bin/env python3
"""Validate and compare the two unchanged-context campaign arms."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

METRICS = (
    "total_tokens",
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "visible_primary_rounds",
    "tool_calls",
    "failed_tool_calls",
    "wall_ms",
    "cost_usd",
)
TASKS = ("method-and-literal", "cross-file-rename-clarified")
ARMS = ("unchanged_locations", "unchanged_excerpts")
CHECK_REUSE_ARMS = ("check_reuse_control", "check_reuse_guidance")
REPETITIONS = range(1, 7)
TOKEN_PARTS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)
COUNT_METRICS = ("visible_primary_rounds", "tool_calls", "failed_tool_calls")
EXPECTED_MODEL_KEY = "haiku"
EXPECTED_MODEL_ID = "claude-haiku-4-5-20251001"


class CompareError(ValueError):
    """The input report cannot support a complete paired comparison."""


def _number(value: Any, field: str) -> int | float | Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise CompareError(f"{field} must be numeric")
    finite = value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)
    if not finite or value < 0:
        raise CompareError(f"{field} must be finite and non-negative")
    return value


def _validate_config(
    report: dict[str, Any], *, arms: tuple[str, str] = ARMS
) -> tuple[list[str], dict[str, str]]:
    config = report.get("config")
    if not isinstance(config, dict):
        raise CompareError("report config is required")
    configured_arms = config.get("arms")
    if not isinstance(configured_arms, list) or set(configured_arms) != set(arms):
        raise CompareError("report config has the wrong arms")
    configured_tasks = config.get("task_ids")
    if not isinstance(configured_tasks, list) or set(configured_tasks) != set(TASKS):
        raise CompareError("report config has the wrong tasks")
    if type(config.get("repetitions")) is not int or config["repetitions"] != 6:
        raise CompareError("report config must specify six repetitions")
    configured_models = config.get("model_keys")
    if configured_models != [EXPECTED_MODEL_KEY]:
        raise CompareError("report config must pin the registered Haiku model")
    model_definitions = config.get("models")
    if not isinstance(model_definitions, dict):
        raise CompareError("report config must specify model identities")
    model = EXPECTED_MODEL_KEY
    definition = model_definitions.get(model)
    if not isinstance(definition, dict):
        raise CompareError("report config has an invalid model identity")
    identity = definition.get("id")
    if identity != EXPECTED_MODEL_ID:
        raise CompareError("report config has an invalid model identity")
    return configured_models, {model: identity}


def _validate_metrics(metrics: Any) -> None:
    if not isinstance(metrics, dict) or not set(METRICS) <= set(metrics):
        raise CompareError("run metrics do not contain the required schema")
    for metric in METRICS:
        _number(metrics[metric], f"metrics.{metric}")
    for metric in (*TOKEN_PARTS, "total_tokens", *COUNT_METRICS):
        if type(metrics[metric]) is not int:
            raise CompareError(f"metrics.{metric} must be an integer")
    if metrics["total_tokens"] != sum(metrics[metric] for metric in TOKEN_PARTS):
        raise CompareError("metrics.total_tokens does not equal its token parts")
    if metrics["failed_tool_calls"] > metrics["tool_calls"]:
        raise CompareError("failed_tool_calls cannot exceed tool_calls")
    if metrics["total_tokens"] <= 0 or metrics["wall_ms"] <= 0:
        raise CompareError("each run needs positive total_tokens and wall_ms")


def _validate_row(
    row: Any,
    seen_ids: set[str],
    seen_pairs: set[tuple[str, str, int]],
    models: set[str],
    configured_models: list[str],
    identities: dict[str, str],
    arms: tuple[str, str],
) -> None:
    if not isinstance(row, dict):
        raise CompareError("each run must be an object")
    task, arm, repetition = row.get("task_id"), row.get("arm"), row.get("repetition")
    if (
        task not in TASKS
        or arm not in arms
        or type(repetition) is not int
        or repetition not in REPETITIONS
    ):
        raise CompareError("run has an unsupported task, arm, or repetition")
    pair = (task, arm, repetition)
    if pair in seen_pairs:
        raise CompareError(f"duplicate run pair: {pair}")
    seen_pairs.add(pair)
    run_id = row.get("run_id")
    if not isinstance(run_id, str) or not run_id or run_id in seen_ids:
        raise CompareError("run_id must be unique and non-empty")
    seen_ids.add(run_id)
    model = row.get("model_key")
    if not isinstance(model, str) or not model or model not in configured_models:
        raise CompareError("model_key must be non-empty")
    models.add(model)
    if row.get("reported_model") != identities[model]:
        raise CompareError("run reported_model does not match configured model")
    if row.get("attempted") is not True:
        raise CompareError("all 24 runs must be attempted")
    if type(row.get("oracle_passed")) is not bool:
        raise CompareError("oracle_passed must be boolean")
    _validate_metrics(row.get("metrics"))


def _validate_report(
    report: dict[str, Any], *, arms: tuple[str, str] = ARMS
) -> list[dict[str, Any]]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise CompareError("report schema_version must be 1")
    if report.get("attempted") != 24 or report.get("scheduled") != 24:
        raise CompareError(
            "report must contain exactly 24 attempted and scheduled runs"
        )
    rows = report.get("runs")
    if not isinstance(rows, list) or len(rows) != 24:
        raise CompareError("report must contain exactly 24 runs")
    configured_models, identities = _validate_config(report, arms=arms)

    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str, int]] = set()
    models: set[str] = set()
    for row in rows:
        _validate_row(
            row,
            seen_ids,
            seen_pairs,
            models,
            configured_models,
            identities,
            arms,
        )
    expected_pairs = {
        (task, arm, repetition)
        for task in TASKS
        for arm in arms
        for repetition in REPETITIONS
    }
    if seen_pairs != expected_pairs:
        raise CompareError(
            "report must contain six complete repetitions for each task and arm"
        )
    if len(models) != 1 or configured_models != list(models):
        raise CompareError("all paired runs must use one model")
    return rows


def _ratio(after: Any, before: Any) -> Any:
    if isinstance(after, Decimal) or isinstance(before, Decimal):
        after, before = Decimal(str(after)), Decimal(str(before))
    return after / before if before else None


def _median(values: list[Any]) -> Any:
    usable = [value for value in values if value is not None]
    return statistics.median(usable) if usable else None


def _exact_median_ratio(control, treatment, metric):
    return statistics.median(
        Fraction(str(treatment[index]["metrics"][metric]))
        / Fraction(str(control[index]["metrics"][metric]))
        for index in REPETITIONS
    )


def _task_result(
    task: str, rows: list[dict[str, Any]], *, arms: tuple[str, str] = ARMS
) -> dict[str, Any]:
    by_arm = {
        arm: {row["repetition"]: row for row in rows if row["arm"] == arm}
        for arm in arms
    }
    control, treatment = by_arm[arms[0]], by_arm[arms[1]]
    pairs = []
    for repetition in REPETITIONS:
        before, after = control[repetition], treatment[repetition]
        pairs.append(
            {
                "repetition": repetition,
                "control": before["run_id"],
                "treatment": after["run_id"],
                "ratios": {
                    metric: _ratio(after["metrics"][metric], before["metrics"][metric])
                    for metric in METRICS
                },
            }
        )
    medians = {
        arm: {
            metric: statistics.median(row["metrics"][metric] for row in values.values())
            for metric in METRICS
        }
        for arm, values in by_arm.items()
    }
    paired_medians = {
        metric: _median([pair["ratios"][metric] for pair in pairs])
        for metric in METRICS
    }
    ratios_of_medians = {
        metric: _ratio(medians[arms[1]][metric], medians[arms[0]][metric])
        for metric in METRICS
    }
    exact_tokens = _exact_median_ratio(control, treatment, "total_tokens")
    exact_wall = _exact_median_ratio(control, treatment, "wall_ms")
    paired_medians.update(total_tokens=float(exact_tokens), wall_ms=float(exact_wall))
    token_wins = sum(
        treatment[index]["metrics"]["total_tokens"]
        < control[index]["metrics"]["total_tokens"]
        for index in REPETITIONS
    )
    passed = exact_tokens <= Fraction(17, 20) and exact_wall <= 1 and token_wins >= 4
    return {
        "task_id": task,
        "n_pairs": len(pairs),
        "medians": medians,
        "ratios_of_medians": ratios_of_medians,
        "paired_median_ratios": paired_medians,
        "token_saving_pairs": token_wins,
        "pairs": pairs,
        "numeric_criterion_passed": passed,
    }


def compare(report: dict[str, Any], *, arms: tuple[str, str] = ARMS) -> dict[str, Any]:
    """Return paired metrics, rejecting incomplete or ambiguous campaigns."""

    rows = _validate_report(report, arms=arms)
    tasks = [
        _task_result(task, [row for row in rows if row["task_id"] == task], arms=arms)
        for task in TASKS
    ]
    return {
        "attempted": report["attempted"],
        "scheduled": report["scheduled"],
        "native_cost_usd": sum(row["metrics"]["cost_usd"] for row in rows),
        "oracle_passes": sum(row["oracle_passed"] is True for row in rows),
        "tasks": tasks,
        "all_tasks_numeric_criterion_passed": all(
            task["numeric_criterion_passed"] for task in tasks
        ),
        "quality_gate": "Separate independent trace review; oracle passes do not infer claims approval",
    }


def _json_default(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main(argv: list[str] | None = None, *, arms: tuple[str, str] = ARMS) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = json.loads(args.report.read_text(), parse_float=Decimal)
        output = compare(report, arms=arms)
    except (OSError, TypeError, json.JSONDecodeError, CompareError) as error:
        print(f"unchanged_compare.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(output, default=_json_default, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
