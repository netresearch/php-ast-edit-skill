"""Prospective forty-attempt gate: robust wins, exact thresholds, no dropped runs."""

import copy
import unittest
from decimal import Decimal

import final_compare
import unchanged_compare


def report():
    rows = []
    for task in final_compare.TASKS:
        for arm in final_compare.ARMS:
            for repetition in range(1, 11):
                tokens = 100 if arm == final_compare.ARMS[0] else 80
                metrics = dict.fromkeys(unchanged_compare.METRICS, 0)
                metrics.update(
                    total_tokens=tokens,
                    input_tokens=tokens,
                    tool_calls=4,
                    wall_ms=Decimal("100.1"),
                    cost_usd=Decimal("0.01"),
                )
                rows.append(
                    {
                        "run_id": f"run{len(rows) + 1:03}",
                        "task_id": task,
                        "arm": arm,
                        "repetition": repetition,
                        "model_key": "haiku",
                        "reported_model": unchanged_compare.EXPECTED_MODEL_ID,
                        "attempted": True,
                        "oracle_passed": True,
                        "metrics": metrics,
                    }
                )
    return {
        "schema_version": 1,
        "attempted": 40,
        "scheduled": 40,
        "runs": rows,
        "config": {
            "arms": list(final_compare.ARMS),
            "task_ids": list(final_compare.TASKS),
            "repetitions": 10,
            "model_keys": ["haiku"],
            "models": {
                "haiku": {"id": unchanged_compare.EXPECTED_MODEL_ID, "effort": None}
            },
        },
    }


class FinalComparisonTests(unittest.TestCase):
    def test_all_attempts_retained_and_quality_remains_separate(self):
        data = report()
        data["runs"][0]["oracle_passed"] = False
        result = final_compare.compare(data)
        self.assertEqual(result["oracle_passes"], 39)
        self.assertTrue(result["all_tasks_numeric_criterion_passed"])
        self.assertNotIn("overall_passed", result)
        self.assertEqual([task["n_pairs"] for task in result["tasks"]], [10, 10])

    def test_nine_strict_wins_required_and_ties_are_nonwins(self):
        data = report()
        treatment = [
            row
            for row in data["runs"]
            if row["arm"] == final_compare.ARMS[1]
            and row["task_id"] == final_compare.TASKS[0]
        ]
        treatment[0]["metrics"].update(total_tokens=100, input_tokens=100)
        task = final_compare.compare(data)["tasks"][0]
        self.assertTrue(task["numeric_criterion_passed"])
        self.assertEqual(task["token_saving_pairs"], 9)
        self.assertEqual(task["binomial_win_tail"], 11 / 1024)
        treatment[1]["metrics"].update(total_tokens=100, input_tokens=100)
        self.assertFalse(
            final_compare.compare(data)["tasks"][0]["numeric_criterion_passed"]
        )

    def test_exact_threshold_and_zero_call_denominator(self):
        data = report()
        for row in data["runs"]:
            if row["arm"] == final_compare.ARMS[1]:
                row["metrics"].update(total_tokens=85, input_tokens=85)
        self.assertTrue(
            final_compare.compare(data)["all_tasks_numeric_criterion_passed"]
        )
        for row in data["runs"]:
            if row["arm"] == final_compare.ARMS[1]:
                row["metrics"]["wall_ms"] = Decimal("100.10000000000000000001")
        self.assertFalse(
            final_compare.compare(data)["all_tasks_numeric_criterion_passed"]
        )
        for row in data["runs"]:
            row["metrics"].update(tool_calls=0, wall_ms=100)
        self.assertFalse(
            final_compare.compare(data)["all_tasks_numeric_criterion_passed"]
        )

    def test_malformed_drifted_and_incomplete_campaigns_rejected(self):
        original = report()
        cases = []
        for key, value in (
            ("attempted", 39),
            ("scheduled", True),
            ("schema_version", True),
        ):
            data = copy.deepcopy(original)
            data[key] = value
            cases.append(data)
        for key, value in (
            ("repetitions", 6),
            ("arms", list(reversed(final_compare.ARMS))),
            ("task_ids", ["old-task"]),
            ("model_keys", ["sonnet"]),
        ):
            data = copy.deepcopy(original)
            data["config"][key] = value
            cases.append(data)
        for key, value in (
            ("run_id", original["runs"][1]["run_id"]),
            ("repetition", True),
            ("attempted", False),
            ("reported_model", "other"),
            ("oracle_passed", 1),
        ):
            data = copy.deepcopy(original)
            data["runs"][0][key] = value
            cases.append(data)
        data = copy.deepcopy(original)
        data["runs"][0]["metrics"]["total_tokens"] += 1
        cases.append(data)
        cases.append({**original, "runs": original["runs"][:-1]})
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                final_compare.compare(data)


if __name__ == "__main__":
    unittest.main()
