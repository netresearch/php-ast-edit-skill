"""Tests for the lossless shared-file report presentation."""

from __future__ import annotations

import json
import unittest

import shared_report


def _raw(document: object, *, indent: int = 4) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=indent) + "\n").encode()


def _file(path: str, **values: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "path": path,
        "mode": "modify",
        "beforeSha256": "before-" + path,
        "afterSha256": "after-" + path,
        "diff": "@@ -1 +1 @@",
        "code": "<?php echo 'changed';",
        "changed": True,
        "dryRun": False,
        "printer": "php-cs-fixer",
        "warnings": [],
        "warning": None,
        "parsed": True,
        "valid": True,
        "validation": {"ok": True, "checks": ["syntax"]},
        "checkIds": ["syntax"],
        "alias": "retained-unknown",
    }
    entry.update(values)
    return entry


class SharedReportTests(unittest.TestCase):
    def test_short_or_unsupported_reports_are_byte_identical(self) -> None:
        for raw in (
            b'{"files":[{"path":"one.php"}]}\n',
            b'{"files":[]} \n',
            b'{"message":"unsupported command"}\n',
            b'{"files":"not-an-array"}\n',
        ):
            self.assertEqual(shared_report.factor(raw), raw)

    def test_common_typed_metadata_factors_and_restores_all_facts(self) -> None:
        files = [
            _file("one.php", effects={"kind": "one"}),
            _file("two.php", effects={"kind": "two"}),
            _file("three.php", effects={"kind": "three"}),
        ]
        files[1]["dryRun"] = 0
        original = {"command": "rename", "files": files, "unknown": {"ü": "保持"}}
        raw = _raw(original)

        projected = shared_report.factor(raw)
        document = json.loads(projected)
        self.assertEqual(
            set(document[shared_report.FILE_DEFAULTS]),
            set(shared_report.FACTORED_KEYS) - {"dryRun"},
        )
        self.assertNotIn("changed", document["files"][0])
        self.assertEqual(document["files"][0]["alias"], "retained-unknown")
        self.assertEqual(shared_report.restore(document), original)
        self.assertIn('\n    "fileDefaults": {', projected.decode())

    def test_different_and_missing_file_facts_stay_per_file(self) -> None:
        first = _file("one.php", dryRun=True, warnings=["lint skipped"])
        second = _file("two.php", warnings=["lint skipped", "missing check"])
        del second["checkIds"]
        projected = json.loads(shared_report.factor(_raw({"files": [first, second]})))

        self.assertNotIn("dryRun", projected.get(shared_report.FILE_DEFAULTS, {}))
        self.assertNotIn("warnings", projected.get(shared_report.FILE_DEFAULTS, {}))
        self.assertNotIn("checkIds", projected.get(shared_report.FILE_DEFAULTS, {}))
        self.assertIs(projected["files"][0]["dryRun"], True)
        self.assertEqual(
            projected["files"][1]["warnings"], ["lint skipped", "missing check"]
        )

    def test_reserved_names_and_restore_overrides_are_rejected(self) -> None:
        reserved_raw = _raw({"fileDefaults": {}, "files": [{}, {}]})
        with self.assertRaises(ValueError):
            shared_report.factor(reserved_raw)
        with self.assertRaises(ValueError):
            shared_report.factor(b'{"files":[{"path":"a"},{"path":"b"}],"files":[]}')
        with self.assertRaises(ValueError):
            shared_report.restore(
                {
                    "files": [{"path": "a", "changed": False}],
                    "fileDefaults": {"changed": True},
                    "fileDefaultsMeaning": shared_report.FILE_DEFAULTS_TEXT,
                }
            )
        with self.assertRaises(ValueError):
            shared_report.restore(
                {
                    "files": [{"path": "a"}, {"path": "b"}],
                    "fileDefaults": {"unknown": 1},
                    "fileDefaultsMeaning": shared_report.FILE_DEFAULTS_TEXT,
                }
            )

    def test_duplicate_keys_and_nonfinite_numbers_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            shared_report.factor(b'{"files":[],"files":[]}')
        with self.assertRaises(ValueError):
            shared_report.factor(b'{"files":[{"path":"a"},{"path":"b","valid":NaN}]}')
        with self.assertRaises(ValueError):
            shared_report.factor(b'{"files":[{"path":"a"},{"path":"b","n":1e400}]}')
        with self.assertRaises(ValueError):
            shared_report.factor(
                b'{"files":[{"path":"a"},{"path":"b","n":9007199254740993.0}]}'
            )

    def test_presentation_validation_requires_the_declared_arm(self) -> None:
        original = _raw({"files": [_file("one.php"), _file("two.php")]})
        presented = shared_report.factor(original)
        factored_entry = {
            "shared_report_mode": "shared_report_factored",
            "shared_report_eligible": True,
            "stdout": original.decode(),
            "presented_stdout": presented.decode(),
            "exit_code": 0,
        }
        self.assertTrue(
            shared_report.presentation_valid(factored_entry, "shared_report_factored")
        )
        self.assertFalse(
            shared_report.presentation_valid(factored_entry, "shared_report_control")
        )
        control_entry = {
            **factored_entry,
            "shared_report_mode": "shared_report_control",
            "presented_stdout": original.decode(),
        }
        self.assertTrue(
            shared_report.presentation_valid(control_entry, "shared_report_control")
        )
        control_entry["presented_stdout"] = presented.decode()
        self.assertFalse(
            shared_report.presentation_valid(control_entry, "shared_report_control")
        )
        control_entry["exit_code"] = 1
        self.assertFalse(
            shared_report.presentation_valid(control_entry, "shared_report_control")
        )

    def test_restore_requires_both_envelope_fields(self) -> None:
        with self.assertRaises(ValueError):
            shared_report.restore(
                {
                    "files": [{"path": "a"}, {"path": "b"}],
                    "fileDefaults": None,
                    "fileDefaultsMeaning": None,
                }
            )

    def test_ineligible_non_json_results_remain_byte_identical(self) -> None:
        entry = {
            "shared_report_mode": "shared_report_factored",
            "shared_report_eligible": False,
            "stdout": "usage: php-ast-edit rename",
            "presented_stdout": "usage: php-ast-edit rename",
            "exit_code": 2,
        }
        self.assertTrue(
            shared_report.presentation_valid(entry, "shared_report_factored")
        )

    def test_no_common_metadata_keeps_unicode_input_bytes(self) -> None:
        original = {
            "files": [
                {"path": "one.php", "note": "Grüße"},
                {"path": "two.php", "note": "另一个"},
            ]
        }
        raw = _raw(original, indent=2)
        self.assertEqual(shared_report.factor(raw), raw)


if __name__ == "__main__":
    unittest.main()
