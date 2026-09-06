"""Prepare and run the bounded four-arm experiment; prepare/validate call no models."""

import argparse
import fcntl
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import tarfile
import time
from decimal import Decimal
from pathlib import Path

from native import read_events, require, summarize

HERE = Path(__file__).resolve().parent
RELATIVE = Path("benchmarks/agent-economics/efficiency")
CONFIG = "config.json"
SCHEDULE = "schedule.json"
MEASUREMENT = "measurement.json"
RAW = "raw.jsonl"
ORACLE = "oracle.json"
INITIAL_HASHES = "initial-hashes.json"
STATE = "state.json"
BASELINE_COMMIT = "baseline-commit.txt"
ARMS = ("contextual_patch", "full_skill", "compact_full", "compact_focused")
MODELS = {
    "sonnet": {"id": "claude-sonnet-4-6", "effort": "medium"},
    "haiku": {"id": "claude-haiku-4-5-20251001", "effort": None},
}
COMMON = """Complete the supplied PHP maintenance task autonomously and accurately.
Read relevant source before editing. Preserve unrelated code and behavior. Batch
related work where useful. Run relevant syntax/behavior checks that remain necessary,
review the intended diff, and finish concisely. Do not create commits, install packages,
use network services or other agents/models. Never inspect home directories, global
instructions/configuration, evaluator/controller/state files or answer keys. Do not
inspect unrelated directories. Work only on the supplied task files; leave no extras.
Dependencies are installed. Bash, Read, Edit and Write are available. Documented tool
and skill paths may be accessed as needed. No repository-wide AST-only rule applies
to these disposable fixtures. Follow this run's editing instructions below.
"""
BASELINE = """Use competent ordinary contextual editing: Edit or contextual patches,
normal source discovery, batching when useful, and relevant checks. Do not use
php-ast-edit or php-ast-agent for this run.
"""
COMPACT = """Use php-ast-agent for PHP reads and writes; do not bypass its guarded apply.
Read with `php-ast-agent read --mode MODE --files FILE --select SELECTOR`.
Selectors include method:Class::method, class:Class and function:name. Read different
selectors with separate commands; related commands can share one Bash invocation.
Keep each returned revision. Submit related edits together via stdin:
`php-ast-agent apply <<'JSON'` followed by the JSON and a closing JSON line.
Payload: {"files":[{"path":"FILE","revision":"RETURNED_REVISION","edits":[EDIT]}]}.
EDIT examples: {"target":{"select":"method:Class::method"},"operation":"rename_variable",
"from":"old","to":"new"}; {"target":{"select":"class:Class"},"operation":"add_member",
"php":"public const VERSION = 2;"}. Optional position is "start", "end" or an integer.
Use `php-ast-edit contexts --operation NAME` for unfamiliar argument schemas.
Read the result's changes, warnings and validation. Reread after stale revisions;
never drop a guard. Run relevant checks still needed and review the intended diff.
"""
CLI_ARGS = [
    "-p",
    "--safe-mode",
    "--disable-slash-commands",
    "--strict-mcp-config",
    "--mcp-config",
    '{"mcpServers":{}}',
    "--setting-sources",
    "",
    "--settings",
    "{}",
    "--no-session-persistence",
    "--tools",
    "Bash,Read,Edit,Write",
    "--output-format",
    "stream-json",
    "--verbose",
    "--permission-mode",
    "bypassPermissions",
    "--prompt-suggestions",
    "false",
    "--name",
    "php-edit-efficiency",
]


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment():
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    return env


