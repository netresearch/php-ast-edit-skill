#!/usr/bin/env python3
"""Offline regressions for complete accounting and preservation of a first attempt."""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import analyze


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.out = self.root / "out"
        self.out.mkdir()

    def candidate(self, stem, turns=5, cost=0.1, milliseconds=1000):
        document = {
            "is_error": False,
            "subtype": "success",
            "num_turns": turns,
            "total_cost_usd": cost,
            "duration_ms": milliseconds,
        }
        (self.out / f"{stem}.json").write_text(json.dumps(document))
        (self.out / f"{stem}.status").write_text("0\n")
        (self.out / f"{stem}.oracle").write_text("0\n")

    def complete(self):
        for task in ("C", "D"):
            for arm in ("free", "gate"):
                for number in range(1, 31):
                    self.candidate(f"{task}{number:02d}-{arm}")
        (self.out / "done").touch()

    def test_empty_campaign_retains_all_planned_rows(self):
        result = analyze.report(self.root)
        self.assertEqual(len(result["runs"]), 120)
        self.assertEqual(result["coverage"]["missing_status"], 120)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(len(result["rows"]), 6)
        self.assertTrue(all(row["p_gate_lower"] is None for row in result["rows"]))

    def test_borrowed_status_oracle_and_result_are_unknown_not_accepted(self):
        for number, extension in enumerate(("status", "oracle", "json"), 1):
            stem = f"C{number:02d}-free"
            self.candidate(stem)
            source = self.out / f"{stem}.{extension}"
            outside = self.root / f"borrowed-{extension}"
            source.rename(outside)
            source.symlink_to(outside)
        result = analyze.report(self.root)
        rows = {run["id"]: run for run in result["runs"]}
        for number in range(1, 4):
            self.assertFalse(rows[f"C{number:02d}-free"]["accepted"])
        self.assertIsNone(rows["C01-free"]["exit_status"])
        self.assertIsNone(rows["C02-free"]["oracle_status"])
        self.assertIsNone(rows["C03-free"]["metrics"]["turns"])
        self.assertEqual(len(result["coverage"]["unsafe_artifacts"]), 3)

    def test_output_directory_symlink_cannot_select_a_different_campaign(self):
        self.complete()
        outside = self.root / "borrowed-out"
        self.out.rename(outside)
        self.out.symlink_to(outside, target_is_directory=True)
        result = analyze.report(self.root)
        self.assertEqual(result["coverage"]["missing_status"], 120)
        self.assertEqual(result["coverage"]["output_root_error"], "unsafe_output_root")
        self.assertFalse(result["coverage"]["complete"])

    def test_borrowed_done_marker_cannot_complete_a_campaign(self):
        self.complete()
        (self.out / "done").unlink()
        outside = self.root / "borrowed-done"
        outside.touch()
        (self.out / "done").symlink_to(outside)
        result = analyze.report(self.root)
        self.assertFalse(result["coverage"]["done_marker"])
        self.assertFalse(result["coverage"]["complete"])

    def test_internal_evidence_symlinks_are_also_rejected(self):
        self.candidate("C01-free")
        (self.out / "C01-free.status").unlink()
        (self.out / "C01-free.status").symlink_to("C01-free.oracle")
        result = analyze.report(self.root)
        self.assertIsNone(result["runs"][0]["exit_status"])
        self.assertIn("C01-free.status", result["coverage"]["unsafe_artifacts"])

    def test_evidence_reader_rejects_traversal_and_nonregular_entries(self):
        (self.root / "borrowed").write_text("outside output root")
        (self.out / "C01-free.status").mkdir()
        evidence = analyze.EvidenceDirectory(self.root)
        with self.assertRaises(ValueError):
            evidence.read_text("../borrowed")
        with self.assertRaises(ValueError):
            evidence.read_text("C01-free.status")
        self.assertIn("C01-free.status", evidence.unsafe_artifacts)

    def test_partial_result_without_status_is_an_interrupted_slot(self):
        self.candidate("C01-free")
        (self.out / "C01-free.status").unlink()
        result = analyze.report(self.root)
        row = next(run for run in result["runs"] if run["id"] == "C01-free")
        self.assertEqual(row["reason"], "missing_status")
        self.assertEqual(row["metrics"]["turns"], 5)
        self.assertFalse(result["coverage"]["complete"])

    def test_done_marker_cannot_hide_missing_attempts(self):
        self.candidate("C01-free")
        (self.out / "done").touch()
        result = analyze.report(self.root)
        self.assertEqual(result["coverage"]["missing_status"], 119)
        self.assertFalse(result["coverage"]["complete"])
        self.assertFalse(any(row["holm_rejects_at_0_05"] for row in result["rows"]))

    def test_all_statuses_without_done_do_not_allow_interim_inference(self):
        self.complete()
        (self.out / "done").unlink()
        result = analyze.report(self.root)
        self.assertFalse(result["coverage"]["complete"])
        self.assertIsNone(result["rows"][0]["median_gate"])
        self.assertEqual(result["decisions"]["C"]["status"], "incomplete_campaign")

    def test_failure_metrics_are_retained_but_not_accepted(self):
        self.candidate("C01-gate", turns=77)
        (self.out / "C01-gate.status").write_text("124\n")
        result = analyze.report(self.root)
        row = next(run for run in result["runs"] if run["id"] == "C01-gate")
        self.assertEqual(row["reason"], "exit_status")
        self.assertEqual(row["metrics"]["turns"], 77)
        self.assertFalse(row["accepted"])

    def test_invalid_result_and_missing_metrics_are_counted(self):
        for stem, document in (
            ("C01-free", []),
            ("C02-free", {"is_error": False, "subtype": "success"}),
            ("C03-free", {"is_error": "false", "subtype": "success"}),
        ):
            self.candidate(stem)
            (self.out / f"{stem}.json").write_text(json.dumps(document))
        result = analyze.report(self.root)
        rows = {run["id"]: run for run in result["runs"]}
        self.assertEqual(rows["C01-free"]["reason"], "invalid_result")
        self.assertEqual(rows["C02-free"]["reason"], "invalid_metrics")
        self.assertEqual(rows["C03-free"]["reason"], "invalid_result")

    def test_nonfinite_negative_and_boolean_metrics_are_not_measurements(self):
        for index, value in enumerate(
            (float("nan"), float("inf"), -1, True, 10**400), 1
        ):
            self.candidate(f"C{index:02d}-free", cost=value)
        result = analyze.report(self.root)
        rows = {run["id"]: run for run in result["runs"]}
        for index in range(1, 6):
            row = rows[f"C{index:02d}-free"]
            self.assertEqual(row["reason"], "invalid_metrics")
            self.assertIsNone(row["metrics"]["usd"])
        json.dumps(result, allow_nan=False)

    def test_unreadable_oracle_is_an_exclusion_not_a_zero(self):
        self.candidate("C01-free")
        (self.out / "C01-free.oracle").write_text("not observed")
        result = analyze.report(self.root)
        row = next(run for run in result["runs"] if run["id"] == "C01-free")
        self.assertEqual(row["reason"], "missing_oracle")
        self.assertIsNone(row["oracle_status"])

    def test_unreasonably_large_status_does_not_crash_the_ledger(self):
        self.candidate("C01-free")
        (self.out / "C01-free.status").write_text("9" * 5000)
        result = analyze.report(self.root)
        self.assertEqual(result["runs"][0]["reason"], "missing_status")

    def test_hypothesis_family_remains_six_when_one_task_has_no_accepted_runs(self):
        self.complete()
        for arm in ("free", "gate"):
            for number in range(1, 31):
                (self.out / f"D{number:02d}-{arm}.oracle").write_text("1\n")
        result = analyze.report(self.root)
        self.assertEqual(len(result["rows"]), 6)
        self.assertEqual(
            [row["p_gate_lower"] for row in result["rows"] if row["task"] == "D"],
            [None] * 3,
        )
        self.assertEqual(result["decisions"]["D"]["status"], "inconclusive_exclusions")

    def test_unknown_run_id_prevents_a_complete_campaign(self):
        self.complete()
        self.candidate("C31-free")
        result = analyze.report(self.root)
        self.assertFalse(result["coverage"]["complete"])
        self.assertIn("C31-free.status", result["coverage"]["unexpected_artifacts"])

    def test_unplanned_oracle_output_also_prevents_a_complete_campaign(self):
        self.complete()
        (self.out / "D31-gate.oracle-output").write_text("unexpected attempt")
        result = analyze.report(self.root)
        self.assertFalse(result["coverage"]["complete"])

    def test_more_than_ten_percent_exclusions_makes_task_inconclusive(self):
        self.complete()
        for number in range(1, 5):
            (self.out / f"C{number:02d}-gate.oracle").write_text("1\n")
        result = analyze.report(self.root)
        self.assertEqual(result["decisions"]["C"]["status"], "inconclusive_exclusions")
        self.assertEqual(result["decisions"]["C"]["excluded"]["gate"], 4)
        self.assertEqual(result["decisions"]["D"]["status"], "not_established")

    def test_exactly_ten_percent_exclusions_does_not_cross_the_rule(self):
        self.complete()
        for number in range(1, 4):
            (self.out / f"C{number:02d}-gate.oracle").write_text("1\n")
        result = analyze.report(self.root)
        self.assertEqual(result["decisions"]["C"]["status"], "not_established")

    def test_faster_turns_do_not_win_when_wall_time_is_significantly_worse(self):
        self.complete()
        for number in range(1, 31):
            self.candidate(f"C{number:02d}-gate", turns=2, cost=0.01, milliseconds=5000)
        result = analyze.report(self.root)
        decision = result["decisions"]["C"]
        self.assertTrue(decision["wall_significantly_worse"])
        self.assertLess(decision["p_wall_two_sided"], 0.05)
        self.assertEqual(decision["status"], "not_established")

    def test_complete_equal_wall_campaign_can_establish_lower_cost(self):
        self.complete()
        for number in range(1, 31):
            self.candidate(f"C{number:02d}-gate", turns=2, cost=0.01)
        result = analyze.report(self.root)
        self.assertEqual(result["decisions"]["C"]["status"], "supported_lower_cost")
        self.assertEqual(result["decisions"]["C"]["p_wall_two_sided"], 1)

    def test_equal_wall_medians_do_not_hide_significantly_worse_ranks(self):
        self.complete()
        for number, (free_ms, gate_ms) in enumerate(
            zip([900] * 14 + [1000] * 16, [1000] * 16 + [2000] * 14), 1
        ):
            self.candidate(f"C{number:02d}-free", milliseconds=free_ms)
            self.candidate(
                f"C{number:02d}-gate", turns=2, cost=0.01, milliseconds=gate_ms
            )
        result = analyze.report(self.root)
        decision = result["decisions"]["C"]
        self.assertTrue(decision["wall_significantly_worse"])
        self.assertEqual(decision["status"], "not_established")


