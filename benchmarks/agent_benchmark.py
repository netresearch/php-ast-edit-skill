#!/usr/bin/env python3
"""Materialize isolated tasks, grade behavior, and import measured agent-run records."""
import argparse
import datetime
import hashlib
import json
import math
import re
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks/tasks.json"
SCHEMA = ROOT / "benchmarks/run.schema.json"


def load(path):
    return json.loads(Path(path).read_text())


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def task_by_id(identifier):
    return next(task for task in load(TASKS)["tasks"] if task["id"] == identifier)


def invoke(args, cwd, payload=None):
    return subprocess.run(args, cwd=cwd, input=None if payload is None else json.dumps(payload),
                          text=True, capture_output=True, timeout=60)


def prepare(task, work, state, binary):
    work = work.resolve()
    state = state.resolve()
    if state.is_relative_to(work):
        raise ValueError("Keep evaluator state outside the agent workspace")
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise ValueError("Task workspace must be empty")
    result = invoke(["php", str(binary), "apply"], work,
                    {"files": [{**file, "mode": "create"} for file in task["files"]]})
    if result.returncode:
        raise RuntimeError(result.stderr)
    baseline = {file["path"]: digest(work / file["path"]) for file in task["files"]}
    save(state, {"task_id": task["id"], "task_manifest_sha256": digest(TASKS),
                 "work": str(work), "baseline": baseline})
    return {"prompt": task["prompt"], "workspace": str(work), "files": list(baseline)}


def grade(task, work, state):
    state = load(state)
    if state["task_id"] != task["id"] or state["task_manifest_sha256"] != digest(TASKS):
        raise ValueError("Evaluator state does not match this task manifest")
    if Path(state["work"]) != work.resolve():
        raise ValueError("Evaluator state belongs to another workspace")
    files = sorted(p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file() and ".git" not in p.relative_to(work).parts)
    same_scope = files == sorted(state["baseline"])
    lint = {name: invoke(["php", "-l", name], work).returncode == 0 for name in state["baseline"]}
    runtime = invoke(["php", "-r", task["oracle"]], work)
    unchanged = all((work / name).is_file() and digest(work / name) == checksum
                    for name, checksum in state["baseline"].items())
    expected_change = (unchanged if task["outcome"] == "rejected_unchanged" else
                       True if task["outcome"] == "changed_or_refused" else not unchanged)
    passed = same_scope and all(lint.values()) and runtime.returncode == 0 and expected_change
    return {"schema_version": 1, "task_id": task["id"], "task_manifest_sha256": digest(TASKS),
            "passed": passed, "file_scope_passed": same_scope, "lint": lint,
            "runtime_passed": runtime.returncode == 0, "expected_change_passed": expected_change,
            "runtime_stderr": runtime.stderr, "output_hashes": {name: digest(work / name)
              for name in state["baseline"] if (work / name).is_file()},
            "limitation": "Runtime oracle covers the supplied behavior. Human review of diff and refusal explanation remains required."}


def validate_schema(value, schema, path="$", root=None):
    """Validate the small, explicit subset used by run.schema.json, without dependencies."""
    root = root or schema
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return validate_schema(value, target, path, root)
    types = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "integer": lambda x: type(x) is int,
             "number": lambda x: type(x) in (int, float) and math.isfinite(x),
             "boolean": lambda x: type(x) is bool, "null": lambda x: x is None}
    expected = schema.get("type", list(types))
    if isinstance(expected, str):
        expected = [expected]
    if not any(types[kind](value) for kind in expected):
        raise ValueError(f"{path}: wrong type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value outside enum")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}: missing {key}")
        for key, child in value.items():
            if key in schema.get("properties", {}):
                validate_schema(child, schema["properties"][key], path + "." + key, root)
            elif schema.get("additionalProperties") is False:
                raise ValueError(f"{path}: unknown {key}")
    if isinstance(value, str) and "pattern" in schema and re.search(schema["pattern"], value) is None:
        raise ValueError(f"{path}: malformed value")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ValueError(f"{path}: empty string")
    if type(value) in (int, float) and value < schema.get("minimum", -math.inf):
        raise ValueError(f"{path}: negative value")


