"""Offline and optional pinned-Phpactor integration checks; no model calls."""

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lsp
import symbol_intent as intent
from lsp import IntentError


def fixture(root, count):
    root.mkdir()
    provider = "<?php\nnamespace Example;\nclass Provider { public function fetch(): int { return 11; } }\nclass Other { public function fetch(): int { return 22; } }\n"
    (root / "Provider.php").write_text(provider)
    expected = {"Provider.php": provider.replace("function fetch", "function load", 1)}
    for i in range(count - 1):
        name = f"Caller{i}.php"
        first, second = ("first", "second") if i % 2 == 0 else ("second", "first")
        source = f"<?php\nnamespace Example;\n// 😀 Keep fetch in unrelated text.\nfunction run{i}(Provider ${first}, Other ${second}): array {{ return [${first}->fetch(), ${second}->fetch()]; }}\n"
        (root / name).write_text(source)
        expected[name] = source.replace(f"${first}->fetch()", f"${first}->load()")
    return expected


class PureTests(unittest.TestCase):
    def test_resolver_trace_survives_teardown_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            expected = {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 1},
            }
            client = MagicMock()
            client.started = 0
            client.events = [{"direction": "in", "message": {"jsonrpc": "2.0"}}]
            client.messages = []
            client.completed_indexes = []
            client.request.side_effect = [expected, {"documentChanges": []}, None]
            client.initialize.return_value = {}
            client.close.side_effect = OSError("teardown failed")
            with (
                patch.object(lsp, "Client", return_value=client),
                self.assertRaisesRegex(OSError, "teardown"),
            ):
                lsp.rename(
                    state / "tool.phar",
                    state,
                    state,
                    state / "source.php",
                    expected["start"],
                    expected,
                    "load",
                    1,
                )
            self.assertEqual(
                client.events, json.loads((state / "lsp.json").read_text())
            )
            client.close.assert_called_once()

    def test_self_consistent_but_incomplete_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            for record in ([], {"schema": 1}, {"schema": True}):
                raw = intent.encode(record)
                identifier = intent.digest(raw)
                (state / (identifier + ".json")).write_bytes(raw)
                with self.assertRaises(IntentError):
                    intent.load_plan(argparse.Namespace(plan=identifier), state)

    def test_unicode_position_conversion_and_split_rejection(self):
        source = "<?php /* 😀 */ fetch();\r\nnext".encode()
        offset = source.index(b"fetch")
        self.assertEqual(
            offset,
            intent.position_to_byte(source, intent.byte_to_position(source, offset)),
        )
        start = source.index("😀".encode())
        position = intent.byte_to_position(source, start)
        position["character"] += 1
        with self.assertRaises(IntentError):
            intent.position_to_byte(source, position)
        with self.assertRaises(IntentError):
            intent.position_to_byte(source, {"line": False, "character": 0})

    def test_snapshot_detects_added_changed_deleted_and_symlink_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            fixture(root, 2)
            original = intent.snapshot(root)
            extra = root / "extra.txt"
            extra.write_text("configuration")
            self.assertNotEqual(original, intent.snapshot(root))
            extra.unlink()
            path = root / "Provider.php"
            source = path.read_bytes()
            path.write_bytes(source + b"\n")
            self.assertNotEqual(original, intent.snapshot(root))
            path.write_bytes(source)
            self.assertEqual(original, intent.snapshot(root))
            (root / "borrowed.php").symlink_to(path)
            with self.assertRaises(IntentError):
                intent.snapshot(root)

    def test_ast_anchor_refuses_collision_magic_and_non_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            fixture(root, 2)
            path = root / "Provider.php"
            request = {
                "mode": "anchor",
                "file": {"path": str(path), "sha256": intent.digest(path.read_bytes())},
                "select": "method:Provider::fetch",
                "to": "load",
            }
            result = intent.ast(request, root)
            self.assertEqual("fetch", result["name"])
            for change in (
                {"to": "fetch"},
                {"to": "__get"},
                {"select": "class:Provider"},
            ):
                with self.assertRaises(IntentError):
                    intent.ast({**request, **change}, root)

    def test_lsp_translation_rejects_resource_operations_wrong_ranges_and_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            fixture(root, 2)
            path = root / "Provider.php"
            source = path.read_bytes()
            inventory = intent.snapshot(root)
            anchor = intent.ast(
                {
                    "mode": "anchor",
                    "file": {"path": str(path), "sha256": inventory["Provider.php"]},
                    "select": "method:Provider::fetch",
                    "to": "load",
                },
                root,
            )
            edit = {
                "range": {
                    key: intent.byte_to_position(source, anchor[key])
                    for key in ("start", "end")
                },
                "newText": "load",
            }
            valid = {
                "documentChanges": [
                    {
                        "textDocument": {"uri": path.as_uri(), "version": 0},
                        "edits": [edit],
                    }
                ]
            }
            translated, expected = intent.translate(
                valid, root, inventory, path, anchor, "load"
            )
            self.assertEqual(inventory["Caller0.php"], expected["Caller0.php"])
            self.assertEqual(
                "set_name", translated["files"][0]["edits"][0]["operation"]
            )
            wrong_text = copy.deepcopy(valid)
            wrong_text["documentChanges"][0]["edits"][0]["newText"] = "load(); exit();"
            wrong_range = copy.deepcopy(valid)
            wrong_range["documentChanges"][0]["edits"][0]["range"]["end"][
                "character"
            ] += 1
            duplicate = copy.deepcopy(valid)
            duplicate["documentChanges"][0]["edits"].append(edit)
            for invalid in (
                {},
                {"documentChanges": []},
                {"documentChanges": [{"kind": "rename"}]},
                wrong_text,
                wrong_range,
                duplicate,
            ):
                with self.subTest(invalid=invalid), self.assertRaises(IntentError):
                    intent.translate(invalid, root, inventory, path, anchor, "load")


