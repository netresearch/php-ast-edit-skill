"""Offline campaign-directory and native-timing regressions; no model calls."""

import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import native
import runner


class SnapshotReached(Exception):
    pass


class CampaignDirectoryTests(unittest.TestCase):
    def fresh_output(self):
        path = Path(tempfile.mkdtemp(prefix="php-ast-campaign-permissions-"))
        path.rmdir()
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def args(self, output):
        return SimpleNamespace(
            arms="compact_full,compact_focused", tasks="fixture", seed=1, output=output
        )

    def test_private_directory_exists_before_any_snapshot_or_command(self):
        output = self.fresh_output()
        previous = os.umask(0)
        try:
            with (
                patch.object(runner, "snapshot", side_effect=SnapshotReached),
                self.assertRaises(SnapshotReached),
            ):
                runner.prepare(self.args(output))
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)

    def test_existing_directory_is_never_reused(self):
        output = self.fresh_output()
        output.mkdir()
        sentinel = output / "sentinel"
        sentinel.write_text("retained")
        with (
            patch.object(runner, "snapshot") as snapshot,
            self.assertRaises(ValueError),
        ):
            runner.prepare(self.args(output))
        snapshot.assert_not_called()
        self.assertEqual(sentinel.read_text(), "retained")

    def test_dangling_symlink_is_rejected_before_snapshot(self):
        output, target = self.fresh_output(), self.fresh_output()
        output.symlink_to(target, target_is_directory=True)
        self.addCleanup(output.unlink)
        with (
            patch.object(runner, "snapshot", side_effect=SnapshotReached) as snapshot,
            self.assertRaises(ValueError),
        ):
            runner.prepare(self.args(output))
        snapshot.assert_not_called()
        self.assertFalse(target.exists())

    def test_nested_output_is_rejected_without_creating_descendants(self):
        parent = self.fresh_output()
        parent.mkdir()
        output = parent / "nested"
        with (
            patch.object(runner, "snapshot", side_effect=SnapshotReached) as snapshot,
            self.assertRaises(ValueError),
        ):
            runner.prepare(self.args(output))
        snapshot.assert_not_called()
        self.assertFalse(output.exists())


class NativeTimingTests(unittest.TestCase):
    def event(self, identifier, metadata):
        return {
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": identifier}]
            },
            "tool_use_result": metadata,
        }

    def test_valid_intervals_zero_and_alias_fallback_are_counted_once(self):
        result = native.tool_timings(
            [
                self.event("one", {"duration_ms": 0, "durationMs": 999}),
                self.event("two", {"duration_ms": float("nan"), "durationMs": 12}),
            ],
            {"one": {}, "two": {}},
        )
        self.assertEqual(result["tool_execution_ms"], 12)
        self.assertEqual(result["tool_timing_status"], "complete_native_intervals")
        self.assertEqual(
            result["native_tool_timings"]["one"]["source_field"],
            "tool_use_result.duration_ms",
        )

    def test_invalid_or_missing_intervals_do_not_imply_zero_elapsed_time(self):
        result = native.tool_timings(
            [self.event("one", {"duration_ms": True, "durationMs": -1})], {"one": {}}
        )
        self.assertEqual(result["tool_timing_status"], "not_exposed")
        self.assertIsNone(result["tool_execution_ms"])
        partial = native.tool_timings(
            [self.event("one", {"duration_ms": 2})], {"one": {}, "two": {}}
        )
        self.assertEqual(partial["tool_timing_status"], "partial")
        self.assertIsNone(partial["tool_execution_ms"])


if __name__ == "__main__":
    unittest.main()
