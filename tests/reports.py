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
            result.append(
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "edits": [
                        {
                            "target": {"select": f"class:Item{i}"},
                            "operation": "add_member",
                            "php": "public const READY = true;",
                        }
                    ],
                }
            )
        return result

    def configure(self, directory=None, failing=False, repeat=1):
        directory = directory or self.root
        code = (
            "file_put_contents('calls.txt', 'x', FILE_APPEND); "
            "echo str_repeat('unique-diagnostic ', 100); "
            f"exit({int(failing)});"
        )
        (directory / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "canonical": False,
                    "verify": [["php", "-r", code, "{files}"]] * repeat,
                }
            )
        )

    def apply(self, files, **extra):
        process = subprocess.run(
            [str(ENGINE), "apply"],
            input=json.dumps({"files": files, **extra}),
            text=True,
            cwd=self.root,
            capture_output=True,
            check=False,
        )
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
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "verify": [
                        {
                            "scope": "project",
                            "command": [
                                "php",
                                "-r",
                                (
                                    "echo str_repeat('stdout-progress ', 1000); "
                                    "fwrite(STDERR, str_repeat('stderr-failure ', 1000)); exit(1);"
                                ),
                            ],
                        }
                    ],
                }
            )
        )
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
        self.assertEqual(
            {str(first), str(second)}, {c["cwd"] for c in report["verify"]}
        )
        self.assertEqual(2, len({c["id"] for c in report["verify"]}))
        self.assertNotEqual(
            report["files"][0]["checkIds"], report["files"][1]["checkIds"]
        )

    def test_a_disappeared_file_is_still_passed_to_the_planned_check(self):
        files = self.files()
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "verify": [
                        {
                            "scope": "project",
                            "command": ["php", "-r", "unlink('Item0.php');"],
                        },
                        [
                            "php",
                            "-r",
                            "exit(count(array_filter(array_slice($argv, 1), 'is_file')) === count($argv) - 1 ? 0 : 1);",
                            "{files}",
                        ],
                    ],
                }
            )
        )
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

    # --- report: "agent" -------------------------------------------------------------------
    # The decision-shaped projection. Its whole value is what it leaves out, so most of these
    # assert absence — and absence is the assertion most easily satisfied by a typo, hence the
    # paired presence checks on the fields that must survive.

    def test_agent_states_the_three_claims_separately(self):
        self.configure()
        status, report, _ = self.apply(self.files(), report="agent")
        self.assertEqual(0, status)
        self.assertEqual(1, report["reportVersion"])
        self.assertEqual("agent", report["report"])
        self.assertEqual("applied", report["outcome"])
        self.assertEqual("passed", report["checks"])
        for file in report["files"]:
            self.assertTrue(file["changed"])
            self.assertEqual("passed", file["syntax"])
            self.assertEqual("passed", file["checks"])
            self.assertEqual([], file["open"])
            self.assertIn("const READY", pathlib.Path(file["path"]).read_text())

    def test_agent_distinguishes_no_checks_declared_from_checks_passed(self):
        # No .php-ast-edit.json at all: nothing verified this edit. A nullable boolean cannot
        # say that, and an agent reading one stops as if the result had been checked.
        status, report, _ = self.apply(self.files(), report="agent")
        self.assertEqual(0, status)
        self.assertEqual("none_declared", report["checks"])
        self.assertIsNone(report["checksPassed"])
        for file in report["files"]:
            self.assertEqual("none_declared", file["checks"])
            self.assertIn(
                "NO_CHECKS_DECLARED",
                " ".join(file["open"]),
            )

    def test_agent_carries_failed_check_output_once_and_drops_passing_noise(self):
        self.configure(failing=True)
        status, report, text = self.apply(self.files(10), report="agent")
        self.assertEqual(1, status)
        self.assertEqual("applied_checks_failed", report["outcome"])
        self.assertEqual("failed", report["checks"])
        self.assertEqual(0, report["checksPassedCount"])
        self.assertEqual(1, len(report["checksFailed"]))
        self.assertIn("unique-diagnostic", report["checksFailed"][0]["output"])
        self.assertEqual(1, text.count('"output":'))
        # The edit is kept on a failed check, in this mode as in every other.
        for file in report["files"]:
            self.assertIn("const READY", pathlib.Path(file["path"]).read_text())

    def test_agent_omits_the_diff_the_generated_code_and_the_duplicated_fields(self):
        self.configure()
        _, full, full_text = self.apply(self.files(), report="full")
        _, agent, agent_text = self.apply(self.files(), report="agent")
        self.assertIn("diff", full["files"][0])
        self.assertLess(len(agent_text), len(full_text))
        for file in agent["files"]:
            for absent in ("diff", "code", "valid", "warning", "validation", "verify"):
                self.assertNotIn(absent, file)
            # ... while the fields the next decision needs are still there.
            self.assertIn("afterSha256", file)
            self.assertIn("beforeSha256", file)
            self.assertIn("checkIds", file)

    def test_agent_dry_run_says_the_tree_is_unchanged(self):
        self.configure()
        files = self.files()
        status, report, _ = self.apply(files, report="agent", dryRun=True)
        self.assertEqual(0, status)
        self.assertEqual("dry_run", report["outcome"])
        for file in report["files"]:
            self.assertNotIn("code", file)
            self.assertIn("NOT_WRITTEN", " ".join(file["open"]))
            self.assertNotIn("const READY", pathlib.Path(file["path"]).read_text())

    def test_agent_names_what_a_rename_left_open(self):
        self.configure()
        source = "<?php final class Caller { public function go(): void { $this->old(); } public function old(): void {} }\n"
        path = self.root / "Caller.php"
        path.write_text(source)
        status, report, _ = self.apply(
            [
                {
                    "path": str(path),
                    "edits": [
                        {
                            "target": {"select": "method:Caller::old"},
                            "operation": "rename_method",
                            "to": "renamed",
                        }
                    ],
                }
            ],
            report="agent",
        )
        self.assertEqual(0, status)
        open_text = " ".join(report["files"][0]["open"])
        self.assertIn("CALLERS_OUTSIDE_FILE", open_text)

    def test_agent_is_reachable_from_the_flag_form(self):
        self.configure()
        source = "<?php final class Flagged { public function run(): int { $n = 1; return $n; } }\n"
        path = self.root / "Flagged.php"
        path.write_text(source)
        process = subprocess.run(
            [
                str(ENGINE),
                "apply",
                "--file",
                str(path),
                "--select",
                "method:Flagged::run",
                "--op",
                "rename_variable",
                "--from",
                "n",
                "--to",
                "count",
                "--report",
                "agent",
            ],
            text=True,
            cwd=self.root,
            capture_output=True,
            check=False,
        )
        report = json.loads(process.stdout or process.stderr)
        self.assertEqual(0, process.returncode)
        self.assertEqual("agent", report["report"])
        self.assertEqual(1, report["reportVersion"])

    def test_an_unknown_report_names_all_three_modes(self):
        self.configure()
        status, _, text = self.apply(self.files(), report="loud")
        self.assertEqual(2, status)
        for mode in ("full", "compact", "agent"):
            self.assertIn(mode, text)

    # --- the proof a caller needs to decide reuse ------------------------------------------

    def test_every_execution_is_named_including_the_passing_ones(self):
        self.configure(repeat=2)
        _, report, _ = self.apply(self.files(), report="agent")
        self.assertEqual("passed", report["checks"])
        self.assertEqual(2, report["checksPassedCount"])
        self.assertEqual(2, len(report["verifications"]))
        for entry in report["verifications"]:
            self.assertTrue(entry["ok"])
            self.assertEqual(str(self.root), entry["cwd"])
            self.assertIn("command", entry)
            self.assertIn("scope", entry)
            # The proof carries no output for a check that passed.
            self.assertNotIn("output", entry)
        self.assertEqual(2, len({e["id"] for e in report["verifications"]}))

    def test_the_proof_joins_to_the_files_by_check_id_and_hash(self):
        self.configure()
        _, report, _ = self.apply(self.files(3), report="agent")
        ids = {entry["id"] for entry in report["verifications"]}
        for file in report["files"]:
            # Which check saw this file, and at exactly which bytes.
            self.assertTrue(set(file["checkIds"]).issubset(ids))
            self.assertEqual(
                hashlib.sha256(pathlib.Path(file["path"]).read_bytes()).hexdigest(),
                file["afterSha256"],
            )

    def test_a_failed_execution_appears_in_both_lists_with_output_only_in_one(self):
        self.configure(failing=True)
        _, report, _ = self.apply(self.files(), report="agent")
        self.assertEqual(1, len(report["verifications"]))
        self.assertEqual(1, len(report["checksFailed"]))
        self.assertFalse(report["verifications"][0]["ok"])
        self.assertEqual(
            report["verifications"][0]["id"], report["checksFailed"][0]["id"]
        )
        self.assertNotIn("output", report["verifications"][0])
        self.assertIn("unique-diagnostic", report["checksFailed"][0]["output"])

    def test_the_report_names_what_the_proof_does_not_cover(self):
        self.configure()
        _, report, _ = self.apply(self.files(), report="agent")
        # A caller keyed only on command plus file hashes reuses a stale pass after a
        # dependency bump. The engine cannot see those inputs, so it says so.
        self.assertEqual(
            ["dependencies", "checkToolVersions", "runtime", "environment"],
            report["proofExcludes"],
        )

    def test_adding_the_proof_did_not_bump_the_schema_version(self):
        # The documented rule: a bump means a field was removed or changed meaning.
        self.configure()
        _, report, _ = self.apply(self.files(), report="agent")
        self.assertEqual(1, report["reportVersion"])

    def test_no_checks_declared_leaves_the_proof_empty_not_absent(self):
        _, report, _ = self.apply(self.files(), report="agent")
        self.assertEqual("none_declared", report["checks"])
        self.assertEqual([], report["verifications"])
        self.assertEqual(0, report["checksPassedCount"])


if __name__ == "__main__":
    unittest.main()