@unittest.skipUnless(
    os.environ.get("PHP_AST_TEST_PHPACTOR"),
    "Set PHP_AST_TEST_PHPACTOR to the pinned PHAR for real LSP tests",
)
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="php-intent-tests-")
        self.base = Path(self.temporary.name)
        self.state = self.base / "state"
        self.state.mkdir()
        self.root = self.base / "work"

    def tearDown(self):
        self.temporary.cleanup()

    def plan(self):
        args = argparse.Namespace(
            root=self.root,
            phpactor=Path(os.environ["PHP_AST_TEST_PHPACTOR"]),
            file="Provider.php",
            select="method:Provider::fetch",
            to="load",
        )
        return intent.plan(args, self.state)[0]

    def apply(self, identifier):
        return intent.apply_plan(argparse.Namespace(plan=identifier), self.state)

    def test_two_ten_fifty_files_preserve_unrelated_methods(self):
        for count in (2, 10, 50):
            with self.subTest(count=count):
                self.root = self.base / f"work{count}"
                expected = fixture(self.root, count)
                before = intent.snapshot(self.root)
                planned = self.plan()
                self.assertEqual(before, intent.snapshot(self.root))
                self.assertEqual(count, planned["files"])
                self.assertEqual(count, planned["edits"])
                self.assertEqual("unknown", planned["completeness"])
                applied, status = self.apply(planned["plan"])
                self.assertEqual(0, status)
                self.assertTrue(applied["ok"])
                for name, source in expected.items():
                    self.assertEqual(source, (self.root / name).read_text())
                runtime = "foreach (glob($argv[1] . '/*.php') as $p) { require $p; } for ($i=0; $i<(int)$argv[2]-1; $i++) { $f='Example\\\\run'.$i; if ($f(new Example\\Provider(), new Example\\Other()) !== [11,22]) {exit(1);} } echo 'ORACLE_OK';"
                run = subprocess.run(
                    ["php", "-r", runtime, str(self.root), str(count)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, run.returncode, run.stderr)
                self.assertEqual("ORACLE_OK", run.stdout)
                with self.assertRaises(IntentError):
                    self.apply(planned["plan"])

    def test_stale_inventory_and_tampered_plan_are_refused(self):
        fixture(self.root, 2)
        planned = self.plan()
        extra = self.root / "NewCaller.php"
        extra.write_text("<?php // added after planning\n")
        with self.assertRaisesRegex(IntentError, "STALE_PLAN"):
            self.apply(planned["plan"])
        extra.unlink()
        record = self.state / (planned["plan"] + ".json")
        record.write_bytes(record.read_bytes() + b" ")
        with self.assertRaisesRegex(IntentError, "hash differs"):
            self.apply(planned["plan"])

    def test_cli_single_intent_keeps_failed_checks_and_consumes_plan(self):
        expected = fixture(self.root, 2)
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(
                {
                    "verify": [
                        {
                            "scope": "project",
                            "command": [
                                "php",
                                "-r",
                                "fwrite(STDERR, 'behavior check failed'); exit(1);",
                            ],
                        }
                    ],
                }
            )
        )
        process = subprocess.run(
            [
                sys.executable,
                str(HERE / "symbol_intent.py"),
                "rename_method",
                "--root",
                str(self.root),
                "--state",
                str(self.state),
                "--phpactor",
                os.environ["PHP_AST_TEST_PHPACTOR"],
                "--file",
                "Provider.php",
                "--select",
                "method:Provider::fetch",
                "--to",
                "load",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(process.stdout)
        self.assertEqual(1, process.returncode, report)
        self.assertFalse(report["ok"])
        self.assertFalse(report["checksPassed"])
        self.assertEqual({"failed": 2}, report["validation"]["checks"])
        self.assertEqual(2, len(report["file_issues"]))
        self.assertEqual("behavior check failed", report["verify"][0]["output"])
        self.assertTrue(Path(report["full_report"]).is_file())
        for name, source in expected.items():
            self.assertEqual(source, (self.root / name).read_text())
        with self.assertRaisesRegex(IntentError, "consumed"):
            self.apply(report["plan"])


if __name__ == "__main__":
    unittest.main()
