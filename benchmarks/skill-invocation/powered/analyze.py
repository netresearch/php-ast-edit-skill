#!/usr/bin/env python3
"""Account for every planned run before applying the historical protocol's tests.

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
from collections import Counter
from itertools import combinations
from pathlib import Path

TASKS = ("C", "D")
ARMS = ("free", "gate")
METRICS = (("turns", "num_turns"), ("usd", "total_cost_usd"), ("wall_s", "duration_ms"))
ALPHA = 0.05
SEED = 20260910
REPETITIONS = 30


def mann_whitney_less(gate, free):
    """P(U >= observed) for 'gate lower', normal approximation with tie correction."""
    u, mean, variance = rank_moments(gate, free)
    if variance == 0:
        return 1.0
    z = (u - mean - 0.5) / math.sqrt(variance)
    return 0.5 * math.erfc(z / math.sqrt(2))


def rank_moments(gate, free):
    """Return the lower-gate U statistic, null mean and tie-corrected variance."""
    u = sum(1.0 if g < f else 0.5 if g == f else 0.0 for g in gate for f in free)
    n1, n2 = len(gate), len(free)
    n = n1 + n2
    counts = {}
    for value in gate + free:
        counts[value] = counts.get(value, 0) + 1
    ties = sum(t**3 - t for t in counts.values())
    variance = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1)))
    return u, n1 * n2 / 2, variance


def mann_whitney_two_sided(gate, free):
    """Two-sided normal test with tie and continuity corrections, including all ties."""
    u, mean, variance = rank_moments(gate, free)
    if variance == 0:
        return 1.0
    z = max(0, abs(u - mean) - 0.5) / math.sqrt(variance)
    return math.erfc(z / math.sqrt(2))


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


def planned_runs():
    """The 120 prospective slots in the driver's alternating execution order."""
    for number in range(1, REPETITIONS + 1):
        tasks = TASKS if number % 2 else TASKS[::-1]
        for task in tasks:
            phase = number + (task == "D")
            arms = ARMS if phase % 2 else ARMS[::-1]
            for arm in arms:
                yield f"{task}{number:02d}-{arm}", task, arm


def read_status(path):
    """Missing or malformed status is unknown, never an implicit success."""
    try:
        value = path.read_text().strip()
        return int(value) if value.isascii() and value.isdecimal() else None
    except (OSError, UnicodeError, ValueError):
        return None


def valid_metric(value, key):
    """Reject missing, nonfinite, Boolean and invalid native counters."""
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False
    if key == "num_turns":
        valid = valid and type(value) is int and value > 0
    return valid


def read_candidate(out, stem, task, arm):
    """Retain valid native counters even when the candidate failed or was interrupted."""
    issues = []
    status = read_status(out / f"{stem}.status")
    oracle = read_status(out / f"{stem}.oracle")
    if status is None:
        issues.append("missing_status")
    elif status != 0:
        issues.append("exit_status")
    try:
        document = json.loads((out / f"{stem}.json").read_text())
    except (OSError, ValueError):
        document = None
        issues.append("unreadable_result")
    if not isinstance(document, dict):
        issues.append("invalid_result")
        document = {}
    elif not isinstance(document.get("is_error"), bool) or not isinstance(
        document.get("subtype"), str
    ):
        issues.append("invalid_result")
    elif document["is_error"] or document["subtype"] != "success":
        issues.append("error_result")
    if oracle is None:
        issues.append("missing_oracle")
    elif oracle != 0:
        issues.append("oracle_failed")
    metrics = {}
    for name, key in METRICS:
        value = document.get(key)
        valid = valid_metric(value, key)
        metrics[name] = (
            value / 1000 if valid and key == "duration_ms" else value if valid else None
        )
    if any(value is None for value in metrics.values()):
        issues.append("invalid_metrics")
    return {
        "id": stem,
        "task": task,
        "arm": arm,
        "accepted": not issues,
        "reason": issues[0] if issues else None,
        "issues": issues,
        "exit_status": status,
        "oracle_status": oracle,
        "metrics": metrics,
    }


