"""Offline review-context arm and proxy boundaries; no candidate model calls."""

import base64
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runner

HERE = Path(__file__).resolve().parent
PROXY = HERE / "engine_proxy.py"
REVIEW_ARMS = ("review_locations", "review_excerpts")
LEGACY_ARMS = (
    "contextual_patch",
    "full_skill",
    "compact_full",
    "compact_focused",
    "check_manual",
    "check_integrated",
)

# A deterministic boundary double keeps these tests independent of excerpt
# selection, which has its own unit tests. The real proxy is always a subprocess.
HELPER_SOURCE = """import json
import os
from pathlib import Path

def record(event):
    with Path("order.txt").open("a") as output:
        output.write(event + "\\n")

def capture(root, allowed_files):
    record("capture")
    if allowed_files != ["source.txt"]:
        raise ValueError("unexpected fixture allowlist")
    if os.environ.get("FIXTURE_HELPER_FAILURE") == "capture":
        raise ValueError("deliberate capture failure")
    return (root / "source.txt").read_text()

def augment(raw, snapshot):
    record("augment")
    if os.environ.get("FIXTURE_HELPER_FAILURE") == "augment":
        raise ValueError("deliberate augmentation failure")
    report = json.loads(raw)
    report["reviewContext"] = {"capturedSource": snapshot}
    return (json.dumps(report) + "\\n").encode()
"""

ENGINE_SOURCE = """import base64
import json
import os
import sys
from pathlib import Path

with Path("order.txt").open("a") as output:
    output.write("engine\\n")
Path("source.txt").write_text("after engine write\\n")
Path("engine-argv.json").write_text(json.dumps(sys.argv[1:]))
if sys.argv[1:2] == ["apply"]:
    Path("engine-stdin.bin").write_bytes(sys.stdin.buffer.read())
sys.stdout.buffer.write(base64.b64decode(os.environ["FIXTURE_STDOUT"]))
sys.stderr.buffer.write(base64.b64decode(os.environ["FIXTURE_STDERR"]))
raise SystemExit(int(os.environ["FIXTURE_EXIT"]))
"""


