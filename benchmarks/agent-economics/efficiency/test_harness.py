"""Offline campaign-directory and native-timing regressions; no model calls."""

import hashlib
import json
import os
import shlex
import shutil
import stat
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import check_arms
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
            arms="compact_full,compact_focused",
            models=",".join(runner.MODELS),
            tasks="fixture",
            seed=1,
            output=output,
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


class ScheduleSelectionTests(unittest.TestCase):
    def test_legacy_schedule_bytes_are_preserved(self):
        cases = [
            (
                ["local-variable", "multi-file-members"],
                20260906,
                runner.ARMS,
                tuple(runner.MODELS),
                "b5ea2c3ffbd3941f95ffdf39323f54bfbbeb6d055b87bca247141d46991b8a2d",
            ),
            (
                ["method-and-literal", "cross-file-rename-clarified"],
                20260914,
                ("minimal_intent", "delegated_intent"),
                ("haiku",),
                "f8a47e9a7029a10e59b58ae3bdc42e9118581d6df913c08974c0fe164daf0eff",
            ),
        ]
        for tasks, seed, arms, models, expected in cases:
            rows = runner.balanced_order(tasks, seed, arms, models)
            self.assertEqual(
                hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                expected,
            )

    def test_six_repetitions_balance_starting_arm_within_each_task_and_model(self):
        arms = ("delegated_intent", "exact_invocation")
        rows = runner.balanced_order(
            ["small", "cross"], 20260915, arms, repetitions=6, balance_by_task=True
        )
        self.assertEqual(len(rows), 48)
        counts = Counter(
            (row["task_id"], row["model_key"], row["variant"]) for row in rows
        )
        starts = Counter(
            (row["task_id"], row["model_key"], row["variant"]) for row in rows[::2]
        )
        self.assertEqual(set(counts.values()), {6})
        self.assertEqual(set(starts.values()), {3})
        for before, after in zip(rows[::2], rows[1::2]):
            actual_arms = {before["variant"], after["variant"]}
            self.assertEqual(actual_arms, set(arms))
            for field in ("task_id", "model_key", "repetition"):
                self.assertEqual(before[field], after[field])
        self.assertEqual(len({row["run_id"] for row in rows}), len(rows))

    def test_invalid_repetition_or_balance_request_is_refused(self):
        for repetitions in (0, -1, 1.5, True):
            with self.subTest(repetitions=repetitions), self.assertRaises(ValueError):
                runner.balanced_order(["fixture"], 1, repetitions=repetitions)
        with self.assertRaises(ValueError):
            runner.balanced_order(
                ["fixture"],
                1,
                arms=("delegated_intent", "exact_invocation"),
                repetitions=3,
                balance_by_task=True,
            )

    def test_the_schedule_holds_only_the_selected_models(self):
        rows = runner.balanced_order(["fixture"], seed=1, model_keys=("haiku",))
        self.assertEqual({row["model_key"] for row in rows}, {"haiku"})
        self.assertEqual(len(rows), 3 * len(runner.ARMS))

    def test_an_unknown_model_key_is_refused(self):
        for keys in [("gpt",), ("haiku", "haiku"), ()]:
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                runner.balanced_order(["fixture"], seed=1, model_keys=keys)


