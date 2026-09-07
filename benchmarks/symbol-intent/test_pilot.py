"""Validate grading and the existing semantic control before spending model calls."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import pilot
from lsp import CONFIG, isolated_environment
from test_symbol_intent import fixture


class PilotTests(unittest.TestCase):
    def test_oracle_rejects_wrong_receivers_partial_rename_and_scope_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "source").symlink_to(pilot.SOURCE, target_is_directory=True)
            run = output / "run001"
            run.mkdir()
            root = run / "work"
            expected = fixture(root, 10)
            pilot.save(run / "expected.json", expected)
            self.assertFalse(pilot.grade(output, run, 10)["success"])
            for name, source in expected.items():
                (root / name).write_text(source)
            self.assertTrue(pilot.grade(output, run, 10)["success"])
            # Layout is separate from structural/behavior correctness.
            path = root / "Provider.php"
            path.write_text(expected["Provider.php"] + "\n")
            self.assertTrue(pilot.grade(output, run, 10)["success"])
            self.assertFalse(pilot.grade(output, run, 10)["exact_bytes"])
            path.write_text(expected["Provider.php"])
            wrong = root / "Caller0.php"
            wrong.write_text(
                expected["Caller0.php"].replace("$second->fetch()", "$second->load()")
            )
            self.assertFalse(pilot.grade(output, run, 10)["success"])
            wrong.write_text(expected["Caller0.php"])
            (root / "unrequested.txt").write_text("extra")
            self.assertFalse(pilot.grade(output, run, 10)["success"])

    @unittest.skipUnless(
        os.environ.get("PHP_AST_TEST_PHPACTOR"), "Pinned Phpactor integration opt-in"
    )
    def test_existing_phpactor_control_renames_two_ten_fifty_files(self):
        for size in (2, 10, 50):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                root = base / "work"
                expected = fixture(root, size)
                state = base / "state"
                state.mkdir()
                env = isolated_environment(state)
                common = [
                    "--working-dir",
                    str(root),
                    "--config-extra",
                    json.dumps(CONFIG),
                    "-n",
                ]
                for operation in (
                    ["index:build"],
                    [
                        "references:member",
                        "Example\\Provider",
                        "fetch",
                        "--type=method",
                        "--replace=load",
                        "--filesystem=simple",
                    ],
                ):
                    subprocess.run(
                        [
                            "php",
                            os.environ["PHP_AST_TEST_PHPACTOR"],
                            *operation,
                            *common,
                        ],
                        env=env,
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                self.assertTrue(
                    all(
                        (root / name).read_text() == source
                        for name, source in expected.items()
                    )
                )


if __name__ == "__main__":
    unittest.main()