class ReviewArmTests(unittest.TestCase):
    def test_new_arms_share_exact_instructions_prompt_and_initial_files(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            skill = base / "runtime/skills/php-structured-edit"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("Fixture skill.\n")
            task = {
                "id": "fixture",
                "prompt": "Rename Demo::old to renamed; preserve source bytes otherwise.",
                "files": [{"path": "source.txt", "php": "fixture source\n"}],
                "intent": {
                    "method": "Demo::old",
                    "file": "source.txt",
                    "to": "renamed",
                    "path": ".",
                },
            }
            runner.save(base / runner.TASK_MANIFEST, {"tasks": [task]})
            template = runner.exact_template(base, task, base / "templates/fixture")
            instructions = runner.variants(base)
            prepared = []
            for number, arm in enumerate(("exact_invocation", *REVIEW_ARMS), 1):
                row = {
                    "run_id": f"run{number:03}",
                    "task_id": "fixture",
                    "variant": arm,
                    "model_key": "haiku",
                    "repetition": 1,
                }
                self.assertEqual(instructions[arm], instructions["exact_invocation"])
                prepared.append(
                    runner.prepare_fixture(base, row, template, instructions[arm])
                )
            reference = Path(prepared[0]["evidence"])
            for row in prepared[1:]:
                evidence = Path(row["evidence"])
                for relative in (
                    "system-append.txt",
                    "prompt.txt",
                    runner.INITIAL_HASHES,
                    "initial/source.txt",
                ):
                    self.assertEqual(
                        (evidence / relative).read_bytes(),
                        (reference / relative).read_bytes(),
                        relative,
                    )
                self.assertEqual(
                    (Path(row["work"]) / "source.txt").read_bytes(),
                    b"fixture source\n",
                )
            self.assertEqual(template["intent"], task["intent"])

    def test_defaults_remain_legacy_and_new_arms_require_selected_intent(self):
        self.assertEqual(runner.ARMS, LEGACY_ARMS)
        schedule = runner.balanced_order(["fixture"], seed=1, model_keys=("haiku",))
        self.assertEqual({row["variant"] for row in schedule}, set(LEGACY_ARMS))
        self.assertEqual({row["repetition"] for row in schedule}, {1, 2, 3})
        for arm in REVIEW_ARMS:
            with self.subTest(arm=arm), self.assertRaises(ValueError):
                runner.intent_prompt({}, arm)

    def test_mode_is_selected_only_by_arm_and_inherited_mode_is_removed(self):
        base, evidence = Path("/tmp/context-fixture"), Path("/tmp/context-evidence")
        with patch.dict(
            os.environ,
            {
                "PHP_AST_REVIEW_CONTEXT": "review_excerpts",
                "PHP_AST_REVIEW_FIXTURE": "/unrelated.json",
            },
        ):
            for arm in (
                None,
                *LEGACY_ARMS,
                "minimal_intent",
                "delegated_intent",
                "exact_invocation",
            ):
                with self.subTest(arm=arm):
                    env = runner.candidate_environment(base, evidence, arm)
                    self.assertNotIn("PHP_AST_REVIEW_CONTEXT", env)
                    self.assertNotIn("PHP_AST_REVIEW_FIXTURE", env)
                    self.assertEqual(
                        env["PHP_AST_EDIT_BIN"], str(base / "runtime/bin/php-ast-edit")
                    )
            for arm in REVIEW_ARMS:
                env = runner.candidate_environment(base, evidence, arm)
                self.assertEqual(env["PHP_AST_REVIEW_CONTEXT"], arm)
                self.assertEqual(
                    env["PHP_AST_ENGINE_AUDIT"], str(evidence / "engine-audit.jsonl")
                )
                self.assertEqual(
                    env["PHP_AST_REVIEW_FIXTURE"], str(evidence / runner.INITIAL_HASHES)
                )
                self.assertEqual(
                    env["PHP_AST_EDIT_BIN"], str(base / "tools/php-ast-edit")
                )
                self.assertEqual(
                    env["PHP_AST_REAL_BIN"], str(base / "runtime/bin/php-ast-edit")
                )
            self.assertEqual(os.environ["PHP_AST_REVIEW_CONTEXT"], "review_excerpts")


class ProxyIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="php-ast-context-proxy-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.work = self.base / "work"
        self.work.mkdir()
        self.proxy = self.base / "proxy.py"
        shutil.copyfile(PROXY, self.proxy)
        (self.base / "review_context.py").write_text(HELPER_SOURCE)
        self.engine = self.base / "engine"
        self.engine.write_text(f"#!{sys.executable}\n" + ENGINE_SOURCE)
        self.engine.chmod(0o700)
        (self.work / "source.txt").write_text("before engine write\n")
        self.fixture = self.base / "initial-hashes.json"
        self.fixture.write_text(
            json.dumps(
                {"source.txt": hashlib.sha256(b"before engine write\n").hexdigest()}
            )
        )
        self.audit = self.base / "audit.jsonl"

    def invoke(
        self,
        *,
        mode=None,
        args=None,
        stdout=b'{ "ok": true }\n',
        stderr=b"engine diagnostic\n",
        exit_code=0,
        failure=None,
        stdin=b"",
    ):
        env = {
            "PATH": os.defpath,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PHP_AST_REAL_BIN": str(self.engine),
            "PHP_AST_ENGINE_AUDIT": str(self.audit),
            "FIXTURE_STDOUT": base64.b64encode(stdout).decode(),
            "FIXTURE_STDERR": base64.b64encode(stderr).decode(),
            "FIXTURE_EXIT": str(exit_code),
        }
        if mode is not None:
            env["PHP_AST_REVIEW_CONTEXT"] = mode
            env["PHP_AST_REVIEW_FIXTURE"] = str(self.fixture)
        if failure is not None:
            env["FIXTURE_HELPER_FAILURE"] = failure
        return subprocess.run(
            [
                sys.executable,
                str(self.proxy),
                *(args or ["rename", "--method", "Demo::old", "--to", "renamed"]),
            ],
            cwd=self.work,
            env=env,
            input=stdin,
            capture_output=True,
            check=False,
            timeout=10,
        )

    def records(self):
        return [json.loads(line) for line in self.audit.read_text().splitlines()]

    def test_legacy_preserves_binary_streams_exit_argv_and_apply_stdin(self):
        stdout, stderr = b"legacy stdout\xff\n", b"legacy stderr\xfe\n"
        payload = b'{ "files": [] }\n'
        result = self.invoke(
            args=["apply", "--input", "-"],
            stdout=stdout,
            stderr=stderr,
            exit_code=7,
            stdin=payload,
        )
        self.assertEqual(
            (result.stdout, result.stderr, result.returncode), (stdout, stderr, 7)
        )
        self.assertEqual((self.work / "engine-stdin.bin").read_bytes(), payload)
        self.assertEqual(
            json.loads((self.work / "engine-argv.json").read_text()),
            ["apply", "--input", "-"],
        )
        self.assertEqual((self.work / "order.txt").read_text(), "engine\n")
        request, response = self.records()
        self.assertEqual(request["payload"], {"files": []})
        self.assertEqual(request["id"], response["id"])
        self.assertEqual(response["stdout"], stdout.decode(errors="replace"))
        self.assertNotIn("presented_stdout", response)
        self.assertNotIn("context_mode", response)

    def test_locations_computes_context_but_forwards_original_bytes(self):
        raw = b'{ "ok": true, "diff": "original" }\n'
        result = self.invoke(mode="review_locations", stdout=raw)
        self.assertEqual(result.stdout, raw)
        self.assertEqual(result.stderr, b"engine diagnostic\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            (self.work / "order.txt").read_text(), "capture\nengine\naugment\n"
        )
        response = self.records()[-1]
        self.assertEqual(response["context_mode"], "review_locations")
        self.assertEqual(response["stdout"], response["presented_stdout"])
        self.assertEqual(response["stdout"], raw.decode())

    def test_excerpts_are_additive_and_use_snapshot_from_before_the_write(self):
        raw = b'{ "ok": true, "diff": "original" }\n'
        result = self.invoke(mode="review_excerpts", stdout=raw)
        presented = json.loads(result.stdout)
        self.assertEqual(
            presented.pop("reviewContext"), {"capturedSource": "before engine write\n"}
        )
        self.assertEqual(presented, json.loads(raw))
        self.assertEqual((self.work / "source.txt").read_text(), "after engine write\n")
        self.assertEqual(
            (self.work / "order.txt").read_text(), "capture\nengine\naugment\n"
        )
        self.assertEqual(result.stderr, b"engine diagnostic\n")
        self.assertEqual(result.returncode, 0)
        response = self.records()[-1]
        self.assertEqual(response["stdout"], raw.decode())
        self.assertEqual(response["presented_stdout"], result.stdout.decode())
        self.assertEqual(response["context_mode"], "review_excerpts")

    def test_nonzero_engine_exit_preserves_streams_without_augmentation(self):
        raw = b"refused rename\xff\n"
        result = self.invoke(mode="review_excerpts", stdout=raw, exit_code=2)
        self.assertEqual((result.stdout, result.returncode), (raw, 2))
        self.assertEqual(result.stderr, b"engine diagnostic\n")
        self.assertEqual((self.work / "order.txt").read_text(), "capture\nengine\n")
        self.assertFalse(
            any(row["event"] == "experiment_error" for row in self.records())
        )

    def test_apply_is_covered_without_losing_the_forwarded_payload(self):
        payload = b'{"files":[]}\n'
        result = self.invoke(mode="review_excerpts", args=["apply"], stdin=payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.work / "engine-stdin.bin").read_bytes(), payload)
        self.assertEqual(
            json.loads(result.stdout)["reviewContext"],
            {"capturedSource": "before engine write\n"},
        )
        self.assertEqual(
            (self.work / "order.txt").read_text(), "capture\nengine\naugment\n"
        )

    def test_real_helper_uses_prewrite_fixture_bytes_in_the_presented_report(self):
        shutil.copyfile(HERE / "review_context.py", self.base / "review_context.py")
        subprocess.run(
            ["git", "-c", "init.templateDir=", "init", "-q"],
            cwd=self.work,
            capture_output=True,
            check=True,
            timeout=10,
        )
        raw = json.dumps(
            {
                "checksPassed": True,
                "renames": [{"literals": [{"file": "source.txt", "lines": [1]}]}],
            }
        ).encode()
        result = self.invoke(mode="review_excerpts", stdout=raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        presented = json.loads(result.stdout)
        context = presented.pop("reviewContext")
        self.assertEqual(presented, json.loads(raw))
        self.assertEqual(context["entries"][0]["text"], "before engine write")
        self.assertEqual(
            context["entries"][0]["sha256"],
            hashlib.sha256(b"before engine write\n").hexdigest(),
        )
        self.assertEqual((self.work / "source.txt").read_text(), "after engine write\n")
        self.assertEqual(self.records()[-1]["stdout"], raw.decode())
        self.assertEqual(self.records()[-1]["presented_stdout"], result.stdout.decode())

    def test_nonrename_command_never_captures_or_augments(self):
        raw = b"help is not JSON\n"
        result = self.invoke(mode="review_excerpts", args=["--help"], stdout=raw)
        self.assertEqual((result.stdout, result.returncode), (raw, 0))
        self.assertEqual((self.work / "order.txt").read_text(), "engine\n")

    def test_snapshot_failure_stops_before_engine_and_records_intervention_error(self):
        result = self.invoke(mode="review_locations", failure="capture")
        self.assertEqual(result.returncode, 70)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            (self.work / "source.txt").read_text(), "before engine write\n"
        )
        self.assertEqual(
            [row["event"] for row in self.records()],
            ["engine_request", "experiment_error"],
        )

    def test_missing_packaged_helper_is_a_recorded_intervention_failure(self):
        (self.base / "review_context.py").unlink()
        result = self.invoke(mode="review_excerpts")
        self.assertEqual(result.returncode, 70)
        self.assertEqual(
            [row["event"] for row in self.records()],
            ["engine_request", "experiment_error"],
        )
        self.assertFalse((self.work / "engine-argv.json").exists())

    def test_augmentation_failure_retains_raw_streams_and_records_stop_marker(self):
        raw = b'{"ok":true}\n'
        result = self.invoke(mode="review_excerpts", stdout=raw, failure="augment")
        self.assertEqual(
            (result.stdout, result.stderr, result.returncode),
            (raw, b"engine diagnostic\n", 0),
        )
        records = self.records()
        self.assertEqual(
            [row["event"] for row in records],
            ["engine_request", "experiment_error", "engine_result"],
        )
        self.assertEqual(len({row["id"] for row in records}), 1)
        self.assertEqual(records[-1]["presented_stdout"], raw.decode())


