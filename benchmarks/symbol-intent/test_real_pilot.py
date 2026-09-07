"""Offline design, receipt and execution-boundary regressions; no model calls."""

import argparse
import contextlib
import copy
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import entrypoint_trial
import pilot
import real_fixture
import real_pilot as study
from lsp import IntentError


class RealPilotTests(unittest.TestCase):
    def test_ten_paired_blocks_have_all_three_arms_once(self):
        rows = study.schedule()
        self.assertEqual(rows, study.schedule())
        self.assertEqual(30, len(rows))
        self.assertEqual(
            [7, 8, 5, 3, 0, 4, 6, 2, 9, 1], [r["repetition"] for r in rows[::3]]
        )
        self.assertEqual(30, len({r["id"] for r in rows}))
        self.assertEqual(
            Counter({i: 3 for i in range(10)}), Counter(r["repetition"] for r in rows)
        )
        for repeat in range(10):
            self.assertEqual(
                set(study.ARMS), {r["arm"] for r in rows if r["repetition"] == repeat}
            )

    def test_guidance_schedule_has_twenty_balanced_prospective_rows(self):
        rows = study.schedule(study.GUIDANCE_EXPERIMENT)
        self.assertEqual(rows, study.schedule(study.GUIDANCE_EXPERIMENT))
        self.assertEqual(20, len(rows))
        self.assertEqual(20, len({r["id"] for r in rows}))
        self.assertEqual(
            Counter(compact=10, guidance=10), Counter(r["arm"] for r in rows)
        )
        self.assertEqual(
            Counter(compact=5, guidance=5), Counter(r["arm"] for r in rows[::2])
        )
        for index in range(0, 20, 2):
            self.assertEqual(rows[index]["repetition"], rows[index + 1]["repetition"])
            self.assertEqual(
                {"compact", "guidance"}, {r["arm"] for r in rows[index : index + 2]}
            )
        with self.assertRaisesRegex(IntentError, "experiment"):
            study.schedule("unknown")

    def test_profile_loading_rejects_unknown_or_incomplete_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for experiment in study.PROFILES:
                config = {
                    "experiment": experiment,
                    "schedule": study.schedule(experiment),
                }
                pilot.save(output / pilot.CONFIG_FILE, config)
                self.assertEqual(config, study.load_config(output))
                config["schedule"].pop()
                pilot.save(output / pilot.CONFIG_FILE, config)
                with self.assertRaisesRegex(IntentError, "schedule"):
                    study.load_config(output)
            pilot.save(output / pilot.CONFIG_FILE, {"experiment": "unknown"})
            with self.assertRaisesRegex(IntentError, "experiment"):
                study.load_config(output)

    def test_entrypoint_pairing_and_only_capability_suffix_changes(self):
        rows = study.schedule(study.ENTRYPOINT_EXPERIMENT)
        self.assertEqual(20, len(rows))
        self.assertEqual(20, len({r["id"] for r in rows}))
        self.assertEqual(
            Counter({"compact": 5, "intent-first": 5}),
            Counter(r["arm"] for r in rows[::2]),
        )
        for index in range(0, 20, 2):
            pair = rows[index : index + 2]
            self.assertEqual(1, len({r["repetition"] for r in pair}))
            self.assertEqual({"compact", "intent-first"}, {r["arm"] for r in pair})
        task = {
            "file": "Classes/Example.php",
            "select": "method:Example::old",
            "to": "newName",
            "expected_edit_inventory": "hidden-answer",
        }
        rename, checker = Path("/run/rename-tool"), Path("/run/check-tests")
        original = study.prompts(task, "ast-integrated", rename, checker)
        compact = study.profile_prompts(
            task, study.ENTRYPOINT_EXPERIMENT, "compact", rename, checker
        )
        treatment = study.profile_prompts(
            task, study.ENTRYPOINT_EXPERIMENT, "intent-first", rename, checker
        )
        self.assertEqual(original, compact)
        self.assertEqual(compact[0], treatment[0])
        self.assertEqual(compact[1] + "\n\n" + entrypoint_trial.CONTRACT, treatment[1])
        self.assertNotIn("hidden-answer", treatment[1])
        self.assertIn("Reference completeness remains", entrypoint_trial.CONTRACT)
        self.assertIn(
            "verification requirements above still apply", entrypoint_trial.CONTRACT
        )
        with self.assertRaisesRegex(IntentError, "arm"):
            study.profile_prompts(
                task, study.ENTRYPOINT_EXPERIMENT, "guidance", rename, checker
            )

    def test_all_prompts_require_same_final_byte_checks_without_oracle_answers(self):
        task = {
            "file": "Classes/Classifier.php",
            "select": "method:Classifier::classify",
            "to": "controlType",
            "expected_changed_files": ["hidden-caller.php"],
            "expected_edit_count": 3,
        }
        texts = [
            study.prompts(task, arm, Path("/run/rename-tool"), Path("/run/check-tests"))
            for arm in study.ARMS
        ]
        self.assertEqual(1, len({text[0] for text in texts}))
        for system, prompt in texts:
            self.assertIn("17", prompt)
            self.assertIn("/run/check-tests", prompt)
            self.assertIn("final", prompt)
            self.assertIn("Only change method-name identifier tokens", prompt)
            self.assertNotIn("hidden-caller.php", prompt)
            self.assertNotIn("expected_edit_count", prompt)
            self.assertIn("Do not repeat", system)
            self.assertIn(
                "not proof of reference completeness", " ".join(system.split())
            )
        self.assertIn("batched", texts[0][1])
        self.assertNotIn("/run/rename-tool", texts[0][1])
        for _, prompt in texts[1:]:
            self.assertIn("All PHP mutations in this arm must use this command", prompt)

    def receipt(self):
        final = {"source.php": "a" * 64, ".php-ast-edit.json": "b" * 64}
        receipt = {
            "ok": True,
            "returncode": 0,
            "tests": 17,
            "assertions": 26,
            "timed_out": False,
            "fixture_unchanged": True,
            "before": final,
            "after": final,
            "duration_ms": 12.5,
            "phpunit_sha256": real_fixture.PHPUNIT_SHA256,
        }
        return final, receipt

    def test_only_successful_complete_unchanged_final_byte_receipts_count(self):
        final, good = self.receipt()
        self.assertTrue(study.receipt_matches(good, final))
        invalid = []
        for changes in (
            {"tests": 0},
            {"tests": 16},
            {"tests": 17.0},
            {"returncode": 1},
            {"returncode": False},
            {"ok": False},
            {"timed_out": True},
            {"fixture_unchanged": False},
            {"phpunit_sha256": "wrong"},
            {"before": {"source.php": "old"}},
            {"after": {"source.php": "old"}},
        ):
            invalid.append({**copy.deepcopy(good), **changes})
        stale = copy.deepcopy(good)
        stale["before"] = stale["after"] = {"source.php": "old"}
        invalid.append(stale)
        for receipt in invalid:
            with self.subTest(receipt=receipt):
                self.assertFalse(study.receipt_matches(receipt, final))
        summary = study.check_summary(invalid + [good], final)
        self.assertEqual(1, summary["passed_final_receipts"])
        self.assertTrue(summary["candidate_verified_final"])

    def test_hidden_check_success_does_not_replace_candidate_proof_or_cli_success(self):
        final, good = self.receipt()
        unchecked = study.check_summary([], final)
        native = {"native_is_error": False, "native_subtype": "success"}
        process = {"process_exit": 0, "timed_out": False}
        outcome = study.outcomes(process, native, {"ok": True}, good, unchecked, final)
        self.assertTrue(outcome["code_correct"])
        self.assertFalse(outcome["candidate_verified_final"])
        self.assertFalse(outcome["success"])
        checked = study.check_summary([good], final)
        self.assertTrue(
            study.outcomes(process, native, {"ok": True}, good, checked, final)[
                "success"
            ]
        )
        for broken_native, broken_process in (
            ({**native, "native_is_error": True}, process),
            ({**native, "native_subtype": "error_max_budget_usd"}, process),
            (native, {**process, "process_exit": 1}),
            (native, {**process, "timed_out": True}),
        ):
            self.assertFalse(
                study.outcomes(
                    broken_process, broken_native, {"ok": True}, good, checked, final
                )["success"]
            )

    def test_freeze_preserves_fixture_config_and_refuses_input_or_phar_drift(self):
        self.assert_freeze()

    def test_guidance_freeze_changes_only_wrapper_flag_between_integrated_arms(self):
        self.assert_freeze(study.GUIDANCE_EXPERIMENT)

    def test_entrypoint_freeze_changes_only_the_prospective_paragraph(self):
        self.assert_freeze(study.ENTRYPOINT_EXPERIMENT)

    def assert_freeze(self, experiment=None):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            (repo / "tracked.txt").write_text("committed controller\n")
            (repo / "vendor").mkdir()
            (repo / "vendor/dependency.txt").write_text("dependency\n")
            pilot.invoke(["git", "init", "-q"], repo, env=pilot.environment())
            (repo / ".git/info/exclude").write_text("vendor/\n")
            pilot.invoke(["git", "add", "tracked.txt"], repo, env=pilot.environment())
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
                repo,
                env=pilot.environment(),
            )
            phpactor, phpunit = base / "resolver.phar", base / "tests.phar"
            phpactor.write_bytes(b"test resolver")
            phpunit.write_bytes(b"test PHPUnit")
            output = base / "campaign"

            def exporting(work, source_repo):
                work.mkdir()
                (work / "source.php").write_text("<?php // disposable fixture\n")
                return {"commit": real_fixture.SOURCE_COMMIT}

            with (
                patch.object(pilot, "SOURCE", repo),
                patch.object(
                    study, "cli_identity", return_value=("/test/claude", "test CLI")
                ),
                patch.object(pilot, "PHAR_SHA256", pilot.sha(phpactor)),
                patch.object(real_fixture, "PHPUNIT_SHA256", pilot.sha(phpunit)),
                patch.object(real_fixture, "export", side_effect=exporting),
                patch.object(
                    real_fixture,
                    "task",
                    return_value={
                        "file": "source.php",
                        "select": "method:Example::classify",
                        "to": "controlType",
                        "source_commit": real_fixture.SOURCE_COMMIT,
                    },
                ),
                patch.object(pilot, "capture") as capture,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                study.prepare(
                    argparse.Namespace(
                        output=output,
                        source_repo=repo,
                        phpactor=phpactor,
                        phpunit=phpunit,
                        **({"experiment": experiment} if experiment else {}),
                    )
                )
                capture.assert_not_called()
                config = json.loads((output / "config.json").read_text())
                guidance = experiment == study.GUIDANCE_EXPERIMENT
                entrypoint = experiment == study.ENTRYPOINT_EXPERIMENT
                paired = guidance or entrypoint
                self.assertEqual(20 if paired else 30, len(config["schedule"]))
                self.assertEqual(5.0 if paired else 8.0, config["campaign_usd"])
                self.assertEqual(0.5, config["max_run_usd"])
                self.assertEqual(120, config["timeout_seconds"])
                self.assertEqual(config, study.load_config(output))
                normalized_inputs = []
                for row in config["schedule"]:
                    study.validate(output, config, row, check_cli=False)
                    work = output / row["id"] / "work"
                    settings = json.loads((work / study.PROJECT_CONFIG).read_text())
                    self.assertEqual(
                        paired or row["arm"] == "ast-integrated",
                        bool(settings["verify"]),
                    )
                    self.assertEqual(
                        real_fixture.snapshot(work),
                        json.loads((work.parent / "initial.json").read_text()),
                    )
                    if paired:
                        run_dir = work.parent
                        rename = (run_dir / "rename-tool").read_text()
                        self.assertIn("'--evidence'", rename)
                        self.assertEqual(
                            row["arm"] == "guidance", "'--guidance'" in rename
                        )
                        normalized_inputs.append(
                            [
                                (run_dir / name)
                                .read_text()
                                .replace(str(run_dir), "/RUN")
                                .replace(", '--guidance'", "")
                                .replace("\n\n" + entrypoint_trial.CONTRACT, "")
                                for name in (
                                    pilot.SYSTEM_FILE,
                                    pilot.PROMPT_FILE,
                                    "rename-tool",
                                    "check-tests",
                                    "work/" + study.PROJECT_CONFIG,
                                )
                            ]
                        )
                if paired:
                    self.assertTrue(
                        all(
                            value == normalized_inputs[0] for value in normalized_inputs
                        )
                    )
                row = config["schedule"][0]
                wrapper = output / row["id"] / "check-tests"
                wrapper.write_text(wrapper.read_text() + "unfrozen change\n")
                with self.assertRaisesRegex(IntentError, "input drift"):
                    study.validate(output, config, row, check_cli=False)
                (output / study.PHPUNIT_FILE).write_bytes(b"modified PHAR")
                with self.assertRaisesRegex(IntentError, "PHPUnit drift"):
                    study.validate(output, config, check_cli=False)

    def test_entrypoint_incomplete_pairs_preserve_unknown_primary_values(self):
        experiment = study.ENTRYPOINT_EXPERIMENT
        planned = study.schedule(experiment)
        empty = study.summarize_records([], experiment)
        self.assertEqual(20, len(empty["planned_rows"]))
        self.assertEqual(10, len(empty["paired_effects"][0]["pairs"]))
        for cell in empty["cells"]:
            self.assertEqual(0, cell["known_pre_calls"])
            self.assertIsNone(cell["median_pre_calls"])
        record = {
            **planned[0],
            "precheck": {"preceding_tool_calls": 0, "peer_tool_calls": 1},
        }
        summary = study.summarize_records([record], experiment)
        arm = next(c for c in summary["cells"] if c["arm"] == record["arm"])
        self.assertEqual(1, arm["known_pre_calls"])
        self.assertEqual(0, arm["median_pre_calls"])
        self.assertEqual(1, arm["median_peer_calls"])
        self.assertEqual(19, len(summary["unattempted_ids"]))
        self.assertTrue(
            all(
                p["deltas"]["pre_calls"] is None
                for p in summary["paired_effects"][0]["pairs"]
            )
        )
        with self.assertRaisesRegex(IntentError, "Duplicate"):
            study.summarize_records([record, record], experiment)

    def test_replay_refused_before_model_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "started.json").write_text("{}")
            with (
                patch.object(study, "load_config", return_value={}),
                patch.object(study, "validate"),
                patch.object(study, "__file__", str(output / study.CONTROLLER)),
                patch.object(pilot, "capture") as capture,
            ):
                args = argparse.Namespace(output=output, execute_models=True)
                with self.assertRaisesRegex(IntentError, "already started"):
                    study.run(args)
                capture.assert_not_called()

    def test_malformed_receipt_keeps_check_count_and_duration_unknown(self):
        final, _ = self.receipt()
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "check-receipts").mkdir()
            (run / "check-receipts/truncated.json").write_text('{"tests":')
            checks = study.candidate_checks(run, final)
        self.assertEqual(1, checks["observed_receipt_files"])
        self.assertIsNone(checks["behavior_checks"])
        self.assertIsNone(checks["checker_ms"])
        self.assertFalse(checks["checker_timing_complete"])
        self.assertFalse(checks["candidate_verified_final"])

    def test_summary_keeps_incomplete_attempt_and_reports_paired_changes(self):
        rows = []
        for row in study.schedule():
            rows.append(
                {
                    **row,
                    "wall_time_ms": 100,
                    "native": {
                        "all_model_tokens": {
                            "totalTokens": 200 if row["arm"] == "text-manual" else 100
                        },
                        "tool_calls": 3,
                        "primary_model_rounds": 4,
                        "native_list_price_usd": 0.01,
                    },
                    "candidate_checks": {"behavior_checks": 1, "checker_ms": 12.5},
                    "outcome": {
                        "code_correct": True,
                        "candidate_verified_final": True,
                        "success": True,
                    },
                }
            )
        rows[0].pop("native")
        rows[0].pop("outcome")
        summary = study.summarize_records(rows)
        self.assertEqual(30, summary["attempts"])
        self.assertEqual(29, summary["known_usage"])
        self.assertEqual(29, sum(cell["successes"] for cell in summary["cells"]))
        self.assertEqual(3, len(summary["cells"]))
        self.assertEqual(-100, summary["paired_effects"][0]["median_delta_tokens"])
        self.assertEqual(30, summary["planned_attempts"])
        self.assertNotIn("planned_rows", summary)
        self.assertNotIn("post_calls", study.metrics({}))

    def test_guidance_unknowns_and_unattempted_pairs_do_not_become_zero(self):
        planned = study.schedule(study.GUIDANCE_EXPERIMENT)
        record = {
            **planned[0],
            "candidate_checks": {"behavior_checks": None, "passed_final_receipts": 0},
        }
        summary = study.summarize_records([record], study.GUIDANCE_EXPERIMENT)
        self.assertEqual(20, summary["planned_attempts"])
        self.assertEqual(1, summary["attempts"])
        self.assertEqual(19, len(summary["unattempted_ids"]))
        self.assertEqual(20, len(summary["planned_rows"]))
        self.assertEqual(1, sum(row["attempted"] for row in summary["planned_rows"]))
        self.assertEqual(10, len(summary["paired_effects"][0]["pairs"]))
        self.assertTrue(
            all(
                pair["deltas"]["post_calls"] is None
                for pair in summary["paired_effects"][0]["pairs"]
            )
        )
        for cell in summary["cells"]:
            self.assertEqual(0, cell["known_post_calls"])
            self.assertEqual(0, cell["known_duplicate_final_checks"])
            self.assertIsNone(cell["median_duplicate_final_checks"])
        empty = study.summarize_records([], study.GUIDANCE_EXPERIMENT)
        self.assertEqual(20, len(empty["unattempted_ids"]))

    def test_duplicate_metric_counts_only_extra_successful_final_byte_receipts(self):
        final, good = self.receipt()
        stale = {**good, "before": {"old": "bytes"}, "after": {"old": "bytes"}}
        record = {
            "candidate_checks": study.check_summary([stale, good, good], final),
            "postcheck": {"subsequent_tool_calls": 4},
        }
        values = study.metrics(record, study.GUIDANCE_EXPERIMENT)
        self.assertEqual(3, values["behavior_checks"])
        self.assertEqual(1, values["duplicate_final_checks"])
        self.assertEqual(4, values["post_calls"])
        record["fixture_error"] = "Final inventory unavailable"
        self.assertIsNone(
            study.metrics(record, study.GUIDANCE_EXPERIMENT)["duplicate_final_checks"]
        )
        record.pop("fixture_error")
        record["candidate_checks"]["behavior_checks"] = None
        self.assertIsNone(
            study.metrics(record, study.GUIDANCE_EXPERIMENT)["duplicate_final_checks"]
        )

    def test_postcheck_observation_reuses_existing_trace_boundary_and_handles_incomplete(
        self,
    ):
        run_dir = Path("/campaign/run001")
        events = [
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "rename",
                            "name": "Bash",
                            "input": {
                                "command": "/campaign/run001/rename-tool --file source.php"
                            },
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "rename",
                            "content": '{"ok": true}',
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "read",
                            "name": "Read",
                            "input": {"file_path": "source.php"},
                        }
                    ]
                }
            },
        ]
        record = {"native": {"native_subtype": "success"}}
        with patch.object(pilot.native, "read_events", return_value=(events, [])):
            self.assertEqual(
                1, study.guidance_observation(run_dir, record)["subsequent_tool_calls"]
            )
        with patch.object(
            pilot.native, "read_events", return_value=(events, ["truncated"])
        ):
            self.assertIsNone(
                study.guidance_observation(run_dir, record)["subsequent_tool_calls"]
            )
        with patch.object(pilot.native, "read_events") as read:
            self.assertIsNone(
                study.guidance_observation(run_dir, {"accounting_error": "incomplete"})[
                    "subsequent_tool_calls"
                ]
            )
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
