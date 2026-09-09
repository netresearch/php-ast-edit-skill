#!/usr/bin/env python3
"""Read the arms' result files and report invocation rate and medians.

The headline number is the invocation rate, not the token count. A run in which the
model never called the skill tells you nothing about the tool — it is a measurement of
the description, and averaging it together with runs that did call the skill hides
exactly the effect under test. So both are reported, and the per-run line says which
runs invoked it.
"""

import glob
import json
import re
import statistics
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


def runs_for(bench, arm):
    arm = token("arm", arm)
    config_dir = bench / f"cfg-{arm}"
    runs = []

    for path in sorted(glob.glob(str(bench / "out" / f"*-{arm}.json"))):
        result_file = Path(path)

        if result_file.stat().st_size == 0:
            continue
        with result_file.open() as handle:
            result = json.load(handle)
        # A run that failed to authenticate or timed out measured nothing; counting it
        # as a run that did not invoke the skill would report the arm as worse than it is.
        if result.get("is_error"):
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
    return runs


def main(bench, arms):
    bench = Path(bench).resolve()
    print(
        f"{'arm':8} {'n':>2} {'invoked':>9} {'turns':>6} {'output':>8} {'cache read':>11} {'usd':>7} {'sec':>6}"
    )

    for arm in arms:
        runs = runs_for(bench, arm)

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
    main(sys.argv[1], sys.argv[2:])
