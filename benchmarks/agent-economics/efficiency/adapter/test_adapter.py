#!/usr/bin/env python3
"""Integration checks against the real engine; fixtures live only in temporary directories."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get("PHP_AST_EDIT_BIN", HERE.parents[3] / "bin/php-ast-edit"))
SOURCE = """<?php
namespace Example;
use RuntimeException as Problem;
final class Cache {
    /** Complete selected method. */
    public function key(string $value): string {
        if ($value === '') {
            throw new Problem('empty');
        }
        return $value;
    }
    public function unrelated(): string { return 'UNRELATED_BODY_SENTINEL'; }
}
"""


class ReadHelperTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            **os.environ,
            "PHP_AST_AGENT_AUTOLOAD": str(
                ENGINE.resolve().parent.parent / "vendor/autoload.php"
            ),
        }

    def call_helper(self, payload=None, *, raw=None, env=None):
        return subprocess.run(
            ["php", "-d", "display_errors=stderr", str(HERE / "read.php")],
            input=raw if raw is not None else json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env if env is None else env,
            check=False,
        )

    def assert_failure(self, result, message):
        self.assertEqual(result.returncode, 2, (result.stdout, result.stderr))
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)
        self.assertNotIn("Warning:", result.stderr)

    def test_invalid_request_shapes_are_rejected_before_rendering(self):
        valid = {"sources": [], "mode": "full", "select": None}
        cases = [None, [], "source", 42, True, {}]
        cases.extend(
            {key: value for key, value in valid.items() if key != omitted}
            for omitted in valid
        )
        cases.extend(
            {**valid, "sources": value}
            for value in (
                None,
                {},
                {"0": SOURCE},
                SOURCE,
                [None],
                [1],
                [False],
                [{}],
                [[]],
                [SOURCE, 1],
            )
        )
        cases.extend(
            {**valid, "mode": value}
            for value in (None, False, 1, [], {}, "", "FULL", "other")
        )
        cases.extend({**valid, "select": value} for value in (False, 1, [], {}))
        for payload in cases:
            with self.subTest(payload=payload):
                result = self.call_helper(payload)
                self.assert_failure(result, "Invalid read request")

    def test_malformed_json_is_rejected_without_success_output(self):
        result = self.call_helper(raw="{invalid")
        self.assert_failure(result, "Syntax error")

    def test_valid_empty_and_full_batches_remain_supported(self):
        for mode in ("full", "focused"):
            result = self.call_helper({"sources": [], "mode": mode, "select": None})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [])
            self.assertEqual(result.stderr, "")
        result = self.call_helper(
            {"sources": [SOURCE, SOURCE], "mode": "full", "select": None}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout), [{"mode": "full", "source": SOURCE}] * 2
        )
        self.assertEqual(result.stderr, "")

    def test_autoload_diagnostic_names_the_actual_configuration(self):
        for configured in (None, "", str(HERE), str(HERE / "missing-autoload.php")):
            env = dict(self.env)
            if configured is None:
                env.pop("PHP_AST_AGENT_AUTOLOAD")
            else:
                env["PHP_AST_AGENT_AUTOLOAD"] = configured
            with self.subTest(autoload=configured):
                result = self.call_helper(
                    {"sources": [], "mode": "full", "select": None}, env=env
                )
                self.assert_failure(result, "PHP_AST_AGENT_AUTOLOAD")
                self.assertNotIn("PHP_AST_EDIT_BIN", result.stderr)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="php-ast-agent-tests-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.work = base / "work"
        self.work.mkdir()
        self.state = base / "state"
        self.env = {
            **os.environ,
            "PHP_AST_EDIT_BIN": str(ENGINE),
            "PHP_AST_AGENT_STATE_DIR": str(self.state),
        }
        self.first = self.work / "First.php"
        self.second = self.work / "Second.php"
        self.first.write_text(SOURCE)
        self.second.write_text(SOURCE.replace("Cache", "Second"))

    def call(self, *args, payload=None, raw=None, status=0):
        process = subprocess.run(
            [str(HERE / "php-ast-agent"), *args],
            input=raw
            if raw is not None
            else json.dumps(payload)
            if payload is not None
            else None,
            text=True,
            capture_output=True,
            cwd=self.work,
            env=self.env,
            check=False,
        )
        self.assertEqual(process.returncode, status, (process.stdout, process.stderr))
        return json.loads(process.stdout)

    def read(self, *files, mode="full", select=None):
        args = ["read", "--files", *(files or ["First.php"]), "--mode", mode]
        if select:
            args += ["--select", select]
        return self.call(*args)["files"]

    def edit(self, view, owner="Cache", to="cacheKey"):
        return {
            "path": view["path"],
            "revision": view["revision"],
            "edits": [
                {
                    "operation": "set_name",
                    "target": {"select": f"method:{owner}::key"},
                    "value": to,
                }
            ],
        }

    def test_focused_source_includes_entire_body_and_context(self):
        full = self.read(select="method:Cache::key")[0]
        self.assertEqual(full["source"], SOURCE)
        focused = self.read(mode="focused", select="method:Cache::key")[0]
        self.assertTrue(
            focused["source"].startswith("/** Complete selected method. */")
        )
        self.assertTrue(focused["source"].endswith("return $value;\n    }"))
        self.assertEqual(focused["lines"], [5, 11])
        self.assertIn("throw new Problem('empty');", focused["source"])
        self.assertEqual(focused["context"]["namespace"], "namespace Example;")
        self.assertEqual(
            focused["context"]["imports"], ["use RuntimeException as Problem;"]
        )
        self.assertEqual(focused["context"]["class_declaration"], "final class Cache {")
        self.assertNotIn("UNRELATED_BODY_SENTINEL", json.dumps(focused))
        self.assertIn(
            "method:Cache::unrelated", [x["select"] for x in focused["outline"]]
        )
        self.assertEqual(self.read(mode="focused")[0]["source"], SOURCE)
        selected_class = self.read(mode="focused", select="class:Cache")[0]
        self.assertIn("UNRELATED_BODY_SENTINEL", selected_class["source"])

    def test_revision_path_and_staleness_guards(self):
        view = self.read()[0]
        bad = self.edit(view)
        bad["revision"] = "unknown"
        self.assertIn(
            "Unknown", self.call("apply", payload={"files": [bad]}, status=2)["error"]
        )
        bad = self.edit(view)
        bad["path"] = "Second.php"
        self.assertIn(
            "different file",
            self.call("apply", payload={"files": [bad]}, status=2)["error"],
        )
        self.assertEqual(self.first.read_text(), SOURCE)
        self.first.write_text(SOURCE + "// external mutation\n")
        stale = self.call("apply", payload={"files": [self.edit(view)]}, status=2)
        self.assertIn("STALE_REVISION", stale["error"])
        self.assertEqual(self.first.read_text(), SOURCE + "// external mutation\n")
        events = [
            json.loads(line)
            for line in (self.state / "audit.jsonl").read_text().splitlines()
        ]
        attempts = [e for e in events if e["event"] == "apply_attempt"]
        results = [e for e in events if e["event"] == "apply_result"]
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len(results), 3)
        self.assertEqual(
            results[-1]["files"][0]["sha256"], events[0]["files"][0]["sha256"]
        )
        self.assertFalse(any(e["ok"] for e in results))

    def test_multifile_engine_failure_preserves_both_files_and_handles(self):
        first, second = self.read("First.php", "Second.php")
        before = (self.first.read_bytes(), self.second.read_bytes())
        bad = self.edit(second, "MissingClass")
        result = self.call(
            "apply", payload={"files": [self.edit(first), bad]}, status=2
        )
        self.assertFalse(result["ok"])
        after = (self.first.read_bytes(), self.second.read_bytes())
        self.assertEqual(after, before)
        # A rejected transaction leaves both read handles available for a corrected transaction.
        good = self.call(
            "apply", payload={"files": [self.edit(first), self.edit(second, "Second")]}
        )
        self.assertTrue(good["ok"])
        self.assertTrue(all(file["changed"] for file in good["files"]))

    def test_real_lint_report_diff_and_consumed_handle(self):
        view = self.read()[0]
        other_view = self.read()[0]
        result = self.call("apply", payload={"files": [self.edit(view)]})
        report = result["files"][0]
        self.assertTrue(result["ok"])
        self.assertEqual(report["validation"]["lint"]["status"], "passed")
        lint = subprocess.run(
            ["php", "-l", str(self.first)], capture_output=True, check=False
        )
        self.assertEqual(lint.returncode, 0)
        self.assertEqual(report["printer_info"], "not_canonical")
        self.assertNotIn("warnings", report)
        self.assertNotIn("valid", report)
        self.assertIn("-    public function key", report["diff"])
        self.assertIn("+    public function cacheKey", report["diff"])
        for previous in (view, other_view):
            self.assertIn(
                "consumed",
                self.call("apply", payload={"files": [self.edit(previous)]}, status=2)[
                    "error"
                ],
            )

    def test_failed_project_check_is_reported_and_invalidates_changed_snapshot(self):
        (self.work / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "canonical": False,
                    "verify": [["php", "-r", "exit(1);", "{files}"]],
                }
            )
        )
        view = self.read()[0]
        result = self.call("apply", payload={"files": [self.edit(view)]}, status=1)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checksPassed"])
        self.assertEqual(result["files"][0]["validation"]["checks"], "failed")
        self.assertFalse(result["verify"][0]["ok"])
        self.assertEqual(
            [result["verify"][0]["id"]], result["files"][0]["checkIds"]
        )
        self.assertNotIn("verify", result["files"][0])
        self.assertIn("cacheKey", self.first.read_text())
        self.assertIn(
            "consumed",
            self.call("apply", payload={"files": [self.edit(view)]}, status=2)["error"],
        )

    def test_genuine_rename_warning_preserved(self):
        self.first.write_text(
            SOURCE + "function elsewhere($value) { return $value; }\n"
        )
        view = self.read()[0]
        spec = self.edit(view)
        spec["edits"] = [
            {
                "operation": "rename_variable",
                "target": {"select": "method:Cache::key"},
                "from": "value",
                "to": "input",
            }
        ]
        result = self.call("apply", payload={"files": [spec]})
        self.assertTrue(
            any(
                w.startswith("INCOMPLETE_RENAME:")
                for w in result["files"][0]["warnings"]
            )
        )
        self.assertIn("effects", result["files"][0])

    def test_truncated_diff_can_be_retrieved_and_replayed(self):
        before = self.first.read_bytes()
        view = self.read()[0]
        spec = self.edit(view)
        method = (
            "public function added(): void {\n"
            + "\n".join(f"echo {n};" for n in range(160))
            + "\n}"
        )
        spec["edits"] = [
            {
                "operation": "add_member",
                "target": {"select": "class:Cache"},
                "php": method,
            }
        ]
        result = self.call("apply", payload={"files": [spec]})
        self.assertTrue(result["files"][0]["diff_truncated"])
        self.assertLessEqual(len(result["files"][0]["diff"].splitlines()), 100)
        full = self.call(*result["full_diff"].split()[1:])["diffs"]["First.php"]
        self.assertIn("echo 159;", full)
        expected = self.first.read_bytes()
        self.first.write_bytes(before)
        patch = subprocess.run(
            ["patch", "--quiet", "First.php"],
            input=full,
            text=True,
            cwd=self.work,
            capture_output=True,
            check=False,
        )
        self.assertEqual(patch.returncode, 0, patch.stderr)
        self.assertEqual(self.first.read_bytes(), expected)

    def test_missing_final_newline_diff_is_replayable(self):
        self.first.write_text(SOURCE.rstrip("\n"))
        before = self.first.read_bytes()
        view = self.read()[0]
        spec = {"path": view["path"], "revision": view["revision"], "mode": "delete"}
        result = self.call("apply", payload={"files": [spec]})
        diff = result["files"][0]["diff"]
        self.assertIn("\\ No newline at end of file", diff)
        self.first.write_bytes(before)
        patch = subprocess.run(
            ["patch", "--quiet", "First.php"],
            input=diff,
            text=True,
            cwd=self.work,
            capture_output=True,
            check=False,
        )
        self.assertEqual(patch.returncode, 0, patch.stderr)
        self.assertEqual(self.first.read_bytes(), b"")

    def test_malformed_apply_is_audited(self):
        self.call("apply", raw="{invalid", status=2)
        events = [
            json.loads(line)
            for line in (self.state / "audit.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            [event["event"] for event in events], ["apply_attempt", "apply_result"]
        )
        self.assertEqual(events[0]["invalid_json"], "{invalid")
        self.assertFalse(events[1]["ok"])

    def test_dry_run_is_explicitly_rejected_without_consuming_snapshot(self):
        view = self.read()[0]
        result = self.call(
            "apply", payload={"dryRun": True, "files": [self.edit(view)]}, status=2
        )
        self.assertIn("dryRun is unsupported", result["error"])
        self.assertEqual(self.first.read_text(), SOURCE)
        self.assertTrue(self.call("apply", payload={"files": [self.edit(view)]})["ok"])

    def test_read_helper_failure_is_wrapped_as_a_json_error(self):
        self.env["PHP_AST_EDIT_BIN"] = str(
            self.work / "missing-runtime/bin/php-ast-edit"
        )
        result = self.call("read", "--files", "First.php", "--mode", "full", status=2)
        self.assertFalse(result["ok"])
        self.assertIn("PHP_AST_AGENT_AUTOLOAD", result["error"])
        self.assertEqual(self.first.read_text(), SOURCE)


if __name__ == "__main__":
    unittest.main()
