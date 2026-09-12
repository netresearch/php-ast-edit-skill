"""Offline contract tests for the opt-in unchanged-file excerpt experiment."""

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import review_context as context

ROOT = Path("/synthetic/project")


def snapshot():
    sources = {
        "changed.txt": b"old target\n",
        "kept.txt": b"literal target\nsecond\n",
        "unlisted.txt": b"captured but not a write target\n",
    }
    return context.WorkspaceSnapshot(
        ROOT,
        {
            name: context.SnapshotFile(data, hashlib.sha256(data).hexdigest())
            for name, data in sources.items()
        },
    )


def report():
    return {
        "ok": True,
        "files": [
            {"path": str(ROOT / "changed.txt"), "changed": True},
            {"path": "kept.txt", "changed": False},
        ],
        "renames": [
            {
                "literals": [
                    {"file": "changed.txt", "lines": [1]},
                    {"file": "kept.txt", "lines": [1]},
                ],
                "notRenamed": ["kept.txt:1", "unlisted.txt:1", "missing.txt:1"],
            }
        ],
    }


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def audit(raw, presented, mode="unchanged_excerpts", exit_code=0):
    return {
        "stdout": raw.decode(),
        "presented_stdout": presented.decode(),
        "context_mode": mode,
        "exit_code": exit_code,
    }


