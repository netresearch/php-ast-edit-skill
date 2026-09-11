"""Offline contract tests for the v0.8 pilot task generator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARTIFACT = Path(
    os.environ.get(
        "PHP_AST_PILOT_ARTIFACT",
        "/tmp/php-ast-release-download-20260911/php-ast-edit.phar",
    )
)
RESOLVER = Path(
    os.environ.get("PHP_AST_PILOT_PHPACTOR", "/tmp/phpactor-release-20260911.phar")
)
SPEC = importlib.util.spec_from_file_location("v080_tasks", HERE / "tasks.py")
assert SPEC and SPEC.loader
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)

EFFICIENCY = HERE.parent / "efficiency"
if str(EFFICIENCY) not in sys.path:
    sys.path.insert(0, str(EFFICIENCY))
import runner

BENCHMARK_SPEC = importlib.util.spec_from_file_location(
    "v080_agent_benchmark", HERE.parents[1] / "agent_benchmark.py"
)
assert BENCHMARK_SPEC and BENCHMARK_SPEC.loader
agent_benchmark = importlib.util.module_from_spec(BENCHMARK_SPEC)
BENCHMARK_SPEC.loader.exec_module(agent_benchmark)


class TaskManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = tasks.manifest()
        self.rows = self.manifest["tasks"]

    def test_manifest_has_four_bounded_tasks(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(
            [row["id"] for row in self.rows],
            [
                "simple-edit",
                "same-file-batch",
                "cross-file-rename",
                "confusable-rename",
            ],
        )
        self.assertEqual(len({row["id"] for row in self.rows}), len(self.rows))

    def test_every_task_carries_pinned_support_files_and_prompt_clause(self):
        for row in self.rows:
            with self.subTest(row=row["id"]):
                paths = {entry["path"] for entry in row["files"]}
                self.assertIn("check.php", paths)
                self.assertIn(".php-ast-edit.json", paths)
                self.assertEqual(
                    next(
                        entry["php"]
                        for entry in row["files"]
                        if entry["path"] == ".php-ast-edit.json"
                    ),
                    tasks.CHECK_CONFIG,
                )
                self.assertIn("Make sure `php check.php` still passes.", row["prompt"])
                self.assertIn("Do not start background processes.", row["prompt"])
                self.assertNotIn("php-ast-edit", row["prompt"])
                self.assertNotIn("AST", row["prompt"])
                self.assertTrue(row["preserve_source"])
                self.assertEqual(row["outcome"], "changed")

    def test_paths_and_sources_are_safe_and_core_sizes_are_bounded(self):
        for row in self.rows:
            with self.subTest(row=row["id"]):
                for entry in row["files"]:
                    path = Path(entry["path"])
                    self.assertFalse(path.is_absolute())
                    self.assertNotIn("..", path.parts)
                    self.assertIsInstance(entry["php"], str)
                self.assertEqual(
                    len({entry["path"] for entry in row["files"]}),
                    len(row["files"]),
                )
                core = [
                    entry
                    for entry in row["files"]
                    if entry["path"] not in tasks.SUPPORT[row["id"]]
                ]
                self.assertTrue(core)
                lines = sum(entry["php"].count("\n") for entry in core)
                self.assertGreaterEqual(lines, 50)
                self.assertLessEqual(lines, 130)
                for entry in core + [
                    entry for entry in row["files"] if entry["path"] == "check.php"
                ]:
                    self.assertTrue(entry["php"].lstrip().startswith("<?php"))

    def test_reference_payloads_match_declared_files(self):
        for row in self.rows:
            declared = {entry["path"] for entry in row["files"]}
            for file_edit in row["edits"]:
                with self.subTest(row=row["id"], path=file_edit["path"]):
                    self.assertIn(file_edit["path"], declared)
                    self.assertTrue(file_edit["edits"])
                    for edit in file_edit["edits"]:
                        self.assertIn("target", edit)
                        self.assertIn("operation", edit)
            self.assertIsInstance(row["oracle"], str)
            self.assertTrue(row["oracle"].strip())

    def test_manifest_is_json_serializable_without_python_only_values(self):
        encoded = json.dumps(self.manifest)
        self.assertEqual(json.loads(encoded), self.manifest)

    @unittest.skipUnless(
        ARTIFACT.is_file() and RESOLVER.is_file(),
        "the pinned release and Phpactor PHARs are required for the offline preflight",
    )
    def test_production_fixture_path_and_oracles(self):
        """Exercise exact_template, prepare_fixture and the independent grader.

        Every workspace is disposable. The test deliberately checks the baseline,
        reference edit, wrong destination, unrelated mutation, and support-file
        mutation. A release PHAR and the pinned Phpactor PHAR are used when present;
        no model or network operation is involved.
        """

        manifest_path_before = agent_benchmark.TASKS
        resolver = RESOLVER
        artifact = ARTIFACT
        old_resolver = os.environ.get("PHP_AST_EDIT_PHPACTOR")
        os.environ["PHP_AST_EDIT_PHPACTOR"] = str(resolver)
        try:
            for row in self.rows:
                with (
                    self.subTest(task=row["id"]),
                    tempfile.TemporaryDirectory(prefix="php-ast-v080-test-") as name,
                ):
                    base = Path(name)
                    manifest_path = base / "controller/benchmarks/tasks.json"
                    runner.save(manifest_path, self.manifest)
                    template = runner.exact_template(
                        base, row, base / "templates" / row["id"]
                    )
                    prepared = runner.prepare_fixture(
                        base,
                        {
                            "run_id": "run001",
                            "task_id": row["id"],
                            "model_key": "haiku",
                            "variant": "full_skill",
                            "repetition": 1,
                        },
                        template,
                        "offline preflight",
                    )
                    work = Path(prepared["work"])
                    state = Path(prepared["evidence"]) / runner.STATE
                    agent_benchmark.TASKS = manifest_path
                    self.assertFalse(agent_benchmark.grade(row, work, state)["passed"])

                    payload = {
                        "files": [
                            {
                                "path": edit_file["path"],
                                "sha256": hashlib.sha256(
                                    (work / edit_file["path"]).read_bytes()
                                ).hexdigest(),
                                "edits": edit_file["edits"],
                            }
                            for edit_file in row["edits"]
                        ]
                    }
                    result = subprocess.run(
                        ["php", str(artifact), "apply"],
                        cwd=work,
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                        env=os.environ.copy(),
                        check=False,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        result.stdout + result.stderr,
                    )
                    reference_grade = agent_benchmark.grade(row, work, state)
                    self.assertTrue(reference_grade["passed"], reference_grade)

                    collateral = {
                        "simple-edit": ("Greeting.php", "'greeting'", "'other'"),
                        "same-file-batch": ("Cart.php", "'value'", "'other'"),
                        "cross-file-rename": (
                            "src/Other.php",
                            "return 7;",
                            "return 8;",
                        ),
                        "confusable-rename": (
                            "Ledger.php",
                            "'label' => 'total'",
                            "'label' => 'other'",
                        ),
                    }[row["id"]]
                    collateral_path = work / collateral[0]
                    collateral_bytes = collateral_path.read_text()
                    collateral_path.write_text(
                        collateral_bytes.replace(collateral[1], collateral[2], 1)
                    )
                    self.assertFalse(agent_benchmark.grade(row, work, state)["passed"])
                    collateral_path.write_text(collateral_bytes)

                    support_path = work / ".php-ast-edit.json"
                    support_bytes = support_path.read_bytes()
                    support_path.write_bytes(support_bytes + b" ")
                    support_result = agent_benchmark.grade(row, work, state)
                    self.assertFalse(support_result["passed"])
                    self.assertFalse(support_result["runtime_passed"])
                    support_path.write_bytes(support_bytes)

                    if row["id"] == "cross-file-rename":
                        child = work / "src/Child.php"
                        child_bytes = child.read_text()
                        child.write_text(
                            child_bytes.replace("parent::load", "parent::fetch", 1)
                        )
                        self.assertFalse(
                            agent_benchmark.grade(row, work, state)["passed"]
                        )
                        child.write_text(child_bytes)
        finally:
            agent_benchmark.TASKS = manifest_path_before
            if old_resolver is None:
                os.environ.pop("PHP_AST_EDIT_PHPACTOR", None)
            else:
                os.environ["PHP_AST_EDIT_PHPACTOR"] = old_resolver


if __name__ == "__main__":
    unittest.main()
