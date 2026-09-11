"""Prepare and run the bounded arm experiment; prepare/validate call no models."""

import argparse
import fcntl
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import signal
import subprocess
import tarfile
import time
from decimal import Decimal
from pathlib import Path

from native import collect, read_events, require, summarize, validate_init

HERE = Path(__file__).resolve().parent
RELATIVE = Path("benchmarks/agent-economics/efficiency")
CONFIG = "config.json"
SCHEDULE = "schedule.json"
MEASUREMENT = "measurement.json"
RECOVERED = "measurement-recovered.json"
AMENDMENT = "amendment-provenance.json"
TIMEOUT_RESERVATION = "timeout-reservation.json"
RAW = "raw.jsonl"
ORACLE = "oracle.json"
INITIAL_HASHES = "initial-hashes.json"
STATE = "state.json"
BASELINE_COMMIT = "baseline-commit.txt"
TASK_MANIFEST = "controller/benchmarks/tasks.json"
ARMS = (
    "contextual_patch",
    "full_skill",
    "compact_full",
    "compact_focused",
    "check_manual",
    "check_integrated",
)
# Experimental arms are opt-in so the established default schedule and its
# validation remain unchanged for released protocols.
EXPERIMENTAL_ARMS = ("minimal_intent", "delegated_intent", "exact_invocation")
SUPPORTED_ARMS = ARMS + EXPERIMENTAL_ARMS
# The two arms that carry a project check. Both get `check.php` and the same task clause;
# only `check_integrated` declares the check to the engine, so the one variable between
# them is whether `apply` runs it and reports the verdict.
CHECK_ARMS = ("check_manual", "check_integrated")
CHECK_SCRIPT = "check.php"
CHECK_COMMAND = ["php", CHECK_SCRIPT]
CHECK_CLAUSE = "Make sure `php check.php` still passes."
CHECK_CONFIG = {"verify": [{"scope": "project", "command": CHECK_COMMAND}]}
# Parses every PHP file in the tree in-process: TOKEN_PARSE makes token_get_all raise on
# a syntax error. Deliberately cheap — it exists so a fixture can declare a project-scoped
# check at all, and is not a stand-in for a real static analyser's cost.
CHECK_SOURCE = """<?php

declare(strict_types=1);

$failures = [];
$tree = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator(__DIR__, FilesystemIterator::SKIP_DOTS),
);

foreach ($tree as $file) {
    if ($file->getExtension() !== 'php' || $file->getPathname() === __FILE__) {
        continue;
    }

    try {
        token_get_all((string) file_get_contents($file->getPathname()), TOKEN_PARSE);
    } catch (ParseError $error) {
        $failures[] = $file->getPathname() . ': ' . $error->getMessage();
    }
}

if ($failures !== []) {
    echo implode("\\n", $failures), "\\n";

    exit(1);
}

echo "OK: every PHP file parses\\n";
"""
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
DELEGATED_COMMON = COMMON.replace(
    "Read relevant source before editing.",
    "Ensure relevant source is read before editing; for a supported method rename, the command performs this discovery.",
)
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
    # Operator-selected executable and argv; no shell/sandbox promise. See benchmarks/TRUST.md.
    return subprocess.run(  # NOSONAR(S6350, S8701, S8705)
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
    minimal_intent = (
        "Use the already supplied `php-ast-edit` executable for PHP writes. For a method "
        "rename, invoke `php-ast-edit rename --method 'Class::old' --to new`; provide the project path "
        "when the command requires it. The command resolves supported project callers "
        "and runs configured checks. Review the returned diff, warnings, and checks. Do "
        "extra work only for remaining requirements or unresolved warnings; preserve guards "
        "and unrelated files. It makes no guarantee for unsupported or unresolved cases."
    )
    instructions = {
        "contextual_patch": BASELINE,
        "full_skill": full,
        "minimal_intent": minimal_intent,
        "delegated_intent": minimal_intent
        + " When the task names the class and method to rename, invoke the command before reading or searching PHP for declaration or caller discovery. Invoke it once for the named method family; it handles supported declarations and callers together. Do not queue separate renames for each implementation or caller. Read source yourself only when needed for another requirement, a failed command, or unresolved warnings.",
        "compact_full": COMPACT.replace("MODE", "full"),
        "compact_focused": COMPACT.replace("MODE", "focused"),
        # Identical text in both check arms: nothing in an instruction may name the
        # declared check, or the measurement would be of the wording rather than of
        # what `apply` reports.
        "check_manual": full,
        "check_integrated": full,
    }
    instructions["exact_invocation"] = instructions["delegated_intent"]
    return instructions


def common_instructions(variant):
    return (
        DELEGATED_COMMON
        if variant in ("delegated_intent", "exact_invocation")
        else COMMON
    )


def system_instructions(variant, instructions):
    return common_instructions(variant) + "\n" + instructions


def balanced_order(
    task_ids,
    seed,
    arms=ARMS,
    model_keys=tuple(MODELS),
    repetitions=3,
    balance_by_task=False,
):
    require(
        arms and len(arms) == len(set(arms)) and set(arms) <= set(SUPPORTED_ARMS),
        "Invalid or duplicate arms",
    )
    require(
        model_keys
        and len(model_keys) == len(set(model_keys))
        and set(model_keys) <= set(MODELS),
        "Invalid or duplicate model keys",
    )
    require(
        type(repetitions) is int and repetitions > 0,
        "Repetitions must be a positive integer",
    )
    require(
        not balance_by_task or repetitions % len(arms) == 0,
        "Per-task balance requires repetitions divisible by the arm count",
    )
    # A fixed seed orders samples reproducibly; it makes no security decisions.
    rng = random.Random(seed)
    blocks = [
        (task, model, repeat)
        for task in task_ids
        for model in model_keys
        for repeat in range(1, repetitions + 1)
    ]
    rng.shuffle(blocks)  # NOSONAR(S2245)
    starts = list(range(len(arms))) * (len(blocks) // len(arms))
    starts += list(range(len(blocks) % len(arms)))
    rng.shuffle(starts)  # NOSONAR(S2245)
    if balance_by_task:
        task_starts = {}
        for task in task_ids:
            for model in model_keys:
                positions = list(range(len(arms))) * (repetitions // len(arms))
                rng.shuffle(positions)  # NOSONAR(S2245)
                task_starts[task, model] = iter(positions)
        starts = [next(task_starts[task, model]) for task, model, _ in blocks]
    rows = []
    for (task, model, repeat), start in zip(blocks, starts):
        order = arms[start:] + arms[:start]
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


def selected_intent(task):
    intent = task.get("intent")
    if "intent" not in task:
        return None
    require(
        isinstance(intent, dict) and set(intent) == {"method", "file", "to", "path"},
        "Intent needs exactly method, file, to and path",
    )
    require(
        all(
            isinstance(value, str) and value.strip() and "\0" not in value
            for value in intent.values()
        ),
        "Intent values must be nonempty strings",
    )
    file = Path(intent["file"])
    require(
        not file.is_absolute()
        and ".." not in file.parts
        and intent["file"] in {entry["path"] for entry in task["files"]},
        "Intent file must be a contained task file",
    )
    require(intent["path"] == ".", "Intent project path must be '.'")
    return dict(intent)


def intent_prompt(template, variant):
    intent = template.get("intent")
    require(
        variant != "exact_invocation" or intent is not None,
        "Exact invocation requires selected intent metadata",
    )
    if intent is None:
        return ""
    text = (
        "\n\nSelected rename intent (provided equally to both arms):\n"
        + json.dumps(intent, sort_keys=True)
        + "\nYou may use the declaration file with --file."
    )
    if variant == "exact_invocation":
        command = [
            "php-ast-edit",
            "rename",
            "--method",
            intent["method"],
            "--to",
            intent["to"],
            "--path",
            intent["path"],
            "--file",
            intent["file"],
        ]
        text += "\n\nReady-to-run invocation:\n" + shlex.join(command)
    return text


def exact_template(base, task, target):
    intent = selected_intent(task)
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
            "task_manifest_sha256": digest(base / TASK_MANIFEST),
        },
    )
    template = {
        "prompt": task["prompt"],
        "workspace": str(work),
        "files": list(baseline),
    }
    if intent is not None:
        template["intent"] = intent
    return template


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
        intent = selected_intent(specification)
        if intent is not None:
            templates[task]["intent"] = intent
    return templates


def check_fixture(work, variant):
    """The project check both check arms carry, declared to the engine in one of them.

    `check.php` is written for both, so the arms differ by the declaration alone. The task
    clause asks for the same command in both, and neither instruction text mentions that
    `apply` can run it: what the integrated arm's model learns, it learns from the report.

    Returns the paths to add to the fixture commit, so an untracked file cannot turn up in
    `diff.patch` or `git-status.txt` and read as something the model left behind.
    """
    if variant not in CHECK_ARMS:
        return []
    (work / CHECK_SCRIPT).write_text(CHECK_SOURCE)
    added = [CHECK_SCRIPT]

    if variant == "check_integrated":
        save(work / ".php-ast-edit.json", CHECK_CONFIG)
        added.append(".php-ast-edit.json")

    return added


def prepare_fixture(base, row, template, instructions):
    intent_text = intent_prompt(template, row["variant"])
    folder = base / "runs" / row["run_id"]
    work, evidence = folder / "work", folder / "evidence"
    evidence.mkdir(parents=True)
    shutil.copytree(Path(template["workspace"]), work)
    extra = check_fixture(work, row["variant"])
    initial = load(base / "templates" / row["task_id"] / STATE)
    state = {
        **initial,
        "work": str(work),
        "fixture": {name: digest(work / name) for name in extra},
    }
    save(evidence / STATE, state)
    save(evidence / INITIAL_HASHES, initial["baseline"])
    shutil.copytree(work, evidence / "initial")
    checked(["git", "-c", "init.templateDir=", "init", "-q"], work)
    checked(["git", "add", "--", *template["files"], *extra], work)
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
    (evidence / "system-append.txt").write_text(
        system_instructions(row["variant"], instructions)
    )
    prompt = template["prompt"]

    if row["variant"] in CHECK_ARMS:
        prompt += " " + CHECK_CLAUSE
    (evidence / "prompt.txt").write_text(
        prompt + "\n\nFiles: " + ", ".join(template["files"]) + intent_text + "\n"
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


def create_campaign_directory(output):
    base = output.absolute()
    # Direct child of sticky Linux /tmp, atomically created owner-only; see TRUST.md.
    require(
        base.parent == Path("/tmp"),  # NOSONAR(S5443)
        "Use a fresh direct child of Linux /tmp as the output directory",
    )
    try:
        base.mkdir(mode=0o700)
    except FileExistsError as error:
        raise ValueError(
            "Output already exists; refusing to replace evidence"
        ) from error
    return base


def prepare(args):
    arms = tuple(args.arms.split(","))
    model_keys = tuple(args.models.split(","))
    repetitions = getattr(args, "repetitions", 3)
    balance_by_task = getattr(args, "balance_by_task", False)
    planned_order = balanced_order(
        args.tasks.split(","), args.seed, arms, model_keys, repetitions, balance_by_task
    )
    base = create_campaign_directory(args.output)
    started = time.monotonic()
    commit, status = snapshot(args, base)
    task_ids = args.tasks.split(",")
    require(len(task_ids) == len(set(task_ids)), "Duplicate task IDs")
    require(
        0 < args.campaign_budget_usd <= 8,
        "Campaign budget must be positive and at most USD 8",
    )
    tasks = load(base / TASK_MANIFEST)["tasks"]
    require(set(task_ids) <= {task["id"] for task in tasks}, "Unknown task IDs")
    instructions = {arm: text for arm, text in variants(base).items() if arm in arms}
    templates = make_templates(base, task_ids, tasks)
    schedule = [
        prepare_fixture(
            base, row, templates[row["task_id"]], instructions[row["variant"]]
        )
        for row in planned_order
    ]
    config = {
        "schema_version": 1,
        "source_commit": commit,
        "source_status": status,
        "execution_allowed": not args.development,
        "models": MODELS,
        "model_keys": model_keys,
        "arms": arms,
        "task_ids": task_ids,
        "repetitions": repetitions,
        "balance_by_task": balance_by_task,
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
        "common_instructions_by_variant": {
            arm: common_instructions(arm) for arm in instructions
        },
        "instruction_words": {
            arm: len(text.split()) for arm, text in instructions.items()
        },
        "common_instruction_words": len(COMMON.split()),
        "full_skill_words": len(
            (base / "runtime/skills/php-structured-edit/SKILL.md").read_text().split()
        ),
        "task_manifest_sha256": digest(base / TASK_MANIFEST),
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
        "controller_provenance": controller_provenance(base),
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


def controller_provenance(base, folder=None):
    folder = HERE if folder is None else folder
    config = load(base / CONFIG)
    if folder == base / "controller/efficiency":
        return {
            "kind": "original_frozen_controller",
            "source_commit": config["source_commit"],
            "runner_sha256": digest(folder / "runner.py"),
            "native_sha256": digest(folder / "native.py"),
        }
    require(
        folder.parent == base
        and folder.resolve() == folder
        and re.fullmatch(
            r"controller-amendment-v[1-9]\d*", folder.name, flags=re.ASCII
        ),
        "Unrecognized controller location",
    )
    manifest = load(folder / AMENDMENT)
    require(
        manifest["original_source_commit"] == config["source_commit"],
        "Amendment source mismatch",
    )
    require(
        manifest["config_sha256"] == digest(base / CONFIG),
        "Amendment configuration mismatch",
    )
    revision = manifest.get("source_commit", "")
    require(
        len(revision) == 40 and all(c in "0123456789abcdef" for c in revision),
        "Missing amendment commit",
    )
    require(
        set(manifest["files"]) == {"runner.py", "native.py", "PROTOCOL.md"},
        "Unexpected amendment files",
    )
    for name, checksum in manifest["files"].items():
        require(digest(folder / name) == checksum, f"Amendment changed: {name}")
    return {
        "kind": folder.name,
        "source_commit": revision,
        "manifest_sha256": digest(folder / AMENDMENT),
        "files": manifest["files"],
    }


def recovered_measurement(base, evidence, folder=None):
    """Reinterpret the legacy controller's input-total rejection under amendment v1.

    Current producers already accept evidenced native retries. Their unexplained
    input gaps remain unsupported; this is not a general accounting-error repair.
    Full current raw-trace validation and the frozen v1 provenance still apply.
    """
    original = load(evidence / MEASUREMENT)
    require(
        original["accounting_errors"] == ["Response input totals differ"],
        "Unsupported recovery error",
    )
    require(not original["timed_out"], "Cannot recover timed-out candidate")
    require(
        original["config_sha256"] == digest(base / CONFIG), "Recovery config changed"
    )
    require(original["raw_sha256"] == digest(evidence / RAW), "Recovery raw changed")
    events, malformed = read_events(evidence / RAW)
    require(not malformed, "Cannot recover malformed native events")
    accounting = summarize(events, original["requested_model"])
    require(
        accounting["response_input_coverage"] == "incomplete_native_retry",
        "Unsupported recovery coverage",
    )
    provenance = controller_provenance(base, folder)
    require(
        provenance["kind"] == "controller-amendment-v1",
        "Recovery requires frozen amendment",
    )
    return {
        **original,
        **accounting,
        "accounting_errors": [],
        "original_accounting_errors": original["accounting_errors"],
        "original_measurement_sha256": digest(evidence / MEASUREMENT),
        "controller_provenance": provenance,
        "recovery_note": "Offline native accounting interpretation only; original attempt and measurement retained",
    }


def recover(base, run_id):
    validate(base)
    matches = [row for row in load(base / SCHEDULE) if row["run_id"] == run_id]
    require(len(matches) == 1, "Recovery run ID not in frozen schedule")
    evidence = Path(matches[0]["evidence"])
    require(not (evidence / RECOVERED).exists(), "Recovery sidecar already exists")
    result = recovered_measurement(base, evidence)
    bounded_cost(result, load(base / CONFIG)["max_run_usd"])
    save(evidence / RECOVERED, result)
    print(
        json.dumps(
            {
                "recovered": run_id,
                "model_calls": 0,
                "sidecar": str(evidence / RECOVERED),
            }
        )
    )


def existing_measurement(base, evidence):
    if not (evidence / RECOVERED).exists():
        return load(evidence / MEASUREMENT)
    recovered = load(evidence / RECOVERED)
    require(
        recovered
        == recovered_measurement(base, evidence, recorded_controller(base, recovered)),
        "Recovery sidecar differs from linked native evidence",
    )
    return recovered


def recorded_controller(base, sidecar):
    kind = sidecar.get("controller_provenance", {}).get("kind")
    require(isinstance(kind, str), "Missing sidecar controller identity")
    return base / kind


def timeout_evidence(base, evidence):
    original = load(evidence / MEASUREMENT)
    require(original["timed_out"] is True, "Reservation requires actual timeout")
    require(
        original["accounting_errors"]
        == ["Missing native terminal result; spend is unknown"],
        "Unsupported timeout accounting error",
    )
    require(
        original.get("native_list_price_usd") is None, "Timeout cost is not unknown"
    )
    require(
        original["config_sha256"] == digest(base / CONFIG), "Timeout config changed"
    )
    require(original["raw_sha256"] == digest(evidence / RAW), "Timeout raw changed")
    events, malformed = read_events(evidence / RAW)
    require(
        not malformed and not any(row.get("type") == "result" for row in events),
        "Timeout has malformed events or a terminal result",
    )
    init = next(
        (
            row
            for row in events
            if row.get("type") == "system" and row.get("subtype") == "init"
        ),
        None,
    )
    validate_init(init, original["requested_model"])
    responses, calls, results = collect(events)
    require(
        responses
        and all(
            row["model"] == original["requested_model"] for row in responses.values()
        ),
        "Timeout response model differs",
    )
    require(set(calls) == set(results), "Timeout tool linkage incomplete")
    return original


def timeout_reservation(base, evidence, folder=None):
    folder = HERE if folder is None else folder
    original = timeout_evidence(base, evidence)
    provenance = controller_provenance(base, folder)
    require(
        provenance["kind"].startswith("controller-amendment-v"),
        "Timeout review requires a frozen versioned controller",
    )
    reviews = load(folder / AMENDMENT).get("approved_timeout_reviews", {})
    review = reviews.get(original["run_id"], {})
    links = {
        "run_id": original["run_id"],
        "config_sha256": digest(base / CONFIG),
        "raw_sha256": digest(evidence / RAW),
        "original_measurement_sha256": digest(evidence / MEASUREMENT),
    }
    require(
        all(review.get(key) == value for key, value in links.items()),
        "Timeout lacks individually linked approval",
    )
    for role in ("operator", "independent"):
        attestation = review.get(role, {})
        require(
            attestation.get("status") == "approved"
            and attestation.get("reviewer")
            and attestation.get("note"),
            "Timeout review is not approved",
        )
    return {
        "schema_version": 1,
        "kind": "operator_reviewed_timeout_budget_reservation",
        **links,
        "budget_reservation_usd": str(Decimal(str(load(base / CONFIG)["max_run_usd"]))),
        "observed_native_cost_usd": None,
        "native_usage_status": "unknown_no_terminal_result",
        "note": "Planning reservation only; neither observed cost nor a proven actual spending ceiling. Original failure and unknown usage remain unchanged.",
        "review": review,
        "controller_provenance": provenance,
    }


def reserve_timeout(base, run_id):
    validate(base)
    matches = [row for row in load(base / SCHEDULE) if row["run_id"] == run_id]
    require(len(matches) == 1, "Timeout run ID not in frozen schedule")
    evidence = Path(matches[0]["evidence"])
    require(
        load(evidence / MEASUREMENT)["run_id"] == run_id,
        "Timeout measurement run ID differs from schedule",
    )
    require(
        not (evidence / TIMEOUT_RESERVATION).exists(),
        "Timeout reservation already exists",
    )
    save(evidence / TIMEOUT_RESERVATION, timeout_reservation(base, evidence))
    print(
        json.dumps(
            {"reserved_timeout": run_id, "model_calls": 0, "observed_cost": None}
        )
    )


def budget_so_far(base, schedule):
    known, reserved = Decimal(0), Decimal(0)
    config = load(base / CONFIG)
    for row in schedule:
        evidence = Path(row["evidence"])
        if (evidence / MEASUREMENT).exists():
            require(
                load(evidence / MEASUREMENT)["run_id"] == row["run_id"],
                "Existing measurement run ID differs from schedule",
            )
            if (evidence / TIMEOUT_RESERVATION).exists():
                sidecar = load(evidence / TIMEOUT_RESERVATION)
                require(
                    sidecar
                    == timeout_reservation(
                        base, evidence, recorded_controller(base, sidecar)
                    ),
                    "Timeout reservation differs from approved evidence",
                )
                reserved += Decimal(sidecar["budget_reservation_usd"])
                continue
            result = existing_measurement(base, evidence)
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
            known += bounded_cost(result, config["max_run_usd"])
        else:
            require(
                not (evidence / RAW).exists(),
                "Interrupted raw run requires offline recovery; never repeat it",
            )
    require(
        known + reserved <= Decimal(str(config["campaign_budget_usd"])),
        "Existing campaign allocation exceeds budget",
    )
    return {
        "known_native_list_usd": known,
        "reserved_unknown_usd": reserved,
        "allocated_usd": known + reserved,
    }


def spent_so_far(base, schedule):
    """Known native subtotal only; use budget_so_far for planning allocation."""
    return budget_so_far(base, schedule)["known_native_list_usd"]


def run(base, execute_models):
    require(
        execute_models, "run requires explicit --execute-models after protocol approval"
    )
    config, schedule = load(base / CONFIG), load(base / SCHEDULE)
    require(config["execution_allowed"], "Development snapshots cannot invoke models")
    validate(base)
    controller_provenance(base)
    with (base / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        budget = budget_so_far(base, schedule)
        for row in schedule:
            if (Path(row["evidence"]) / MEASUREMENT).exists():
                continue
            require(
                budget["allocated_usd"] + Decimal(str(config["max_run_usd"]))
                <= Decimal(str(config["campaign_budget_usd"])),
                "Campaign budget cannot reserve the next run; stop",
            )
            result = run_one(base, row, config)
            amount = Decimal(str(result["native_list_price_usd"]))
            budget["known_native_list_usd"] += amount
            budget["allocated_usd"] += amount
            save(
                base / "campaign-progress.json",
                {
                    "spent_native_list_usd": str(budget["known_native_list_usd"]),
                    "reserved_unknown_usd": str(budget["reserved_unknown_usd"]),
                    "allocated_budget_usd": str(budget["allocated_usd"]),
                    "last_run": row["run_id"],
                },
            )
            require(
                budget["allocated_usd"] <= Decimal(str(config["campaign_budget_usd"])),
                "Campaign allocation exceeded; stop",
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "validate", "recover", "reserve-timeout", "run"]
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=HERE.parents[2])
    parser.add_argument("--source-ref", default="HEAD")
    parser.add_argument("--vendor", type=Path)
    parser.add_argument("--manifest", "--tasks-json", type=Path)
    parser.add_argument("--tasks", default="local-variable,multi-file-members")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--balance-by-task", action="store_true")
    parser.add_argument("--campaign-budget-usd", type=float, default=8.0)
    parser.add_argument(
        "--claude", type=Path, default=Path(shutil.which("claude") or "claude")
    )
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--execute-models", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.command == "prepare":
        args.vendor = args.vendor or args.source / "vendor"
        prepare(args)
    elif args.command == "validate":
        validate(args.output.resolve())
    elif args.command == "recover":
        recover(args.output.resolve(), args.run_id)
    elif args.command == "reserve-timeout":
        reserve_timeout(args.output.resolve(), args.run_id)
    else:
        run(args.output.resolve(), args.execute_models)


if __name__ == "__main__":
    main()
