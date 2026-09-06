"""Materialize isolated tasks, grade behavior, and import measured agent-run records."""

import argparse
import hashlib
import json
import math
import re
import secrets
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks/tasks.json"
SCHEMA = ROOT / "benchmarks/run.schema.json"
HASH_PATTERNS = {
    "^[a-f0-9]{40}$": re.compile(r"[a-f0-9]{40}"),
    "^[a-f0-9]{64}$": re.compile(r"[a-f0-9]{64}"),
}


def load(path):
    # Local evaluator inputs are operator-selected files; see TRUST.md.
    return json.loads(Path(path).read_text())  # NOSONAR(S2083, S8707)


def save(path, data):
    # The operator selects state/report destinations outside the task; see TRUST.md.
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)  # NOSONAR(S8707)
    serialized = json.dumps(data, indent=2) + "\n"
    target.write_text(serialized)  # NOSONAR(S2083, S8707)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def task_by_id(identifier):
    return next(task for task in load(TASKS)["tasks"] if task["id"] == identifier)


def invoke(args, cwd, payload=None):
    # Trusted evaluator argv intentionally runs the selected PHP CLI; see TRUST.md.
    return subprocess.run(  # NOSONAR(S6350)
        args,
        cwd=cwd,
        input=None if payload is None else json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=60,
        shell=False,
        check=False,
    )


def prepare(task, work, state, binary):
    work = work.resolve()
    state = state.resolve()
    if state.is_relative_to(work):
        raise ValueError("Keep evaluator state outside the agent workspace")
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise ValueError("Task workspace must be empty")
    result = invoke(
        ["php", str(binary), "apply"],
        work,
        {"files": [{**file, "mode": "create"} for file in task["files"]]},
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    baseline = {file["path"]: digest(work / file["path"]) for file in task["files"]}
    save(
        state,
        {
            "task_id": task["id"],
            "task_manifest_sha256": digest(TASKS),
            "work": str(work),
            "baseline": baseline,
        },
    )
    return {"prompt": task["prompt"], "workspace": str(work), "files": list(baseline)}


def grade(task, work, state):
    state = load(state)
    if state["task_id"] != task["id"] or state["task_manifest_sha256"] != digest(TASKS):
        raise ValueError("Evaluator state does not match this task manifest")
    if Path(state["work"]) != work.resolve():
        raise ValueError("Evaluator state belongs to another workspace")
    work = work.resolve()
    entries = [
        path for path in work.rglob("*") if ".git" not in path.relative_to(work).parts
    ]
    has_symlinks = any(path.is_symlink() for path in entries)
    files = {
        path.relative_to(work).as_posix(): path
        for path in entries
        if not path.is_symlink()
        and path.is_file()
        and path.resolve().is_relative_to(work)
    }
    same_scope = not has_symlinks and sorted(files) == sorted(state["baseline"])
    lint = {
        name: invoke(["php", "-l", name], work).returncode == 0 if same_scope else None
        for name in state["baseline"]
    }
    # A candidate can exit successfully while require() is still loading it. Only
    # reaching the end of the evaluator's assertions completes the runtime check.
    # This detects early termination; it is not an adversarial execution sandbox.
    marker = "\nPHP_AST_ORACLE_COMPLETE:" + secrets.token_hex(24) + "\n"
    oracle = task["oracle"] + "\n; fwrite(STDOUT, " + json.dumps(marker) + ");"
    runtime = (
        invoke(["php", "-r", oracle], work)
        if same_scope and all(lint.values())
        else None
    )
    runtime_passed = (
        runtime is not None
        and runtime.returncode == 0
        and runtime.stdout.endswith(marker)
    )
    unchanged = all(
        name in files and digest(files[name]) == checksum
        for name, checksum in state["baseline"].items()
    )
    expected_change = (
        unchanged
        if task["outcome"] == "rejected_unchanged"
        else True
        if task["outcome"] == "changed_or_refused"
        else not unchanged
    )
    passed = same_scope and all(lint.values()) and runtime_passed and expected_change
    return {
        "schema_version": 1,
        "task_id": task["id"],
        "task_manifest_sha256": digest(TASKS),
        "passed": passed,
        "file_scope_passed": same_scope,
        "lint": lint,
        "runtime_passed": runtime_passed,
        "expected_change_passed": expected_change,
        "runtime_stderr": runtime.stderr
        if runtime is not None
        else "Skipped: source scope or lint failed.",
        "output_hashes": {
            name: digest(files[name]) for name in state["baseline"] if name in files
        },
        "limitation": "Runtime oracle covers the supplied behavior. Human review of diff and refusal explanation remains required.",
    }


def validate_schema(value, schema, path="$", root=None):
    """Validate the small, explicit subset used by run.schema.json, without dependencies."""
    root = root or schema
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return validate_schema(value, target, path, root)
    types = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "integer": lambda x: type(x) is int,
        "number": lambda x: type(x) in (int, float) and math.isfinite(x),
        "boolean": lambda x: type(x) is bool,
        "null": lambda x: x is None,
    }
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
                validate_schema(
                    child, schema["properties"][key], path + "." + key, root
                )
            elif schema.get("additionalProperties") is False:
                raise ValueError(f"{path}: unknown {key}")
    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            validate_schema(child, schema["items"], f"{path}[{index}]", root)
    if isinstance(value, str) and "pattern" in schema:
        pattern = HASH_PATTERNS.get(schema["pattern"])
        if pattern is None:
            raise ValueError(f"{path}: unsupported schema pattern")
        if pattern.fullmatch(value) is None:
            raise ValueError(f"{path}: malformed value")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ValueError(f"{path}: empty string")
    if type(value) in (int, float) and value < schema.get("minimum", -math.inf):
        raise ValueError(f"{path}: negative value")