class UnchangedContextTests(unittest.TestCase):
    def test_changed_files_are_excluded_and_unknown_files_remain_candidates(self):
        original = report()
        raw = encoded(original)
        presented = context.augment(raw, snapshot(), unchanged_only=True)
        parsed = json.loads(presented)
        excerpts = parsed.pop("reviewContext")
        self.assertEqual(parsed, original)
        self.assertEqual(excerpts["scope"], "unchanged-files")
        self.assertEqual(excerpts["excludedChanged"], 1)
        self.assertEqual(excerpts["omitted"], 1)
        self.assertEqual(
            [entry["file"] for entry in excerpts["entries"]],
            ["kept.txt", "unlisted.txt"],
        )
        self.assertTrue(
            context.presentation_valid(
                audit(raw, presented), "unchanged_excerpts", root=ROOT
            )
        )

    def test_absolute_relative_and_dot_aliases_share_one_warning_location(self):
        original = report()
        original["renames"] = [
            {
                "notRenamed": [
                    "./changed.txt:1",
                    str(ROOT / "changed.txt") + ":1",
                    "./kept.txt:1",
                    str(ROOT / "kept.txt") + ":1",
                    "kept.txt:1",
                ]
            }
        ]
        raw = encoded(original)
        presented = context.augment(raw, snapshot(), unchanged_only=True)
        excerpts = json.loads(presented)["reviewContext"]
        self.assertEqual(excerpts["excludedChanged"], 1)
        self.assertEqual(excerpts["omitted"], 0)
        self.assertEqual([entry["file"] for entry in excerpts["entries"]], ["kept.txt"])
        self.assertTrue(
            context.presentation_valid(
                audit(raw, presented), "unchanged_excerpts", root=ROOT
            )
        )

    def test_all_changed_locations_have_an_explicit_empty_context(self):
        original = report()
        original["renames"] = [{"notRenamed": ["changed.txt:1", "changed.txt:1"]}]
        raw = encoded(original)
        presented = context.augment(raw, snapshot(), unchanged_only=True)
        excerpts = json.loads(presented)["reviewContext"]
        self.assertEqual(excerpts["entries"], [])
        self.assertEqual(excerpts["omitted"], 0)
        self.assertEqual(excerpts["excludedChanged"], 1)
        self.assertTrue(
            context.presentation_valid(
                audit(raw, presented), "unchanged_excerpts", root=ROOT
            )
        )

    def test_missing_or_malformed_files_fail_closed_when_warnings_exist(self):
        for files in (
            None,
            {},
            [None],
            [{}],
            [{"path": "kept.txt"}],
            [{"path": "kept.txt", "changed": 1}],
            [{"path": "kept.txt", "changed": "false"}],
            [{"path": 7, "changed": False}],
        ):
            original = {**report(), "files": files}
            raw = encoded(original)
            captured = snapshot()
            with self.subTest(files=files):
                with self.assertRaises(ValueError):
                    context.augment(raw, captured, unchanged_only=True)
                for mode in ("unchanged_locations", "unchanged_excerpts"):
                    self.assertFalse(
                        context.presentation_valid(
                            audit(raw, raw, mode), mode, root=ROOT
                        )
                    )

    def test_duplicate_canonical_file_entries_are_rejected(self):
        original = report()
        original["files"].append({"path": "./changed.txt", "changed": True})
        raw, captured = encoded(original), snapshot()
        with self.assertRaises(ValueError):
            context.augment(raw, captured, unchanged_only=True)

    def test_dry_run_changes_remain_eligible_and_flag_requires_a_boolean(self):
        original = report()
        original["files"][0]["dryRun"] = True
        raw = encoded(original)
        presented = context.augment(raw, snapshot(), unchanged_only=True)
        excerpts = json.loads(presented)["reviewContext"]
        self.assertEqual(excerpts["excludedChanged"], 0)
        self.assertEqual(excerpts["entries"][0]["file"], "changed.txt")
        self.assertTrue(
            context.presentation_valid(
                audit(raw, presented), "unchanged_excerpts", root=ROOT
            )
        )
        for invalid in (None, 0, 1, "false"):
            original["files"][0]["dryRun"] = invalid
            raw, captured = encoded(original), snapshot()
            with self.subTest(dry_run=invalid), self.assertRaises(ValueError):
                context.augment(raw, captured, unchanged_only=True)

    def test_unsafe_report_and_warning_paths_are_rejected_without_reading_files(self):
        for name in (
            "../outside.txt",
            str(ROOT.parent / "other/file.txt"),
            "kept/../kept.txt",
            "",
            ".",
            "bad\0name",
        ):
            for use_warning in (False, True):
                original = report()
                if use_warning:
                    original["renames"] = [{"literals": [{"file": name, "lines": [1]}]}]
                else:
                    original["files"] = [{"path": name, "changed": False}]
                raw = encoded(original)
                captured = snapshot()
                with self.subTest(name=name, warning=use_warning):
                    with self.assertRaises(ValueError):
                        context.augment(raw, captured, unchanged_only=True)
                    self.assertFalse(
                        context.presentation_valid(
                            audit(raw, raw), "unchanged_excerpts", root=ROOT
                        )
                    )

    def test_nonexistent_root_needs_no_filesystem_operations(self):
        raw = encoded(report())
        with (
            patch.object(Path, "resolve", side_effect=AssertionError("no resolve")),
            patch.object(Path, "read_bytes", side_effect=AssertionError("no read")),
            patch.object(Path, "stat", side_effect=AssertionError("no stat")),
        ):
            presented = context.augment(raw, snapshot(), unchanged_only=True)
            self.assertTrue(
                context.presentation_valid(
                    audit(raw, presented), "unchanged_excerpts", root=ROOT
                )
            )
        self.assertFalse(
            context.presentation_valid(audit(raw, presented), "unchanged_excerpts")
        )

    def test_control_is_identical_but_still_validates_required_classification(self):
        raw = encoded(report())
        presented = context.augment(raw, snapshot(), unchanged_only=True)
        self.assertTrue(
            context.presentation_valid(
                audit(raw, raw, "unchanged_locations"), "unchanged_locations", root=ROOT
            )
        )
        self.assertFalse(
            context.presentation_valid(
                audit(raw, presented, "unchanged_locations"),
                "unchanged_locations",
                root=ROOT,
            )
        )

    def test_nonrename_no_warning_and_error_outputs_keep_legacy_noop_behavior(self):
        for raw, code in (
            (b'{"contexts":[]}', 0),
            (b'{"renames":[]}', 0),
            (b'{"files":null,"renames":[{}]}', 0),
            (b'{"renames":[{"notRenamed":["kept.txt:1"]}]}', 1),
            (b"engine error", 1),
        ):
            with self.subTest(raw=raw, code=code):
                if code == 0:
                    self.assertEqual(
                        context.augment(raw, snapshot(), unchanged_only=True), raw
                    )
                for mode in ("unchanged_locations", "unchanged_excerpts"):
                    self.assertTrue(
                        context.presentation_valid(
                            audit(raw, raw, mode, code), mode, root=ROOT
                        )
                    )

    def test_omission_and_whole_context_caps_include_new_metadata(self):
        original = report()
        original["renames"] = [
            {
                "notRenamed": [f"kept.txt:{line}" for line in range(1, 30)]
                + ["changed.txt:1"]
            }
        ]
        snap = snapshot()
        data = ("é" * 120 + "\n").encode() * 29
        snap.files["kept.txt"] = context.SnapshotFile(
            data, hashlib.sha256(data).hexdigest()
        )
        raw = encoded(original)
        presented = context.augment(raw, snap, unchanged_only=True)
        excerpts = json.loads(presented)["reviewContext"]
        self.assertEqual(excerpts["excludedChanged"], 1)
        self.assertEqual(len(excerpts["entries"]) + excerpts["omitted"], 29)
        self.assertLessEqual(len(excerpts["entries"]), 20)
        self.assertLessEqual(
            len(
                json.dumps(excerpts, ensure_ascii=True, separators=(",", ":")).encode()
            ),
            8192,
        )
        self.assertGreater(excerpts["omitted"], 0)
        self.assertTrue(
            context.presentation_valid(
                audit(raw, presented), "unchanged_excerpts", root=ROOT
            )
        )

    def test_validator_rejects_false_scope_count_and_changed_file_context(self):
        raw = encoded(report())
        presented = context.augment(raw, snapshot(), unchanged_only=True)
        valid = json.loads(presented)["reviewContext"]
        changed_entry = {**valid["entries"][0], "file": "changed.txt"}
        for altered in (
            {key: value for key, value in valid.items() if key != "scope"},
            {**valid, "scope": "all-files"},
            {**valid, "excludedChanged": 0},
            {**valid, "excludedChanged": True},
            {**valid, "excludedChanged": -1},
            {**valid, "entries": [changed_entry, *valid["entries"][1:]]},
            {**valid, "omitted": valid["omitted"] + 1},
        ):
            forged = presented.replace(
                json.dumps(valid, separators=(",", ":")).encode(),
                json.dumps(altered, separators=(",", ":")).encode(),
                1,
            )
            with self.subTest(altered=altered):
                self.assertFalse(
                    context.presentation_valid(
                        audit(raw, forged), "unchanged_excerpts", root=ROOT
                    )
                )

    def test_default_output_is_byte_equal_to_explicit_legacy_mode(self):
        raw = encoded(report())
        default = context.augment(raw, snapshot())
        self.assertEqual(
            hashlib.sha256(default).hexdigest(),
            "4a631689891b664dce27ab6ae629d7fa3879836dd850e7ede89251f9c48d643c",
        )
        self.assertEqual(
            default, context.augment(raw, snapshot(), unchanged_only=False)
        )
        self.assertNotIn("scope", json.loads(default)["reviewContext"])
        self.assertNotIn("excludedChanged", json.loads(default)["reviewContext"])
        self.assertTrue(
            context.presentation_valid(
                audit(raw, default, "review_excerpts"), "review_excerpts"
            )
        )


if __name__ == "__main__":
    unittest.main()
