#!/usr/bin/env python3
"""Regression tests for direct intent accounting and CLI JSON output."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


summarize = load_module("intent_command_summarize", HERE / "summarize.py")
fixtures = load_module(
    "v080_summarize_fixtures", HERE.parent / "v080-pilot" / "test_summarize.py"
)


def audit(evidence: Path, *events: dict) -> None:
    fixtures.write(
        evidence / "engine-audit.jsonl",
        "".join(json.dumps(event) + "\n" for event in events),
    )


class IntentSummaryTests(unittest.TestCase):
    def test_rename_pair_is_separate_from_existing_apply_accounting(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixtures.row("run001")
            fixtures.make_campaign(base, [run], {"run001": fixtures.measurement()})
            evidence = base / "runs" / "run001" / "evidence"
            audit(
                evidence,
                {
                    "event": "engine_request",
                    "id": "rename-1",
                    "argv": ["rename", "--method", "A::old", "--to", "new"],
                },
                {"event": "engine_result", "id": "rename-1", "exit_code": 0},
                {"event": "engine_request", "id": "apply-1", "argv": ["apply"]},
                {"event": "engine_result", "id": "apply-1", "exit_code": 2},
            )
            observed = summarize.summarize_campaign(base)["runs"][0]

        self.assertEqual(observed["intent_calls"], 1)
        self.assertEqual(observed["failed_intent_calls"], 0)
        self.assertEqual(observed["intent_observation"], "known")
        self.assertFalse(observed["intent_unknown"])
        self.assertEqual(observed["engine"]["apply_calls"], 1)
        self.assertEqual(observed["engine"]["failed_engine_apply"], 1)

    def test_failed_intents_and_cell_medians_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            rows = [fixtures.row("run001"), fixtures.row("run002", repetition=2)]
            fixtures.make_campaign(
                base,
                rows,
                {"run001": fixtures.measurement(), "run002": fixtures.measurement()},
            )
            for run_id, code in (("run001", 0), ("run002", 1)):
                evidence = base / "runs" / run_id / "evidence"
                audit(
                    evidence,
                    {
                        "event": "engine_request",
                        "id": run_id,
                        "argv": ["rename", "--method", "A::old", "--to", "new"],
                    },
                    {"event": "engine_result", "id": run_id, "exit_code": code},
                )
            report = summarize.summarize_campaign(base)

        group = report["cells"][0]
        self.assertEqual(group["intent_calls"], {"median": 1, "n": 2, "denominator": 2})
        self.assertEqual(
            group["failed_intent_calls"], {"median": 0.5, "n": 2, "denominator": 2}
        )
        self.assertEqual(
            group["intent_observations"], {"known": 2, "unknown": 0, "denominator": 2}
        )

    def test_missing_and_malformed_pairs_are_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            rows = [fixtures.row("run001"), fixtures.row("run002", repetition=2)]
            fixtures.make_campaign(
                base,
                rows,
                {"run001": fixtures.measurement(), "run002": fixtures.measurement()},
            )
            audit(
                base / "runs" / "run001" / "evidence",
                {
                    "event": "engine_request",
                    "id": "missing",
                    "argv": ["rename", "--method", "A::old", "--to", "new"],
                },
            )
            fixtures.write(
                base / "runs" / "run002" / "evidence" / "engine-audit.jsonl",
                '{"event":"engine_request","id":"bad","argv":["rename"]}\n{"broken"\n',
            )
            runs = summarize.summarize_campaign(base)["runs"]

        self.assertEqual(runs[0]["intent_observation"], "unknown_unpaired")
        self.assertIsNone(runs[0]["intent_calls"])
        self.assertEqual(runs[1]["intent_observation"], "unknown_malformed")
        self.assertIsNone(runs[1]["failed_intent_calls"])

    def test_present_audit_without_rename_is_known_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixtures.row("run001")
            fixtures.make_campaign(base, [run], {"run001": fixtures.measurement()})
            audit(
                base / "runs" / "run001" / "evidence",
                {"event": "engine_request", "id": "apply", "argv": ["apply"]},
                {"event": "engine_result", "id": "apply", "exit_code": 0},
            )
            observed = summarize.summarize_campaign(base)["runs"][0]

        self.assertEqual(observed["intent_calls"], 0)
        self.assertEqual(observed["failed_intent_calls"], 0)
        self.assertEqual(observed["intent_observation"], "known")

    def test_external_schedule_evidence_is_not_read(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as outside,
        ):
            base = Path(directory)
            external = Path(outside) / "evidence"
            external.mkdir()
            audit(
                external,
                {"event": "engine_request", "id": "rename", "argv": ["rename"]},
                {"event": "engine_result", "id": "rename", "exit_code": 0},
            )
            fixtures.write(
                base / "config.json",
                {"models": {"haiku": {"id": "claude-haiku-4-5-20251001"}}},
            )
            row = fixtures.row("run001")
            row["evidence"] = str(external)
            fixtures.write(base / "schedule.json", [row])
            observed = summarize.summarize_campaign(base)["runs"][0]

        self.assertFalse(observed["attempted"])
        self.assertIsNone(observed["evidence_path"])
        self.assertEqual(observed["intent_observation"], "unknown_missing_evidence")

    def test_symlinked_engine_audit_is_rejected_without_external_records(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as outside,
        ):
            base = Path(directory)
            fixtures.make_campaign(
                base, [fixtures.row("run001")], {"run001": fixtures.measurement()}
            )
            external = Path(outside) / "engine-audit.jsonl"
            audit(
                external.parent,
                {"event": "engine_request", "id": "external", "argv": ["rename"]},
                {"event": "engine_result", "id": "external", "exit_code": 0},
            )
            audit_path = base / "runs" / "run001" / "evidence" / "engine-audit.jsonl"
            audit_path.symlink_to(external)
            observed = summarize.summarize_campaign(base)["runs"][0]

        self.assertEqual(observed["intent_observation"], "unknown_malformed")
        self.assertIsNone(observed["intent_calls"])
        self.assertEqual(observed["intent_records"], [])
        self.assertTrue(
            any("symlink" in error["error"] for error in observed["intent_errors"])
        )

    def test_cli_emits_complete_json_report(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixtures.row("run001")
            fixtures.make_campaign(base, [run], {"run001": fixtures.measurement()})
            audit(
                base / "runs" / "run001" / "evidence",
                {"event": "engine_request", "id": "rename", "argv": ["rename"]},
                {"event": "engine_result", "id": "rename", "exit_code": 0},
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = summarize.main([str(base)])
            report = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["runs"][0]["intent_calls"], 1)
        self.assertIn("metrics", report["runs"][0])
        self.assertIn("successful_observed", report["cells"][0])


if __name__ == "__main__":
    unittest.main()
