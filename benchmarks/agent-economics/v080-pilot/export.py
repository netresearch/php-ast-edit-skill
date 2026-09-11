#!/usr/bin/env python3
"""Copy an explicit evidence allowlist from a completed local pilot campaign."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TOP_LEVEL = (
    "config.json",
    "schedule.json",
    "operator-provenance.json",
    "frozen-sha256.json",
    "campaign-progress.json",
    "controller-run.log",
)
CONTROLLER = (
    "controller/benchmarks/tasks.json",
    "controller/benchmarks/agent_benchmark.py",
    "controller/efficiency/runner.py",
    "controller/efficiency/native.py",
    "controller/efficiency/engine_proxy.py",
)
EVIDENCE = (
    "argv.json",
    "state.json",
    "initial-hashes.json",
    "final-hashes.json",
    "baseline-commit.txt",
    "system-append.txt",
    "prompt.txt",
    "raw.jsonl",
    "stderr.txt",
    "measurement.json",
    "oracle.json",
    "engine-audit.jsonl",
    "diff.patch",
    "git-status.txt",
    "grade-stdout.txt",
    "grade-stderr.txt",
    "diff.patch.stderr",
    "git-status.txt.stderr",
)


def validate_metadata(schedule, manifest):
    if not isinstance(schedule, list) or not isinstance(manifest, dict):
        raise TypeError("Expected a schedule array and task manifest object")
    rows = manifest.get("tasks")
    if not isinstance(rows, list):
        raise TypeError("Task manifest needs a tasks array")
    tasks = {}
    for task in rows:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str):
            raise TypeError("Invalid task identity")
        if task["id"] in tasks or not isinstance(task.get("files"), list):
            raise ValueError("Duplicate task identity or invalid files array")
        paths = set()
        for entry in task["files"]:
            name = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(name, str) or not name or name in paths:
                raise ValueError("Invalid or duplicate task file path")
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Task file must be a contained relative path")
            paths.add(name)
        tasks[task["id"]] = task
    identifiers = set()
    for row in schedule:
        identifier = row.get("run_id") if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not re.fullmatch(
            r"run[0-9]{3,}", identifier
        ):
            raise ValueError("Invalid scheduled run ID")
        if identifier in identifiers:
            raise ValueError("Duplicate scheduled run ID")
        if not isinstance(row.get("task_id"), str) or row["task_id"] not in tasks:
            raise ValueError("Scheduled task is absent from manifest")
        identifiers.add(identifier)
    return tasks


def export_campaign(source: Path, target: Path) -> dict[str, str]:
    """Preserve exact bytes; never traverse outside the selected campaign."""
    source = source.resolve(strict=True)
    if target.exists():
        raise ValueError("Export destination exists; refusing to replace evidence")
    schedule = json.loads((source / "schedule.json").read_text())
    manifest = json.loads((source / "controller/benchmarks/tasks.json").read_text())
    tasks = validate_metadata(schedule, manifest)
    names = list(TOP_LEVEL) + list(CONTROLLER)
    names.extend(
        path.relative_to(source).as_posix()
        for path in (source / "runtime/skills/php-structured-edit").rglob("*")
        if path.is_file()
    )
    for row in schedule:
        identifier = row["run_id"]
        prefix = f"runs/{identifier}"
        names.extend(f"{prefix}/evidence/{name}" for name in EVIDENCE)
        for entry in tasks[row["task_id"]]["files"]:
            names.append(f"{prefix}/evidence/initial/{entry['path']}")
            names.append(f"{prefix}/work/{entry['path']}")

    selected = []
    for name in sorted(set(names)):
        path = source / name
        if not path.resolve().is_relative_to(source) or path.is_symlink():
            raise ValueError(f"Unsafe evidence path: {name}")
        if path.is_file():
            selected.append((name, path))
    target.mkdir(parents=True)
    checksums = {}
    for name, path in selected:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        checksums[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    (target / "export-sha256.json").write_text(json.dumps(checksums, indent=2) + "\n")
    return checksums


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    print(json.dumps({"copied": len(export_campaign(args.source, args.target))}))


if __name__ == "__main__":
    main()
