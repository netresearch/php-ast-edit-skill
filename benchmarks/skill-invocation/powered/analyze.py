#!/usr/bin/env python3
"""The powered round's analysis, exactly as PROTOCOL.md fixes it.

Usage: analyze.py <BENCH>            the report for a finished round
       analyze.py --self-test        the statistics against exact enumeration

For each task and metric: medians per arm, the Hodges-Lehmann shift (gate minus free), a
bootstrap 95% interval for the difference of medians, and a one-sided Mann-Whitney test
that the gate is lower. The six p-values are then held to Holm's procedure at 0.05.
"""

import json
import math
import random
import sys
from itertools import combinations
from pathlib import Path

TASKS = ("C", "D")
ARMS = ("free", "gate")
METRICS = (("turns", "num_turns"), ("usd", "total_cost_usd"), ("wall_s", "duration_ms"))
ALPHA = 0.05
SEED = 20260910


def mann_whitney_less(gate, free):
    """P(U >= observed) for 'gate lower', normal approximation with tie correction."""
    u = sum(1.0 if g < f else 0.5 if g == f else 0.0 for g in gate for f in free)
    n1, n2 = len(gate), len(free)
    n = n1 + n2
    counts = {}
    for value in gate + free:
        counts[value] = counts.get(value, 0) + 1
    ties = sum(t**3 - t for t in counts.values())
    variance = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1)))
    if variance == 0:
        return 1.0
    z = (u - n1 * n2 / 2 - 0.5) / math.sqrt(variance)
    return 0.5 * math.erfc(z / math.sqrt(2))


def exact_less(gate, free):
    """The same test by enumeration, for the self-test only."""
    pooled = gate + free
    observed = sum(1.0 if g < f else 0.5 if g == f else 0.0 for g in gate for f in free)
    hits = total = 0
    for picked in combinations(range(len(pooled)), len(gate)):
        chosen = set(picked)
        a = [pooled[i] for i in picked]
        b = [pooled[i] for i in range(len(pooled)) if i not in chosen]
        total += 1
        hits += (
            sum(1.0 if x < y else 0.5 if x == y else 0.0 for x in a for y in b)
            >= observed
        )
    return hits / total


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )


def hodges_lehmann(gate, free):
    return median([g - f for g in gate for f in free])


def bootstrap(gate, free, draws=10000):
    rng = random.Random(SEED)
    differences = sorted(
        median(rng.choices(gate, k=len(gate))) - median(rng.choices(free, k=len(free)))
        for _ in range(draws)
    )
    return differences[int(0.025 * draws)], differences[int(0.975 * draws) - 1]


def holm(pvalues):
    """Which hypotheses Holm's step-down procedure rejects at ALPHA."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    rejected = [False] * len(pvalues)
    for rank, index in enumerate(order):
        if pvalues[index] > ALPHA / (len(pvalues) - rank):
            break
        rejected[index] = True
    return rejected


def load(bench):
    runs = {(t, a): [] for t in TASKS for a in ARMS}
    excluded = {(t, a): {} for t in TASKS for a in ARMS}
    for status in sorted(Path(bench, "out").glob("*.status")):
        stem = status.name[: -len(".status")]
        task_id, arm = stem.rsplit("-", 1)
        task = task_id[0]
        if (task, arm) not in runs:
            continue
        reason = None
        result = status.with_suffix(".json")
        oracle = status.with_suffix(".oracle")
        document = None
        if status.read_text().strip() != "0":
            reason = "exit status"
        else:
            try:
                document = json.loads(result.read_text())
            except (OSError, ValueError):
                reason = "unreadable result"
        if reason is None and (
            document.get("is_error") or document.get("subtype") != "success"
        ):
            reason = "error result"
        if reason is None and (
            not oracle.exists() or oracle.read_text().strip() != "0"
        ):
            reason = "oracle failed"
        if reason:
            excluded[(task, arm)][reason] = excluded[(task, arm)].get(reason, 0) + 1
            continue
        runs[(task, arm)].append(
            {
                name: document[key] / 1000 if key == "duration_ms" else document[key]
                for name, key in METRICS
            }
        )
    return runs, excluded


def report(bench):
    runs, excluded = load(bench)
    rows = []
    for task in TASKS:
        for name, _ in METRICS:
            gate = [run[name] for run in runs[(task, "gate")]]
            free = [run[name] for run in runs[(task, "free")]]
            if not gate or not free:
                continue
            low, high = bootstrap(gate, free)
            rows.append(
                {
                    "task": task,
                    "metric": name,
                    "n_gate": len(gate),
                    "n_free": len(free),
                    "median_gate": median(gate),
                    "median_free": median(free),
                    "hodges_lehmann": hodges_lehmann(gate, free),
                    "ci95_median_difference": [low, high],
                    "p_gate_lower": mann_whitney_less(gate, free),
                }
            )
    for row, rejected in zip(rows, holm([row["p_gate_lower"] for row in rows])):
        row["holm_rejects_at_0_05"] = rejected
    return {"rows": rows, "excluded": {f"{t}-{a}": v for (t, a), v in excluded.items()}}


def self_test():
    rng = random.Random(SEED)
    for _ in range(20):
        gate = [rng.randint(8, 20) for _ in range(6)]
        free = [rng.randint(10, 22) for _ in range(6)]
        approx, exact = mann_whitney_less(gate, free), exact_less(gate, free)
        assert abs(approx - exact) < 0.06, (gate, free, approx, exact)
    assert holm([0.001, 0.04, 0.03]) == [True, False, False]
    assert holm([0.001, 0.01, 0.02]) == [True, True, True]
    assert hodges_lehmann([1, 2], [3, 4]) == -2
    print(
        "OK: Mann-Whitney approximation within 0.06 of exact on 20 samples; Holm and Hodges-Lehmann as specified."
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
    elif len(sys.argv) == 2:
        print(json.dumps(report(sys.argv[1]), indent=2))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
