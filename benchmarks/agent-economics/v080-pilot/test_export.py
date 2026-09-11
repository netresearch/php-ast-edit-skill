"""Verify evidence selection and refusal before creating an export directory."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "pilot_export", Path(__file__).with_name("export.py")
)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def test_invalid_metadata_is_rejected(self):
        manifest = {"tasks": [{"id": "task", "files": [{"path": "Code.php"}]}]}
        row = {"run_id": "run001", "task_id": "task"}
        for schedule in (
            [row, row],
            [{**row, "run_id": "run0"}],
            [{**row, "task_id": []}],
            [None],
        ):
            with (
                self.subTest(schedule=schedule),
                self.assertRaises((TypeError, ValueError)),
            ):
                exporter.validate_metadata(schedule, manifest)

    def test_allowlist_preserves_bytes_and_refuses_external_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "campaign"
            evidence = source / "runs/run001/evidence"
            evidence.mkdir(parents=True)
            controller = source / "controller/benchmarks"
            controller.mkdir(parents=True)
            (source / "schedule.json").write_text(
                json.dumps([{"run_id": "run001", "task_id": "task"}])
            )
            (controller / "tasks.json").write_text(
                json.dumps({"tasks": [{"id": "task", "files": [{"path": "Code.php"}]}]})
            )
            raw = evidence / "raw.jsonl"
            raw.write_bytes(b'{"type":"result"}\n')
            (evidence / "unlisted-secret.txt").write_text("must not be copied")
            target = root / "exported"
            checksums = exporter.export_campaign(source, target)
            self.assertEqual(
                (target / "runs/run001/evidence/raw.jsonl").read_bytes(),
                raw.read_bytes(),
            )
            self.assertIn("runs/run001/evidence/raw.jsonl", checksums)
            self.assertFalse(
                (target / "runs/run001/evidence/unlisted-secret.txt").exists()
            )
            with self.assertRaises(ValueError):
                exporter.export_campaign(source, target)
            outside = root / "outside.jsonl"
            outside.write_text("private")
            raw.unlink()
            raw.symlink_to(outside)
            refused = root / "refused"
            with self.assertRaises(ValueError):
                exporter.export_campaign(source, refused)
            self.assertFalse(refused.exists())


if __name__ == "__main__":
    unittest.main()
