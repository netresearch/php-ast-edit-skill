"""Offline schema and paired-metric tests for unchanged_compare.py."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import unchanged_compare


class CompareTests(unittest.TestCase):
    def report(self):
        rows = []
        for task in unchanged_compare.TASKS:
            for arm in unchanged_compare.ARMS:
                for repetition in unchanged_compare.REPETITIONS:
                    base_metrics = {
                        metric: 10 if metric != "wall_ms" else 100
                        for metric in unchanged_compare.METRICS
                    }
                    base_metrics.update(
                        input_tokens=10,
                        cache_creation_input_tokens=0,
                        cache_read_input_tokens=0,
                        output_tokens=0,
                    )
                    if arm == unchanged_compare.ARMS[1]:
                        base_metrics["total_tokens"] = 8
                        base_metrics.update(
                            input_tokens=8,
                            cache_creation_input_tokens=0,
                            cache_read_input_tokens=0,
                            output_tokens=0,
                        )
                        base_metrics["wall_ms"] = 90
                    rows.append(
                        {
                            "run_id": f"{task}-{arm}-{repetition}",
                            "task_id": task,
                            "arm": arm,
                            "repetition": repetition,
                            "model_key": "haiku",
                            "reported_model": "claude-haiku-4-5-20251001",
                            "attempted": True,
                            "oracle_passed": True,
                            "metrics": base_metrics,
                        }
                    )
        return {
            "schema_version": 1,
            "attempted": 24,
            "scheduled": 24,
            "config": {
                "arms": list(unchanged_compare.ARMS),
                "task_ids": list(unchanged_compare.TASKS),
                "model_keys": ["haiku"],
                "models": {"haiku": {"id": "claude-haiku-4-5-20251001"}},
                "repetitions": 6,
            },
            "runs": rows,
        }

    def test_valid_report_has_six_pairs_per_task_and_full_metrics(self):
        output = unchanged_compare.compare(self.report())
        self.assertEqual(output["attempted"], 24)
        self.assertEqual([task["n_pairs"] for task in output["tasks"]], [6, 6])
        self.assertEqual(
            set(output["tasks"][0]["paired_median_ratios"]),
            set(unchanged_compare.METRICS),
        )
        self.assertTrue(output["all_tasks_numeric_criterion_passed"])

    def test_paired_median_catches_regression_hidden_by_cell_medians(self):
        report = self.report()
        rows = [
            row
            for row in report["runs"]
            if row["task_id"] == unchanged_compare.TASKS[0]
        ]
        controls = [row for row in rows if row["arm"] == unchanged_compare.ARMS[0]]
        treatments = [row for row in rows if row["arm"] == unchanged_compare.ARMS[1]]
        control_values = [1, 1, 100, 100, 100, 100]
        treatment_values = [2, 2, 200, 1, 1, 1]
        for row, value in zip(controls, control_values):
            row["metrics"]["total_tokens"] = value
            row["metrics"]["input_tokens"] = value
        for row, value in zip(treatments, treatment_values):
            row["metrics"]["total_tokens"] = value
            row["metrics"]["input_tokens"] = value
        result = unchanged_compare.compare(report)["tasks"][0]
        self.assertLess(result["ratios_of_medians"]["total_tokens"], 1)
        self.assertGreater(result["paired_median_ratios"]["total_tokens"], 1)
        self.assertFalse(result["numeric_criterion_passed"])

    def test_missing_duplicate_and_extra_task_data_are_rejected(self):
        report = self.report()
        with self.assertRaises(ValueError):
            unchanged_compare.compare({**report, "runs": report["runs"][:-1]})
        duplicate = copy.deepcopy(report)
        duplicate["runs"][-1]["repetition"] = 5
        with self.assertRaises(ValueError):
            unchanged_compare.compare(duplicate)
        extra = copy.deepcopy(report)
        extra["runs"][0]["task_id"] = "other"
        with self.assertRaises(ValueError):
            unchanged_compare.compare(extra)

    def test_exact_threshold_is_accepted_but_no_tolerance_expands_it(self):
        for token_third, wall_fourth, expected in (
            (800, 11, True),
            (801, 11, False),
            (800, 11.000000000001, False),
        ):
            report = self.report()
            tokens = [100, 100, token_third, 900, 1000, 1000]
            wall = [5, 5, 9, wall_fourth, 15, 15]
            for row in report["runs"]:
                index = row["repetition"] - 1
                treatment = row["arm"] == unchanged_compare.ARMS[1]
                count = tokens[index] if treatment else 1000
                row["metrics"].update(
                    total_tokens=count,
                    input_tokens=count,
                    wall_ms=wall[index] if treatment else 10,
                )
            with self.subTest(token_third=token_third, wall_fourth=wall_fourth):
                output = unchanged_compare.compare(report)
                self.assertIs(output["all_tasks_numeric_criterion_passed"], expected)
                if expected:
                    self.assertEqual(
                        output["tasks"][0]["paired_median_ratios"]["total_tokens"], 0.85
                    )
                    self.assertEqual(output["tasks"][0]["token_saving_pairs"], 4)

    def test_model_and_metric_validation_is_strict(self):
        report = self.report()
        report["runs"][1]["reported_model"] = "other"
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)

    def test_schema_config_types_are_required(self):
        report = self.report()
        report["config"]["arms"] = {arm: True for arm in unchanged_compare.ARMS}
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)
        report = self.report()
        del report["runs"][0]["metrics"]["wall_ms"]
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)
        report = self.report()
        report["runs"][0]["metrics"]["total_tokens"] = 0
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)
        report = self.report()
        report["runs"][0]["metrics"]["wall_ms"] = 0
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)
        report = self.report()
        report["runs"][0]["metrics"]["total_tokens"] = 11
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)
        report = self.report()
        report["runs"][0]["metrics"]["failed_tool_calls"] = 11
        with self.assertRaises(ValueError):
            unchanged_compare.compare(report)

    def test_cli_emits_json_and_rejects_missing_argument(self):
        report = self.report()
        with tempfile.TemporaryDirectory(prefix="unchanged-compare-") as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(report))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = unchanged_compare.main([str(path)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["scheduled"], 24)
        with self.assertRaises(SystemExit) as missing:
            unchanged_compare.main([])
        self.assertEqual(missing.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