def import_run(record_path, destination):
    record = load(record_path)
    validate_schema(record, load(SCHEMA))
    task_by_id(record["task_id"])
    parent = record_path.resolve().parent
    transcript = (parent / record["transcript"]["path"]).resolve()
    oracle_path = (parent / record["oracle"]["path"]).resolve()
    if digest(transcript) != record["transcript"]["sha256"]:
        raise ValueError("Transcript checksum mismatch")
    if digest(oracle_path) != record["oracle"]["sha256"]:
        raise ValueError("Oracle checksum mismatch")
    oracle = load(oracle_path)
    if oracle["task_id"] != record["task_id"] or oracle["task_manifest_sha256"] != digest(TASKS):
        raise ValueError("Oracle does not match current task")
    success = oracle["passed"] and record["review"]["passed"]
    if record["success"] != success:
        raise ValueError("Reported success disagrees with oracle and human review")
    if record["first_attempt_success"] and (not success or record["repair_attempts"] != 0):
        raise ValueError("First-attempt success inconsistent with repairs/outcome")
    if record["tokens"]["cached_input"] > record["tokens"]["input"]:
        raise ValueError("Cached input must be a subset of total input")
    identity = [record[key] for key in ("task_id", "variant", "model", "model_version", "reasoning", "cache_condition", "repetition", "source_commit", "harness_config_sha256")]
    existing = [] if not destination.exists() else [json.loads(line) for line in destination.read_text().splitlines()]
    for previous in existing:
        if identity == [previous[key] for key in ("task_id", "variant", "model", "model_version", "reasoning", "cache_condition", "repetition", "source_commit", "harness_config_sha256")]:
            raise ValueError("Duplicate run identity")
    # Preserve origin for resolving relative evidence paths after import.
    record["record_source"] = str(record_path.resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    return {"imported": True, "success": success, "task_id": record["task_id"]}


def summarize(path):
    records = [json.loads(line) for line in path.read_text().splitlines()]
    groups = {}
    dimensions = ("source_commit", "model", "model_version", "reasoning", "cache_condition", "harness_config_sha256", "variant")
    for record in records:
        key = tuple(record[field] for field in dimensions)
        groups.setdefault(key, []).append(record)
    results = []
    for key, rows in groups.items():
        elapsed = sorted(row["elapsed_ms"] for row in rows)
        successes = sum(row["success"] for row in rows)
        results.append({**dict(zip(dimensions, key)), "runs": len(rows), "successful_runs": successes,
           "success_rate": successes / len(rows), "first_attempt_success_rate": sum(r["first_attempt_success"] for r in rows) / len(rows),
           "median_elapsed_ms_all_attempts": statistics.median(elapsed),
           "p95_elapsed_ms_all_attempts": elapsed[math.ceil(len(elapsed) * .95) - 1],
           "elapsed_ms_per_success_including_failures": sum(elapsed) / successes if successes else None,
           "input_tokens_all_attempts": sum(r["tokens"]["input"] for r in rows),
           "output_tokens_all_attempts": sum(r["tokens"]["output"] for r in rows),
           "cached_input_tokens_all_attempts": sum(r["tokens"]["cached_input"] for r in rows),
           "tool_calls_all_attempts": sum(r["tool_calls"] for r in rows),
           "model_rounds_all_attempts": sum(r["model_rounds"] for r in rows)})
    return {"groups": results, "limitation": "Check paired task coverage before comparisons. Groups do not imply statistical significance or universal savings."}



def self_test_imports(task, work, state, base):
    # Synthetic importer fixtures live only in this temporary test directory. They
    # are not measurements and are never published into benchmarks/results/.
    transcript = base / "synthetic-transcript.txt"
    transcript.write_text("Synthetic importer validation fixture; no model was called.\n")
    oracle = base / "synthetic-oracle.json"
    save(oracle, grade(task, work, state))
    record = {"task_id": task["id"], "variant": "full_skill", "model": "synthetic-test-only",
        "model_version": "test", "reasoning": "test", "cache_condition": "cold", "repetition": 1,
        "source_commit": "0" * 40, "harness_config_sha256": "0" * 64,
        "tokens": {"input": 0, "output": 0, "cached_input": 0}, "tool_calls": 0,
        "cli_invocations": 0, "model_rounds": 0, "repair_attempts": 0,
        "elapsed_ms": 0, "setup_elapsed_ms": 0, "cost_usd": None,
        "success": True, "first_attempt_success": True,
        "review": {"passed": True, "reviewer": "test", "notes": "Synthetic fixture"},
        "transcript": {"path": transcript.name, "sha256": digest(transcript)},
        "oracle": {"path": oracle.name, "sha256": digest(oracle)}}
    candidate, results = base / "synthetic-record.json", base / "synthetic-results.jsonl"
    save(candidate, record)
    import_run(candidate, results)
    mutations = [lambda r: r, lambda r: {**r, "success": False},
        lambda r: {**r, "tokens": {"input": 0, "output": 0, "cached_input": 1}},
        lambda r: {**r, "first_attempt_success": True, "repair_attempts": 1},
        lambda r: {**r, "tool_calls": -1}, lambda r: {**r, "model_rounds": None},
        lambda r: {**r, "elapsed_ms": float("nan")},
        lambda r: {**r, "transcript": {"path": transcript.name, "sha256": "f" * 64}}]
    for index, mutate in enumerate(mutations):
        altered = mutate({**record, "repetition": 1 if index == 0 else index + 1})
        save(candidate, altered)
        try:
            import_run(candidate, results)
        except ValueError:
            continue
        raise RuntimeError(f"Invalid synthetic importer case {index} was accepted")
    summary = summarize(results)
    if summary["groups"][0]["runs"] != 1 or summary["groups"][0]["successful_runs"] != 1:
        raise RuntimeError("Synthetic import summary counted rejected rows")
    print("OK: synthetic importer checks reject duplicates, invalid metrics, and altered evidence")


def self_test(binary):
    tasks = load(TASKS)["tasks"]
    with tempfile.TemporaryDirectory(prefix="php-ast-evals-") as temporary:
        base = Path(temporary)
        for task in tasks:
            work, state = base / task["id"], base / (task["id"] + ".state.json")
            prepare(task, work, state, binary)
            payload = {"files": [{**file, "sha256": digest(work / file["path"])} for file in task["edits"]]}
            result = invoke(["php", str(binary), "apply"], work, payload)
            rejected = task.get("reference_rejects", task["outcome"] == "rejected_unchanged")
            if (result.returncode != 0) != rejected:
                raise RuntimeError(f"{task['id']}: unexpected exit {result.returncode}: {result.stderr}")
            if not grade(task, work, state)["passed"]:
                raise RuntimeError(f"{task['id']}: reference failed independent oracle")
            if task is tasks[0]:
                self_test_imports(task, work, state, base)
            if task["outcome"] == "changed_or_refused":
                alternative = invoke(["php", str(binary), "apply"], work, {"files": [{
                    "path": "Child.php", "sha256": digest(work / "Child.php"), "edits": [{
                        "target": {"select": "method:ChildExample::old"},
                        "operation": "set_name", "value": "renamed"}]}]})
                if alternative.returncode or not grade(task, work, state)["passed"]:
                    raise RuntimeError("Safe alternative child rename failed the common oracle")
            # A missing expected source file must fail even if another outcome happens to match.
            missing = task["files"][0]["path"]
            deletion = invoke(["php", str(binary), "apply"], work,
                {"files": [{"path": missing, "mode": "delete", "sha256": digest(work / missing)}]})
            if deletion.returncode or grade(task, work, state)["passed"]:
                raise RuntimeError(f"{task['id']}: broken output escaped oracle")
            print(f"OK: {task['id']} reference outcome and failing-output oracle")
    return {"task_count": len(tasks), "model_runs": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, default=ROOT / "bin/php-ast-edit")
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "grade"):
        sub = subs.add_parser(command)
        sub.add_argument("task")
        sub.add_argument("--work", type=Path, required=True)
        sub.add_argument("--state", type=Path, required=True)
        if command == "grade":
            sub.add_argument("--output", type=Path, required=True)
    sub = subs.add_parser("import")
    sub.add_argument("record", type=Path)
    sub.add_argument("--results", type=Path, required=True)
    sub = subs.add_parser("summarize")
    sub.add_argument("results", type=Path)
    subs.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(task_by_id(args.task), args.work, args.state, args.bin.resolve())
    elif args.command == "grade":
        result = grade(task_by_id(args.task), args.work, args.state)
        save(args.output, result)
    elif args.command == "import":
        result = import_run(args.record, args.results)
    elif args.command == "summarize":
        result = summarize(args.results)
    else:
        result = self_test(args.bin.resolve())
    print(json.dumps(result, indent=2))
    if args.command == "grade" and not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
