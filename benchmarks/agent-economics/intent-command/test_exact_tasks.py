"""Offline target and direct invocation checks; never invoke a candidate model."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import exact_tasks
import test_tasks as base

ARTIFACT = Path(
    os.environ.get("PHP_AST_PILOT_ARTIFACT", str(base.ROOT / "bin/php-ast-edit"))
)


class ExactTaskTests(unittest.TestCase):
    def test_only_selected_intent_metadata_is_added(self):
        original = base.tasks.manifest()
        selected = exact_tasks.manifest()
        self.assertEqual(json.loads(json.dumps(selected)), selected)
        for old, new in zip(original["tasks"], selected["tasks"], strict=True):
            metadata = new.pop("intent")
            self.assertEqual(old, new)
            self.assertEqual(set(metadata), {"method", "file", "to", "path"})
            self.assertEqual(metadata["path"], ".")
            self.assertIn(metadata["file"], {entry["path"] for entry in old["files"]})
        self.assertEqual(original, selected)

    @unittest.skipUnless(
        ARTIFACT.is_file() and base.RESOLVER.is_file(),
        "the pinned runtime and Phpactor PHAR are required for offline preflight",
    )
    def test_selected_invocations_pass_independent_oracles(self):
        previous_tasks = base.agent_benchmark.TASKS
        try:
            for task in exact_tasks.manifest()["tasks"]:
                with (
                    self.subTest(task=task["id"]),
                    tempfile.TemporaryDirectory() as name,
                ):
                    campaign = Path(name)
                    manifest_path = campaign / "controller/benchmarks/tasks.json"
                    base.runner.save(manifest_path, exact_tasks.manifest())
                    base.agent_benchmark.TASKS = manifest_path
                    template = base.runner.exact_template(
                        campaign, task, campaign / "templates" / task["id"]
                    )
                    prepared = base.runner.prepare_fixture(
                        campaign,
                        {
                            "run_id": "run001",
                            "task_id": task["id"],
                            "model_key": "haiku",
                            "variant": "delegated_intent",
                            "repetition": 1,
                        },
                        template,
                        "offline preflight",
                    )
                    work = Path(prepared["work"])
                    state = Path(prepared["evidence"]) / base.runner.STATE
                    self.assertFalse(
                        base.agent_benchmark.grade(task, work, state)["passed"]
                    )
                    intent = task["intent"]
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
                        text=True,
                        check=False,
                        timeout=60,
                        env={**os.environ, "PHP_AST_EDIT_PHPACTOR": str(base.RESOLVER)},
                    )
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    self.assertTrue(json.loads(result.stdout)["checksPassed"])
                    self.assertTrue(
                        base.agent_benchmark.grade(task, work, state)["passed"]
                    )
        finally:
            base.agent_benchmark.TASKS = previous_tasks


if __name__ == "__main__":
    unittest.main()
