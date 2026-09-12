"""Offline shared-report arm, real proxy and controller-stop boundaries."""

import base64
import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runner
import shared_report
import test_context_integration as integration

ARMS = ("shared_report_control", "shared_report_factored")
STDERR = b"engine diagnostic\xfe\n"
FACTOR_TRACE = """
from pathlib import Path
_original_factor = factor
def factor(raw):
    with Path("order.txt").open("a") as stream:
        stream.write("factor\\n")
    return _original_factor(raw)
"""


def report_bytes(count=2):
    return (
        json.dumps(
            {
                "files": [
                    {
                        "path": f"source{number}.txt",
                        "changed": True,
                        "warnings": [
                            {"code": "REVIEW", "message": "Review separately"}
                        ],
                        "diff": f"--- source{number}.txt\n-old\n+neu ü\n",
                        "unknown": {"number": number},
                    }
                    for number in range(count)
                ],
                "verify": [
                    {"scope": "project", "command": ["php", "check.php"], "ok": True}
                ],
                "alreadyRun": "Project check passed on these files.",
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n"
    ).encode()


class SharedArmTests(unittest.TestCase):
    def test_both_arms_keep_legacy_prompt_and_exact_argv(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            skill = base / "runtime/skills/php-structured-edit"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("Fixture skill.\n")
            instructions = runner.variants(base)
            template = {
                "intent": {
                    "method": "Demo\\Contract::old",
                    "file": "a b.php",
                    "to": "newName",
                    "path": ".",
                }
            }
            expected_prompt = runner.intent_prompt(template, "exact_invocation")
            for arm in ARMS:
                self.assertEqual(instructions[arm], instructions["exact_invocation"])
                self.assertEqual(
                    runner.system_instructions(arm, instructions[arm]),
                    runner.system_instructions(
                        "exact_invocation", instructions["exact_invocation"]
                    ),
                )
                prompt = runner.intent_prompt(template, arm)
                self.assertEqual(prompt, expected_prompt)
                self.assertEqual(
                    shlex.split(prompt.split("Ready-to-run invocation:\n")[1]),
                    [
                        "php-ast-edit",
                        "rename",
                        "--method",
                        "Demo\\Contract::old",
                        "--to",
                        "newName",
                        "--path",
                        ".",
                        "--file",
                        "a b.php",
                    ],
                )
                with self.assertRaisesRegex(ValueError, "selected intent"):
                    runner.intent_prompt({}, arm)

    def test_modes_are_selected_by_arm_without_inherited_context_or_fixture(self):
        inherited = {
            "PHP_AST_SHARED_REPORT": ARMS[1],
            "PHP_AST_REVIEW_CONTEXT": "unchanged_excerpts",
            "PHP_AST_REVIEW_FIXTURE": "/missing/private-fixture.json",
        }
        base, evidence = Path("/tmp/shared-runtime"), Path("/tmp/shared-evidence")
        with patch.dict(os.environ, inherited):
            for arm in (*ARMS, "exact_invocation", "check_reuse_guidance", None):
                env = runner.candidate_environment(base, evidence, arm)
                self.assertNotIn("PHP_AST_REVIEW_CONTEXT", env)
                self.assertNotIn("PHP_AST_REVIEW_FIXTURE", env)
                self.assertEqual(
                    env.get("PHP_AST_SHARED_REPORT"), arm if arm in ARMS else None
                )
                self.assertEqual(
                    env["PHP_AST_REAL_BIN"], str(base / "runtime/bin/php-ast-edit")
                )
                expected = (
                    "runtime/review-proxy/php-ast-edit"
                    if arm in ARMS
                    else "runtime/bin/php-ast-edit"
                )
                self.assertEqual(env["PHP_AST_EDIT_BIN"], str(base / expected))
            for key, value in inherited.items():
                self.assertEqual(os.environ[key], value)


class SharedProxyTests(unittest.TestCase):
    def fixture(self):
        fixture = integration.ProxyIntegrationTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        helper = fixture.base / "shared_report.py"
        shutil.copyfile(integration.HERE / "shared_report.py", helper)
        with helper.open("a") as output:
            output.write(FACTOR_TRACE)
        # A shared-report call has no source-capture prerequisite.
        fixture.fixture.unlink()
        return fixture

    def invoke(self, fixture, arm, raw, *, args=None, exit_code=0, stdin=b""):
        env = {
            "PATH": os.defpath,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PHP_AST_REAL_BIN": str(fixture.engine),
            "PHP_AST_ENGINE_AUDIT": str(fixture.audit),
            "PHP_AST_SHARED_REPORT": arm,
            "FIXTURE_STDOUT": base64.b64encode(raw).decode(),
            "FIXTURE_STDERR": base64.b64encode(STDERR).decode(),
            "FIXTURE_EXIT": str(exit_code),
        }
        return subprocess.run(
            [
                sys.executable,
                str(fixture.proxy),
                *(
                    args
                    or [
                        "rename",
                        "--method",
                        "Demo\\Contract::old",
                        "--to",
                        "newName",
                        "--file",
                        "a b.php",
                    ]
                ),
            ],
            cwd=fixture.work,
            env=env,
            input=stdin,
            capture_output=True,
            check=False,
            timeout=10,
        )

    def test_both_compute_once_without_snapshot_but_only_treatment_changes_stdout(self):
        for arm in ARMS:
            with self.subTest(arm=arm):
                fixture = self.fixture()
                raw = report_bytes()
                result = self.invoke(fixture, arm, raw)
                self.assertEqual((result.returncode, result.stderr), (0, STDERR))
                self.assertEqual(
                    (fixture.work / "order.txt").read_text(), "engine\nfactor\n"
                )
                records = fixture.records()
                self.assertEqual(
                    [entry["event"] for entry in records],
                    ["engine_request", "engine_result"],
                )
                self.assertEqual(
                    records[0]["argv"],
                    json.loads((fixture.work / "engine-argv.json").read_text()),
                )
                response = records[-1]
                self.assertEqual(response["stdout"], raw.decode())
                self.assertEqual(response["presented_stdout"], result.stdout.decode())
                self.assertNotIn("context_mode", response)
                self.assertTrue(shared_report.presentation_valid(response, arm))
                if arm == ARMS[0]:
                    self.assertEqual(result.stdout, raw)
                else:
                    self.assertNotEqual(result.stdout, raw)
                    self.assertEqual(
                        shared_report.restore(json.loads(result.stdout)),
                        json.loads(raw),
                    )
                self.assertEqual(
                    (fixture.work / "source.txt").read_text(), "after engine write\n"
                )

    def test_single_file_apply_keeps_stdout_and_stdin_bytes_in_both_arms(self):
        payload = b'{ "files": [] }\n'
        for arm in ARMS:
            with self.subTest(arm=arm):
                fixture = self.fixture()
                raw = report_bytes(1)
                result = self.invoke(
                    fixture, arm, raw, args=["apply", "--input", "-"], stdin=payload
                )
                self.assertEqual(
                    (result.stdout, result.stderr, result.returncode), (raw, STDERR, 0)
                )
                self.assertEqual(
                    (fixture.work / "engine-stdin.bin").read_bytes(), payload
                )
                self.assertEqual(
                    (fixture.work / "order.txt").read_text(), "engine\nfactor\n"
                )
                self.assertTrue(
                    shared_report.presentation_valid(fixture.records()[-1], arm)
                )

    def test_failed_engine_and_nonmutation_commands_bypass_projection(self):
        for arm in ARMS:
            for args, code in ((["rename"], 7), (["--help"], 0)):
                with self.subTest(arm=arm, args=args):
                    fixture = self.fixture()
                    raw = b"not JSON: original engine message\xff\n"
                    result = self.invoke(fixture, arm, raw, args=args, exit_code=code)
                    self.assertEqual(
                        (result.stdout, result.stderr, result.returncode),
                        (raw, STDERR, code),
                    )
                    self.assertEqual(
                        (fixture.work / "order.txt").read_text(), "engine\n"
                    )
                    records = fixture.records()
                    self.assertEqual(
                        [entry["event"] for entry in records],
                        ["engine_request", "engine_result"],
                    )
                    self.assertFalse(records[-1]["shared_report_eligible"])
                    self.assertTrue(shared_report.presentation_valid(records[-1], arm))

    def test_projection_failure_preserves_native_bytes_and_stops_after_cost_capture(
        self,
    ):
        raw = b'{ "fileDefaults": {}, "files": [{}, {}] }\n'
        for arm in ARMS:
            with self.subTest(arm=arm):
                fixture = self.fixture()
                result = self.invoke(fixture, arm, raw)
                self.assertEqual(
                    (result.stdout, result.stderr, result.returncode), (raw, STDERR, 0)
                )
                records = fixture.records()
                self.assertEqual(
                    [entry["event"] for entry in records],
                    ["engine_request", "experiment_error", "engine_result"],
                )
                self.assertEqual(records[-1]["stdout"], raw.decode())
                self.assertEqual(records[-1]["presented_stdout"], raw.decode())
                self.assert_stops_with_cost(fixture, arm)

    def test_successful_rename_cannot_hide_projection_as_ineligible(self):
        fixture = self.fixture()
        self.invoke(fixture, ARMS[1], report_bytes())
        records = fixture.records()
        response = records[-1]
        response["shared_report_eligible"] = False
        response["presented_stdout"] = response["stdout"]
        fixture.audit.write_text(
            "".join(json.dumps(record) + "\n" for record in records)
        )
        self.assert_stops_with_cost(fixture, ARMS[1])

    def assert_stops_with_cost(self, fixture, arm):
        evidence = fixture.base / "evidence"
        evidence.mkdir()
        shutil.copyfile(fixture.audit, evidence / "engine-audit.jsonl")
        runner.save(evidence / runner.INITIAL_HASHES, {})
        runner.save(fixture.base / runner.CONFIG, {"fixture": True})
        row = {
            "run_id": "run001",
            "variant": arm,
            "model_key": "haiku",
            "evidence": str(evidence),
            "work": str(fixture.work),
        }
        config = {
            "source_commit": "a" * 40,
            "models": {"haiku": {"id": "fixture", "effort": None}},
            "max_run_usd": 0.75,
        }

        def capture(*_args):
            (evidence / runner.RAW).write_text("{}\n")
            return {"process_exit_code": 0, "timed_out": False, "candidate_wall_ms": 1}

        with (
            patch.object(runner, "candidate_args", return_value=[]),
            patch.object(runner, "capture", side_effect=capture),
            patch.object(runner, "controller_provenance", return_value={}),
            patch.object(
                runner, "summarize", return_value={"native_list_price_usd": 0.01}
            ),
            patch.object(
                runner, "grade_and_diff", return_value={"oracle": {"passed": True}}
            ),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(ValueError, "stop subsequent runs"),
        ):
            runner.run_one(fixture.base, row, config)
        measurement = runner.load(evidence / runner.MEASUREMENT)
        self.assertEqual(measurement["native_list_price_usd"], 0.01)
        self.assertIn(
            "Shared-report intervention failed", measurement["accounting_errors"]
        )
        self.assertEqual(measurement["engine_audit"]["records"], fixture.records())
        with self.assertRaisesRegex(ValueError, "never rerun"):
            runner.run_one(fixture.base, row, config)


if __name__ == "__main__":
    unittest.main()
