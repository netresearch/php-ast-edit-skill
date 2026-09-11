"""Contract tests for the clarified cross-file follow-up fixture."""

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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


original = load_module("v080_original_tasks", HERE / "tasks.py")
clarified = load_module("v080_clarified_tasks", HERE / "clarified_tasks.py")
if str(HERE.parent / "efficiency") not in sys.path:
    sys.path.insert(0, str(HERE.parent / "efficiency"))
runner = load_module("v080_runner", HERE.parent / "efficiency" / "runner.py")
agent_benchmark = load_module(
    "v080_agent_benchmark", HERE.parents[1] / "agent_benchmark.py"
)

ARTIFACT = Path(
    os.environ.get(
        "PHP_AST_PILOT_ARTIFACT",
        "/tmp/php-ast-release-download-20260911/php-ast-edit.phar",
    )
)
RESOLVER = Path(
    os.environ.get("PHP_AST_PILOT_PHPACTOR", "/tmp/phpactor-release-20260911.phar")
)


class ClarifiedTaskTests(unittest.TestCase):
    def setUp(self):
        self.original_before = json.loads(json.dumps(original.manifest()))
        self.manifest = clarified.manifest()
        self.row = self.manifest["tasks"][0]

    def test_single_new_id_does_not_mutate_original_manifest(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(
            [row["id"] for row in self.manifest["tasks"]],
            [
                "cross-file-rename-clarified",
            ],
        )
        self.assertEqual(original.manifest(), self.original_before)

    def test_only_yaml_support_bytes_change_and_prompt_clarifies_scope(self):
        original_row = next(
            row
            for row in self.original_before["tasks"]
            if row["id"] == "cross-file-rename"
        )
        original_files = {
            entry["path"]: entry["php"] for entry in original_row["files"]
        }
        clarified_files = {entry["path"]: entry["php"] for entry in self.row["files"]}
        self.assertEqual(set(clarified_files), set(original_files))
        changed = {
            path
            for path in original_files
            if original_files[path] != clarified_files[path]
        }
        self.assertEqual(changed, {"config/services.yaml"})
        self.assertEqual(clarified_files["config/services.yaml"], "label: fetch\n")
        self.assertIn("Make sure `php check.php` still passes.", self.row["prompt"])
        self.assertIn(
            "Preserve check.php, .php-ast-edit.json, composer.json, and config/services.yaml byte-for-byte",
            self.row["prompt"],
        )
        self.assertIn(
            "YAML label is metadata and is not a method call site", self.row["prompt"]
        )
        self.assertNotIn("AST", self.row["prompt"])
        source_row = clarified.original_row_without_guard(clarified.load_original())
        self.assertEqual(self.row["edits"], source_row["edits"])
        self.assertTrue(self.row["oracle"].endswith(source_row["oracle"]))

    def test_oracle_guard_contains_new_support_hashes_only(self):
        original_row = next(
            row
            for row in self.original_before["tasks"]
            if row["id"] == "cross-file-rename"
        )
        old_yaml = next(
            entry["php"]
            for entry in original_row["files"]
            if entry["path"] == "config/services.yaml"
        )
        new_yaml_hash = hashlib.sha256(b"label: fetch\n").hexdigest()
        old_yaml_hash = hashlib.sha256(old_yaml.encode("utf-8")).hexdigest()
        self.assertIn(new_yaml_hash, self.row["oracle"])
        self.assertNotIn(old_yaml_hash, self.row["oracle"])
        for path in clarified.SUPPORT["cross-file-rename-clarified"]:
            source = next(
                entry["php"] for entry in self.row["files"] if entry["path"] == path
            )
            self.assertIn(
                hashlib.sha256(source.encode("utf-8")).hexdigest(), self.row["oracle"]
            )

    def test_manifest_is_json_serializable(self):
        self.assertEqual(json.loads(json.dumps(self.manifest)), self.manifest)

    @unittest.skipUnless(
        ARTIFACT.is_file() and RESOLVER.is_file(),
        "the pinned release and Phpactor PHARs are required for the offline integration test",
    )
    def test_production_materialization_reference_and_support_guard(self):
        previous_tasks = agent_benchmark.TASKS
        previous_resolver = os.environ.get("PHP_AST_EDIT_PHPACTOR")
        os.environ["PHP_AST_EDIT_PHPACTOR"] = str(RESOLVER)
        try:
            with tempfile.TemporaryDirectory(prefix="php-ast-v080-clarified-") as name:
                base = Path(name)
                manifest_path = base / "controller/benchmarks/tasks.json"
                runner.save(manifest_path, self.manifest)
                template = runner.exact_template(
                    base, self.row, base / "templates" / self.row["id"]
                )
                prepared = runner.prepare_fixture(
                    base,
                    {
                        "run_id": "run001",
                        "task_id": self.row["id"],
                        "model_key": "haiku",
                        "variant": "full_skill",
                        "repetition": 1,
                    },
                    template,
                    "offline clarified preflight",
                )
                work = Path(prepared["work"])
                state = Path(prepared["evidence"]) / runner.STATE
                agent_benchmark.TASKS = manifest_path
                self.assertFalse(agent_benchmark.grade(self.row, work, state)["passed"])
                payload = {
                    "files": [
                        {
                            "path": edit_file["path"],
                            "sha256": hashlib.sha256(
                                (work / edit_file["path"]).read_bytes()
                            ).hexdigest(),
                            "edits": edit_file["edits"],
                        }
                        for edit_file in self.row["edits"]
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
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(agent_benchmark.grade(self.row, work, state)["passed"])
                support = work / "config/services.yaml"
                support.write_text("label: changed\n", encoding="utf-8")
                self.assertFalse(agent_benchmark.grade(self.row, work, state)["passed"])
        finally:
            agent_benchmark.TASKS = previous_tasks
            if previous_resolver is None:
                os.environ.pop("PHP_AST_EDIT_PHPACTOR", None)
            else:
                os.environ["PHP_AST_EDIT_PHPACTOR"] = previous_resolver


if __name__ == "__main__":
    unittest.main()