def load(bench):
    out = Path(bench, "out")
    records = [read_candidate(out, *slot) for slot in planned_runs()]
    expected = {record["id"] for record in records}
    unexpected = sorted(
        path.name
        for extension in (
            "status",
            "oracle",
            "json",
            "err",
            "diff",
            "version",
            "oracle-output",
            "untracked",
        )
        for path in out.glob(f"*.{extension}")
        if path.stem not in expected
    )
    missing_status = sum(record["exit_status"] is None for record in records)
    done = (out / "done").is_file()
    coverage = {
        "expected": len(records),
        "status_observed": len(records) - missing_status,
        "missing_status": missing_status,
        "done_marker": done,
        "unexpected_artifacts": unexpected,
        "complete": done and missing_status == 0 and not unexpected,
    }
    return records, coverage


def report(bench):
    records, coverage = load(bench)
    runs = {(t, a): [] for t in TASKS for a in ARMS}
    excluded = {(t, a): Counter() for t in TASKS for a in ARMS}
    for record in records:
        key = record["task"], record["arm"]
        if record["accepted"]:
            runs[key].append(record["metrics"])
        else:
            excluded[key][record["reason"]] += 1
    rows = []
    for task in TASKS:
        for name, _ in METRICS:
            gate = [run[name] for run in runs[(task, "gate")]]
            free = [run[name] for run in runs[(task, "free")]]
            available = coverage["complete"] and bool(gate) and bool(free)
            interval = list(bootstrap(gate, free)) if available else None
            rows.append(
                {
                    "task": task,
                    "metric": name,
                    "n_gate": len(gate),
                    "n_free": len(free),
                    "median_gate": median(gate) if available else None,
                    "median_free": median(free) if available else None,
                    "hodges_lehmann": hodges_lehmann(gate, free) if available else None,
                    "ci95_median_difference": interval,
                    "p_gate_lower": mann_whitney_less(gate, free)
                    if available
                    else None,
                }
            )
    # Always correct for six hypotheses. An unavailable comparison cannot reduce the
    # family and silently make the remaining claims easier to pass.
    pvalues = [
        row["p_gate_lower"] if row["p_gate_lower"] is not None else 1 for row in rows
    ]
    for row, rejected in zip(rows, holm(pvalues)):
        row["holm_rejects_at_0_05"] = rejected and coverage["complete"]
    decisions = {}
    for task in TASKS:
        counts = {arm: sum(excluded[task, arm].values()) for arm in ARMS}
        gate = [run["wall_s"] for run in runs[task, "gate"]]
        free = [run["wall_s"] for run in runs[task, "free"]]
        p_wall = (
            mann_whitney_two_sided(gate, free)
            if coverage["complete"] and gate and free
            else None
        )
        worse = (
            rank_moments(gate, free)[0] < len(gate) * len(free) / 2 and p_wall < ALPHA
            if p_wall is not None
            else None
        )
        cheaper = any(
            row["holm_rejects_at_0_05"]
            for row in rows
            if row["task"] == task and row["metric"] in ("turns", "usd")
        )
        if not coverage["complete"]:
            status = "incomplete_campaign"
        elif any(count / REPETITIONS > 0.1 for count in counts.values()):
            status = "inconclusive_exclusions"
        elif cheaper and worse is False:
            status = "supported_lower_cost"
        else:
            status = "not_established"
        decisions[task] = {
            "status": status,
            "excluded": counts,
            "planned_per_arm": REPETITIONS,
            "p_wall_two_sided": p_wall,
            "wall_significantly_worse": worse,
        }
    return {
        "coverage": coverage,
        "runs": records,
        "rows": rows,
        "decisions": decisions,
        "excluded": {f"{t}-{a}": dict(v) for (t, a), v in excluded.items()},
    }


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
