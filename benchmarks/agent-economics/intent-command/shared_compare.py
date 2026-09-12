#!/usr/bin/env python3
"""Compare shared report metadata; the unchanged single-file task is an A/A control."""

import argparse
import json
import statistics
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import unchanged_compare

ARMS = ("shared_report_control", "shared_report_factored")
PRIMARY_TASK = "cross-file-rename-clarified"


def compare(report):
    result = unchanged_compare.compare(report, arms=ARMS)
    del result["all_tasks_numeric_criterion_passed"]
    for task in result["tasks"]:
        if task["task_id"] != PRIMARY_TASK:
            task["numeric_criterion_passed"] = None
            task["role"] = "A/A noise control: unchanged single-file report"
            continue
        task["role"] = "primary multi-file comparison"
        rows = [row for row in report["runs"] if row["task_id"] == PRIMARY_TASK]
        by_arm = {
            arm: {row["repetition"]: row for row in rows if row["arm"] == arm}
            for arm in ARMS
        }
        controls = by_arm[ARMS[0]]
        if any(row["metrics"]["tool_calls"] == 0 for row in controls.values()):
            task["numeric_criterion_passed"] = False
            result["primary_numeric_criterion_passed"] = False
            continue
        calls = statistics.median(
            Fraction(by_arm[ARMS[1]][n]["metrics"]["tool_calls"])
            / controls[n]["metrics"]["tool_calls"]
            for n in unchanged_compare.REPETITIONS
        )
        task["numeric_criterion_passed"] &= calls <= 1
        result["primary_numeric_criterion_passed"] = task["numeric_criterion_passed"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(), parse_float=Decimal)
        result = compare(report)
    except (OSError, ValueError, TypeError) as error:
        print(f"shared_compare.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