class ExperimentalArmTests(unittest.TestCase):
    def test_minimal_intent_is_opt_in_and_uses_generic_instructions(self):
        rows = runner.balanced_order(
            ["fixture"], seed=1, arms=("minimal_intent",), model_keys=("haiku",)
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["variant"] for row in rows}, {"minimal_intent"})
        base = Path(tempfile.mkdtemp(prefix="php-ast-minimal-intent-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        skill = base / "runtime/skills/php-structured-edit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Fixture skill body.\n")
        text = runner.variants(base)["minimal_intent"]
        self.assertGreaterEqual(len(text.split()), 60)
        self.assertLessEqual(len(text.split()), 80)
        self.assertIn("rename --method 'Class::old' --to new", text)
        self.assertIn("configured checks", text)
        self.assertIn("no guarantee", text)
        for task_specific in ("Product", "CrossFile", "src/", "check.php"):
            self.assertNotIn(task_specific, text)

    def test_minimal_intent_does_not_change_the_default_arm_set(self):
        self.assertEqual(
            runner.SUPPORTED_ARMS,
            runner.ARMS + ("minimal_intent", "delegated_intent", "exact_invocation"),
        )
        rows = runner.balanced_order(["fixture"], seed=1, model_keys=("haiku",))
        self.assertEqual({row["variant"] for row in rows}, set(runner.ARMS))
        self.assertEqual(len(rows), 3 * len(runner.ARMS))

    def test_delegated_intent_extends_minimal_instructions_only(self):
        base = Path(tempfile.mkdtemp(prefix="php-ast-delegated-intent-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        skill = base / "runtime/skills/php-structured-edit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Fixture skill body.\n")
        instructions = runner.variants(base)
        self.assertEqual(
            instructions["exact_invocation"], instructions["delegated_intent"]
        )
        self.assertEqual(
            runner.system_instructions(
                "exact_invocation", instructions["exact_invocation"]
            ),
            runner.system_instructions(
                "delegated_intent", instructions["delegated_intent"]
            ),
        )
        addition = (
            "When the task names the class and method to rename, invoke the command before "
            "reading or searching PHP for declaration or caller discovery. Invoke it "
            "once for the named method family; it handles supported declarations and callers "
            "together. Do not queue separate renames for each implementation or caller. Read "
            "source yourself only when needed for another requirement, a failed command, or "
            "unresolved warnings."
        )
        self.assertEqual(
            instructions["delegated_intent"],
            instructions["minimal_intent"] + " " + addition,
        )
        self.assertEqual(runner.common_instructions("minimal_intent"), runner.COMMON)
        self.assertEqual(
            runner.common_instructions("delegated_intent"), runner.DELEGATED_COMMON
        )
        self.assertIn(
            "Ensure relevant source is read before editing; for a supported method rename, the command performs this discovery.",
            runner.common_instructions("delegated_intent"),
        )
        self.assertNotIn("Ensure relevant source is read before editing", runner.COMMON)

    def test_delegated_system_append_and_fixture_are_scoped(self):
        base = Path(tempfile.mkdtemp(prefix="php-ast-delegated-system-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        skill = base / "runtime/skills/php-structured-edit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Fixture skill body.\n")
        instructions = runner.variants(base)
        for arm in runner.ARMS:
            with self.subTest(arm=arm):
                self.assertEqual(
                    runner.system_instructions(arm, instructions[arm]),
                    runner.COMMON + "\n" + instructions[arm],
                )
        delegated = runner.system_instructions(
            "delegated_intent", instructions["delegated_intent"]
        )
        self.assertTrue(delegated.startswith(runner.DELEGATED_COMMON + "\n"))
        self.assertNotIn(
            runner.COMMON + "\n" + instructions["delegated_intent"], delegated
        )
        work = base / "work"
        work.mkdir()
        self.assertEqual(runner.check_fixture(work, "delegated_intent"), [])
        self.assertEqual(list(work.iterdir()), [])

    def test_unknown_experimental_arm_is_refused(self):
        delegated = runner.balanced_order(
            ["fixture"], seed=1, arms=("delegated_intent",), model_keys=("haiku",)
        )
        self.assertEqual(len(delegated), 3)
        with self.assertRaises(ValueError):
            runner.balanced_order(
                ["fixture"],
                seed=1,
                arms=("minimal_intent_typo",),
                model_keys=("haiku",),
            )


class ExactInvocationTests(unittest.TestCase):
    def metadata(self):
        return {
            "method": "Demo\\Product::old",
            "file": "src/odd ' $(touch sentinel).php",
            "to": "newName",
            "path": ".",
        }

    def test_both_arms_get_same_metadata_only_treatment_gets_quoted_command(self):
        intent = self.metadata()
        template = {"intent": intent}
        generic = runner.intent_prompt(template, "delegated_intent")
        treatment = runner.intent_prompt(template, "exact_invocation")
        shared, command = treatment.split("\n\nReady-to-run invocation:\n")
        self.assertEqual(generic, shared)
        self.assertIn(json.dumps(intent, sort_keys=True), shared)
        self.assertIn("--file", shared)
        self.assertNotIn("php-ast-edit rename", generic)
        self.assertEqual(
            shlex.split(command),
            [
                "php-ast-edit",
                "rename",
                "--method",
                intent["method"],
                "--to",
                intent["to"],
                "--path",
                ".",
                "--file",
                intent["file"],
            ],
        )

    def test_missing_metadata_leaves_legacy_prompt_unchanged_and_refuses_exact_arm(
        self,
    ):
        for variant in runner.ARMS + ("minimal_intent", "delegated_intent"):
            self.assertEqual(runner.intent_prompt({}, variant), "")
        with self.assertRaises(ValueError):
            runner.intent_prompt({}, "exact_invocation")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with self.assertRaises(ValueError):
                runner.prepare_fixture(root, {"variant": "exact_invocation"}, {}, "")
            self.assertEqual(list(root.iterdir()), [])

    def test_metadata_validation_rejects_invalid_schema_or_outside_file(self):
        intent = self.metadata()
        task = {"intent": intent, "files": [{"path": intent["file"]}]}
        self.assertEqual(runner.selected_intent(task), intent)
        self.assertIsNone(runner.selected_intent({"files": []}))
        for invalid in (
            None,
            {},
            {**intent, "oracle": "answer"},
            {**intent, "file": "../escape.php"},
            {**intent, "file": "/absolute.php"},
            {**intent, "file": "missing.php"},
            {**intent, "path": ".."},
            {**intent, "to": ""},
            {**intent, "to": 3},
            {**intent, "to": "\0"},
        ):
            with self.subTest(intent=invalid), self.assertRaises(ValueError):
                runner.selected_intent({**task, "intent": invalid})


class EvidenceRelocationTests(unittest.TestCase):
    """An unpacked evidence archive must summarize, and a missing one must not."""

    def campaign(self):
        base = Path(tempfile.mkdtemp(prefix="php-ast-relocated-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        (base / "runs/run001/evidence").mkdir(parents=True)
        return base

    def test_evidence_is_found_where_the_archive_put_it(self):
        base = self.campaign()
        row = {"run_id": "run001", "evidence": "/nonexistent/runs/run001/evidence"}
        self.assertEqual(
            check_arms.resolve_evidence(base, row),
            base / "runs/run001/evidence",
        )

    def test_the_recorded_path_wins_when_it_is_still_there(self):
        base = self.campaign()
        original = Path(tempfile.mkdtemp(prefix="php-ast-original-"))
        self.addCleanup(lambda: shutil.rmtree(original, ignore_errors=True))
        row = {"run_id": "run001", "evidence": str(original)}
        self.assertEqual(check_arms.resolve_evidence(base, row), original)

    def test_absent_evidence_is_raised_rather_than_counted_as_an_empty_campaign(self):
        base = self.campaign()
        row = {"run_id": "run002", "evidence": "/nonexistent/runs/run002/evidence"}
        with self.assertRaises(FileNotFoundError):
            check_arms.resolve_evidence(base, row)


class CheckArmTests(unittest.TestCase):
    """The two check arms must differ by the declaration and by nothing else."""

    def work(self):
        temporary = tempfile.TemporaryDirectory(prefix="php-ast-check-arm-")
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_only_the_integrated_arm_declares_the_check(self):
        for arm, expected in [
            ("check_manual", [runner.CHECK_SCRIPT]),
            ("check_integrated", [runner.CHECK_SCRIPT, ".php-ast-edit.json"]),
            ("full_skill", []),
            ("contextual_patch", []),
        ]:
            work = self.work()
            with self.subTest(arm=arm):
                self.assertEqual(runner.check_fixture(work, arm), expected)
                # Every returned name is added to the fixture commit, so one that was
                # never written would leave `git add` failing rather than silently
                # dropping the treatment.
                self.assertEqual(
                    sorted(path.name for path in work.iterdir()), sorted(expected)
                )

    def test_the_declared_command_is_the_one_the_task_clause_names(self):
        declared = runner.CHECK_CONFIG["verify"][0]
        self.assertEqual(declared["scope"], "project")
        self.assertIn(
            " ".join(declared["command"]),
            runner.CHECK_CLAUSE,
            "A clause naming a different command would make the arms two tasks.",
        )

    def test_no_instruction_text_distinguishes_the_check_arms(self):
        base = Path(tempfile.mkdtemp(prefix="php-ast-check-variants-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        skill = base / "runtime/skills/php-structured-edit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Fixture skill body.\n")
        instructions = runner.variants(base)
        self.assertEqual(instructions["check_manual"], instructions["check_integrated"])
        for arm in runner.CHECK_ARMS:
            with self.subTest(arm=arm):
                self.assertNotIn("alreadyRun", instructions[arm])
                self.assertNotIn(".php-ast-edit.json", instructions[arm])

    def test_the_check_fails_on_a_file_that_does_not_parse(self):
        """A check nothing can fail would make every treatment run vacuous."""
        work = self.work()
        runner.check_fixture(work, "check_manual")
        (work / "Good.php").write_text("<?php\n\nclass Good {}\n")
        passing = runner.invoke(["php", runner.CHECK_SCRIPT], work)
        self.assertEqual(passing.returncode, 0, passing.stdout + passing.stderr)
        (work / "Broken.php").write_text("<?php\n\nclass Broken {\n")
        failing = runner.invoke(["php", runner.CHECK_SCRIPT], work)
        self.assertEqual(failing.returncode, 1, failing.stdout + failing.stderr)
        self.assertIn("Broken.php", failing.stdout)


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
