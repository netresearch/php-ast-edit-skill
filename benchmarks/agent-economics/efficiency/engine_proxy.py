#!/usr/bin/env python3
"""Capture engine calls; opt-in synthetic experiments may add review excerpts."""

import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def append(value):
    path = Path(os.environ["PHP_AST_ENGINE_AUDIT"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as output:
        output.write(json.dumps(value) + "\n")


def input_path(args):
    value = "-"
    for index, arg in enumerate(args):
        if arg == "--input" and index + 1 < len(args):
            value = args[index + 1]
        elif arg.startswith("--input="):
            value = arg.split("=", 1)[1]
    return value


def guard_entries(document):
    rows = []
    for entry in document.get("files", []):
        path = Path(entry["path"]).resolve()
        checksum = None
        if path.is_relative_to(Path.cwd()) and path.is_file():
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        supplied = entry.get("sha256")
        rows.append(
            {
                "path": entry["path"],
                "sha256_present": "sha256" in entry,
                "supplied_sha256": supplied,
                "snapshot_sha256": checksum,
                "matches_capture_snapshot": checksum is not None
                and supplied == checksum,
            }
        )
    return rows


def capture_input(args):
    forwarded = None
    captured = {"input_path": input_path(args)}
    try:
        if captured["input_path"] == "-":
            forwarded = sys.stdin.buffer.read()
            data = forwarded
        else:
            data = Path(captured["input_path"]).read_bytes()
        document = json.loads(data)
        captured.update({"payload": document, "files": guard_entries(document)})
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        captured["capture_error"] = str(error)
    return forwarded, captured


def augment_for_mode(context, stdout, snapshot, mode):
    if mode in ("unchanged_locations", "unchanged_excerpts"):
        return context.augment(stdout, snapshot, unchanged_only=True)
    return context.augment(stdout, snapshot)


def _snapshot_for_mode(args, mode):
    if mode is None:
        return None, None
    import review_context

    if mode not in (
        "review_locations",
        "review_excerpts",
        "unchanged_locations",
        "unchanged_excerpts",
    ):
        raise ValueError("Unknown review-context experiment mode")
    if not args or args[0] not in ("rename", "apply"):
        return review_context, None
    allowed_files = json.loads(Path(os.environ["PHP_AST_REVIEW_FIXTURE"]).read_text())
    return review_context, review_context.capture(Path.cwd(), list(allowed_files))


def _shared_eligibility(args, result):
    return result.returncode == 0 and bool(args) and args[0] in ("rename", "apply")


def _present_output(args, result, mode, snapshot, context, shared_mode):
    presented = result.stdout
    eligible = _shared_eligibility(args, result)
    if shared_mode is not None:
        import shared_report

        if mode is not None or shared_mode not in (
            "shared_report_control",
            "shared_report_factored",
        ):
            raise ValueError("Unknown or conflicting shared-report mode")
        if eligible:
            factored = shared_report.factor(result.stdout)
            if shared_mode == "shared_report_factored":
                presented = factored
    if snapshot is not None and result.returncode == 0:
        augmented = augment_for_mode(context, result.stdout, snapshot, mode)
        if mode in ("review_excerpts", "unchanged_excerpts"):
            presented = augmented
    return presented, eligible


def _result_record(identifier, result, presented, mode, shared_mode, eligible):
    record = {
        "event": "engine_result",
        "id": identifier,
        "exit_code": result.returncode,
        "stdout": result.stdout.decode(errors="replace"),
        "stderr": result.stderr.decode(errors="replace"),
    }
    if shared_mode:
        record.update(
            {
                "shared_report_mode": shared_mode,
                "shared_report_eligible": eligible,
                "presented_stdout": presented.decode(errors="replace"),
            }
        )
    if mode:
        record.update(
            {
                "context_mode": mode,
                "presented_stdout": presented.decode(errors="replace"),
            }
        )
    return record


def main():
    args = sys.argv[1:]
    identifier = uuid.uuid4().hex
    forwarded, captured = (
        capture_input(args) if args and args[0] == "apply" else (None, {})
    )
    append({"event": "engine_request", "id": identifier, "argv": args, **captured})
    mode = os.environ.get("PHP_AST_REVIEW_CONTEXT")
    try:
        context, snapshot = _snapshot_for_mode(args, mode)
    except (
        ValueError,
        OSError,
        ImportError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        append({"event": "experiment_error", "id": identifier, "error": str(error)})
        print("Review-context snapshot failed", file=sys.stderr)
        return 70
    # Passive capture preserves the engine's normal argv; no sandbox. See benchmarks/TRUST.md.
    result = subprocess.run(  # NOSONAR(S6350, S8705)
        [os.environ["PHP_AST_REAL_BIN"], *args],
        input=forwarded,
        capture_output=True,
        check=False,
    )
    presented = result.stdout
    shared_mode = os.environ.get("PHP_AST_SHARED_REPORT")
    shared_eligible = _shared_eligibility(args, result)
    try:
        presented, shared_eligible = _present_output(
            args, result, mode, snapshot, context, shared_mode
        )
    except (ValueError, OSError, KeyError, TypeError, ImportError) as error:
        append({"event": "experiment_error", "id": identifier, "error": str(error)})
    append(
        _result_record(
            identifier, result, presented, mode, shared_mode, shared_eligible
        )
    )
    sys.stdout.buffer.write(presented)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
