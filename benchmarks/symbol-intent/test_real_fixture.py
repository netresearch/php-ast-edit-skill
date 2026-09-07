"""Offline fixture-oracle checks and opt-in public-source PHPUnit checks."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import real_fixture as fixture


class OracleTests(unittest.TestCase):
    def test_missing_caller_and_unrelated_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = {
                "Provider.php": b"<?php function classify() {}\n",
                "Caller.php": b"<?php $classifier->classify();\n",
                "Unrelated.php": b"<?php function classify() { return 7; }\n",
            }
            renamed = {
                **original,
                "Provider.php": b"<?php function controlType() {}\n",
                "Caller.php": b"<?php $classifier->controlType();\n",
            }
            expected = {name: fixture.digest(data) for name, data in renamed.items()}
            for name, data in renamed.items():
                (root / name).write_bytes(data)
            with patch.object(fixture, "expected_inventory", return_value=expected):
                self.assertTrue(fixture.oracle(root)["ok"])
                (root / "Caller.php").write_bytes(original["Caller.php"])
                self.assertEqual(["Caller.php"], fixture.oracle(root)["mismatched"])
                (root / "Caller.php").write_bytes(renamed["Caller.php"])
                (root / "Unrelated.php").write_bytes(original["Unrelated.php"] + b"\n")
                self.assertEqual(["Unrelated.php"], fixture.oracle(root)["mismatched"])
                (root / "extra.txt").write_text("unexpected")
                self.assertEqual(["extra.txt"], fixture.oracle(root)["unexpected"])
                (root / "Provider.php").unlink()
                self.assertEqual(["Provider.php"], fixture.oracle(root)["missing"])

    def test_snapshot_rejects_symlinks_instead_of_following_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.php").write_text("<?php\n")
            (root / "link.php").symlink_to(root / "source.php")
            with self.assertRaises(fixture.FixtureError):
                fixture.snapshot(root)

    def test_provenance_contains_only_original_source_information(self):
        baseline = fixture.expected_inventory(renamed=False)
        renamed = fixture.expected_inventory()
        self.assertEqual(8, len(baseline))
        self.assertEqual(3, sum(baseline[name] != renamed[name] for name in baseline))
        self.assertEqual(baseline["PROVENANCE.json"], renamed["PROVENANCE.json"])
        self.assertNotIn("controlType", json.dumps(fixture.provenance()))

    def test_checker_rejects_an_unpinned_phar_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            phar = root / "untrusted.phar"
            phar.write_bytes(b"not the pinned PHPUnit release")
            with patch.object(fixture.subprocess, "run") as run:
                with self.assertRaisesRegex(fixture.FixtureError, "PHPUnit checksum"):
                    fixture.check(root, phar)
                run.assert_not_called()

    def test_command_exposes_behavior_check_without_oracle(self):
        command = fixture.command(
            Path("/work"), Path("/phpunit.phar"), receipt_dir=Path("/receipts")
        )
        self.assertIn("check", command)
        self.assertIn("--receipt-dir", command)
        self.assertNotIn("oracle", command)
        self.assertNotIn("--renamed", command)

    def test_frozen_configuration_is_allowed_only_at_its_independent_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".php-ast-edit.json"
            source = b'{"verification": {}}\n'
            path.write_bytes(source)
            extras = {path.name: fixture.digest(source)}
            with patch.object(fixture, "expected_inventory", return_value={}):
                self.assertTrue(fixture.oracle(root, allowed_extras=extras)["ok"])
                path.write_bytes(source + b"\n")
                self.assertEqual(
                    [path.name],
                    fixture.oracle(root, allowed_extras=extras)["mismatched"],
                )
            overlapping = {fixture.DECLARATION: fixture.digest(source)}
            with self.assertRaisesRegex(fixture.FixtureError, "overlapping"):
                fixture.oracle(root, allowed_extras=overlapping)

    def test_successful_tests_on_mutating_source_cannot_certify_final_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "fixture"
            root.mkdir()
            source = root / "source.php"
            source.write_bytes(b"<?php // original\n")
            phar = base / "test.phar"
            phar.write_bytes(b"unit test runner")

            def mutating_runner(argv, **kwargs):
                source.write_bytes(b"<?php // changed while tests ran\n")
                junit = Path(argv[argv.index("--log-junit") + 1])
                junit.write_text(
                    '<testsuites><testsuite tests="17" assertions="29" errors="0" failures="0" skipped="0"/></testsuites>'
                )
                return SimpleNamespace(returncode=0, stdout=b"tests passed", stderr=b"")

            with (
                patch.object(
                    fixture, "PHPUNIT_SHA256", fixture.digest(phar.read_bytes())
                ),
                patch.object(fixture.subprocess, "run", side_effect=mutating_runner),
            ):
                result = fixture.check(root, phar, receipt_dir=base / "receipts")
            self.assertEqual(0, result["returncode"])
            self.assertEqual(17, result["tests"])
            self.assertFalse(result["ok"])
            self.assertFalse(result["fixture_unchanged"])
            self.assertNotEqual(result["before"], result["after"])


SOURCE = os.environ.get("NR_LLM_SOURCE_REPO")
PHPUNIT = os.environ.get("PHP_AST_TEST_PHPUNIT")


@unittest.skipUnless(
    SOURCE and PHPUNIT, "set NR_LLM_SOURCE_REPO and PHP_AST_TEST_PHPUNIT"
)
class PublicFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "fixture"
        fixture.export(self.root, Path(SOURCE))

    def rename(self, omitted=None):
        # Disposable benchmark fixtures are the AGENTS.md PHP-edit exception.
        for name, (old, new) in fixture.REPLACEMENTS.items():
            if name != omitted:
                path = self.root / name
                data = path.read_bytes()
                self.assertEqual(1, data.count(old))
                path.write_bytes(data.replace(old, new, 1))

    def test_baseline_and_renamed_run_original_tests_with_distinct_receipts(self):
        receipts = self.base / "receipts"
        self.assertTrue(fixture.oracle(self.root, renamed=False)["ok"])
        before = fixture.check(self.root, Path(PHPUNIT), receipt_dir=receipts)
        self.assertTrue(before["ok"], before)
        self.assertEqual(17, before["tests"])
        self.rename()
        self.assertTrue(fixture.oracle(self.root)["ok"])
        after = fixture.check(self.root, Path(PHPUNIT), receipt_dir=receipts)
        self.assertTrue(after["ok"], after)
        self.assertEqual(before["assertions"], after["assertions"])
        self.assertNotEqual(before["receipt"], after["receipt"])
        receipt = json.loads(Path(after["receipt"]).read_text())
        self.assertEqual(fixture.snapshot(self.root), receipt["after"])
        self.assertEqual(receipt["before"], receipt["after"])
        self.assertNotEqual(
            json.loads(Path(before["receipt"]).read_text())["after"], receipt["after"]
        )
        self.assertEqual(2, len(list(receipts.glob("*.json"))))

    def test_omitted_production_caller_fails_behavior_and_inventory(self):
        caller = "Classes/Service/Tool/SchemaInputCoercer.php"
        self.rename(omitted=caller)
        checked = fixture.check(self.root, Path(PHPUNIT))
        self.assertFalse(checked["ok"])
        self.assertNotEqual(0, checked["returncode"])
        self.assertIn("classify", checked["stdout"] + checked["stderr"])
        self.assertEqual([caller], fixture.oracle(self.root)["mismatched"])
        command = subprocess.run(
            fixture.command(self.root, Path(PHPUNIT)),
            capture_output=True,
            text=True,
            check=False,
        )
        reported = json.loads(command.stdout)
        self.assertEqual(1, command.returncode)
        self.assertIn("classify", reported["diagnostics"])
        self.assertLessEqual(len(reported["diagnostics"]), 4000)
        self.assertNotIn("before", reported)
        self.assertNotIn("mismatched", reported)

    def test_assertion_tamper_passes_behavior_but_fails_hidden_oracle(self):
        self.rename()
        test = "Tests/Unit/Service/Tool/SchemaInputCoercerTest.php"
        path = self.root / test
        source = path.read_bytes()
        assertion = b"self::assertSame(['must' => false], $result);"
        self.assertEqual(1, source.count(assertion))
        path.write_bytes(source.replace(assertion, b"self::assertTrue(true);", 1))
        checked = fixture.check(self.root, Path(PHPUNIT))
        self.assertTrue(checked["ok"], checked)
        self.assertEqual([test], fixture.oracle(self.root)["mismatched"])

    def test_export_refuses_populated_destination(self):
        with self.assertRaises(fixture.FixtureError):
            fixture.export(self.root, Path(SOURCE))


if __name__ == "__main__":
    unittest.main()
