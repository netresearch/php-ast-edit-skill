#!/usr/bin/env python3
"""Prospective public-PHP rename trial with final-byte behavior-test receipts."""

import argparse
import json
import math
import random
import shlex
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pilot
import postcheck_pilot
import real_fixture as fixture
from lsp import require

EXPERIMENT = "real-php-verification-v1"
ARMS = ("text-manual", "ast-manual", "ast-integrated")
GUIDANCE_EXPERIMENT = "real-php-guidance-v1"
PROFILES = {
    EXPERIMENT: {
        "arms": ARMS,
        "seed": 20260909,
        "campaign_usd": 8.0,
        "pairs": (("text-manual", "ast-manual"), ("ast-manual", "ast-integrated")),
    },
    GUIDANCE_EXPERIMENT: {
        "arms": ("compact", "guidance"),
        "seed": 20260910,
        "campaign_usd": 5.0,
        "pairs": (("compact", "guidance"),),
    },
}
PROJECT_CONFIG = ".php-ast-edit.json"
PHPUNIT_FILE = "phpunit.phar"
CONTROLLER = "source/benchmarks/symbol-intent/real_pilot.py"
COMMON = """Complete the requested PHP change efficiently and correctly. You may batch
reads, searches, edits and checks in one tool call. Work only in this workspace.
Do not read home instructions, controller, evaluator, state, receipt or answer files.
Invoke the provided external commands only as documented; do not inspect their
implementation. Bash/Read/Edit/Write are available. Do not commit or change Git config.
Use reported facts only for their stated scope. Exact replacement evidence is not
proof of reference completeness; the provided checker exercises the existing tests.
Do not repeat passed parser, lint, byte or behavior checks on unchanged final files.
A passed configured verification using the provided checker satisfies the same test
obligation as invoking it manually. If files change after a passed check, check the
final bytes again. Finish once the requested edit and final-byte test obligation are
met; do not add inspection merely to reconfirm a passed check. State what changed
and what was actually checked, including any failed or unrun required checks.
"""


def profile(experiment):
    require(experiment in PROFILES, "Unknown experiment")
    return PROFILES[experiment]


def schedule(experiment=EXPERIMENT):
    design = profile(experiment)
    arms = design["arms"]
    repeats = list(range(10))
    # Fixed prospective order; not security-sensitive randomness.
    random.Random(design["seed"]).shuffle(repeats)  # NOSONAR(S2245)
    rows = []
    for block, repeat in enumerate(repeats):
        offset = block % len(arms)
        for arm in arms[offset:] + arms[:offset]:
            rows.append(
                {"id": f"run{len(rows) + 1:03d}", "repetition": repeat, "arm": arm}
            )
    return rows


def prompts(task, arm, rename, checker):
    require(arm in ARMS, "Unknown treatment")
    common = (
        f"Rename {task['select']} in {task['file']} to {task['to']} and update its PHP callers "
        "within this workspace, including callers in the existing tests. "
        "Only change method-name identifier tokens required by that rename; preserve all other bytes, "
        "including assertions, comments, strings, whitespace, LICENSE, provenance and project configuration.\n\n"
        f"Required verification: all 17 existing PHPUnit tests must actually execute successfully on the final "
        f"file bytes using {shlex.quote(str(checker))}. The checker runs the existing test suite and fails if "
        "the test count differs or the files change during checking. It does not judge whether the requested "
        "rename was performed. A successful configured invocation of this same checker also satisfies "
        "the requirement. Do not substitute syntax checks or an invented test for this command.\n\n"
    )
    if arm == "text-manual":
        route = "Use ordinary text edits or a batched script. No AST or semantic mutation tool is provided for this arm. Invoke the checker after your final edit."
    else:
        command = shlex.join(
            [
                str(rename),
                "--file",
                task["file"],
                "--select",
                task["select"],
                "--to",
                task["to"],
            ]
        )
        route = f"Use the symbol-aware AST rename command: {command}. It resolves references, applies a guarded transaction and reports evidence; completeness remains unknown. Failed project verification retains edits (exit 1). "
        route += "All PHP mutations in this arm must use this command; ordinary tools may be used for reads and checks. "
        route += (
            "Project configuration invokes the same checker automatically after applying the rename."
            if arm == "ast-integrated"
            else "Invoke the checker after your final edit."
        )
    return COMMON, common + route


