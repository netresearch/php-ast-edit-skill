#!/usr/bin/env python3
"""Compare the forty preregistered final-guidance attempts without dropping failures."""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import unchanged_compare as metrics

TASKS = ("ledger-method-rename", "transport-contract-rename")
ARMS = ("final_guidance_control", "final_guidance_bounded")
REPETITIONS = range(1, 11)


def require(condition, message):
    if not condition:
        raise metrics.CompareError(message)


def validate_config(config):
    require(isinstance(config, dict), "Missing config")
    for field, expected in (
        ("arms", list(ARMS)),
        ("task_ids", list(TASKS)),
        ("repetitions", 10),
        ("model_keys", ["haiku"]),
    ):
        require(
            type(config.get(field)) is type(expected) and config[field] == expected,
            f"Unexpected config.{field}",
        )
    models = config.get("models")
    require(
        isinstance(models, dict) and isinstance(models.get("haiku"), dict),
        "Missing model identity",
    )
    require(
        models["haiku"].get("id") == metrics.EXPECTED_MODEL_ID
        and models["haiku"].get("effort") is None,
        "Model or effort drift",
    )


def validate_row(row):
    require(isinstance(row, dict), "Expected run object")
    require(isinstance(row.get("run_id"), str) and row["run_id"], "Missing run ID")
    require(
        row.get("task_id") in TASKS
        and row.get("arm") in ARMS
        and type(row.get("repetition")) is int
        and row["repetition"] in REPETITIONS,
        "Unexpected task, arm or repetition",
    )
    require(
        row.get("model_key") == "haiku"
        and row.get("reported_model") == metrics.EXPECTED_MODEL_ID,
        "Run model drift",
    )
    require(
        row.get("attempted") is True and type(row.get("oracle_passed")) is bool,
        "Missing attempt or oracle observation",
    )
    metrics._validate_metrics(row.get("metrics"))


def validate(report):
    require(isinstance(report, dict), "Expected report object")
    for field, expected in (
        ("schema_version", 1),
        ("attempted", 40),
        ("scheduled", 40),
    ):
        require(
            type(report.get(field)) is int and report[field] == expected,
            f"Expected {field}={expected}",
        )
    validate_config(report.get("config"))
    rows = report.get("runs")
    require(isinstance(rows, list) and len(rows) == 40, "Expected forty runs")
    for row in rows:
        validate_row(row)
    require(len({row["run_id"] for row in rows}) == 40, "Duplicate run ID")
    keys = {(row["task_id"], row["arm"], row["repetition"]) for row in rows}
    require(len(keys) == 40, "Duplicate task/arm/repetition")
    return rows


def task_result(task, rows):
    arms = {
        arm: {row["repetition"]: row for row in rows if row["arm"] == arm}
        for arm in ARMS
    }
    pairs = []
    for repetition in REPETITIONS:
        before, after = (arms[arm][repetition] for arm in ARMS)
        ratios = {
            metric: (
                Fraction(str(after["metrics"][metric]))
                / Fraction(str(before["metrics"][metric]))
                if before["metrics"][metric]
                else None
            )
            for metric in metrics.METRICS
        }
        pairs.append(
            {
                "repetition": repetition,
                "control": before["run_id"],
                "treatment": after["run_id"],
                "ratios": ratios,
            }
        )
    paired = {
        metric: metrics._median([pair["ratios"][metric] for pair in pairs])
        for metric in metrics.METRICS
    }
    wins = sum(pair["ratios"]["total_tokens"] < 1 for pair in pairs)
    tail = Fraction(sum(math.comb(10, count) for count in range(wins, 11)), 1024)
    passed = (
        paired["total_tokens"] <= Fraction(17, 20)
        and paired["wall_ms"] <= 1
        and all(pair["ratios"]["tool_calls"] is not None for pair in pairs)
        and paired["tool_calls"] <= 1
        and wins >= 9
    )
    medians = {
        arm: {
            metric: metrics._median([row["metrics"][metric] for row in values.values()])
            for metric in metrics.METRICS
        }
        for arm, values in arms.items()
    }
    return {
        "task_id": task,
        "n_pairs": 10,
        "medians": medians,
        "paired_median_ratios": paired,
        "token_saving_pairs": wins,
        "binomial_win_tail": float(tail),
        "bonferroni_two_task_tail": float(min(1, 2 * tail)),
        "pairs": pairs,
        "numeric_criterion_passed": passed,
    }


def compare(report):
    rows = validate(report)
    tasks = [
        task_result(task, [row for row in rows if row["task_id"] == task])
        for task in TASKS
    ]
    return {
        "attempted": 40,
        "scheduled": 40,
        "native_cost_usd": sum(row["metrics"]["cost_usd"] for row in rows),
        "oracle_passes": sum(row["oracle_passed"] for row in rows),
        "tasks": tasks,
        "all_tasks_numeric_criterion_passed": all(
            task["numeric_criterion_passed"] for task in tasks
        ),
        "quality_gate": "Separate independent audit: all code/check/route gates and twenty supported, complete treatment finals.",
        "binomial_reference": "Ties are nonwins. Descriptive tail only; session independence and provider cache control are not established.",
    }


def json_default(value):
    if isinstance(value, (Decimal, Fraction)):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        output = compare(json.loads(args.report.read_text(), parse_float=Decimal))
    except (OSError, ValueError, TypeError) as error:
        print(f"final_compare.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(output, default=json_default, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
