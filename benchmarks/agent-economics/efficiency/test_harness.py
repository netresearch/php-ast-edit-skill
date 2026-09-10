"""Offline campaign-directory and native-timing regressions; no model calls."""

import json
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
        path = Path(
            tempfile.mkdtemp(prefix="php-ast-campaign-permissions-", dir="/tmp")
        )
        path.rmdir()
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def args(self, output):
        return SimpleNamespace(
            arms="compact_full,compact_focused", tasks="fixture", seed=1, output=output
        )

    def test_private_directory_exists_before_any_snapshot_or_command(self):
        output = self.fresh_output()
        args = self.args(output)
        previous = os.umask(0)
        try:
            with (
                patch.object(runner, "snapshot", side_effect=SnapshotReached),
                self.assertRaises(SnapshotReached),
            ):
                runner.prepare(args)
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)

    def test_existing_directory_is_never_reused(self):
        output = self.fresh_output()
        output.mkdir()
        sentinel = output / "sentinel"
        sentinel.write_text("retained")
        args = self.args(output)
        with (
            patch.object(runner, "snapshot") as snapshot,
            self.assertRaises(ValueError),
        ):
            runner.prepare(args)
        snapshot.assert_not_called()
        self.assertEqual(sentinel.read_text(), "retained")

    def test_dangling_symlink_is_rejected_before_snapshot(self):
        output, target = self.fresh_output(), self.fresh_output()
        output.symlink_to(target, target_is_directory=True)
        self.addCleanup(output.unlink)
        args = self.args(output)
        with (
            patch.object(runner, "snapshot", side_effect=SnapshotReached) as snapshot,
            self.assertRaises(ValueError),
        ):
            runner.prepare(args)
        snapshot.assert_not_called()
        self.assertFalse(target.exists())

    def test_nested_output_is_rejected_without_creating_descendants(self):
        parent = self.fresh_output()
        parent.mkdir()
        output = parent / "nested"
        args = self.args(output)
        with (
            patch.object(runner, "snapshot", side_effect=SnapshotReached) as snapshot,
            self.assertRaises(ValueError),
        ):
            runner.prepare(args)
        snapshot.assert_not_called()
        self.assertFalse(output.exists())


class LegacyRecoveryTests(unittest.TestCase):
    def fixture(
        self,
        *,
        retry=True,
        error="Response input totals differ",
        timed_out=False,
        terminal_input=3,
    ):
        temporary = tempfile.TemporaryDirectory(prefix="php-ast-legacy-recovery-")
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        evidence = base / "runs/run004/evidence"
        evidence.mkdir(parents=True)
        config = {"source_commit": "a" * 40}
        runner.save(base / runner.CONFIG, config)
        model = "fixture-model"
        response_input = {
            "input_tokens": 1,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        events = [
            {
                "type": "system",
                "subtype": "init",
                "model": model,
                "tools": ["Bash", "Read", "Edit", "Write"],
                "plugins": [],
                "skills": [],
                "mcp_servers": [],
            },
            {
                "type": "assistant",
                "message": {
                    "id": "before-retry",
                    "model": model,
                    "usage": response_input,
                    "content": [],
                },
            },
        ]
        if retry:
            events.append(
                {
                    "type": "user",
                    "isSynthetic": True,
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "[Your previous response had no visible output. Please continue and produce a user-visible response.]",
                            }
                        ]
                    },
                }
            )
        events.extend(
            [
                {
                    "type": "assistant",
                    "message": {
                        "id": "after-retry",
                        "model": model,
                        "usage": response_input,
                        "content": [],
                    },
                },
                {
                    "type": "result",
                    "usage": {
                        **response_input,
                        "input_tokens": terminal_input,
                        "output_tokens": 1,
                    },
                    "modelUsage": {
                        model: {
                            "inputTokens": 3,
                            "outputTokens": 1,
                            "cacheReadInputTokens": 0,
                            "cacheCreationInputTokens": 0,
                        }
                    },
                    "total_cost_usd": 0.01,
                },
            ]
        )
        (evidence / runner.RAW).write_text(
            "\n".join(json.dumps(event) for event in events) + "\n"
        )
        runner.save(
            evidence / runner.MEASUREMENT,
            {
                "run_id": "run004",
                "accounting_errors": [error] if error else [],
                "timed_out": timed_out,
                "config_sha256": runner.digest(base / runner.CONFIG),
                "raw_sha256": runner.digest(evidence / runner.RAW),
                "requested_model": model,
                "oracle": {"passed": False},
            },
        )
        folder = base / "controller-amendment-v1"
        folder.mkdir()
        for name in ("runner.py", "native.py", "PROTOCOL.md"):
            (folder / name).write_text("Frozen test provenance; never executed.\n")
        runner.save(
            folder / runner.AMENDMENT,
            {
                "original_source_commit": config["source_commit"],
                "source_commit": "b" * 40,
                "config_sha256": runner.digest(base / runner.CONFIG),
                "files": {
                    name: runner.digest(folder / name)
                    for name in ("runner.py", "native.py", "PROTOCOL.md")
                },
            },
        )
        return base, evidence, folder

    def test_legacy_retry_recovery_preserves_originals_and_grading(self):
        base, evidence, folder = self.fixture()
        before = {
            path.relative_to(base): path.read_bytes()
            for path in base.rglob("*")
            if path.is_file()
        }
        result = runner.recovered_measurement(base, evidence, folder)
        self.assertEqual(result["all_model_tokens"]["totalTokens"], 4)
        self.assertEqual(result["native_list_price_usd"], 0.01)
        self.assertEqual(result["response_input_coverage"], "incomplete_native_retry")
        self.assertFalse(result["primary_model_rounds_exact"])
        self.assertEqual(
            result["original_accounting_errors"], ["Response input totals differ"]
        )
        self.assertEqual(
            result["original_measurement_sha256"],
            runner.digest(evidence / runner.MEASUREMENT),
        )
        self.assertEqual(result["oracle"], {"passed": False})
        after = {
            path.relative_to(base): path.read_bytes()
            for path in base.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_legacy_label_does_not_bypass_missing_retry_evidence(self):
        base, evidence, folder = self.fixture(retry=False)
        with self.assertRaisesRegex(ValueError, "without native retry evidence"):
            runner.recovered_measurement(base, evidence, folder)

    def test_current_unexplained_gap_and_success_are_not_legacy_recovery(self):
        for error in (
            "Response input totals differ without native retry evidence",
            None,
        ):
            base, evidence, folder = self.fixture(retry=False, error=error)
            with (
                self.subTest(error=error),
                self.assertRaisesRegex(ValueError, "Unsupported recovery error"),
            ):
                runner.recovered_measurement(base, evidence, folder)

    def test_legacy_recovery_still_checks_terminal_agreement(self):
        base, evidence, folder = self.fixture(terminal_input=4)
        with self.assertRaisesRegex(ValueError, "Terminal usage and modelUsage differ"):
            runner.recovered_measurement(base, evidence, folder)

    def test_legacy_label_does_not_allow_timeout_recovery(self):
        base, evidence, folder = self.fixture(timed_out=True)
        with self.assertRaisesRegex(ValueError, "Cannot recover timed-out candidate"):
            runner.recovered_measurement(base, evidence, folder)


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