class StatisticsTests(unittest.TestCase):
    def test_two_sided_known_no_tie_value_and_symmetry(self):
        # U=0, n1=n2=3; variance=5.25; continuity-corrected normal p.
        expected = 0.0808555983700523
        self.assertAlmostEqual(
            analyze.mann_whitney_two_sided([1, 2, 3], [4, 5, 6]), expected
        )
        self.assertAlmostEqual(
            analyze.mann_whitney_two_sided([4, 5, 6], [1, 2, 3]), expected
        )

    def test_all_ties_and_balanced_ranks(self):
        self.assertEqual(analyze.mann_whitney_two_sided([1, 1], [1, 1]), 1)
        self.assertEqual(analyze.mann_whitney_two_sided([1, 4], [2, 3]), 1)


class DriverTests(unittest.TestCase):
    def test_setup_quotes_the_exact_hook_path_inside_valid_json(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            tool = root / "tool with 'single' and \"double\" quotes"
            prepare = tool / "benchmarks/skill-invocation/prepare.sh"
            prepare.parent.mkdir(parents=True)
            prepare.write_text("""#!/bin/sh
cfg="$BENCH/cfg-$1"
mkdir -p "$cfg"
printf '%s\\n' "$cfg"
""")
            prepare.chmod(0o755)
            fakebin = root / "bin"
            fakebin.mkdir()
            commands = {
                "git": 'case "$*" in *"rev-parse HEAD"*) echo faaea34e994e17cf2bd907727bc69a413bc130fe;; esac\n',
                "sha256sum": "echo 8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d\n",
            }
            for command, body in commands.items():
                path = fakebin / command
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o755)
            bench = root / "campaign"
            env = dict(
                os.environ,
                BENCH=str(bench),
                REPO=str(root),
                TOOL=str(tool),
                PHP_AST_EDIT_PHPACTOR=str(root / "fake.phar"),
                PATH=f"{fakebin}:{os.environ['PATH']}",
            )
            result = subprocess.run(
                ["bash", str(Path(__file__).with_name("drive.sh")), "setup"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            settings = json.loads((bench / "cfg-gate/settings.json").read_text())
            command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
            self.assertEqual(
                shlex.split(command), ["python3", str(tool / "hooks/php-ast-only.py")]
            )

    def test_staged_edit_is_archived_before_cleanup_and_driver_error_stops(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            subject, tool, harness, fakebin = (
                root / part for part in ("subject", "tool", "harness", "bin")
            )
            for directory in (subject, tool, harness, fakebin):
                directory.mkdir()
            env = dict(
                os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull
            )

            def git(directory, *args):
                return subprocess.run(
                    ["git", "-C", str(directory), *args],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip()

            def commit(directory):
                git(directory, "add", "--all")
                git(
                    directory,
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-qm",
                    "fixture",
                )
                return git(directory, "rev-parse", "HEAD")

            git(subject, "init", "-q")
            (subject / "source.txt").write_text("before\n")
            base = commit(subject)
            git(tool, "init", "-q")
            runner = tool / "benchmarks/skill-invocation/run.sh"
            runner.parent.mkdir(parents=True)
            runner.write_text("""#!/bin/sh
if [ "$1-$2" != C01-free ]; then exit 13; fi
work="$BENCH/work/$1-$2"
git -C "$REPO" worktree add --detach "$work" "$BASE" >/dev/null
echo after > "$work/source.txt"
git -C "$work" add source.txt
echo evidence > "$work/untracked.txt"
echo 0 > "$BENCH/out/$1-$2.status"
echo '{}' > "$BENCH/out/$1-$2.json"
""")
            runner.chmod(0o755)
            tool_commit = commit(tool)
            shutil.copyfile(Path(__file__).with_name("drive.sh"), harness / "drive.sh")
            (harness / "PROTOCOL.md").write_text(
                f"- Subject commit: `{base}`\n- Tool commit: `{tool_commit}`\n"
            )
            for filename in ("analyze.py", "task-C.txt", "task-D.txt"):
                (harness / filename).write_text("offline fixture\n")
            for filename in ("oracle-C.sh", "oracle-D.sh"):
                (harness / filename).write_text("exit 0\n")
            sha_program = shutil.which("sha256sum")
            (fakebin / "sha256sum").write_text(f"""#!/bin/sh
case "$1" in
  */fake.phar) echo 8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d ;;
  *) exec {sha_program} "$@" ;;
esac
""")
            (fakebin / "sha256sum").chmod(0o755)
            (fakebin / "claude").write_text("#!/bin/sh\necho offline-fixture-version\n")
            (fakebin / "claude").chmod(0o755)
            bench = root / "bench"
            bench.mkdir()
            env.update(
                BENCH=str(bench),
                REPO=str(subject),
                TOOL=str(tool),
                PHP_AST_EDIT_PHPACTOR=str(root / "fake.phar"),
                PATH=f"{fakebin}:{env['PATH']}",
            )
            result = subprocess.run(
                ["bash", str(harness / "drive.sh"), "run"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
            self.assertEqual(result.returncode, 13, result.stderr)
            patch = (bench / "out/C01-free.diff").read_text()
            self.assertIn("-before", patch)
            self.assertIn("+after", patch)
            self.assertEqual(
                (bench / "out/C01-free.untracked").read_bytes(), b"untracked.txt\0"
            )
            self.assertFalse((bench / "work/C01-free").exists())
            self.assertFalse((bench / "out/done").exists())
            self.assertFalse((bench / "out/D01-gate.version").exists())

    def test_existing_outputs_are_never_reused_or_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            bench = root / "bench"
            (bench / "out").mkdir(parents=True)
            original = bench / "out/C01-free.json"
            original.write_text("first attempt\n")
            fakebin = root / "bin"
            fakebin.mkdir()
            tool = root / "tool"
            (tool / "benchmarks/skill-invocation").mkdir(parents=True)
            scripts = {
                fakebin
                / "git": 'case "$*" in *"rev-parse HEAD"*) echo faaea34e994e17cf2bd907727bc69a413bc130fe;; esac\n',
                fakebin
                / "sha256sum": "echo 8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d\n",
                fakebin / "claude": "echo fake-version\n",
                tool
                / "benchmarks/skill-invocation/run.sh": 'echo overwritten > "$BENCH/out/$1-$2.json"\nexit 13\n',
            }
            for path, content in scripts.items():
                path.write_text("#!/bin/sh\n" + content)
                path.chmod(0o755)
            env = dict(
                os.environ,
                BENCH=str(bench),
                REPO=str(root),
                TOOL=str(tool),
                PHP_AST_EDIT_PHPACTOR=str(root / "fake.phar"),
                PATH=f"{fakebin}:{os.environ['PATH']}",
            )
            result = subprocess.run(
                ["bash", str(Path(__file__).with_name("drive.sh")), "run"],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(original.read_text(), "first attempt\n")
            self.assertFalse((bench / "out/done").exists())

    def test_setup_does_not_replace_existing_configuration(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            configuration = root / "cfg-free"
            configuration.mkdir()
            sentinel = configuration / "settings.json"
            sentinel.write_text("preserve this configuration")
            env = dict(
                os.environ,
                BENCH=str(root),
                REPO=str(root),
                TOOL=str(root),
                PHP_AST_EDIT_PHPACTOR=str(root / "missing.phar"),
            )
            result = subprocess.run(
                ["bash", str(Path(__file__).with_name("drive.sh")), "setup"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("new BENCH path", result.stderr)
            self.assertEqual(sentinel.read_text(), "preserve this configuration")

    def test_run_rejects_dangling_output_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "out").symlink_to(root / "missing")
            env = dict(
                os.environ,
                BENCH=str(root),
                REPO=str(root),
                TOOL=str(root),
                PHP_AST_EDIT_PHPACTOR=str(root / "missing.phar"),
            )
            result = subprocess.run(
                ["bash", str(Path(__file__).with_name("drive.sh")), "run"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to rerun", result.stderr)
            self.assertTrue((root / "out").is_symlink())


if __name__ == "__main__":
    unittest.main()
