#!/usr/bin/env python3
"""Read the arms' result files and report invocation rate and medians.

The headline number is the invocation rate, not the token count. A run in which the
model never called the skill tells you nothing about the tool — it is a measurement of
the description, and averaging it together with runs that did call the skill hides
exactly the effect under test. So both are reported, and the per-run column says which
runs invoked it.
"""
import glob
import json
import os
import statistics
import sys


def tools(config_dir, session_id):
    for path in glob.glob(f"{config_dir}/projects/*/{session_id}.jsonl"):
        names = []
        for line in open(path):
            entry = json.loads(line)
            message = entry.get("message") or {}
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    names.append(block["name"])
        return names
    return []


def main(bench, arms):
    print(f"{'arm':8} {'n':>2} {'invoked':>9} {'turns':>6} {'output':>8} {'cache read':>11} {'usd':>7} {'sec':>6}")
    for arm in arms:
        runs = []
        for path in sorted(glob.glob(f"{bench}/out/*-{arm}.json")):
            if os.path.getsize(path) == 0:
                continue
            result = json.load(open(path))
            if result.get("is_error"):
                continue
            usage = result["usage"]
            runs.append({
                "turns": result.get("num_turns"),
                "output": usage["output_tokens"],
                "cache_read": usage["cache_read_input_tokens"],
                "usd": result.get("total_cost_usd", 0),
                "sec": round(result.get("duration_ms", 0) / 1000, 1),
                "skill": "Skill" in tools(f"{bench}/cfg-{arm}", result["session_id"]),
            })
        if not runs:
            continue
        med = lambda key: statistics.median([run[key] for run in runs])
        invoked = sum(run["skill"] for run in runs)
        print(f"{arm:8} {len(runs):>2} {invoked:>4}/{len(runs):<4} {med('turns'):>6.0f} "
              f"{med('output'):>8.0f} {med('cache_read'):>11.0f} {med('usd'):>7.3f} {med('sec'):>6.1f}")
        print(f"{'':8} runs: " + ", ".join(f"{r['turns']}{'*' if r['skill'] else ''}" for r in runs))
    print("\n* the run invoked the skill")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
