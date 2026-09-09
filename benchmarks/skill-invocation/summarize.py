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
import os
import statistics
import sys
from pathlib import Path


def under(root, *parts):
    """Resolve a path and refuse anything that leaves the working root.

    Both arguments this script takes come from a command line, and every path it opens is
    built from them. Nothing here needs to reach outside the run directory, so it does not
    get to: a `..` or an absolute segment in either argument stops the script instead of
    reading whatever it names.
    """
    root = Path(root).resolve()
    candidate = root.joinpath(*parts).resolve()

    if candidate != root and root not in candidate.parents:
        raise SystemExit(f"refusing to read outside {root}: {candidate}")

    return candidate


def invoked_skill(config_dir, session_id):
    """Whether this session called the Skill tool, read from its own transcript."""
    for path in glob.glob(f"{config_dir}/projects/*/{session_id}.jsonl"):
        with open(under(config_dir, os.path.relpath(path, config_dir))) as transcript:
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
    # Both directories are resolved before anything is globbed or opened, so an arm name
    # carrying a path segment is refused here rather than at whichever file it first
    # reaches — a check that only fires once a matching file exists is not a check.
    config_dir = str(under(bench, f"cfg-{arm}"))
    out_dir = under(bench, "out")
    runs = []

    for path in sorted(glob.glob(f"{out_dir}/*-{arm}.json")):
        resolved = under(out_dir, os.path.basename(path))

        if resolved.stat().st_size == 0:
            continue
        with open(resolved) as handle:
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
    header = ("arm", "n", "invoked", "turns", "output", "cache read", "usd", "sec")
    print(
        f"{header[0]:8} {header[1]:>2} {header[2]:>9} {header[3]:>6} {header[4]:>8} {header[5]:>11} {header[6]:>7} {header[7]:>6}"
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