class InterventionAbortTests(unittest.TestCase):
    def test_error_marker_is_retained_in_measurement_and_prevents_continuation(self):
        self.assert_stops([{"event": "experiment_error", "error": "fixture failure"}])

    def test_request_without_result_stops_even_without_an_explicit_error_marker(self):
        self.assert_stops([{"event": "engine_request", "id": "unfinished"}])

    def assert_stops(self, records):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            evidence, work = base / "evidence", base / "work"
            evidence.mkdir()
            work.mkdir()
            runner.save(evidence / runner.INITIAL_HASHES, {})
            runner.save(base / runner.CONFIG, {"fixture": True})
            (evidence / "engine-audit.jsonl").write_text(
                "".join(json.dumps(record) + "\n" for record in records)
            )
            row = {
                "run_id": "run001",
                "variant": "review_excerpts",
                "model_key": "haiku",
                "evidence": str(evidence),
                "work": str(work),
            }
            config = {
                "source_commit": "a" * 40,
                "models": {"haiku": {"id": "fixture", "effort": None}},
                "max_run_usd": 0.75,
            }

            def capture_fixture(*_args):
                (evidence / runner.RAW).write_text("{}\n")
                return {
                    "process_exit_code": 0,
                    "timed_out": False,
                    "candidate_wall_ms": 1,
                }

            with (
                patch.object(runner, "candidate_args", return_value=[]),
                patch.object(runner, "capture", side_effect=capture_fixture),
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
                runner.run_one(base, row, config)
            measurement = runner.load(evidence / runner.MEASUREMENT)
            self.assertIn(
                "Review-context intervention failed", measurement["accounting_errors"]
            )
            self.assertEqual(measurement["native_list_price_usd"], 0.01)
            self.assertTrue(measurement["oracle"]["passed"])
            with self.assertRaisesRegex(ValueError, "never rerun"):
                runner.run_one(base, row, config)


if __name__ == "__main__":
    unittest.main()
