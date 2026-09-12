"""Independent instruction-only final-guidance contract; no candidate calls."""

import hashlib
import os
import shlex
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import runner

ARMS = ("final_guidance_control", "final_guidance_bounded")
GUIDANCE = (
    "Keep the final response to the requested changes, observed check results and "
    "remaining requirements or warnings. Ground every name or value in a specific "
    "observed source or report entry. A passing check does not prove unchanged file "
    "bytes or complete correctness. Use existing evidence; do not reread files "
    "merely to decorate the final response with extra details. Preserve necessary "
    "investigation and disclose unresolved limitations."
)
LEGACY_DEFAULTS = (
    "contextual_patch",
    "full_skill",
    "compact_full",
    "compact_focused",
    "check_manual",
    "check_integrated",
)
# Captured before this intervention, with a tiny fixture SKILL.md and only the
# temporary campaign path normalized. Guard all previous complete system prompts.
LEGACY_PROMPTS = {
    "7f7b51f5781fab52ac09eae2d7f0ff8ea4a1a11babc0f8a79a4609d1969542b4": (
        "contextual_patch",
    ),
    "fcaa10aa068a00cac6fd72f4ec9b3b7d99791feba5ba2bf89becb55d3b81687f": (
        "full_skill",
        "check_manual",
        "check_integrated",
    ),
    "f361dfcbdf99f4ecb7be0ab33cd6b5aa1ce43ba11571e1d4735c17abaa877781": (
        "minimal_intent",
    ),
    "28f2414b9827e19d597d9027c33da410621c3413ebe60bd178005e7c35b37ecc": (
        "delegated_intent",
        "exact_invocation",
        "review_locations",
        "review_excerpts",
        "unchanged_locations",
        "unchanged_excerpts",
        "check_reuse_control",
        "shared_report_control",
        "shared_report_factored",
    ),
    "6198984aab4032be95a14bbb4b0c7f7252e337bf228d8abfd76fabc6e5b53945": (
        "compact_full",
    ),
    "da8e815fbb3ebaa969cb2635dcacb239461e62c38fdb3106d180f41244a9ee92": (
        "compact_focused",
    ),
    "6067eea66c7f6a1b8ffb1733f97065623105b28a496a9ebbe69c755b9d2a9b94": (
        "check_reuse_guidance",
    ),
}


class FinalGuidanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="php-ast-final-guidance-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        skill = self.base / "runtime/skills/php-structured-edit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Fixture skill.\n")

    def test_opt_in_registration_keeps_every_previous_prompt_and_default(self):
        instructions = runner.variants(self.base)
        self.assertEqual(runner.ARMS, LEGACY_DEFAULTS)
        for checksum, arms in LEGACY_PROMPTS.items():
            for arm in arms:
                with self.subTest(legacy_arm=arm):
                    text = runner.system_instructions(arm, instructions[arm])
                    normalized = text.replace(str(self.base), "$CAMPAIGN")
                    self.assertEqual(
                        hashlib.sha256(normalized.encode()).hexdigest(), checksum
                    )
        self.assertEqual(runner.FINAL_GUIDANCE_ARMS, ARMS)
        self.assertTrue(set(ARMS) <= set(runner.EXACT_COMMAND_ARMS))
        previous = {arm for arms in LEGACY_PROMPTS.values() for arm in arms}
        self.assertEqual(set(runner.SUPPORTED_ARMS), previous | set(ARMS))
        self.assertEqual(set(instructions), previous | set(ARMS))
        default = runner.balanced_order(["fixture"], seed=20260920)
        self.assertEqual({row["variant"] for row in default}, set(LEGACY_DEFAULTS))

    def test_only_treatment_adds_the_exact_final_guidance(self):
        instructions = runner.variants(self.base)
        control = instructions["delegated_intent"] + " " + runner.CHECK_REUSE_GUIDANCE
        self.assertEqual(runner.FINAL_GUIDANCE, GUIDANCE)
        self.assertEqual(instructions[ARMS[0]], control)
        self.assertEqual(instructions[ARMS[1]], control + " " + GUIDANCE)
        self.assertEqual(instructions[ARMS[0]], instructions["check_reuse_guidance"])
        self.assertEqual(
            runner.system_instructions(ARMS[1], instructions[ARMS[1]]),
            runner.system_instructions(ARMS[0], instructions[ARMS[0]]) + " " + GUIDANCE,
        )

    def test_same_user_prompt_exact_command_and_native_tools(self):
        template = {
            "intent": {
                "method": "Invoice\\Repository::lookup",
                "file": "src/Invoice Repository.php",
                "to": "resolve",
                "path": ".",
            }
        }
        expected = runner.intent_prompt(template, "exact_invocation")
        instructions = runner.variants(self.base)
        config = {
            "claude": "/fixture/claude",
            "cli_common": runner.CLI_ARGS,
            "models": {"haiku": {"id": "fixture-haiku", "effort": None}},
            "max_run_usd": 0.75,
        }
        argv = []
        for arm in ARMS:
            self.assertEqual(runner.intent_prompt(template, arm), expected)
            command = expected.split("Ready-to-run invocation:\n")[1]
            self.assertEqual(
                shlex.split(command),
                [
                    "php-ast-edit",
                    "rename",
                    "--method",
                    "Invoice\\Repository::lookup",
                    "--to",
                    "resolve",
                    "--path",
                    ".",
                    "--file",
                    "src/Invoice Repository.php",
                ],
            )
            with self.assertRaisesRegex(ValueError, "selected intent"):
                runner.intent_prompt({}, arm)
            evidence = self.base / arm
            evidence.mkdir()
            (evidence / "prompt.txt").write_text(expected)
            (evidence / "system-append.txt").write_text(
                runner.system_instructions(arm, instructions[arm])
            )
            argv.append(
                runner.candidate_args(
                    {"evidence": str(evidence), "model_key": "haiku", "variant": arm},
                    config,
                )
            )
        self.assertEqual(argv[0][:-2], argv[1][:-2])
        self.assertEqual(argv[0][-1], argv[1][-1])
        self.assertEqual(argv[0][-2] + " " + GUIDANCE, argv[1][-2])
        self.assertEqual(argv[0][argv[0].index("--tools") + 1], "Bash,Read,Edit,Write")
        self.assertNotIn("--effort", argv[0])

    def test_inherited_report_modes_are_removed_without_new_runtime_or_tools(self):
        inherited = {
            "PHP_AST_SHARED_REPORT": "shared_report_factored",
            "PHP_AST_REVIEW_CONTEXT": "unchanged_excerpts",
            "PHP_AST_REVIEW_FIXTURE": "/unrelated/fixture.json",
        }
        evidence = self.base / "evidence"
        with patch.dict(os.environ, inherited):
            expected = runner.candidate_environment(
                self.base, evidence, "exact_invocation"
            )
            for arm in ARMS:
                env = runner.candidate_environment(self.base, evidence, arm)
                self.assertEqual(env, expected)
                for name in inherited:
                    self.assertNotIn(name, env)
                self.assertEqual(
                    env["PHP_AST_EDIT_BIN"], str(self.base / "runtime/bin/php-ast-edit")
                )
                self.assertEqual(env["PHP_AST_REAL_BIN"], env["PHP_AST_EDIT_BIN"])
            for name, value in inherited.items():
                self.assertEqual(os.environ[name], value)

    def test_forty_attempts_form_ten_balanced_pairs_per_task(self):
        tasks = ("heldout-small", "heldout-cross")
        schedule = runner.balanced_order(
            tasks,
            20260920,
            arms=ARMS,
            model_keys=("haiku",),
            repetitions=10,
            balance_by_task=True,
        )
        self.assertEqual(len(schedule), 40)
        self.assertEqual(len({row["run_id"] for row in schedule}), 40)
        self.assertEqual({row["model_key"] for row in schedule}, {"haiku"})
        starts = {task: Counter() for task in tasks}
        for first, second in zip(schedule[::2], schedule[1::2]):
            self.assertEqual(
                (first["task_id"], first["repetition"]),
                (second["task_id"], second["repetition"]),
            )
            self.assertEqual({first["variant"], second["variant"]}, set(ARMS))
            starts[first["task_id"]][first["variant"]] += 1
        for task in tasks:
            self.assertEqual(starts[task], {ARMS[0]: 5, ARMS[1]: 5})
            for arm in ARMS:
                self.assertEqual(
                    sorted(
                        row["repetition"]
                        for row in schedule
                        if row["task_id"] == task and row["variant"] == arm
                    ),
                    list(range(1, 11)),
                )


if __name__ == "__main__":
    unittest.main()
