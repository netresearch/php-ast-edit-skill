"""Evidence proves byte preservation, not resolver coverage or runtime behavior."""

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import symbol_intent as intent
from test_symbol_intent import fixture


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "work"
        self.state = self.base / "state"
        self.state.mkdir()
        fixture(self.root, 2)

    def tearDown(self):
        self.temporary.cleanup()

    def planned(self, include_caller=True, new_name="loadLonger", caller_starts=None):
        inventory = intent.snapshot(self.root)
        path = self.root / "Provider.php"
        anchor = intent.ast(
            {
                "mode": "anchor",
                "file": {"path": str(path), "sha256": inventory[path.name]},
                "select": "method:Provider::fetch",
                "to": new_name,
            },
            self.root,
        )
        changes = []
        names = ["Provider.php", "Caller0.php"] if include_caller else ["Provider.php"]
        for name in names:
            current = self.root / name
            source = current.read_bytes()
            starts = (
                [anchor["start"]]
                if current == path
                else caller_starts or [source.index(b"->fetch()") + 2]
            )
            changes.append(
                {
                    "textDocument": {"uri": current.as_uri(), "version": None},
                    "edits": [
                        {
                            "range": {
                                "start": intent.byte_to_position(source, start),
                                "end": intent.byte_to_position(source, start + 5),
                            },
                            "newText": new_name,
                        }
                        for start in starts
                    ],
                }
            )
        document, expected = intent.translate(
            {"documentChanges": changes},
            self.root,
            inventory,
            path,
            anchor,
            new_name,
        )
        record = {
            "schema": 1,
            "root": str(self.root),
            "inventory": inventory,
            "runtime": intent.runtime_identity(),
            "resolver": {},
            "request": {
                "file": path.name,
                "select": "method:Provider::fetch",
                "to": new_name,
            },
            "document": document,
            "expected_inventory": expected,
            "resolver_result": {},
            "elapsed_ms": 0,
        }
        identifier = intent.digest(intent.encode(record))
        (self.state / (identifier + ".json")).write_bytes(intent.encode(record))
        return argparse.Namespace(plan=identifier, evidence=True)

    def test_exact_result_groups_warnings_and_preserves_unicode_and_unrelated_names(
        self,
    ):
        result, status = intent.apply_plan(self.planned(), self.state)
        self.assertEqual(0, status)
        self.assertEqual("passed", result["exact_edit_match"]["status"])
        self.assertEqual(2, result["exact_edit_match"]["checked_files"])
        self.assertEqual(2, result["planned_edits"])
        self.assertEqual(2, result["edits_applied"])
        self.assertEqual("unknown", result["completeness"])
        self.assertEqual({"not_run": 2}, result["validation"]["checks"])
        self.assertIsNone(result["checksPassed"])
        self.assertEqual("loadLonger", result["request"]["to"])
        self.assertNotIn("file_issues", result)
        self.assertEqual(1, len(result["issue_groups"]))
        lint = result["issue_groups"][0]["validation"]["lint"]
        self.assertIn("php_version", lint)
        self.assertNotIn("runtime", lint)
        self.assertCountEqual(
            ["Provider.php", "Caller0.php"], result["issue_groups"][0]["paths"]
        )
        self.assertIn("NOT_CANONICAL", result["issue_groups"][0]["warnings"][0])
        readback = Path(result["full_report"]).with_suffix(".readback.json")
        self.assertEqual(
            intent.snapshot(self.root),
            json.loads(readback.read_text())["observed_inventory"],
        )
        source = (self.root / "Caller0.php").read_text()
        self.assertIn("😀 Keep fetch in unrelated text.", source)
        self.assertIn("$second->fetch()", source)

    def test_exact_match_cannot_certify_an_omitted_reference(self):
        result, status = intent.apply_plan(
            self.planned(include_caller=False), self.state
        )
        self.assertEqual(0, status)
        self.assertEqual("passed", result["exact_edit_match"]["status"])
        self.assertEqual("unknown", result["completeness"])
        self.assertIn("$first->fetch()", (self.root / "Caller0.php").read_text())

    def test_multiple_longer_replacements_use_original_offsets_in_reverse_lsp_order(
        self,
    ):
        caller = self.root / "Caller0.php"
        source = (
            "<?php\nnamespace Example;\n"
            "function run0(Provider $first, Other $second): array {\n"
            "    // 😀 Keep fetch in unrelated text.\n"
            "    return [$first->fetch(), $second->fetch(), /* 😀 */ $first->fetch()];\n"
            "}\n"
        ).encode()
        caller.write_bytes(source)
        first = source.index(b"$first->fetch()") + len(b"$first->")
        last = source.rindex(b"$first->fetch()") + len(b"$first->")
        result, status = intent.apply_plan(
            self.planned(caller_starts=[last, first]), self.state
        )
        self.assertEqual(0, status)
        self.assertEqual("passed", result["exact_edit_match"]["status"])
        self.assertEqual(3, result["planned_edits"])
        self.assertEqual(3, result["edits_applied"])
        self.assertEqual(
            source.replace(b"$first->fetch()", b"$first->loadLonger()"),
            caller.read_bytes(),
        )

    def test_readback_detects_added_deleted_and_changed_non_php_files(self):
        (self.root / "removed.txt").write_bytes(b"remove me")
        (self.root / "changed.bin").write_bytes(b"\x00\xff original")
        (self.root / "unchanged.txt").write_bytes(b"keep me")
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
                                    "file_put_contents('added.txt', 'new'); "
                                    "unlink('removed.txt'); "
                                    "file_put_contents('changed.bin', 'changed');"
                                ),
                            ],
                        }
                    ]
                }
            )
        )
        result, status = intent.apply_plan(self.planned(), self.state)
        self.assertEqual(0, status)
        self.assertTrue(result["checksPassed"])
        self.assertEqual("not_established", result["exact_edit_match"]["status"])
        self.assertEqual(
            ["added.txt", "changed.bin", "removed.txt"],
            result["exact_edit_match"]["mismatched_files"],
        )
        self.assertEqual(b"keep me", (self.root / "unchanged.txt").read_bytes())

    def test_unsupported_final_inventory_preserves_engine_result(self):
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "verify": [
                        {
                            "scope": "project",
                            "command": [
                                "php",
                                "-r",
                                "symlink('Provider.php', 'copy.php');",
                            ],
                        }
                    ]
                }
            )
        )
        result, status = intent.apply_plan(self.planned(), self.state)
        self.assertEqual(0, status)
        self.assertTrue(result["ok"])
        self.assertTrue(result["checksPassed"])
        self.assertEqual("not_established", result["exact_edit_match"]["status"])
        self.assertIn("Symlinks are unsupported", result["exact_edit_match"]["reason"])
        readback = Path(result["full_report"]).with_suffix(".readback.json")
        self.assertIsNone(json.loads(readback.read_text())["observed_inventory"])

    def test_issue_groups_keep_different_warnings_and_skipped_lint_separate(self):
        passed = {"parser": "passed", "lint": {"status": "passed"}, "checks": "not_run"}
        skipped = {
            **passed,
            "lint": {"status": "skipped", "reason": "target_newer_than_runtime"},
        }
        result = {
            "file_issues": [
                {"path": path, "validation": validation, "warnings": warnings}
                for path, validation, warnings in (
                    ("First.php", passed, ["NOT_CANONICAL"]),
                    ("Second.php", passed, ["NOT_CANONICAL"]),
                    ("Third.php", passed, ["FORMATTER_FALLBACK"]),
                    ("Fourth.php", skipped, ["NOT_CANONICAL"]),
                )
            ]
        }
        record = {"request": {}, "document": {"files": []}}
        intent.add_result_evidence(
            result, record, self.root, self.state / "report.json"
        )
        self.assertEqual(3, len(result["issue_groups"]))
        groups = {tuple(group["paths"]): group for group in result["issue_groups"]}
        self.assertEqual(passed, groups[("First.php", "Second.php")]["validation"])
        self.assertEqual(["FORMATTER_FALLBACK"], groups[("Third.php",)]["warnings"])
        self.assertEqual(skipped, groups[("Fourth.php",)]["validation"])

    def test_readback_detects_changes_after_engine_validation(self):
        # Disposable fixture commands deliberately mutate code after engine lint.
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "verify": [
                        {
                            "scope": "project",
                            "command": [
                                "php",
                                "-r",
                                "file_put_contents('Provider.php', '// changed', FILE_APPEND);",
                            ],
                        }
                    ]
                }
            )
        )
        result, status = intent.apply_plan(self.planned(), self.state)
        self.assertEqual(0, status)
        self.assertTrue(result["checksPassed"])
        self.assertEqual("not_established", result["exact_edit_match"]["status"])
        self.assertEqual(
            ["Provider.php"], result["exact_edit_match"]["mismatched_files"]
        )

    def test_failed_verification_is_preserved_even_when_exact_bytes_match(self):
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {"verify": [{"scope": "project", "command": ["php", "-r", "exit(1);"]}]}
            )
        )
        result, status = intent.apply_plan(self.planned(), self.state)
        self.assertEqual(1, status)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checksPassed"])
        self.assertEqual("passed", result["exact_edit_match"]["status"])
        self.assertEqual("failed", result["issue_groups"][0]["validation"]["checks"])

    def test_readback_storage_failure_preserves_retained_edits_and_failed_checks(self):
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {"verify": [{"scope": "project", "command": ["php", "-r", "exit(1);"]}]}
            )
        )
        args = self.planned()
        original_open = Path.open

        def fail_readback(path, *args, **kwargs):
            if path.name.endswith(".readback.json"):
                raise OSError("simulated full storage")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", fail_readback):
            result, status = intent.apply_plan(args, self.state)
        self.assertEqual(1, status)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checksPassed"])
        self.assertEqual("passed", result["exact_edit_match"]["status"])
        self.assertEqual("failed", result["issue_groups"][0]["validation"]["checks"])
        self.assertTrue(
            any("READBACK_NOT_SAVED" in item for item in result["warnings"])
        )
        self.assertTrue(Path(result["full_report"]).is_file())
        self.assertIn("function loadLonger", (self.root / "Provider.php").read_text())

    def test_default_output_keeps_existing_shape(self):
        args = self.planned()
        args.evidence = False
        result, _ = intent.apply_plan(args, self.state)
        self.assertIn("file_issues", result)
        self.assertIn("runtime", result["file_issues"][0]["validation"]["lint"])
        self.assertNotIn("exact_edit_match", result)


if __name__ == "__main__":
    unittest.main()
