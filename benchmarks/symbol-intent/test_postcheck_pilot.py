"""Offline checks for the independently frozen post-rename ablation."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pilot
import postcheck_pilot as study
from lsp import IntentError


class PostcheckTests(unittest.TestCase):
    def test_schedule_has_all_four_treatments_in_each_size_repeat_block(self):
        rows = study.schedule()
        self.assertEqual(rows, study.schedule())
        self.assertEqual(24, len(rows))
        self.assertEqual(24, len({row["id"] for row in rows}))
        self.assertEqual(
            Counter({(size, repeat): 4 for size in (10, 50) for repeat in range(3)}),
            Counter((row["size"], row["repetition"]) for row in rows),
        )
        for size in (10, 50):
            for repeat in range(3):
                self.assertEqual(
                    {
                        (False, "current"),
                        (True, "current"),
                        (False, "scoped"),
                        (True, "scoped"),
                    },
                    {
                        (r["evidence"], r["guidance"])
                        for r in rows
                        if r["size"] == size and r["repetition"] == repeat
                    },
                )

    def test_guidance_is_independent_of_result_arm_and_keeps_semantic_checks(self):
        command = Path("/campaign/run001/rename-tool")
        current = study.prompts(10, command, "current")
        scoped = study.prompts(10, command, "scoped")
        self.assertEqual(pilot.COMMON, current[0])
        self.assertEqual(current[1], scoped[1])
        self.assertIn("completeness is unknown", scoped[1])
        for phrase in ("reference completeness", "behavior", "failed", "skipped"):
            self.assertIn(phrase, scoped[0])
        for text in (*current, *scoped):
            self.assertNotIn("ORACLE_OK", text)
            self.assertNotIn("[11, 22]", text)
            self.assertNotIn("expected.json", text)
            self.assertNotIn("--evidence", text)

    def test_preparation_freezes_all_inputs_without_calling_models(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "repo"
            source.mkdir()
            (source / "source.txt").write_text("frozen implementation\n")
            (source / "vendor").mkdir()
            (source / "vendor/dependency.txt").write_text("frozen dependency\n")
            pilot.invoke(["git", "init", "-q"], source, env=pilot.environment())
            pilot.invoke(["git", "add", "source.txt"], source, env=pilot.environment())
            pilot.invoke(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-qm",
                    "Fixture",
                ],
                source,
                env=pilot.environment(),
            )
            # Runtime dependencies are copied separately from the committed tree.
            (source / ".git/info/exclude").write_text("vendor/\n")
            phar = base / "test.phar"
            phar.write_bytes(b"pinned test resolver")
            output = base / "campaign"
            with (
                patch.object(pilot, "SOURCE", source),
                patch.object(pilot, "PHAR_SHA256", pilot.sha(phar)),
                patch.object(
                    study, "cli_identity", return_value=("/test/claude", "frozen CLI")
                ),
                patch.object(pilot, "capture") as capture,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                study.prepare(argparse.Namespace(output=output, phpactor=phar))
                capture.assert_not_called()
            config = json.loads((output / pilot.CONFIG_FILE).read_text())
            self.assertEqual(24, len(config["schedule"]))
            self.assertEqual(4.0, config["campaign_usd"])
            self.assertEqual(0.5, config["max_run_usd"])
            self.assertEqual(120, config["timeout_seconds"])
            self.assertEqual(pilot.MODEL, config["model"])
            self.assertFalse((output / "started.json").exists())
            for row in config["schedule"]:
                pilot.validate(output, config, row)
                run = output / row["id"]
                wrapper = (run / "rename-tool").read_text()
                self.assertEqual(row["evidence"], "--evidence" in wrapper)
                initial = json.loads((run / pilot.INITIAL_FILE).read_text())
                self.assertEqual(row["size"], len(initial))
                self.assertTrue(
                    all(
                        pilot.sha(run / "work" / name) == value
                        for name, value in initial.items()
                    )
                )
            row = config["schedule"][0]
            prompt = output / row["id"] / pilot.PROMPT_FILE
            prompt.write_text(prompt.read_text() + "unfrozen instruction")
            with self.assertRaisesRegex(IntentError, "Run input drift"):
                pilot.validate(output, config, row)

    def test_post_calls_start_after_successful_result_and_deduplicate_stream_blocks(
        self,
    ):
        def event(role, blocks):
            return {"type": role, "message": {"content": blocks}}

        rename = {
            "type": "tool_use",
            "id": "rename",
            "name": "Bash",
            "input": {"command": "/trial/rename-tool --to load"},
        }
        read = {"type": "tool_use", "id": "read", "name": "Read", "input": {}}
        events = [
            event("assistant", [rename]),
            event("assistant", [rename]),
            event(
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": "rename",
                        "content": '{"ok":true,"completeness":"unknown"}',
                    }
                ],
            ),
            event("assistant", [read]),
            event("assistant", [read]),
        ]
        result = study.post_calls(events, "/trial/rename-tool")
        self.assertEqual(1, result["subsequent_tool_calls"])
        self.assertEqual({"Read": 1}, result["subsequent_tools"])
        events[2]["message"]["content"][0]["content"] = '{"ok":false}'
        self.assertIsNone(
            study.post_calls(events, "/trial/rename-tool")["subsequent_tool_calls"]
        )

    def test_summary_keeps_unknown_attempts_and_pairs_only_this_experiment(self):
        records = []
        for row in study.schedule():
            records.append(
                {
                    **row,
                    "oracle": {"success": True},
                    "wall_time_ms": 100,
                    "native": {
                        "all_model_tokens": {"totalTokens": 100 - 10 * row["evidence"]},
                        "tool_calls": 5,
                        "primary_model_rounds": 4,
                        "native_list_price_usd": 0.01,
                    },
                    "postcheck": {"subsequent_tool_calls": 2},
                }
            )
        records[0].pop("native")
        records[0]["oracle"] = None
        summary = study.summarize_records(records)
        self.assertEqual(24, summary["attempts"])
        self.assertEqual(23, summary["known_usage"])
        self.assertTrue(all(row["median_rounds"] == 4 for row in summary["cells"]))
        self.assertEqual(23, sum(row["successes"] for row in summary["cells"]))
        evidence_effects = [
            row for row in summary["paired_effects"] if row["factor"] == "evidence"
        ]
        self.assertEqual(4, len(evidence_effects))
        self.assertTrue(
            all(row["median_delta_tokens"] == -10 for row in evidence_effects)
        )
        self.assertEqual(11, sum(len(row["delta_tokens"]) for row in evidence_effects))

    def test_malformed_or_missing_trace_cannot_support_known_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            row = study.schedule()[0]
            run = output / row["id"]
            run.mkdir()
            config = {"schedule": [row], "model": pilot.MODEL}
            pilot.save(run / pilot.MEASUREMENT_FILE, {**row, "native": {"tokens": 42}})
            with patch.object(pilot, "validate"):
                with self.assertRaisesRegex(IntentError, "Missing native trace"):
                    study.records(output, config)
                (run / pilot.NATIVE_FILE).write_text("broken json\n")
                with self.assertRaisesRegex(IntentError, "Malformed trace"):
                    study.records(output, config)
                (run / pilot.MEASUREMENT_FILE).unlink()
                incomplete = study.records(output, config)
            self.assertEqual(1, len(incomplete))
            self.assertIn(
                "Malformed incomplete trace", incomplete[0]["accounting_error"]
            )
            self.assertEqual(0, study.summarize_records(incomplete)["known_usage"])

    def test_execution_requires_the_frozen_controller_before_dispatch(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(study, "configuration"),
            patch.object(pilot, "run_pilot") as dispatch,
        ):
            with self.assertRaisesRegex(IntentError, "prepared source snapshot"):
                study.run(
                    argparse.Namespace(output=Path(directory), execute_models=True)
                )
            dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