def cli_identity():
    executable = shutil.which("claude")
    require(executable is not None, "Claude CLI is unavailable")
    return executable, pilot.invoke([executable, "--version"]).stdout.strip()


def runtime_identity():
    php = shutil.which("php")
    require(php is not None, "PHP interpreter is unavailable")
    return {
        "php_executable": php,
        "php_version": pilot.invoke([php, "--version"]).stdout.splitlines()[0],
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def wrapper(path, argv, *, arguments=False):
    script = "#!/usr/bin/env python3\nimport os,sys\n"
    if not arguments:
        script += "if len(sys.argv)!=1: raise SystemExit('This command accepts no arguments')\n"
    script += "os.execvp(" + repr(argv[0]) + ", " + repr(argv)
    script += " + sys.argv[1:]" if arguments else ""
    path.write_text(script + ")\n")
    path.chmod(0o755)


def rename_argv(output, run_dir, experiment, arm):
    argv = [
        "python3",
        str(output / "source/benchmarks/symbol-intent/symbol_intent.py"),
        "rename_method",
        "--evidence",
        "--root",
        str(run_dir / "work"),
        "--state",
        str(run_dir / "state"),
        "--phpactor",
        str(output / pilot.PHAR_FILE),
    ]
    if experiment == GUIDANCE_EXPERIMENT and arm == "guidance":
        argv.append("--guidance")
    return argv


def prepare(args):
    experiment = getattr(args, "experiment", EXPERIMENT)
    design = profile(experiment)
    require(
        not pilot.invoke(["git", "status", "--porcelain"], pilot.SOURCE).stdout,
        "Commit source before preparation",
    )
    phpactor, phpunit = (
        args.phpactor.resolve(strict=True),
        args.phpunit.resolve(strict=True),
    )
    require(pilot.sha(phpactor) == pilot.PHAR_SHA256, "Wrong pinned Phpactor PHAR")
    require(pilot.sha(phpunit) == fixture.PHPUNIT_SHA256, "Wrong pinned PHPUnit PHAR")
    cli, cli_version = cli_identity()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    source = output / "source"
    source.mkdir()
    # Fixed archive tools and operator-selected paths; see ../TRUST.md.
    archive = subprocess.check_output(
        ["git", "archive", "HEAD"], cwd=pilot.SOURCE
    )  # NOSONAR(S2076, S6350)
    subprocess.run(
        ["tar", "-x", "-C", str(source)], input=archive, check=True
    )  # NOSONAR(S2076, S6350)
    shutil.copytree(pilot.SOURCE / "vendor", source / "vendor")
    shutil.copyfile(phpactor, output / pilot.PHAR_FILE)
    shutil.copyfile(phpunit, output / PHPUNIT_FILE)
    rows = schedule(experiment)
    for row in rows:
        route = "ast-integrated" if experiment == GUIDANCE_EXPERIMENT else row["arm"]
        run_dir = output / row["id"]
        run_dir.mkdir()
        work = run_dir / "work"
        fixture.export(work, args.source_repo)
        task = fixture.task(work)
        require(
            task["source_commit"] == fixture.SOURCE_COMMIT,
            "Unexpected public source commit",
        )
        task_file = Path(task["file"])
        if task_file.is_absolute():
            task["file"] = task_file.relative_to(work).as_posix()
        (run_dir / "state").mkdir()
        (run_dir / "check-receipts").mkdir()
        checker = run_dir / "check-tests"
        check_argv = fixture.command(
            work, output / PHPUNIT_FILE, receipt_dir=run_dir / "check-receipts"
        )
        check_argv[1] = str(source / "benchmarks/symbol-intent/real_fixture.py")
        wrapper(checker, check_argv)
        verification = (
            [{"scope": "project", "command": [str(checker)]}]
            if route == "ast-integrated"
            else []
        )
        pilot.save(work / PROJECT_CONFIG, {"verify": verification})
        rename = run_dir / "rename-tool"
        if route != "text-manual":
            wrapper(
                rename,
                rename_argv(output, run_dir, experiment, row["arm"]),
                arguments=True,
            )
        system, prompt = prompts(task, route, rename, checker)
        (run_dir / pilot.SYSTEM_FILE).write_text(system)
        (run_dir / pilot.PROMPT_FILE).write_text(prompt)
        pilot.save(run_dir / "task.json", task)
        initial = fixture.snapshot(work)
        pilot.save(run_dir / pilot.INITIAL_FILE, initial)
        pilot.invoke(["git", "init", "-q"], work, env=pilot.environment())
        pilot.invoke(["git", "add", "--", *initial], work, env=pilot.environment())
        pilot.invoke(
            [
                "git",
                "-c",
                "user.name=Benchmark",
                "-c",
                "user.email=benchmark@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Initial public fixture",
            ],
            work,
            env=pilot.environment(),
        )
        names = [
            pilot.SYSTEM_FILE,
            pilot.PROMPT_FILE,
            pilot.INITIAL_FILE,
            "task.json",
            "check-tests",
        ]
        if rename.exists():
            names.append("rename-tool")
        row["frozen"] = {name: pilot.sha(run_dir / name) for name in names}
    config = {
        "experiment": experiment,
        "source_commit": pilot.invoke(
            ["git", "rev-parse", "HEAD"], pilot.SOURCE
        ).stdout.strip(),
        "source_manifest": pilot.manifest(source),
        "fixture_source_commit": fixture.SOURCE_COMMIT,
        "phpactor_sha256": pilot.sha(output / pilot.PHAR_FILE),
        "phpunit_sha256": pilot.sha(output / PHPUNIT_FILE),
        "phpunit_version": fixture.PHPUNIT_VERSION,
        "model": pilot.MODEL,
        "cli": cli,
        "cli_version": cli_version,
        "schedule": rows,
        "runtimes": runtime_identity(),
        "max_run_usd": 0.5,
        "campaign_usd": design["campaign_usd"],
        "timeout_seconds": 120,
    }
    if experiment == GUIDANCE_EXPERIMENT:
        config["comparison"] = {
            "shared_route": "ast-integrated",
            "compact_flags": ["--evidence"],
            "guidance_flags": ["--evidence", "--guidance"],
            "treatment": "Whole guidance output bundle, including syntactic role counts",
            "forecast_native_list_price_usd_below": 1.0,
        }
    pilot.save(output / pilot.CONFIG_FILE, config)
    (output / "config.sha256").write_text(pilot.sha(output / pilot.CONFIG_FILE) + "\n")
    print(
        json.dumps(
            {
                "prepared": str(output),
                "candidates": len(rows),
                "model_calls": 0,
                "source_commit": config["source_commit"],
            }
        )
    )


def validate(output, config, row=None, *, check_cli=True):
    require(
        pilot.sha(output / pilot.CONFIG_FILE)
        == (output / "config.sha256").read_text().strip(),
        "Config drift",
    )
    require(
        pilot.manifest(output / "source") == config["source_manifest"],
        "Source/dependency drift",
    )
    require(
        pilot.sha(output / pilot.PHAR_FILE) == config["phpactor_sha256"],
        "Phpactor drift",
    )
    require(
        pilot.sha(output / PHPUNIT_FILE) == config["phpunit_sha256"], "PHPUnit drift"
    )
    if row:
        require(
            all(
                pilot.sha(output / row["id"] / name) == value
                for name, value in row["frozen"].items()
            ),
            "Candidate input drift",
        )
    if check_cli:
        require(
            pilot.invoke([config["cli"], "--version"]).stdout.strip()
            == config["cli_version"],
            "CLI version drift",
        )
        require(runtime_identity() == config["runtimes"], "PHP/Python runtime drift")


def load_config(output):
    config = json.loads((output / pilot.CONFIG_FILE).read_text())
    experiment = config.get("experiment")
    profile(experiment)
    require(
        [{k: v for k, v in r.items() if k != "frozen"} for r in config["schedule"]]
        == schedule(experiment),
        "Unexpected schedule",
    )
    return config


def receipt_matches(receipt, final):
    return bool(final) and all(
        (
            receipt.get("ok") is True,
            type(receipt.get("returncode")) is int and receipt["returncode"] == 0,
            type(receipt.get("tests")) is int
            and receipt["tests"] == fixture.TEST_COUNT,
            receipt.get("timed_out") is False,
            receipt.get("fixture_unchanged") is True,
            receipt.get("phpunit_sha256") == fixture.PHPUNIT_SHA256,
            receipt.get("before") == receipt.get("after") == final,
        )
    )


def check_summary(receipts, final):
    durations = [r.get("duration_ms") for r in receipts]
    known = all(
        type(t) in (int, float) and math.isfinite(t) and t >= 0 for t in durations
    )
    passed = sum(receipt_matches(receipt, final) for receipt in receipts)
    return {
        "behavior_checks": len(receipts),
        "passed_final_receipts": passed,
        "candidate_verified_final": passed > 0,
        "checker_ms": sum(durations) if known else None,
        "checker_timing_complete": known,
    }


def candidate_checks(run_dir, final):
    receipts, errors = [], []
    for path in sorted((run_dir / "check-receipts").glob("*.json")):
        try:
            require(not path.is_symlink(), "Symlink receipt")
            value = json.loads(path.read_text())
            require(isinstance(value, dict), "Receipt is not an object")
            receipts.append(value)
        except (ValueError, OSError) as error:
            errors.append({"path": str(path), "error": str(error)})
    summary = check_summary(receipts, final)
    if errors:
        summary.update(
            behavior_checks=None, checker_ms=None, checker_timing_complete=False
        )
    return {
        **summary,
        "observed_receipt_files": len(receipts) + len(errors),
        "receipts": receipts,
        "receipt_errors": errors,
    }


def outcomes(process, native, oracle, hidden, checks, final):
    execution = (
        process.get("process_exit") == 0
        and process.get("timed_out") is False
        and native.get("native_is_error") is False
        and native.get("native_subtype") == "success"
    )
    behavior = receipt_matches(hidden, final)
    code = oracle.get("ok") is True and behavior
    verified = checks.get("candidate_verified_final") is True
    return {
        "execution_completed": execution,
        "exact_scope_correct": oracle.get("ok") is True,
        "hidden_behavior_passed": behavior,
        "code_correct": code,
        "candidate_verified_final": verified,
        "success": execution and code and verified,
    }


def candidate_argv(config, run_dir):
    return [
        config["cli"],
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
        "--model",
        config["model"],
        "--max-budget-usd",
        str(config["max_run_usd"]),
        "--append-system-prompt",
        (run_dir / pilot.SYSTEM_FILE).read_text(),
        (run_dir / pilot.PROMPT_FILE).read_text(),
    ]


def evaluate(output, run_dir, record):
    work = run_dir / "work"
    try:
        final = fixture.snapshot(work)
    except (ValueError, OSError) as error:
        final = {}
        record["fixture_error"] = str(error)
    pilot.save(run_dir / "final.json", final)
    # Snapshot candidate receipts BEFORE any independent controller check.
    record["candidate_checks"] = candidate_checks(run_dir, final)
    record["oracle"], record["hidden_behavior"] = {"ok": False}, {"ok": False}
    if final:
        try:
            initial = json.loads((run_dir / pilot.INITIAL_FILE).read_text())
            record["oracle"] = fixture.oracle(
                work, allowed_extras={PROJECT_CONFIG: initial[PROJECT_CONFIG]}
            )
            record["hidden_behavior"] = fixture.check(work, output / PHPUNIT_FILE)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            record["oracle_error"] = str(error)
    record["outcome"] = outcomes(
        record,
        record.get("native", {}),
        record["oracle"],
        record["hidden_behavior"],
        record["candidate_checks"],
        final,
    )
    (run_dir / "diff.patch").write_text(
        pilot.invoke(
            ["git", "diff", "--no-ext-diff", "HEAD"], work, env=pilot.environment()
        ).stdout
    )


def guidance_observation(run_dir, record):
    if record.get("accounting_error") or not record.get("native"):
        return postcheck_pilot.unavailable_postcheck(
            "Native accounting unavailable; trace may be incomplete"
        )
    try:
        events, malformed = pilot.native.read_events(run_dir / pilot.NATIVE_FILE)
        require(not malformed, "Malformed native trace")
        return postcheck_pilot.post_calls(events, str(run_dir / "rename-tool"))
    except (ValueError, TypeError, KeyError, OSError) as error:
        return postcheck_pilot.unavailable_postcheck(str(error))


def run(args):
    require(args.execute_models, "Run requires --execute-models")
    output = args.output.resolve(strict=True)
    config = load_config(output)
    require(
        Path(__file__).resolve() == output / CONTROLLER,
        "Run the frozen controller copy",
    )
    require(
        not (output / "started.json").exists(),
        "Campaign already started; reruns are forbidden",
    )
    validate(output, config)
    with (output / "started.json").open("x") as marker:
        json.dump(
            {
                "started_at_ns": time.time_ns(),
                "config_sha256": pilot.sha(output / pilot.CONFIG_FILE),
            },
            marker,
        )
    spent = 0.0
    for row in config["schedule"]:
        run_dir = output / row["id"]
        require(
            not (run_dir / pilot.NATIVE_FILE).exists(), "Candidate already attempted"
        )
        require(
            spent + config["max_run_usd"] <= config["campaign_usd"],
            "Planning allowance exhausted",
        )
        validate(output, config, row)
        initial = json.loads((run_dir / pilot.INITIAL_FILE).read_text())
        require(fixture.snapshot(run_dir / "work") == initial, "Fixture drift")
        require(
            not any((run_dir / "check-receipts").iterdir()),
            "Candidate receipts exist before execution",
        )
        require(
            not pilot.invoke(
                ["git", "status", "--porcelain"],
                run_dir / "work",
                env=pilot.environment(),
            ).stdout,
            "Dirty fixture",
        )
        argv = candidate_argv(config, run_dir)
        pilot.save(run_dir / "argv.json", argv)
        record = {**row, "config_sha256": pilot.sha(output / pilot.CONFIG_FILE)}
        try:
            record.update(pilot.capture(argv, run_dir, config["timeout_seconds"]))
        except (OSError, subprocess.SubprocessError) as error:
            record.update(process_exit=None, timed_out=False, capture_error=str(error))
        pilot.save(run_dir / "process.json", record)
        try:
            events, malformed = pilot.native.read_events(run_dir / pilot.NATIVE_FILE)
            require(not malformed, "Malformed native trace")
            record["native"] = pilot.accounting.summarize(events, config["model"])
        except (ValueError, KeyError, TypeError, OSError, StopIteration) as error:
            record["accounting_error"] = str(error)
        if config["experiment"] == GUIDANCE_EXPERIMENT:
            record["postcheck"] = guidance_observation(run_dir, record)
        try:
            evaluate(output, run_dir, record)
        except (
            ValueError,
            TypeError,
            KeyError,
            OSError,
            subprocess.SubprocessError,
        ) as error:
            record["evaluation_error"] = str(error)
            record.setdefault("candidate_checks", {"behavior_checks": None})
            record.setdefault("outcome", {})["success"] = False
        try:
            validate(output, config, row)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            record["integrity_error"] = str(error)
            record["outcome"]["success"] = False
        pilot.save(run_dir / pilot.MEASUREMENT_FILE, record)
        print(
            json.dumps(
                {
                    "id": row["id"],
                    "arm": row["arm"],
                    "outcome": record["outcome"],
                    "behavior_checks": record["candidate_checks"]["behavior_checks"],
                    "usd": record.get("native", {}).get("native_list_price_usd"),
                }
            ),
            flush=True,
        )
        require(
            not any(
                record.get(k)
                for k in (
                    "capture_error",
                    "accounting_error",
                    "integrity_error",
                    "evaluation_error",
                    "timed_out",
                )
            ),
            "Stopped on capture/accounting/integrity/timeout failure; attempt retained",
        )
        require(
            record["process_exit"] == 0,
            "Stopped on unexpected CLI process exit; attempt retained",
        )
        cost = record["native"]["native_list_price_usd"]
        spent += cost
        require(
            cost <= config["max_run_usd"] and spent <= config["campaign_usd"],
            "Observed budget overrun",
        )
    pilot.save(
        output / "complete.json",
        {"attempts": len(config["schedule"]), "native_list_price_usd": spent},
    )


def metrics(record, experiment=EXPERIMENT):
    native = record.get("native", {}) if not record.get("accounting_error") else {}
    checks = record.get("candidate_checks", {})
    values = {
        "tokens": native.get("all_model_tokens", {}).get("totalTokens"),
        "calls": native.get("tool_calls"),
        "rounds": native.get("primary_model_rounds"),
        "usd": native.get("native_list_price_usd"),
        "wall_ms": record.get("wall_time_ms"),
        "behavior_checks": checks.get("behavior_checks"),
        "checker_ms": checks.get("checker_ms"),
    }
    if experiment == GUIDANCE_EXPERIMENT:
        count, passed = (
            checks.get("behavior_checks"),
            checks.get("passed_final_receipts"),
        )
        known = (
            type(count) is int
            and type(passed) is int
            and 0 <= passed <= count
            and not checks.get("receipt_errors")
            and not record.get("fixture_error")
            and not record.get("evaluation_error")
        )
        values.update(
            post_calls=record.get("postcheck", {}).get("subsequent_tool_calls"),
            duplicate_final_checks=max(0, passed - 1) if known else None,
        )
    return values


def distributions(values, prefix=""):
    return {
        key: value
        for metric, data in values.items()
        for key, value in (
            (prefix + metric, data),
            ("median_" + prefix + metric, statistics.median(data) if data else None),
        )
    }


def paired_effect(records, before_arm, after_arm, experiment=EXPERIMENT):
    deltas, pairs = {key: [] for key in metrics({}, experiment)}, []
    planned = schedule(experiment)
    candidates = [*records, *planned] if experiment == GUIDANCE_EXPERIMENT else records
    indexed = {}
    for record in candidates:
        # Keep the first observed row; planned rows only fill unattempted pairs.
        indexed.setdefault((record["arm"], record["repetition"]), record)
    for repeat in range(10):
        pair = [indexed.get((arm, repeat)) for arm in (before_arm, after_arm)]
        if any(r is None for r in pair):
            continue
        before, after = (metrics(r, experiment) for r in pair)
        values = {
            key: after[key] - before[key]
            if before[key] is not None and after[key] is not None
            else None
            for key in deltas
        }
        pairs.append({"ids": [r["id"] for r in pair], "deltas": values})
        for key, value in values.items():
            if value is not None:
                deltas[key].append(value)
    return {
        "before": before_arm,
        "after": after_arm,
        "pairs": pairs,
        **distributions(deltas, "delta_"),
    }


def summarize_records(records, experiment=EXPERIMENT):
    design = profile(experiment)
    cells = []
    for arm in design["arms"]:
        group = [r for r in records if r["arm"] == arm]
        values = {
            key: [
                metrics(r, experiment)[key]
                for r in group
                if metrics(r, experiment)[key] is not None
            ]
            for key in metrics({}, experiment)
        }
        cells.append(
            {
                "arm": arm,
                "attempts": len(group),
                "known_usage": len(values["tokens"]),
                **{
                    key: sum(r.get("outcome", {}).get(field, False) for r in group)
                    for key, field in (
                        ("successes", "success"),
                        ("code_correct", "code_correct"),
                        ("candidate_verified_final", "candidate_verified_final"),
                    )
                },
                **distributions(values),
            }
        )
        if experiment == GUIDANCE_EXPERIMENT:
            cells[-1].update(
                {
                    "known_" + key: len(values[key])
                    for key in ("post_calls", "duplicate_final_checks")
                }
            )
    result = {
        "experiment": experiment,
        "planned_attempts": len(schedule(experiment)),
        "attempts": len(records),
        "known_usage": sum(metrics(r)["tokens"] is not None for r in records),
        "known_native_list_price_usd": sum(metrics(r)["usd"] or 0 for r in records),
        "cells": cells,
        "paired_effects": [
            paired_effect(records, before_arm, after_arm, experiment)
            for before_arm, after_arm in design["pairs"]
        ],
        "interpretation": "One small public-source case repeated ten times. Text versus AST bundles resolver, writer and evidence; manual versus integrated bundles automatic triggering and reporting. Checker duration is observed separately, not an inferred total tool duration. Candidate verification and hidden oracle success are distinct.",
    }
    if experiment == GUIDANCE_EXPERIMENT:
        planned = schedule(experiment)
        identities = {(r["id"], r["arm"], r["repetition"]) for r in planned}
        require(
            all((r["id"], r["arm"], r["repetition"]) in identities for r in records),
            "Unexpected guidance row",
        )
        attempted = {r["id"] for r in records}
        require(len(attempted) == len(records), "Duplicate guidance attempt")
        result.update(
            planned_rows=[
                {**row, "attempted": row["id"] in attempted} for row in planned
            ],
            unattempted_ids=[
                row["id"] for row in planned if row["id"] not in attempted
            ],
            post_calls_boundary=postcheck_pilot.POSTCALL_BOUNDARY,
            interpretation="One public-source case, ten paired repetitions. Both arms use the same AST mutation and integrated checker; the treatment is the whole guidance output bundle, including syntactic role counts. Later tool calls are observable continuation, not automatically redundancy. Repeated successful final-byte receipts exclude checks on earlier bytes. Missing observations remain unknown; all twenty planned rows remain visible. Candidate verification and hidden oracle success are distinct.",
        )
    return result


def summarize(args):
    output = args.output.resolve(strict=True)
    config = load_config(output)
    validate(output, config, check_cli=False)
    records = []
    for row in config["schedule"]:
        run_dir = output / row["id"]
        measurement = run_dir / pilot.MEASUREMENT_FILE
        trace = run_dir / pilot.NATIVE_FILE
        if not any(p.exists() for p in (measurement, trace, run_dir / "process.json")):
            continue
        validate(output, config, row, check_cli=False)
        record = {
            **row,
            "accounting_error": "Incomplete attempt; raw evidence retained",
        }
        if measurement.exists():
            record = json.loads(measurement.read_text())
            require(
                all(record.get(k) == v for k, v in row.items()),
                "Measurement treatment drift",
            )
        if "native" in record:
            events, malformed = pilot.native.read_events(trace)
            require(not malformed, "Malformed measured native trace")
            require(
                record["native"] == pilot.accounting.summarize(events, config["model"]),
                "Native accounting drift",
            )
        if config["experiment"] == GUIDANCE_EXPERIMENT:
            observed = guidance_observation(run_dir, record)
            require(
                "postcheck" not in record or record["postcheck"] == observed,
                "Post-call observation drift",
            )
            record["postcheck"] = observed
        records.append(record)
    summary = {
        **summarize_records(records, config["experiment"]),
        "config_sha256": pilot.sha(output / pilot.CONFIG_FILE),
    }
    pilot.save(output / "real-runs.json", records)
    pilot.save(output / "real-summary.json", summary)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("prepare", "run", "summarize"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            command.add_argument(
                "--experiment", choices=tuple(PROFILES), default=EXPERIMENT
            )
            for option in ("source-repo", "phpactor", "phpunit"):
                command.add_argument("--" + option, type=Path, required=True)
        if name == "run":
            command.add_argument("--execute-models", action="store_true")
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "summarize": summarize}[args.action](args)


if __name__ == "__main__":
    main()
