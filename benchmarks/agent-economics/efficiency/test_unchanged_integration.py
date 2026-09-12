"""Real proxy/selection boundaries for the unchanged-file experiment; no models."""

import hashlib
import json
import shutil
import subprocess
import unittest

import review_context
import test_context_integration as integration


class UnchangedProxyTests(unittest.TestCase):
    def fixture(self):
        fixture = integration.ProxyIntegrationTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        shutil.copyfile(
            integration.HERE / "review_context.py", fixture.base / "review_context.py"
        )
        (fixture.work / "untouched.txt").write_text("an unresolved old name\n")
        fixture.fixture.write_text(
            json.dumps(
                {
                    name: hashlib.sha256((fixture.work / name).read_bytes()).hexdigest()
                    for name in ("source.txt", "untouched.txt")
                }
            )
        )
        subprocess.run(
            ["git", "-c", "init.templateDir=", "init", "-q"],
            cwd=fixture.work,
            check=True,
            capture_output=True,
        )
        return fixture

    def test_both_arms_compute_selection_but_only_treatment_shows_it(self):
        for mode in ("unchanged_locations", "unchanged_excerpts"):
            with self.subTest(mode=mode):
                fixture = self.fixture()
                raw = (
                    json.dumps(
                        {
                            "files": [
                                {
                                    "path": str(fixture.work / "source.txt"),
                                    "changed": True,
                                }
                            ],
                            "renames": [
                                {"notRenamed": ["source.txt:1", "untouched.txt:1"]}
                            ],
                            "checksPassed": True,
                        }
                    ).encode()
                    + b"\n"
                )
                result = fixture.invoke(mode=mode, stdout=raw)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"engine diagnostic\n")
                response = fixture.records()[-1]
                self.assertEqual(response["stdout"], raw.decode())
                self.assertEqual(response["presented_stdout"], result.stdout.decode())
                self.assertTrue(
                    review_context.presentation_valid(response, mode, root=fixture.work)
                )
                self.assertEqual(
                    (fixture.work / "source.txt").read_text(), "after engine write\n"
                )
                if mode == "unchanged_locations":
                    self.assertEqual(result.stdout, raw)
                else:
                    presented = json.loads(result.stdout)
                    context = presented.pop("reviewContext")
                    self.assertEqual(presented, json.loads(raw))
                    self.assertEqual(context["excludedChanged"], 1)
                    self.assertEqual(context["scope"], "unchanged-files")
                    self.assertEqual(context["omitted"], 0)
                    self.assertEqual(
                        [
                            (entry["file"], entry["text"])
                            for entry in context["entries"]
                        ],
                        [("untouched.txt", "an unresolved old name")],
                    )

    def test_malformed_file_report_stops_both_arms_without_hiding_engine_output(self):
        for mode in ("unchanged_locations", "unchanged_excerpts"):
            with self.subTest(mode=mode):
                fixture = self.fixture()
                raw = b'{"files":[{"path":"source.txt","changed":"false"}],"renames":[{"notRenamed":["source.txt:1"]}]}\n'
                result = fixture.invoke(mode=mode, stdout=raw)
                self.assertEqual(result.stdout, raw)
                self.assertEqual(result.returncode, 0)
                records = fixture.records()
                self.assertEqual(
                    [entry["event"] for entry in records],
                    ["engine_request", "experiment_error", "engine_result"],
                )
                assertion = integration.InterventionAbortTests("runTest")
                assertion.assert_stops(records, variant=mode)

    def test_error_and_nonmutation_calls_preserve_original_streams(self):
        for mode in ("unchanged_locations", "unchanged_excerpts"):
            for args, exit_code, raw in (
                (["rename"], 2, b"engine refused\xff\n"),
                (["contexts"], 0, b'{"operations":[]}\n'),
            ):
                with self.subTest(mode=mode, args=args):
                    fixture = self.fixture()
                    result = fixture.invoke(
                        mode=mode, args=args, stdout=raw, exit_code=exit_code
                    )
                    self.assertEqual(
                        (result.stdout, result.returncode), (raw, exit_code)
                    )
                    self.assertFalse(
                        any(
                            entry["event"] == "experiment_error"
                            for entry in fixture.records()
                        )
                    )


if __name__ == "__main__":
    unittest.main()
