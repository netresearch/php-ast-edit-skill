"""The primary multi-file gate must not relabel the A/A control as treatment."""

import unittest

import shared_compare
import test_unchanged_compare


class SharedComparisonTests(unittest.TestCase):
    def report(self):
        return test_unchanged_compare.CompareTests().report(shared_compare.ARMS)

    def test_single_file_is_descriptive_and_calls_can_fail_primary_gate(self):
        report = self.report()
        for row in report["runs"]:
            if row["task_id"] != shared_compare.PRIMARY_TASK:
                row["metrics"].update(total_tokens=10000, input_tokens=10000)
        result = shared_compare.compare(report)
        self.assertIsNone(result["tasks"][0]["numeric_criterion_passed"])
        self.assertTrue(result["primary_numeric_criterion_passed"])
        self.assertNotIn("all_tasks_numeric_criterion_passed", result)
        for row in report["runs"]:
            if (
                row["task_id"] == shared_compare.PRIMARY_TASK
                and row["arm"] == shared_compare.ARMS[1]
            ):
                row["metrics"]["tool_calls"] = 11
        self.assertFalse(
            shared_compare.compare(report)["primary_numeric_criterion_passed"]
        )

    def test_zero_control_calls_cannot_establish_a_paired_call_saving(self):
        report = self.report()
        for row in report["runs"]:
            row["metrics"].update(tool_calls=0, failed_tool_calls=0)
        self.assertFalse(
            shared_compare.compare(report)["primary_numeric_criterion_passed"]
        )


if __name__ == "__main__":
    unittest.main()
