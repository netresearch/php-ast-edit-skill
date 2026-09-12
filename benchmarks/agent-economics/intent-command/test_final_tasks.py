"""Held-out fixture and independent-oracle tests; no candidate model calls."""

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
if str(ROOT / "benchmarks/agent-economics/efficiency") not in sys.path:
    sys.path.insert(0, str(ROOT / "benchmarks/agent-economics/efficiency"))
import final_tasks
import runner

ARTIFACT = Path(
    os.environ.get(
        "PHP_AST_PILOT_ARTIFACT",
        "/tmp/php-ast-intent-command-20260911/bin/php-ast-edit",
    )
)
RESOLVER = Path(
    os.environ.get("PHP_AST_PILOT_PHPACTOR", "/tmp/phpactor-release-20260911.phar")
)
BENCHMARK_SPEC = importlib.util.spec_from_file_location(
    "final_agent_benchmark", ROOT / "benchmarks/agent_benchmark.py"
)
assert BENCHMARK_SPEC is not None and BENCHMARK_SPEC.loader is not None
agent_benchmark = importlib.util.module_from_spec(BENCHMARK_SPEC)
BENCHMARK_SPEC.loader.exec_module(agent_benchmark)


class FinalTaskTests(unittest.TestCase):
    def test_manifest_is_held_out_and_intents_are_exact(self) -> None:
        manifest = final_tasks.manifest()
        self.assertEqual(
            [row["id"] for row in manifest["tasks"]],
            [final_tasks.SINGLE_TASK, final_tasks.CROSS_TASK],
        )
        encoded = json.dumps(manifest)
        self.assertEqual(json.loads(encoded), manifest)
        source = encoded.lower()
        self.assertNotIn("product", source)
        self.assertNotIn("fetch", source)
        for row in manifest["tasks"]:
            self.assertTrue(row["preserve_source"])
            self.assertEqual(set(row["intent"]), {"method", "file", "to", "path"})
            self.assertEqual(row["intent"]["path"], ".")
            self.assertIn(
                row["intent"]["file"], {entry["path"] for entry in row["files"]}
            )
            self.assertIn("php check.php", row["prompt"])
            self.assertIn(".php-ast-edit.json", row["oracle"])
            self.assertIn("check.php", row["oracle"])

    def test_support_hashes_match_declared_files(self) -> None:
        for row in final_tasks.manifest()["tasks"]:
            files = {entry["path"]: entry["php"] for entry in row["files"]}
            for path, source in final_tasks.SUPPORT[row["id"]].items():
                self.assertEqual(files[path], source)
                self.assertIn(
                    hashlib.sha256(source.encode()).hexdigest(), row["oracle"]
                )
            self.assertEqual(files[".php-ast-edit.json"], final_tasks.CHECK_CONFIG)

    @unittest.skipUnless(
        ARTIFACT.is_file() and RESOLVER.is_file(),
        "the pinned runtime and Phpactor PHARs are required for oracle preflight",
    )
    def test_checks_fail_before_and_oracles_pass_after_reference_rename(self) -> None:
        previous_tasks = agent_benchmark.TASKS
        with tempfile.TemporaryDirectory(prefix="php-ast-evidence-final-") as name:
            base = Path(name)
            manifest_path = base / "controller/benchmarks/tasks.json"
            runner.save(manifest_path, final_tasks.manifest())
            agent_benchmark.TASKS = manifest_path
            try:
                for row in final_tasks.manifest()["tasks"]:
                    with self.subTest(task=row["id"]):
                        template = runner.exact_template(
                            base, row, base / "templates" / row["id"]
                        )
                        prepared = runner.prepare_fixture(
                            base,
                            {
                                "run_id": row["id"],
                                "task_id": row["id"],
                                "model_key": "haiku",
                                "variant": "full_skill",
                                "repetition": 1,
                            },
                            template,
                            "offline held-out preflight",
                        )
                        work = Path(prepared["work"])
                        state = Path(prepared["evidence"]) / runner.STATE
                        self.assertNotEqual(
                            subprocess.run(
                                ["php", "check.php"],
                                cwd=work,
                                capture_output=True,
                                check=False,
                            ).returncode,
                            0,
                        )
                        self.assertFalse(
                            agent_benchmark.grade(row, work, state)["passed"]
                        )
                        intent = row["intent"]
                        result = subprocess.run(
                            [
                                "php",
                                str(ARTIFACT),
                                "rename",
                                "--method",
                                intent["method"],
                                "--to",
                                intent["to"],
                                "--path",
                                intent["path"],
                                "--file",
                                intent["file"],
                            ],
                            cwd=work,
                            capture_output=True,
                            check=False,
                            timeout=60,
                            env={**os.environ, "PHP_AST_EDIT_PHPACTOR": str(RESOLVER)},
                        )
                        self.assertEqual(
                            result.returncode, 0, result.stdout + result.stderr
                        )
                        self.assertTrue(
                            agent_benchmark.grade(row, work, state)["passed"]
                        )

                        if row["id"] == final_tasks.SINGLE_TASK:
                            path, old, new = "Catalog.php", "'findSku',", "'changed',"
                        else:
                            path, old, new = (
                                "src/LegacySender.php",
                                "return $transport->deliver();",
                                "return 'changed';",
                            )
                        collateral = work / path
                        original = collateral.read_text()
                        collateral.write_text(original.replace(old, new, 1))
                        try:
                            self.assertFalse(
                                agent_benchmark.grade(row, work, state)["passed"]
                            )
                        finally:
                            collateral.write_text(original)
            finally:
                agent_benchmark.TASKS = previous_tasks


if __name__ == "__main__":
    unittest.main()
