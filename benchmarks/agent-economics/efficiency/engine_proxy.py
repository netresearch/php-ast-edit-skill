#!/usr/bin/env python3
"""Passive local capture of full-skill engine calls; preserve native stdout/stderr."""

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


def main():
    args = sys.argv[1:]
    identifier = uuid.uuid4().hex
    forwarded, captured = (None, {})
    if args and args[0] == "apply":
        forwarded, captured = capture_input(args)
    append({"event": "engine_request", "id": identifier, "argv": args, **captured})
    # Passive capture preserves the engine's normal argv; no sandbox. See benchmarks/TRUST.md.
    result = subprocess.run(  # NOSONAR(S6350, S8705)
        [os.environ["PHP_AST_REAL_BIN"], *args],
        input=forwarded,
        capture_output=True,
        check=False,
    )
    append(
        {
            "event": "engine_result",
            "id": identifier,
            "exit_code": result.returncode,
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace"),
        }
    )
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
