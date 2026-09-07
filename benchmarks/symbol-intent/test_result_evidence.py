"""Evidence proves byte preservation, not resolver coverage or runtime behavior."""

import argparse
import json
import tempfile
import unittest
from pathlib import Path

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

    def planned(self, include_caller=True, new_name="loadLonger"):
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
            start = (
                anchor["start"] if current == path else source.index(b"->fetch()") + 2
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

    def test_default_output_keeps_existing_shape(self):
        args = self.planned()
        args.evidence = False
        result, _ = intent.apply_plan(args, self.state)
        self.assertIn("file_issues", result)
        self.assertNotIn("exact_edit_match", result)


if __name__ == "__main__":
    unittest.main()
