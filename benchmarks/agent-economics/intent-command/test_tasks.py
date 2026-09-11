"""Offline manifest and oracle falsification tests; no model calls."""

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
ROOT = HERE.parents[2]
ARTIFACT = Path(
    os.environ.get(
        "PHP_AST_PILOT_ARTIFACT",
        "/tmp/php-ast-release-download-20260911/php-ast-edit.phar",
    )
)
RESOLVER = Path(
    os.environ.get("PHP_AST_PILOT_PHPACTOR", "/tmp/phpactor-release-20260911.phar")
)

if str(ROOT / "benchmarks/agent-economics/efficiency") not in sys.path:
    sys.path.insert(0, str(ROOT / "benchmarks/agent-economics/efficiency"))
import runner

SPEC = importlib.util.spec_from_file_location("intent_tasks", HERE / "tasks.py")
assert SPEC is not None and SPEC.loader is not None
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)

BENCHMARK_SPEC = importlib.util.spec_from_file_location(
    "intent_agent_benchmark", ROOT / "benchmarks/agent_benchmark.py"
)
assert BENCHMARK_SPEC is not None and BENCHMARK_SPEC.loader is not None
agent_benchmark = importlib.util.module_from_spec(BENCHMARK_SPEC)
BENCHMARK_SPEC.loader.exec_module(agent_benchmark)


class ManifestTests(unittest.TestCase):
    def test_reuses_only_the_two_existing_method_tasks(self):
        manifest = tasks.manifest()
        self.assertEqual(
            [row["id"] for row in manifest["tasks"]],
            [tasks.METHOD_TASK, tasks.CROSS_TASK],
        )
        self.assertTrue(all(row["preserve_source"] for row in manifest["tasks"]))

    def test_support_is_present_and_protected(self):
        for row in tasks.manifest()["tasks"]:
            files = {entry["path"]: entry["php"] for entry in row["files"]}
            for path in (tasks.CHECK_PATH, tasks.CONFIG_PATH):
                self.assertIn(path, files, row["id"])
            self.assertIn("php check.php", row["prompt"])
            self.assertIn(tasks.CHECK_PATH, row["oracle"])
            self.assertIn(tasks.CONFIG_PATH, row["oracle"])
            self.assertEqual(files[tasks.CONFIG_PATH], tasks.CHECK_CONFIG)
            self.assertNotIn("php-ast-edit apply", row["prompt"])
            self.assertNotIn("AST", row["prompt"])

    def test_manifest_is_stable_json(self):
        manifest = tasks.manifest()
        self.assertEqual(json.loads(json.dumps(manifest)), manifest)

    @unittest.skipUnless(
        ARTIFACT.is_file() and RESOLVER.is_file(),
        "the pinned release and Phpactor PHARs are required for oracle preflight",
    )
    def test_baseline_fails_reference_passes_and_support_mutation_fails(self):
        previous_tasks = agent_benchmark.TASKS
        old_resolver = os.environ.get("PHP_AST_EDIT_PHPACTOR")
        os.environ["PHP_AST_EDIT_PHPACTOR"] = str(RESOLVER)
        try:
            for row in tasks.manifest()["tasks"]:
                with (
                    self.subTest(task=row["id"]),
                    tempfile.TemporaryDirectory(
                        prefix="php-ast-intent-command-test-"
                    ) as name,
                ):
                    base = Path(name)
                    manifest_path = base / "controller/benchmarks/tasks.json"
                    runner.save(manifest_path, tasks.manifest())
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
                        "offline intent preflight",
                    )
                    work = Path(prepared["work"])
                    state = Path(prepared["evidence"]) / runner.STATE
                    agent_benchmark.TASKS = manifest_path
                    self.assertFalse(agent_benchmark.grade(row, work, state)["passed"])
                    initial_check = subprocess.run(
                        ["php", tasks.CHECK_PATH],
                        cwd=work,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if row["id"] == tasks.METHOD_TASK:
                        self.assertNotEqual(initial_check.returncode, 0)

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
                        ["php", str(ARTIFACT), "apply"],
                        cwd=work,
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                        env=os.environ.copy(),
                        check=False,
                        timeout=60,
                    )
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    report = json.loads(result.stdout)
                    self.assertTrue(report["checksPassed"], report)
                    self.assertTrue(agent_benchmark.grade(row, work, state)["passed"])

                    collateral = {
                        tasks.METHOD_TASK: ("Product.php", "'findByUid'", "'other'"),
                        tasks.CROSS_TASK: ("src/Other.php", "return 7;", "return 8;"),
                    }[row["id"]]
                    collateral_path = work / collateral[0]
                    collateral_original = collateral_path.read_text()
                    collateral_path.write_text(
                        collateral_original.replace(collateral[1], collateral[2], 1)
                    )
                    self.assertFalse(agent_benchmark.grade(row, work, state)["passed"])
                    collateral_path.write_text(collateral_original)

                    for support_name in (tasks.CONFIG_PATH, tasks.CHECK_PATH):
                        with self.subTest(task=row["id"], support=support_name):
                            support = work / support_name
                            original = support.read_bytes()
                            support.write_bytes(original + b" ")
                            self.assertFalse(
                                agent_benchmark.grade(row, work, state)["passed"]
                            )
                            support.write_bytes(original)
        finally:
            agent_benchmark.TASKS = previous_tasks
            if old_resolver is None:
                os.environ.pop("PHP_AST_EDIT_PHPACTOR", None)
            else:
                os.environ["PHP_AST_EDIT_PHPACTOR"] = old_resolver


if __name__ == "__main__":
    unittest.main()
