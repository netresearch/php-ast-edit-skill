#!/usr/bin/env python3
"""What --task keeps apart, and what happens without it.

A working root holds one result file per run and nothing in the name says which task the
run was. Two tasks measured in the same root are therefore indistinguishable to a glob,
and the median that comes out of pooling them belongs to neither. The first test here is
the hazard, asserted rather than described; the rest are the filter that answers it.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SUMMARIZE = pathlib.Path(__file__).resolve().parent / "summarize.py"

specification = importlib.util.spec_from_file_location("summarize", SUMMARIZE)
summarize = importlib.util.module_from_spec(specification)
specification.loader.exec_module(summarize)


class TaskFilterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="skill-invocation-")
        self.root = pathlib.Path(self.temporary.name)
        (self.root / "out").mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def run_result(self, task, arm, turns):
        """One completed run, in the shape the CLI writes it."""
        (self.root / "out" / f"{task}-{arm}.json").write_text(
            json.dumps(
                {
                    "session_id": f"{task}-{arm}",
                    "num_turns": turns,
                    "duration_ms": 1000 * turns,
                    "total_cost_usd": 0.1,
                    "usage": {
                        "output_tokens": 100 * turns,
                        "cache_read_input_tokens": 1000 * turns,
                    },
                }
            )
        )

    def summary(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SUMMARIZE), str(self.root), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def two_tasks(self):
        # Task A is cheap, task B is not. Pooled, the median lands between them and
        # describes no run that was ever made.
        for repetition, turns in enumerate([4, 6], start=1):
            self.run_result(f"A{repetition}", "ast", turns)
        for repetition, turns in enumerate([20, 22], start=1):
            self.run_result(f"B{repetition}", "ast", turns)

    def test_without_a_task_the_two_are_pooled(self):
        self.two_tasks()
        result = self.summary("ast")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("runs: 4 6 20 22", result.stdout)

    def test_a_task_keeps_a_summary_to_its_own_runs(self):
        self.two_tasks()
        first = self.summary("ast", "--task", "A")
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertIn("runs: 4 6", first.stdout)
        self.assertNotIn("20", first.stdout)
        second = self.summary("ast", "--task", "B")
        self.assertIn("runs: 20 22", second.stdout)
        self.assertNotIn(" 4 ", second.stdout)

    def test_the_named_task_is_reported_so_a_pasted_table_says_which(self):
        self.two_tasks()
        self.assertIn("task ids beginning A", self.summary("ast", "--task", "A").stdout)

    def test_a_task_nothing_matches_reports_nothing_rather_than_everything(self):
        self.two_tasks()
        result = self.summary("ast", "--task", "C")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("no completed runs", result.stdout)

    def test_a_task_that_looks_like_a_path_is_refused(self):
        self.two_tasks()
        result = self.summary("ast", "--task", "../../etc")
        self.assertNotEqual(0, result.returncode)
        # Named as a task, not as an arm: a build that does not know the flag reads it as
        # two more arms and refuses the flag itself, which is the right exit for the wrong
        # reason and would let an unfiltered summary pass this test.
        self.assertIn("refusing to use task '../../etc'", result.stderr)


if __name__ == "__main__":
    unittest.main()
