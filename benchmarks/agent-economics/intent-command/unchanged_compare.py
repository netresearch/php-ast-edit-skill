#!/usr/bin/env python3
"""Validate and compare the two unchanged-context campaign arms."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
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
REPETITIONS = range(1, 7)
TOKEN_PARTS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)
COUNT_METRICS = ("visible_primary_rounds", "tool_calls", "failed_tool_calls")


class CompareError(ValueError):
    """The input report cannot support a complete paired comparison."""


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CompareError(f"{field} must be numeric")
    if not math.isfinite(value) or value < 0:
        raise CompareError(f"{field} must be finite and non-negative")
    return value


def _validate_config(report: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    config = report.get("config")
    if not isinstance(config, dict):
        raise CompareError("report config is required")
    configured_arms = config.get("arms")
    if not isinstance(configured_arms, list) or set(configured_arms) != set(ARMS):
        raise CompareError("report config has the wrong arms")
    configured_tasks = config.get("task_ids")
    if not isinstance(configured_tasks, list) or set(configured_tasks) != set(TASKS):
        raise CompareError("report config has the wrong tasks")
    if type(config.get("repetitions")) is not int or config["repetitions"] != 6:
        raise CompareError("report config must specify six repetitions")
    configured_models = config.get("model_keys")
    if not isinstance(configured_models, list) or len(configured_models) != 1:
        raise CompareError("report config must specify one model")
    model_definitions = config.get("models")
    if not isinstance(model_definitions, dict):
        raise CompareError("report config must specify model identities")
    model = configured_models[0]
    definition = model_definitions.get(model) if isinstance(model, str) else None
    if not isinstance(definition, dict):
        raise CompareError("report config has an invalid model identity")
    identity = definition.get("id")
    if not isinstance(identity, str) or not identity:
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
) -> None:
    if not isinstance(row, dict):
        raise CompareError("each run must be an object")
    task, arm, repetition = row.get("task_id"), row.get("arm"), row.get("repetition")
    if (
        task not in TASKS
        or arm not in ARMS
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


def _validate_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise CompareError("report schema_version must be 1")
    if report.get("attempted") != 24 or report.get("scheduled") != 24:
        raise CompareError(
            "report must contain exactly 24 attempted and scheduled runs"
        )
    rows = report.get("runs")
    if not isinstance(rows, list) or len(rows) != 24:
        raise CompareError("report must contain exactly 24 runs")
    configured_models, identities = _validate_config(report)

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
        )
    expected_pairs = {
        (task, arm, repetition)
        for task in TASKS
        for arm in ARMS
        for repetition in REPETITIONS
    }
    if seen_pairs != expected_pairs:
        raise CompareError(
            "report must contain six complete repetitions for each task and arm"
        )
    if len(models) != 1 or configured_models != list(models):
        raise CompareError("all paired runs must use one model")
    return rows


def _ratio(after: float, before: float) -> float | None:
    return after / before if before else None


def _median(values: list[int | float | None]) -> int | float | None:
    usable = [value for value in values if value is not None]
    return statistics.median(usable) if usable else None


def _task_result(task: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm = {
        arm: {row["repetition"]: row for row in rows if row["arm"] == arm}
        for arm in ARMS
    }
    control, treatment = by_arm[ARMS[0]], by_arm[ARMS[1]]
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
        metric: _ratio(medians[ARMS[1]][metric], medians[ARMS[0]][metric])
        for metric in METRICS
    }
    token_wins = sum(pair["ratios"]["total_tokens"] < 1 for pair in pairs)
    passed = (
        paired_medians["total_tokens"] is not None
        and paired_medians["wall_ms"] is not None
        and paired_medians["total_tokens"] <= 0.85
        and paired_medians["wall_ms"] <= 1.0
        and token_wins >= 4
    )
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


def compare(report: dict[str, Any]) -> dict[str, Any]:
    """Return paired metrics, rejecting incomplete or ambiguous campaigns."""

    rows = _validate_report(report)
    tasks = [
        _task_result(task, [row for row in rows if row["task_id"] == task])
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = json.loads(args.report.read_text())
        output = compare(report)
    except (OSError, TypeError, json.JSONDecodeError, CompareError) as error:
        print(f"unchanged_compare.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