def invoke(argv, cwd=None, timeout=90):
    # Explicit trusted local operator/grader argv, never a shell. See PROTOCOL.md.
    return subprocess.run(  # NOSONAR(S6350)
        argv,
        cwd=cwd,
        env=environment(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def checked(argv, cwd=None):
    result = invoke(argv, cwd)
    require(result.returncode == 0, result.stderr or "Local command failed")
    return result.stdout


def archive(source, commit, paths, destination):
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / "snapshot.tar"
    # The local operator selects the checkout, commit and archive paths.
    with temporary.open("wb") as output:
        subprocess.run(  # NOSONAR(S6350)
            ["git", "archive", commit, *paths],
            cwd=source,
            stdout=output,
            check=True,
            timeout=90,
            env=environment(),
        )
    with tarfile.open(temporary) as contents:
        contents.extractall(destination, filter="data")
    temporary.unlink()


def snapshot(args, base):
    source = args.source.resolve()
    commit = checked(["git", "rev-parse", args.source_ref], source).strip()
    status = checked(["git", "status", "--porcelain", "--untracked-files=all"], source)
    require(
        args.development or not status,
        "Commit the experiment before executable preparation",
    )
    runtime, controller = base / "runtime", base / "controller"
    archive(source, commit, ["src", "bin", "skills/php-structured-edit"], runtime)
    archive(
        source,
        commit,
        ["benchmarks/agent_benchmark.py", "benchmarks/tasks.json"],
        controller,
    )
    if args.development:
        shutil.copytree(
            source / RELATIVE,
            controller / "efficiency",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    else:
        archive(source, commit, [str(RELATIVE)], base / "harness-snapshot")
        shutil.copytree(base / "harness-snapshot" / RELATIVE, controller / "efficiency")
    adapter = controller / "efficiency/adapter"
    require((adapter / "php-ast-agent").is_file(), "Adapter executable is not ready")
    shutil.copytree(adapter, runtime / "adapter")
    shutil.copytree(args.vendor.resolve(), runtime / "vendor", symlinks=False)
    if args.manifest:
        shutil.copy2(args.manifest, controller / "benchmarks/tasks.json")
    (base / "tools").mkdir()
    launcher = base / "tools/php-ast-edit"
    shutil.copy2(controller / "efficiency/engine_proxy.py", launcher)
    launcher.chmod(0o755)
    return commit, status


def variants(base):
    skill = base / "runtime/skills/php-structured-edit"
    full = (
        "Apply the complete skill below. Its executable is already on PATH. "
        f"Relative references resolve beneath {skill}.\n\n"
        + (skill / "SKILL.md").read_text()
    )
    return {
        "contextual_patch": BASELINE,
        "full_skill": full,
        "compact_full": COMPACT.replace("MODE", "full"),
        "compact_focused": COMPACT.replace("MODE", "focused"),
    }


def balanced_order(task_ids, seed):
    # A fixed seed orders samples reproducibly; it makes no security decisions.
    rng = random.Random(seed)
    blocks = [
        (task, model, repeat)
        for task in task_ids
        for model in MODELS
        for repeat in range(1, 4)
    ]
    rng.shuffle(blocks)  # NOSONAR(S2245)
    starts = list(range(4)) * (len(blocks) // 4)
    starts += list(range(len(blocks) % 4))
    rng.shuffle(starts)  # NOSONAR(S2245)
    rows = []
    for (task, model, repeat), start in zip(blocks, starts):
        order = ARMS[start:] + ARMS[:start]
        for arm in order:
            rows.append(
                {
                    "run_id": f"run{len(rows) + 1:03}",
                    "task_id": task,
                    "model_key": model,
                    "variant": arm,
                    "repetition": repeat,
                }
            )
    return rows


def exact_template(base, task, target):
    work = target / "work"
    work.mkdir(parents=True)
    for entry in task["files"]:
        path = work / entry["path"]
        require(path.resolve().is_relative_to(work), "Fixture path escapes workspace")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(entry["php"].encode("utf-8"))
    baseline = {entry["path"]: digest(work / entry["path"]) for entry in task["files"]}
    save(
        target / STATE,
        {
            "task_id": task["id"],
            "work": str(work),
            "baseline": baseline,
            "task_manifest_sha256": digest(base / "controller/benchmarks/tasks.json"),
        },
    )
    return {"prompt": task["prompt"], "workspace": str(work), "files": list(baseline)}


def make_templates(base, task_ids, tasks):
    templates = {}
    for task in task_ids:
        target = base / "templates" / task
        specification = next(row for row in tasks if row["id"] == task)
        if specification.get("preserve_source") is True:
            templates[task] = exact_template(base, specification, target)
            continue
        output = checked(
            [
                "python3",
                str(base / "controller/benchmarks/agent_benchmark.py"),
                "--bin",
                str(base / "runtime/bin/php-ast-edit"),
                "prepare",
                task,
                "--work",
                str(target / "work"),
                "--state",
                str(target / STATE),
            ]
        )
        templates[task] = json.loads(output)
    return templates


def prepare_fixture(base, row, template, instructions):
    folder = base / "runs" / row["run_id"]
    work, evidence = folder / "work", folder / "evidence"
    evidence.mkdir(parents=True)
    shutil.copytree(Path(template["workspace"]), work)
    initial = load(base / "templates" / row["task_id"] / STATE)
    state = {**initial, "work": str(work)}
    save(evidence / STATE, state)
    save(evidence / INITIAL_HASHES, initial["baseline"])
    shutil.copytree(work, evidence / "initial")
    checked(["git", "-c", "init.templateDir=", "init", "-q"], work)
    checked(["git", "add", "--", *template["files"]], work)
    checked(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=Benchmark Fixture",
            "-c",
            "user.email=benchmark@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Fixture baseline",
        ],
        work,
    )
    (evidence / BASELINE_COMMIT).write_text(checked(["git", "rev-parse", "HEAD"], work))
    (evidence / "system-append.txt").write_text(COMMON + "\n" + instructions)
    (evidence / "prompt.txt").write_text(
        template["prompt"] + "\n\nFiles: " + ", ".join(template["files"]) + "\n"
    )
    return {**row, "work": str(work), "evidence": str(evidence)}


def freeze(base):
    roots = ["runtime", "controller", "tools", "templates"]
    paths = [
        path for root in roots for path in (base / root).rglob("*") if path.is_file()
    ]
    paths += [base / CONFIG, base / SCHEDULE]
    for row in load(base / SCHEDULE):
        paths += [path for path in Path(row["evidence"]).rglob("*") if path.is_file()]
    save(
        base / "frozen-sha256.json",
        {str(path.relative_to(base)): digest(path) for path in sorted(paths)},
    )


def prepare(args):
    base = args.output.resolve()
    require(
        base.is_relative_to(Path("/tmp")), "Use a fresh Linux /tmp output directory"
    )
    require(not base.exists(), "Output already exists; refusing to replace evidence")
    base.mkdir(parents=True)
    started = time.monotonic()
    commit, status = snapshot(args, base)
    task_ids = args.tasks.split(",")
    require(len(task_ids) == len(set(task_ids)), "Duplicate task IDs")
    require(
        0 < args.campaign_budget_usd <= 8,
        "Campaign budget must be positive and at most USD 8",
    )
    tasks = load(base / "controller/benchmarks/tasks.json")["tasks"]
    require(set(task_ids) <= {task["id"] for task in tasks}, "Unknown task IDs")
    instructions = variants(base)
    templates = make_templates(base, task_ids, tasks)
    schedule = [
        prepare_fixture(
            base, row, templates[row["task_id"]], instructions[row["variant"]]
        )
        for row in balanced_order(task_ids, args.seed)
    ]
    config = {
        "schema_version": 1,
        "source_commit": commit,
        "source_status": status,
        "execution_allowed": not args.development,
        "models": MODELS,
        "arms": ARMS,
        "task_ids": task_ids,
        "repetitions": 3,
        "seed": args.seed,
        "claude": str(args.claude.resolve()),
        "cli_version": checked([str(args.claude), "--version"]).strip(),
        "php_version": checked(["php", "--version"]).splitlines()[0],
        "cli_common": CLI_ARGS,
        "timeout_seconds": 120,
        "max_run_usd": 0.75,
        "campaign_budget_usd": args.campaign_budget_usd,
        "cache_condition": "unknown; fresh independent sessions",
        "effort_policy": "Sonnet medium; Haiku null/not_supported, no effort flag or inherited effort override",
        "billing_note": "Native list-price estimates under existing authentication, not proof of charges",
        "variant_instructions": instructions,
        "common_instructions": COMMON,
        "instruction_words": {
            arm: len(text.split()) for arm, text in instructions.items()
        },
        "common_instruction_words": len(COMMON.split()),
        "full_skill_words": len(
            (base / "runtime/skills/php-structured-edit/SKILL.md").read_text().split()
        ),
        "task_manifest_sha256": digest(base / "controller/benchmarks/tasks.json"),
        "preparation_ms": (time.monotonic() - started) * 1000,
    }
    save(base / CONFIG, config)
    save(base / SCHEDULE, schedule)
    freeze(base)
    validate(base)
    print(
        json.dumps(
            {
                "prepared": len(schedule),
                "execution_allowed": config["execution_allowed"],
                "model_calls": 0,
            }
        )
    )


def validate(base):
    for name, checksum in load(base / "frozen-sha256.json").items():
        require(digest(base / name) == checksum, f"Frozen file changed: {name}")
    grouped = {}
    for row in load(base / SCHEDULE):
        hashes = load(Path(row["evidence"]) / INITIAL_HASHES)
        key = row["task_id"]
        require(
            key not in grouped or grouped[key] == hashes, "Task starting bytes differ"
        )
        grouped[key] = hashes
    print("OK: frozen files and identical task fixtures; model calls: 0")


def candidate_args(row, config):
    evidence = Path(row["evidence"])
    model = config["models"][row["model_key"]]
    argv = [
        config["claude"],
        *config["cli_common"],
        "--model",
        model["id"],
        "--max-budget-usd",
        str(config["max_run_usd"]),
    ]
    if model["effort"] is not None:
        argv += ["--effort", model["effort"]]
    return argv + [
        "--append-system-prompt",
        (evidence / "system-append.txt").read_text(),
        (evidence / "prompt.txt").read_text(),
    ]


def candidate_environment(base, evidence):
    env = environment()
    env["PATH"] = os.pathsep.join(
        [str(base / "tools"), str(base / "runtime/adapter"), env.get("PATH", "")]
    )
    env["PHP_AST_EDIT_BIN"] = str(base / "runtime/bin/php-ast-edit")
    env["PHP_AST_REAL_BIN"] = env["PHP_AST_EDIT_BIN"]
    env["PHP_AST_ENGINE_AUDIT"] = str(evidence / "engine-audit.jsonl")
    env["PHP_AST_AGENT_STATE_DIR"] = str(evidence / "adapter-state")
    return env


def capture(base, row, config, argv):
    evidence = Path(row["evidence"])
    started = time.monotonic()
    timed_out = False
    with (
        (evidence / RAW).open("xb") as output,
        (evidence / "stderr.txt").open("xb") as error,
    ):
        # The local operator selects this argv; no candidate-selected process or shell.
        process = subprocess.Popen(  # NOSONAR(S6350)
            argv,
            cwd=row["work"],
            env=candidate_environment(base, evidence),
            stdout=output,
            stderr=error,
            start_new_session=True,
        )
        try:
            process.wait(timeout=config["timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    return {
        "process_exit_code": process.returncode,
        "timed_out": timed_out,
        "candidate_wall_ms": (time.monotonic() - started) * 1000,
    }


def grade_and_diff(base, row):
    evidence, work = Path(row["evidence"]), Path(row["work"])
    started = time.monotonic()
    graded = invoke(
        [
            "python3",
            str(base / "controller/benchmarks/agent_benchmark.py"),
            "grade",
            row["task_id"],
            "--work",
            str(work),
            "--state",
            str(evidence / STATE),
            "--output",
            str(evidence / ORACLE),
        ]
    )
    (evidence / "grade-stdout.txt").write_text(graded.stdout)
    (evidence / "grade-stderr.txt").write_text(graded.stderr)
    baseline = (evidence / BASELINE_COMMIT).read_text().strip()
    git_statuses = {}
    for name, argv in [
        ("diff.patch", ["git", "diff", "--no-ext-diff", baseline, "--"]),
        ("git-status.txt", ["git", "status", "--porcelain"]),
    ]:
        result = invoke(argv, work)
        (evidence / name).write_text(result.stdout)
        (evidence / f"{name}.stderr").write_text(result.stderr)
        git_statuses[name] = result.returncode
    files = load(evidence / INITIAL_HASHES)
    save(
        evidence / "final-hashes.json",
        {
            name: digest(work / name) if (work / name).is_file() else None
            for name in files
        },
    )
    return {
        "external_grading_ms": (time.monotonic() - started) * 1000,
        "oracle": load(evidence / ORACLE) if (evidence / ORACLE).exists() else None,
        "grader_exit_code": graded.returncode,
        "git_capture_exit_codes": git_statuses,
    }


def audit_records(path):
    if not path.exists():
        return {"records": [], "errors": [], "present": False}
    records, errors = read_events(path)
    return {"records": records, "errors": errors, "present": True}


def run_one(base, row, config):
    evidence = Path(row["evidence"])
    require(
        not (evidence / RAW).exists(), "Raw evidence exists; never rerun a candidate"
    )
    for name, checksum in load(evidence / INITIAL_HASHES).items():
        require(digest(Path(row["work"]) / name) == checksum, "Pending fixture changed")
    argv = candidate_args(row, config)
    save(evidence / "argv.json", argv)
    try:
        observed = capture(base, row, config, argv)
    except OSError as error:
        observed = {
            "process_exit_code": None,
            "timed_out": False,
            "candidate_wall_ms": None,
            "process_start_error": str(error),
        }
    events, malformed = read_events(evidence / RAW)
    result = {
        **row,
        **observed,
        "source_commit": config["source_commit"],
        "config_sha256": digest(base / CONFIG),
        "raw_sha256": digest(evidence / RAW),
        "requested_model": config["models"][row["model_key"]]["id"],
        "effort": config["models"][row["model_key"]]["effort"],
        "malformed_native_lines": malformed,
        "accounting_errors": [],
        "review": {"agent": "pending", "human": "pending"},
    }
    try:
        require(not malformed, "Malformed native events")
        result.update(summarize(events, result["requested_model"]))
    except (ValueError, KeyError, TypeError) as error:
        result["accounting_errors"].append(str(error))
    try:
        result.update(grade_and_diff(base, row))
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        result["grading_error"] = str(error)
    result["engine_audit"] = audit_records(evidence / "engine-audit.jsonl")
    result["adapter_audit"] = audit_records(evidence / "adapter-state/audit.jsonl")
    result["adherence_review"] = (
        "Pending trace review; supplied arm does not prove instruction compliance"
    )
    save(evidence / MEASUREMENT, result)
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in [
                    "run_id",
                    "variant",
                    "model_key",
                    "native_list_price_usd",
                    "all_model_tokens",
                    "candidate_wall_ms",
                    "accounting_errors",
                ]
            }
        ),
        flush=True,
    )
    require(
        not result["accounting_errors"],
        "Accounting/model/isolation failure; stop subsequent runs",
    )
    require(not result["timed_out"], "Candidate timed out; stop subsequent runs")
    require(
        result["native_list_price_usd"] <= config["max_run_usd"],
        "Native per-run cap exceeded; stop",
    )
    return result


def bounded_cost(result, limit):
    value = result.get("native_list_price_usd")
    require(type(value) in (int, float), "Existing native cost is unknown")
    amount = Decimal(str(value))
    require(
        amount.is_finite() and 0 <= amount <= Decimal(str(limit)),
        "Existing native cost violates per-run cap",
    )
    return amount


def spent_so_far(base, schedule):
    spent = Decimal(0)
    config = load(base / CONFIG)
    for row in schedule:
        evidence = Path(row["evidence"])
        if (evidence / MEASUREMENT).exists():
            result = load(evidence / MEASUREMENT)
            require(
                not result["accounting_errors"],
                "Existing run has unresolved accounting",
            )
            require(not result["timed_out"], "Existing timed-out run requires review")
            require(
                result["config_sha256"] == digest(base / CONFIG),
                "Existing run configuration differs",
            )
            require(
                result["raw_sha256"] == digest(evidence / RAW),
                "Existing raw evidence changed",
            )
            spent += bounded_cost(result, config["max_run_usd"])
        else:
            require(
                not (evidence / RAW).exists(),
                "Interrupted raw run requires offline recovery; never repeat it",
            )
    require(
        spent <= Decimal(str(config["campaign_budget_usd"])),
        "Existing campaign spend exceeds budget",
    )
    return spent


def run(base, execute_models):
    require(
        execute_models, "run requires explicit --execute-models after protocol approval"
    )
    config, schedule = load(base / CONFIG), load(base / SCHEDULE)
    require(config["execution_allowed"], "Development snapshots cannot invoke models")
    validate(base)
    with (base / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        spent = spent_so_far(base, schedule)
        for row in schedule:
            if (Path(row["evidence"]) / MEASUREMENT).exists():
                continue
            require(
                spent + Decimal(str(config["max_run_usd"]))
                <= Decimal(str(config["campaign_budget_usd"])),
                "Campaign budget cannot reserve the next run; stop",
            )
            result = run_one(base, row, config)
            spent += Decimal(str(result["native_list_price_usd"]))
            save(
                base / "campaign-progress.json",
                {"spent_native_list_usd": str(spent), "last_run": row["run_id"]},
            )
            require(
                spent <= Decimal(str(config["campaign_budget_usd"])),
                "Campaign native budget exceeded; stop",
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "validate", "run"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=HERE.parents[2])
    parser.add_argument("--source-ref", default="HEAD")
    parser.add_argument("--vendor", type=Path)
    parser.add_argument("--manifest", "--tasks-json", type=Path)
    parser.add_argument("--tasks", default="local-variable,multi-file-members")
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--campaign-budget-usd", type=float, default=8.0)
    parser.add_argument(
        "--claude", type=Path, default=Path(shutil.which("claude") or "claude")
    )
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--execute-models", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        args.vendor = args.vendor or args.source / "vendor"
        prepare(args)
    elif args.command == "validate":
        validate(args.output.resolve())
    else:
        run(args.output.resolve(), args.execute_models)


if __name__ == "__main__":
    main()
