#!/usr/bin/env python3
"""CLI regressions for shared verification reports and their compact projection."""
import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "bin/php-ast-edit"


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="php-ast-reports-")
        self.root = pathlib.Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def files(self, count=2, directory=None):
        directory = directory or self.root
        directory.mkdir(exist_ok=True)
        result = []
        for i in range(count):
            path = directory / f"Item{i}.php"
            source = f"<?php final class Item{i} {{}}\n"
            path.write_text(source)
            result.append({
                "path": str(path),
                "sha256": hashlib.sha256(source.encode()).hexdigest(),
                "edits": [{"target": {"select": f"class:Item{i}"},
                           "operation": "add_member", "php": "public const READY = true;"}],
            })
        return result

    def configure(self, directory=None, failing=False, repeat=1):
        directory = directory or self.root
        code = ("file_put_contents('calls.txt', 'x', FILE_APPEND); "
                "echo str_repeat('unique-diagnostic ', 100); "
                f"exit({int(failing)});")
        (directory / ".php-ast-edit.json").write_text(json.dumps({
            "canonical": False,
            "verify": [["php", "-r", code, "{files}"]] * repeat,
        }))

    def apply(self, files, **extra):
        process = subprocess.run([str(ENGINE), "apply"],
                                 input=json.dumps({"files": files, **extra}), text=True,
                                 cwd=self.root, capture_output=True, check=False)
        output = process.stdout or process.stderr
        return process.returncode, json.loads(output), output

    def test_compact_shares_one_failed_execution_and_retains_edits(self):
        self.configure(failing=True)
        files = self.files(10)
        status, report, output = self.apply(files, report="compact")
        self.assertEqual(1, status)
        self.assertFalse(report["checksPassed"])
        self.assertEqual("x", (self.root / "calls.txt").read_text())
        self.assertEqual(1, len(report["verify"]))
        check = report["verify"][0]
        self.assertEqual(str(self.root), check["cwd"])
        self.assertEqual("changed_files", check["scope"])
        self.assertFalse(check["ok"])
        self.assertIn("unique-diagnostic", check["output"])
        for file in report["files"]:
            self.assertNotIn("verify", file)
            self.assertEqual([check["id"]], file["checkIds"])
            self.assertEqual("failed", file["validation"]["checks"])
            self.assertIn("const READY", pathlib.Path(file["path"]).read_text())
        self.assertEqual(1, output.count('"output":'))

    def test_full_default_keeps_file_verification_contract(self):
        self.configure()
        status, report, _ = self.apply(self.files())
        self.assertEqual(0, status)
        self.assertTrue(report["checksPassed"])
        for file in report["files"]:
            self.assertTrue(file["verify"][0]["ok"])
            self.assertIn("command", file["verify"][0])

    def test_noisy_failed_check_preserves_both_streams_within_cap(self):
        (self.root / ".php-ast-edit.json").write_text(json.dumps({
            "verify": [{"scope": "project", "command": [
                "php", "-r", "echo str_repeat('stdout-progress ', 1000); "
                "fwrite(STDERR, str_repeat('stderr-failure ', 1000)); exit(1);",
            ]}],
        }))
        status, report, _ = self.apply(self.files(), report="compact")
        self.assertEqual(1, status)
        output = report["verify"][0]["output"]
        self.assertTrue(output.startswith("stderr-failure"))
        self.assertIn("stdout-progress", output)
        self.assertLessEqual(len(output.encode()), 4000)

    def test_identical_commands_are_distinct_executions(self):
        self.configure(repeat=2)
        status, report, _ = self.apply(self.files(), report="compact")
        self.assertEqual(0, status)
        self.assertEqual("xx", (self.root / "calls.txt").read_text())
        ids = [check["id"] for check in report["verify"]]
        self.assertEqual(2, len(set(ids)))
        self.assertEqual(ids, report["files"][0]["checkIds"])

    def test_same_commands_in_different_roots_remain_separate(self):
        first, second = self.root / "one", self.root / "two"
        files = self.files(1, first) + self.files(1, second)
        self.configure(first)
        self.configure(second)
        status, report, _ = self.apply(files, report="compact")
        self.assertEqual(0, status)
        self.assertEqual({str(first), str(second)}, {c["cwd"] for c in report["verify"]})
        self.assertEqual(2, len({c["id"] for c in report["verify"]}))
        self.assertNotEqual(report["files"][0]["checkIds"], report["files"][1]["checkIds"])

    def test_a_disappeared_file_is_still_passed_to_the_planned_check(self):
        files = self.files()
        (self.root / ".php-ast-edit.json").write_text(json.dumps({
            "verify": [
                {"scope": "project", "command": ["php", "-r", "unlink('Item0.php');"]},
                ["php", "-r", "exit(count(array_filter(array_slice($argv, 1), 'is_file')) === count($argv) - 1 ? 0 : 1);", "{files}"],
            ],
        }))
        status, report, _ = self.apply(files, report="compact")
        self.assertEqual(1, status)
        self.assertEqual(2, len(report["verify"]))
        self.assertFalse(report["verify"][1]["ok"])
        self.assertIn(files[0]["path"], report["verify"][1]["command"])
        for file in report["files"]:
            self.assertEqual("failed", file["validation"]["checks"])

    def test_invalid_report_modes_fail_before_mutation(self):
        for value in (None, True, 1, [], {}, "typo", ""):
            with self.subTest(value=value):
                files = self.files(1)
                before = pathlib.Path(files[0]["path"]).read_bytes()
                status, report, _ = self.apply(files, report=value)
                self.assertEqual(2, status)
                self.assertIn("report", report["error"])
                self.assertEqual(before, pathlib.Path(files[0]["path"]).read_bytes())

    def test_dry_run_has_no_check_ids_and_no_execution(self):
        self.configure()
        files = self.files()
        status, report, _ = self.apply(files, report="compact", dryRun=True)
        self.assertEqual(0, status)
        self.assertIsNone(report["checksPassed"])
        self.assertEqual([], report["verify"])
        self.assertFalse((self.root / "calls.txt").exists())
        for file in report["files"]:
            self.assertEqual([], file["checkIds"])
            self.assertEqual("not_run", file["validation"]["checks"])
            self.assertNotIn("const READY", pathlib.Path(file["path"]).read_text())

    def test_compact_removes_repeated_payload_at_scale(self):
        self.configure(failing=True)
        _, full, full_text = self.apply(self.files(30), report="full")
        _, compact, compact_text = self.apply(self.files(30), report="compact")
        self.assertEqual(full["checksPassed"], compact["checksPassed"])
        self.assertLess(len(compact_text), len(full_text) // 2)
        self.assertEqual(30, full_text.count('"output":'))
        self.assertEqual(1, compact_text.count('"output":'))


if __name__ == "__main__":
    unittest.main()