def validate_optional_metrics(record, parent, schema):
    if record.get("failed_tool_calls", 0) > record["tool_calls"]:
        raise ValueError("Failed tool calls cannot exceed total tool calls")
    tokens = record["tokens"]
    if tokens["cached_input"] + tokens.get("cache_write_input", 0) > tokens["input"]:
        raise ValueError("Cache-read and cache-write tokens exceed total input")
    timing = record.get("tool_timing")
    if timing is None:
        return
    evidence = timing["evidence"]
    source = (parent / evidence["path"]).resolve()
    if digest(source) != evidence["sha256"]:
        raise ValueError("Tool timing evidence checksum mismatch")
    native = load(source)
    validate_schema(native, {"$ref": "#/$defs/tool_intervals"}, root=schema)
    events = native["intervals"]
    if len(events) != record["tool_calls"] or len(
        {e["call_id"] for e in events}
    ) != len(events):
        raise ValueError("Tool intervals must cover every tool call exactly once")
    intervals = sorted((e["start_ms"], e["end_ms"]) for e in events)
    covered_until = 0
    busy = 0
    durations = []
    for start, end in intervals:
        if end < start or end > record["elapsed_ms"]:
            raise ValueError("Tool interval lies outside the task duration")
        durations.append(end - start)
        busy += max(0, end - max(start, covered_until))
        covered_until = max(covered_until, end)
    measured = {"execution_sum_ms": math.fsum(durations), "busy_wall_ms": busy}
    for key, value in measured.items():
        if not math.isclose(timing[key], value, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError(f"{key} disagrees with native tool intervals")


def summarize_optional_metrics(rows):
    failures = [r["failed_tool_calls"] for r in rows if "failed_tool_calls" in r]
    writes = [
        r["tokens"]["cache_write_input"]
        for r in rows
        if "cache_write_input" in r["tokens"]
    ]
    timings = [r["tool_timing"] for r in rows if "tool_timing" in r]
    return {
        "failed_tool_calls": {
            "measured_runs": len(failures),
            "total": sum(failures) if failures else None,
        },
        "cache_write_input": {
            "measured_runs": len(writes),
            "total": sum(writes) if writes else None,
        },
        "tool_timing": {
            "measured_runs": len(timings),
            "execution_sum_ms": math.fsum(t["execution_sum_ms"] for t in timings)
            if timings
            else None,
            "busy_wall_ms": math.fsum(t["busy_wall_ms"] for t in timings)
            if timings
            else None,
        },
    }


def import_run(record_path, destination):
    record = load(record_path)
    schema = load(SCHEMA)
    validate_schema(record, schema)
    task_by_id(record["task_id"])
    parent = record_path.resolve().parent
    transcript = (parent / record["transcript"]["path"]).resolve()
    oracle_path = (parent / record["oracle"]["path"]).resolve()
    if digest(transcript) != record["transcript"]["sha256"]:
        raise ValueError("Transcript checksum mismatch")
    if digest(oracle_path) != record["oracle"]["sha256"]:
        raise ValueError("Oracle checksum mismatch")
    oracle = load(oracle_path)
    if oracle["task_id"] != record["task_id"] or oracle[
        "task_manifest_sha256"
    ] != digest(TASKS):
        raise ValueError("Oracle does not match current task")
    success = oracle["passed"] and record["review"]["passed"]
    if record["success"] != success:
        raise ValueError("Reported success disagrees with oracle and human review")
    if record["first_attempt_success"] and (
        not success or record["repair_attempts"] != 0
    ):
        raise ValueError("First-attempt success inconsistent with repairs/outcome")
    if record["tokens"]["cached_input"] > record["tokens"]["input"]:
        raise ValueError("Cached input must be a subset of total input")
    validate_optional_metrics(record, parent, schema)
    identity = [
        record[key]
        for key in (
            "task_id",
            "variant",
            "model",
            "model_version",
            "reasoning",
            "cache_condition",
            "repetition",
            "source_commit",
            "harness_config_sha256",
        )
    ]
    # --results is the operator's chosen ledger, with no repository-root restriction.
    existing_text = ""
    if destination.exists():
        existing_text = destination.read_text()  # NOSONAR(S8707)
    existing = [json.loads(line) for line in existing_text.splitlines()]
    for previous in existing:
        if identity == [
            previous[key]
            for key in (
                "task_id",
                "variant",
                "model",
                "model_version",
                "reasoning",
                "cache_condition",
                "repetition",
                "source_commit",
                "harness_config_sha256",
            )
        ]:
            raise ValueError("Duplicate run identity")
    # Preserve origin for resolving relative evidence paths after import.
    record["record_source"] = str(record_path.resolve())
    # These writes use the same explicit local destination; see TRUST.md.
    destination.parent.mkdir(parents=True, exist_ok=True)  # NOSONAR(S8707)
    with destination.open("a") as stream:  # NOSONAR(S8707)
        stream.write(json.dumps(record) + "\n")
    return {"imported": True, "success": success, "task_id": record["task_id"]}


def summarize(path):
    # Read the operator-selected results ledger, as documented in TRUST.md.
    ledger_text = path.read_text()  # NOSONAR(S8707)
    records = [json.loads(line) for line in ledger_text.splitlines()]
    groups = {}
    dimensions = (
        "source_commit",
        "model",
        "model_version",
        "reasoning",
        "cache_condition",
        "harness_config_sha256",
        "variant",
    )
    for record in records:
        key = tuple(record[field] for field in dimensions)
        groups.setdefault(key, []).append(record)
    results = []
    for key, rows in groups.items():
        elapsed = sorted(row["elapsed_ms"] for row in rows)
        successes = sum(row["success"] for row in rows)
        results.append(
            {
                **dict(zip(dimensions, key)),
                "runs": len(rows),
                "successful_runs": successes,
                "success_rate": successes / len(rows),
                "first_attempt_success_rate": sum(
                    r["first_attempt_success"] for r in rows
                )
                / len(rows),
                "median_elapsed_ms_all_attempts": statistics.median(elapsed),
                "p95_elapsed_ms_all_attempts": elapsed[
                    math.ceil(len(elapsed) * 0.95) - 1
                ],
                "elapsed_ms_per_success_including_failures": sum(elapsed) / successes
                if successes
                else None,
                "input_tokens_all_attempts": sum(r["tokens"]["input"] for r in rows),
                "output_tokens_all_attempts": sum(r["tokens"]["output"] for r in rows),
                "cached_input_tokens_all_attempts": sum(
                    r["tokens"]["cached_input"] for r in rows
                ),
                "tool_calls_all_attempts": sum(r["tool_calls"] for r in rows),
                "model_rounds_all_attempts": sum(r["model_rounds"] for r in rows),
                "optional_metrics": summarize_optional_metrics(rows),
            }
        )
    return {
        "groups": results,
        "limitation": "Check paired task coverage before comparisons. Groups do not imply statistical significance or universal savings.",
    }


def self_test_imports(task, work, state, base):
    # Synthetic importer fixtures live only in this temporary test directory. They
    # are not measurements and are never published into benchmarks/results/.
    for length in (40, 64):
        hash_schema = {"type": "string", "pattern": f"^[a-f0-9]{{{length}}}$"}
        validate_schema("a" * length, hash_schema)
        for malformed in ("a" * (length - 1), "A" * length, "a" * length + "\n"):
            try:
                validate_schema(malformed, hash_schema)
            except ValueError:
                continue
            raise RuntimeError("Malformed hash escaped fixed-pattern validation")
    try:
        validate_schema("a", {"type": "string", "pattern": "(a+)+$"})
    except ValueError:
        pass
    else:
        raise RuntimeError("Unsupported schema regex was accepted")
    transcript = base / "synthetic-transcript.txt"
    transcript.write_text(
        "Synthetic importer validation fixture; no model was called.\n"
    )
    oracle = base / "synthetic-oracle.json"
    save(oracle, grade(task, work, state))
    record = {
        "task_id": task["id"],
        "variant": "full_skill",
        "model": "synthetic-test-only",
        "model_version": "test",
        "reasoning": "test",
        "cache_condition": "cold",
        "repetition": 1,
        "source_commit": "0" * 40,
        "harness_config_sha256": "0" * 64,
        "tokens": {"input": 0, "output": 0, "cached_input": 0},
        "tool_calls": 0,
        "cli_invocations": 0,
        "model_rounds": 0,
        "repair_attempts": 0,
        "elapsed_ms": 0,
        "setup_elapsed_ms": 0,
        "cost_usd": None,
        "success": True,
        "first_attempt_success": True,
        "review": {"passed": True, "reviewer": "test", "notes": "Synthetic fixture"},
        "transcript": {"path": transcript.name, "sha256": digest(transcript)},
        "oracle": {"path": oracle.name, "sha256": digest(oracle)},
    }
    candidate, results = (
        base / "synthetic-record.json",
        base / "synthetic-results.jsonl",
    )
    save(candidate, record)
    import_run(candidate, results)
    mutations = [
        lambda r: r,
        lambda r: {**r, "success": False},
        lambda r: {**r, "tokens": {"input": 0, "output": 0, "cached_input": 1}},
        lambda r: {**r, "first_attempt_success": True, "repair_attempts": 1},
        lambda r: {**r, "tool_calls": -1},
        lambda r: {**r, "model_rounds": None},
        lambda r: {**r, "elapsed_ms": float("nan")},
        lambda r: {**r, "transcript": {"path": transcript.name, "sha256": "f" * 64}},
    ]
    for index, mutate in enumerate(mutations):
        altered = mutate({**record, "repetition": 1 if index == 0 else index + 1})
        save(candidate, altered)
        try:
            import_run(candidate, results)
        except ValueError:
            continue
        raise RuntimeError(f"Invalid synthetic importer case {index} was accepted")
    summary = summarize(results)
    if (
        summary["groups"][0]["runs"] != 1
        or summary["groups"][0]["successful_runs"] != 1
    ):
        raise RuntimeError("Synthetic import summary counted rejected rows")
    self_test_optional_metrics(record, candidate, base)
    print(
        "OK: synthetic importer checks reject duplicates, invalid metrics, and altered evidence"
    )


def self_test_optional_metrics(legacy, candidate, base):
    results = base / "synthetic-optional-results.jsonl"
    save(candidate, legacy)
    import_run(candidate, results)
    old_summary = summarize(results)["groups"][0]["optional_metrics"]
    if (
        old_summary["tool_timing"]["measured_runs"] != 0
        or old_summary["tool_timing"]["busy_wall_ms"] is not None
    ):
        raise RuntimeError("Unmeasured legacy timing was converted to zero")
    source = base / "synthetic-tool-intervals.json"
    native = {
        "origin": "native_harness_tool_execution",
        "clock": "monotonic_ms_from_task_start",
        "intervals": [
            {"call_id": "a", "start_ms": 0, "end_ms": 20},
            {"call_id": "b", "start_ms": 10, "end_ms": 25},
        ],
    }
    save(source, native)
    measured = {
        **legacy,
        "repetition": 20,
        "tool_calls": 2,
        "failed_tool_calls": 1,
        "first_attempt_success": False,
        "repair_attempts": 1,
        "elapsed_ms": 30,
        "tokens": {
            "input": 100,
            "output": 0,
            "cached_input": 40,
            "cache_write_input": 20,
        },
        "tool_timing": {
            "execution_sum_ms": 35,
            "busy_wall_ms": 25,
            "evidence": {"path": source.name, "sha256": digest(source)},
        },
    }
    save(candidate, measured)
    import_run(candidate, results)
    summary = summarize(results)["groups"][0]["optional_metrics"]
    if summary != {
        "failed_tool_calls": {"measured_runs": 1, "total": 1},
        "cache_write_input": {"measured_runs": 1, "total": 20},
        "tool_timing": {"measured_runs": 1, "execution_sum_ms": 35, "busy_wall_ms": 25},
    }:
        raise RuntimeError("Mixed legacy/measured rows lost optional metric coverage")
    invalid_records = [
        {**measured, "failed_tool_calls": 3},
        {**measured, "tokens": {**measured["tokens"], "cache_write_input": 70}},
        {**measured, "failed_tool_calls": None},
        {**measured, "tool_timing": {**measured["tool_timing"], "busy_wall_ms": 35}},
        {
            **measured,
            "tool_timing": {**measured["tool_timing"], "execution_sum_ms": 25},
        },
        {**measured, "tool_timing": {"execution_sum_ms": 35, "busy_wall_ms": 25}},
        {
            **measured,
            "tool_timing": {
                **measured["tool_timing"],
                "evidence": {"path": source.name, "sha256": "f" * 64},
            },
        },
    ]
    for index, record in enumerate(invalid_records):
        save(candidate, {**record, "repetition": 30 + index})
        try:
            import_run(candidate, results)
        except ValueError:
            continue
        raise RuntimeError("Invalid optional metric record was accepted")
    invalid_intervals = [
        [],
        [native["intervals"][0], native["intervals"][0]],
        [native["intervals"][0], {"call_id": "b", "start_ms": 25, "end_ms": 10}],
        [native["intervals"][0], {"call_id": "b", "start_ms": 10, "end_ms": 31}],
        [
            native["intervals"][0],
            {"call_id": "b", "start_ms": float("nan"), "end_ms": 25},
        ],
    ]
    for index, intervals in enumerate(invalid_intervals):
        save(source, {**native, "intervals": intervals})
        save(
            candidate,
            {
                **measured,
                "repetition": 50 + index,
                "tool_timing": {
                    **measured["tool_timing"],
                    "evidence": {"path": source.name, "sha256": digest(source)},
                },
            },
        )
        try:
            import_run(candidate, results)
        except ValueError:
            continue
        raise RuntimeError("Invalid native tool intervals were accepted")
    print(
        "OK: optional native metrics preserve legacy rows and account for overlapping tools"
    )


def self_test_oracle_integrity(task, work, state, base, binary):
    early_work, early_state = base / "early-exit", base / "early-exit.state.json"
    prepare(task, early_work, early_state, binary)
    result = invoke(
        ["php", str(binary), "apply"],
        early_work,
        {
            "files": [
                {
                    "path": "Clock.php",
                    "sha256": digest(early_work / "Clock.php"),
                    "edits": [
                        {
                            "target": {"select": "class:Clock"},
                            "operation": "insert_before",
                            "php": "exit(0);",
                        }
                    ],
                }
            ]
        },
    )
    if result.returncode:
        raise RuntimeError("Could not prepare early-exit regression: " + result.stderr)
    outcome = grade(task, early_work, early_state)
    if (
        outcome["passed"]
        or outcome["runtime_passed"]
        or not outcome["file_scope_passed"]
        or not all(outcome["lint"].values())
    ):
        raise RuntimeError("An early exit(0) escaped the runtime oracle")

    source = work / "Clock.php"
    borrowed = base / "borrowed-Clock.php"
    source.rename(borrowed)
    try:
        source.symlink_to(borrowed)
        outcome = grade(task, work, state)
        if (
            outcome["passed"]
            or outcome["file_scope_passed"]
            or outcome["runtime_passed"]
            or any(value is not None for value in outcome["lint"].values())
        ):
            raise RuntimeError(
                "A borrowed source symlink escaped the oracle or skipped lint was misreported"
            )
    finally:
        source.unlink()
        borrowed.rename(source)

    borrowed_directory = base / "borrowed-directory"
    borrowed_directory.mkdir()
    link = work / "external"
    try:
        link.symlink_to(borrowed_directory, target_is_directory=True)
        outcome = grade(task, work, state)
        if (
            outcome["passed"]
            or outcome["file_scope_passed"]
            or outcome["runtime_passed"]
        ):
            raise RuntimeError("A directory symlink escaped the source scope check")
    finally:
        link.unlink()
    print("OK: runtime completion and source scope reject early exits and symlinks")


def self_test(binary):
    tasks = load(TASKS)["tasks"]
    with tempfile.TemporaryDirectory(prefix="php-ast-evals-") as temporary:
        base = Path(temporary)
        for task in tasks:
            work, state = base / task["id"], base / (task["id"] + ".state.json")
            prepare(task, work, state, binary)
            payload = {
                "files": [
                    {**file, "sha256": digest(work / file["path"])}
                    for file in task["edits"]
                ]
            }
            result = invoke(["php", str(binary), "apply"], work, payload)
            rejected = task.get(
                "reference_rejects", task["outcome"] == "rejected_unchanged"
            )
            if (result.returncode != 0) != rejected:
                raise RuntimeError(
                    f"{task['id']}: unexpected exit {result.returncode}: {result.stderr}"
                )
            if not grade(task, work, state)["passed"]:
                raise RuntimeError(f"{task['id']}: reference failed independent oracle")
            if task is tasks[0]:
                self_test_imports(task, work, state, base)
                self_test_oracle_integrity(task, work, state, base, binary)
            if task["outcome"] == "changed_or_refused":
                alternative = invoke(
                    ["php", str(binary), "apply"],
                    work,
                    {
                        "files": [
                            {
                                "path": "Child.php",
                                "sha256": digest(work / "Child.php"),
                                "edits": [
                                    {
                                        "target": {
                                            "select": "method:ChildExample::old"
                                        },
                                        "operation": "set_name",
                                        "value": "renamed",
                                    }
                                ],
                            }
                        ]
                    },
                )
                if alternative.returncode or not grade(task, work, state)["passed"]:
                    raise RuntimeError(
                        "Safe alternative child rename failed the common oracle"
                    )
            # A missing expected source file must fail even if another outcome happens to match.
            missing = task["files"][0]["path"]
            deletion = invoke(
                ["php", str(binary), "apply"],
                work,
                {
                    "files": [
                        {
                            "path": missing,
                            "mode": "delete",
                            "sha256": digest(work / missing),
                        }
                    ]
                },
            )
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
        result = prepare(
            task_by_id(args.task), args.work, args.state, args.bin.resolve()
        )
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
