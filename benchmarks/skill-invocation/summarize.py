#!/usr/bin/env python3
"""Read the arms' result files and report invocation rate and medians.

The headline number is the invocation rate, not the token count. A run in which the
model never called the skill tells you nothing about the tool — it is a measurement of
the description, and averaging it together with runs that did call the skill hides
exactly the effect under test. So both are reported, and the per-run line says which
runs invoked it.

Two things are counted rather than dropped. An attempt that failed — a timeout, an
expired token — is excluded from the medians but reported, because an arm whose failures
are invisible reports a flattering rate off a smaller denominator. And where an oracle is
given, a run whose result does not satisfy it is excluded and reported too: a run that
finished without doing the task is not a cheap run.

Usage: summarize.py <bench> <arm> [arm ...] [--oracle 'shell command']

The oracle runs once per completed run, in that run's working tree, and its exit status
decides. For a rename: --oracle "grep -q queryBuilderFor Classes/Service/Repo.php"
"""

import glob
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

# An arm is a short name and a session id is what the CLI writes into its result file.
# Neither is ever a path, so neither is allowed to look like one: every value that reaches
# a filename here is matched against this first, and anything else stops the script rather
# than being resolved, cleaned up or trusted.
TOKEN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def token(kind, value):
    if not TOKEN.fullmatch(str(value)):
        raise SystemExit(f"refusing to use {kind} {value!r} in a path")

    return str(value)


def invoked_skill(config_dir, session_id):
    """Whether this session called the Skill tool, read from its own transcript."""
    pattern = str(
        config_dir / "projects" / "*" / f"{token('session id', session_id)}.jsonl"
    )

    for path in glob.glob(pattern):
        with Path(path).open() as transcript:
            for line in transcript:
                message = json.loads(line).get("message") or {}
                for block in message.get("content") or []:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block["name"] == "Skill"
                    ):
                        return True
        return False
    return False


def satisfies(bench, task_id, arm, oracle):
    """Whether this run's working tree passes the caller's success check."""
    if oracle is None:
        return True
    work = bench / "work" / f"{task_id}-{arm}"

    if not work.is_dir():
        return False

    return subprocess.run(oracle, cwd=work, shell=True, check=False).returncode == 0


def runs_for(bench, arm, oracle=None):
    arm = token("arm", arm)
    config_dir = bench / f"cfg-{arm}"
    runs, failed, wrong = [], 0, 0

    for path in sorted(glob.glob(str(bench / "out" / f"*-{arm}.json"))):
        result_file = Path(path)
        task_id = result_file.name[: -len(f"-{arm}.json")]
        status = result_file.with_suffix(".status")
        # A run that timed out or could not authenticate measured nothing. It is excluded
        # from the medians and counted, never silently dropped.
        exit_status = int(status.read_text().strip()) if status.exists() else 0

        if exit_status != 0 or result_file.stat().st_size == 0:
            failed += 1
            continue
        with result_file.open() as handle:
            result = json.load(handle)

        if result.get("is_error"):
            failed += 1
            continue

        if not satisfies(bench, task_id, arm, oracle):
            wrong += 1
            continue
        usage = result["usage"]
        runs.append(
            {
                "turns": result.get("num_turns"),
                "output": usage["output_tokens"],
                "cache_read": usage["cache_read_input_tokens"],
                "usd": result.get("total_cost_usd", 0),
                "sec": round(result.get("duration_ms", 0) / 1000, 1),
                "skill": invoked_skill(config_dir, result["session_id"]),
            }
        )
    return runs, failed, wrong


def main(bench, arms, oracle=None):
    bench = Path(bench).resolve()
    print(
        f"{'arm':8} {'n':>2} {'invoked':>9} {'turns':>6} {'output':>8} {'cache read':>11} {'usd':>7} {'sec':>6}"
    )

    for arm in arms:
        runs, failed, wrong = runs_for(bench, arm, oracle)

        if failed or wrong:
            print(
                f"{arm:8} excluded: {failed} failed attempt(s), "
                f"{wrong} run(s) that did not do the task"
            )

        if not runs:
            print(f"{arm:8} no completed runs")
            continue
        median = {
            key: statistics.median([run[key] for run in runs])
            for key in ("turns", "output", "cache_read", "usd", "sec")
        }
        invoked = sum(run["skill"] for run in runs)
        print(
            f"{arm:8} {len(runs):>2} {invoked:>4}/{len(runs):<4} {median['turns']:>6.1f} "
            f"{median['output']:>8.0f} {median['cache_read']:>11.0f} {median['usd']:>7.3f} {median['sec']:>6.1f}"
        )
        print(
            f"{'':8} runs: "
            + " ".join(f"{run['turns']}{'*' if run['skill'] else ''}" for run in runs)
        )
    print("\n* the run invoked the skill")


if __name__ == "__main__":
    argv = sys.argv[1:]
    check = None

    if "--oracle" in argv:
        at = argv.index("--oracle")
        check = argv[at + 1]
        argv = argv[:at] + argv[at + 2 :]
    main(argv[0], argv[1:], check)
