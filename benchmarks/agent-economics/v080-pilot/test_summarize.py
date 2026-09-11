#!/usr/bin/env python3
"""Synthetic regression tests for the bounded offline pilot reporter."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pilot_summarize", HERE / "summarize.py")
assert SPEC and SPEC.loader
summarize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summarize)


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def measurement(
    exit_code: int = 0, total: int | None = 100, passed: bool = True
) -> dict:
    row = {
        "process_exit_code": exit_code,
        "timed_out": False,
        "native_is_error": False,
        "native_result_present": True,
        "native_subtype": "success",
        "reported_model": "claude-haiku-4-5-20251001",
        "native_num_turns": 2,
        "primary_model_rounds": 3,
        "primary_model_rounds_exact": True,
        "response_input_coverage": "complete",
        "tool_calls": 2,
        "failed_tool_calls": 0,
        "candidate_wall_ms": 20,
        "native_list_price_usd": 0.01,
        "tool_timing_status": "complete_native_intervals",
        "tool_execution_ms": 8,
        "oracle": {"passed": passed},
        "accounting_errors": [],
        "all_model_usage": {"claude-haiku-4-5-20251001": {}},
    }
    if total is not None:
        row["all_model_tokens"] = {
            "inputTokens": total,
            "outputTokens": 10,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 0,
            "totalTokens": total + 10,
        }
    return row


def raw_trace() -> str:
    events = [
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "Bash",
                        "input": {"command": "printf one"},
                    }
                ]
            }
        },
        {
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-1",
                        "is_error": False,
                    }
                ]
            }
        },
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-2",
                        "name": "Bash",
                        "input": {"command": "printf two"},
                    }
                ]
            }
        },
        {
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-2",
                        "is_error": False,
                    }
                ]
            }
        },
    ]
    return "".join(json.dumps(event) + "\n" for event in events)


def make_campaign(
    root: Path, rows: list[dict], measured: dict[str, dict] | None = None
) -> None:
    write(
        root / "config.json", {"models": {"haiku": {"id": "claude-haiku-4-5-20251001"}}}
    )
    write(root / "schedule.json", rows)
    for row in rows:
        evidence = root / "runs" / row["run_id"] / "evidence"
        evidence.mkdir(parents=True)
        if measured and row["run_id"] in measured:
            observed = dict(measured[row["run_id"]])
            trace = raw_trace()
            observed.setdefault(
                "raw_sha256", hashlib.sha256(trace.encode("utf-8")).hexdigest()
            )
            write(
                evidence / "measurement.json",
                {
                    **observed,
                    **{
                        k: row[k]
                        for k in ("run_id", "task_id", "variant", "repetition")
                    },
                },
            )
            write(evidence / "raw.jsonl", trace)


def row(
    run_id: str, task: str = "task", arm: str = "contextual_patch", repetition: int = 1
) -> dict:
    return {
        "run_id": run_id,
        "task_id": task,
        "variant": arm,
        "model_key": "haiku",
        "repetition": repetition,
    }


class SummarizeTests(unittest.TestCase):
    def test_empty_campaign_slots_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            rows = [row("run001"), row("run002", repetition=2)]
            make_campaign(base, rows)
            report = summarize.summarize_campaign(base)
        self.assertEqual(report["scheduled"], 2)
        self.assertEqual(report["attempted"], 0)
        self.assertEqual(len(report["runs"]), 2)
        self.assertTrue(all(not item["attempted"] for item in report["runs"]))
        self.assertIsNone(
            report["cells"][0]["medians_all_observed"]["total_tokens"]["median"]
        )

    def test_failed_run_stays_in_all_observed_and_success_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            rows = [row("run001"), row("run002", repetition=2)]
            make_campaign(
                base,
                rows,
                {
                    "run001": measurement(total=10),
                    "run002": measurement(exit_code=1, total=30),
                },
            )
            report = summarize.summarize_campaign(base)
        cell = report["cells"][0]
        self.assertEqual(
            (cell["scheduled"], cell["attempted"], cell["successful"]), (2, 2, 1)
        )
        self.assertEqual(cell["medians_all_observed"]["total_tokens"]["median"], 30)
        self.assertEqual(cell["medians_successful"]["total_tokens"]["median"], 20)
        failed = report["runs"][1]
        self.assertFalse(failed["correctness"])
        self.assertEqual(failed["process_exit_code"], 1)

    def test_unknown_measurements_are_null_and_collateral_exit_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            rows = [row("run001"), row("run002", repetition=2)]
            incomplete = measurement(total=None)
            collateral = measurement(exit_code=7, total=20)
            make_campaign(base, rows, {"run001": incomplete, "run002": collateral})
            report = summarize.summarize_campaign(base)
        self.assertIsNone(report["runs"][0]["metrics"]["total_tokens"])
        self.assertFalse(report["runs"][1]["correctness"])
        self.assertEqual(
            report["cells"][0]["medians_all_observed"]["total_tokens"]["n"], 1
        )

    def test_engine_apply_failures_are_separate_and_capture_error_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schedule = [row("run001", arm="full_skill")]
            make_campaign(base, schedule, {"run001": measurement()})
            evidence = base / "runs" / "run001" / "evidence"
            raw = [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "tool-1",
                                "name": "Bash",
                                "input": {"command": "php-ast-agent apply"},
                            }
                        ]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "tool-1",
                                "is_error": False,
                            }
                        ]
                    },
                },
            ]
            write(
                evidence / "raw.jsonl",
                "\n".join(json.dumps(item) for item in raw) + "\n",
            )
            audit = [
                {
                    "event": "engine_request",
                    "id": "apply-ok",
                    "argv": ["apply"],
                    "capture_error": "empty stdin",
                },
                {"event": "engine_result", "id": "apply-ok", "exit_code": 0},
                {
                    "event": "engine_request",
                    "id": "apply-bad",
                    "argv": ["apply", "--input", "edits.json"],
                },
                {"event": "engine_result", "id": "apply-bad", "exit_code": 2},
            ]
            write(
                evidence / "engine-audit.jsonl",
                "\n".join(json.dumps(item) for item in audit) + "\n",
            )
            report = summarize.summarize_campaign(base)
        observed = report["runs"][0]
        self.assertEqual(observed["engine"]["failed_engine_apply"], 1)
        self.assertEqual(observed["engine"]["apply_calls"], 2)
        self.assertEqual(observed["metrics"]["failed_tool_calls"], 0)
        self.assertEqual(observed["review_queue"][0]["call_id"], "tool-1")
        self.assertEqual(
            observed["engine"]["apply_records"][0]["capture_error"], "empty stdin"
        )

    def test_malformed_present_files_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schedule = [row("run001")]
            make_campaign(base, schedule, {"run001": measurement()})
            evidence = base / "runs" / "run001" / "evidence"
            write(evidence / "raw.jsonl", '{"broken"\n')
            report = summarize.summarize_campaign(base)
        self.assertTrue(report["runs"][0]["evidence_errors"])
        self.assertTrue(report["runs"][0]["raw_present"])

    def test_missing_native_fields_do_not_look_successful(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schedule = [row("run001")]
            observed = measurement()
            observed.pop("native_subtype")
            observed.pop("reported_model")
            observed.pop("accounting_errors")
            make_campaign(base, schedule, {"run001": observed})
            report = summarize.summarize_campaign(base)
        self.assertIsNone(report["runs"][0]["correctness"])
        self.assertTrue(report["runs"][0]["oracle_passed"])

    def test_partial_token_counters_leave_total_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schedule = [row("run001")]
            observed = measurement()
            observed["all_model_tokens"] = {"inputTokens": 10, "totalTokens": 999}
            make_campaign(base, schedule, {"run001": observed})
            report = summarize.summarize_campaign(base)
        self.assertIsNone(report["runs"][0]["metrics"]["total_tokens"])
        self.assertEqual(report["runs"][0]["metrics"]["input_tokens"], 10)

    def test_unpaired_tool_and_engine_results_remain_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schedule = [row("run001", arm="full_skill")]
            make_campaign(base, schedule, {"run001": measurement()})
            evidence = base / "runs" / "run001" / "evidence"
            write(
                evidence / "raw.jsonl",
                json.dumps(
                    {
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "tool-1",
                                    "name": "Bash",
                                    "input": {"command": "apply"},
                                }
                            ]
                        }
                    }
                )
                + "\n",
            )
            write(
                evidence / "engine-audit.jsonl",
                json.dumps(
                    {"event": "engine_request", "id": "apply-1", "argv": ["apply"]}
                )
                + "\n"
                + json.dumps({"event": "future_shape", "id": "future-1"})
                + "\n",
            )
            report = summarize.summarize_campaign(base)
        observed = report["runs"][0]
        self.assertIsNone(observed["metrics"]["failed_tool_calls"])
        self.assertIsNone(observed["engine"]["failed_engine_apply"])
        self.assertTrue(observed["evidence_errors"])

    def test_campaign_model_identity_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schedule = [row("run001")]
            observed = measurement()
            observed["reported_model"] = "wrong-model"
            observed["all_model_usage"] = {"wrong-model": {}}
            make_campaign(base, schedule, {"run001": observed})
            report = summarize.summarize_campaign(base)
        self.assertIsNone(report["runs"][0]["correctness"])
        self.assertTrue(
            any(
                "reported model" in item["error"]
                for item in report["runs"][0]["evidence_errors"]
            )
        )

    def test_success_requires_present_raw_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_campaign(base, [row("run001")], {"run001": measurement()})
            measurement_path = (
                base / "runs" / "run001" / "evidence" / "measurement.json"
            )
            observed = json.loads(measurement_path.read_text(encoding="utf-8"))
            observed.pop("raw_sha256")
            write(measurement_path, observed)
            (base / "runs" / "run001" / "evidence" / "raw.jsonl").unlink()
            report = summarize.summarize_campaign(base)
        observed = report["runs"][0]
        self.assertIsNone(observed["correctness"])
        self.assertFalse(observed["raw_present"])

    def test_success_requires_raw_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            make_campaign(base, [row("run001")], {"run001": measurement()})
            measurement_path = (
                base / "runs" / "run001" / "evidence" / "measurement.json"
            )
            observed = json.loads(measurement_path.read_text(encoding="utf-8"))
            observed.pop("raw_sha256")
            write(measurement_path, observed)
            report = summarize.summarize_campaign(base)
        observed = report["runs"][0]
        self.assertIsNone(observed["correctness"])
        self.assertTrue(observed["raw_present"])
        self.assertTrue(
            any("raw_sha256" in item["error"] for item in observed["evidence_errors"])
        )

    def test_raw_hash_and_tool_count_mismatches_are_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            observed = measurement()
            observed["tool_calls"] = 1
            observed["raw_sha256"] = "0" * 64
            make_campaign(base, [row("run001")], {"run001": observed})
            report = summarize.summarize_campaign(base)
        observed = report["runs"][0]
        self.assertIsNone(observed["correctness"])
        self.assertIsNone(observed["metrics"]["tool_calls"])
        self.assertTrue(
            any("raw_sha256" in item["error"] for item in observed["evidence_errors"])
        )
        self.assertTrue(
            any(
                "tool_calls differs" in item["error"]
                for item in observed["evidence_errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
