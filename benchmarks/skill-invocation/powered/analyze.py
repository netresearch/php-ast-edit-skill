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
        median(
            rng.choices(gate, k=len(gate))  # NOSONAR(S2245)
        )
        - median(
            rng.choices(free, k=len(free))  # NOSONAR(S2245)
        )
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


class EvidenceDirectory:
    """Read regular evidence files contained in an operator-selected campaign's out/."""

    def __init__(self, bench):
        self.root = Path(bench).resolve() / "out"
        self.unsafe_artifacts = set()
        self.root_error = None
        if self.root.is_symlink() or (self.root.exists() and not self.root.is_dir()):
            self.root_error = "unsafe_output_root"

    def regular_path(self, name):
        """Reject path traversal, symlinks, borrowed files and nonregular evidence."""
        if self.root_error:
            raise ValueError(self.root_error)
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("evidence name must be one filename")
        path = self.root / name
        if path.is_symlink():
            self.unsafe_artifacts.add(name)
            raise ValueError("symlink evidence is not accepted")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            self.unsafe_artifacts.add(name)
            raise ValueError("evidence must be a regular file within the output root")
        return resolved

    def read_text(self, name):
        return self.regular_path(name).read_text()

    def is_regular(self, name):
        try:
            self.regular_path(name)
            return True
        except (OSError, ValueError):
            return False

    def candidate_artifacts(self):
        if self.root_error or not self.root.is_dir():
            return []
        extensions = {
            ".status",
            ".oracle",
            ".json",
            ".err",
            ".diff",
            ".version",
            ".oracle-output",
            ".untracked",
        }
        paths = [path for path in self.root.iterdir() if path.suffix in extensions]
        for path in paths:
            self.is_regular(path.name)
        return paths


def read_status(evidence, name):
    """Missing or malformed status is unknown, never an implicit success."""
    try:
        value = evidence.read_text(name).strip()
        return int(value) if value.isascii() and value.isdecimal() else None
    except (OSError, ValueError):
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


def result_document(evidence, stem):
    """Return a result object and its integrity issues without inventing a success."""
    issues = []
    try:
        document = json.loads(evidence.read_text(f"{stem}.json"))
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
    return document, issues


def normalized_metric(value, key):
    if not valid_metric(value, key):
        return None
    if key == "duration_ms":
        return value / 1000
    return value


def status_issues(status, missing, failed):
    if status is None:
        return [missing]
    if status != 0:
        return [failed]
    return []


def read_candidate(evidence, stem, task, arm):
    """Retain valid native counters even when the candidate failed or was interrupted."""
    status = read_status(evidence, f"{stem}.status")
    oracle = read_status(evidence, f"{stem}.oracle")
    document, document_issues = result_document(evidence, stem)
    issues = status_issues(status, "missing_status", "exit_status")
    issues.extend(document_issues)
    issues.extend(status_issues(oracle, "missing_oracle", "oracle_failed"))
    metrics = {name: normalized_metric(document.get(key), key) for name, key in METRICS}
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
    evidence = EvidenceDirectory(bench)
    records = [read_candidate(evidence, *slot) for slot in planned_runs()]
    expected = {record["id"] for record in records}
    unexpected = sorted(
        path.name
        for path in evidence.candidate_artifacts()
        if path.stem not in expected
    )
    missing_status = sum(record["exit_status"] is None for record in records)
    done = evidence.is_regular("done")
    coverage = {
        "expected": len(records),
        "status_observed": len(records) - missing_status,
        "missing_status": missing_status,
        "done_marker": done,
        "unexpected_artifacts": unexpected,
        "unsafe_artifacts": sorted(evidence.unsafe_artifacts),
        "output_root_error": evidence.root_error,
        "complete": done
        and missing_status == 0
        and not unexpected
        and not evidence.unsafe_artifacts,
    }
    return records, coverage


def group_records(records):
    """Separate accepted metric observations from the full exclusion denominator."""
    runs = {(t, a): [] for t in TASKS for a in ARMS}
    excluded = {(t, a): Counter() for t in TASKS for a in ARMS}
    for record in records:
        key = record["task"], record["arm"]
        if record["accepted"]:
            runs[key].append(record["metrics"])
        else:
            excluded[key][record["reason"]] += 1
    return runs, excluded


def metric_row(task, name, runs, complete):
    gate = [run[name] for run in runs[(task, "gate")]]
    free = [run[name] for run in runs[(task, "free")]]
    row = {
        "task": task,
        "metric": name,
        "n_gate": len(gate),
        "n_free": len(free),
        "median_gate": None,
        "median_free": None,
        "hodges_lehmann": None,
        "ci95_median_difference": None,
        "p_gate_lower": None,
    }
    if complete and gate and free:
        row.update(
            median_gate=median(gate),
            median_free=median(free),
            hodges_lehmann=hodges_lehmann(gate, free),
            ci95_median_difference=list(bootstrap(gate, free)),
            p_gate_lower=mann_whitney_less(gate, free),
        )
    return row


def correct_hypothesis_family(rows, complete):
    # Always correct for six hypotheses. An unavailable comparison cannot reduce the
    # family and silently make the remaining claims easier to pass.
    pvalues = [
        row["p_gate_lower"] if row["p_gate_lower"] is not None else 1 for row in rows
    ]
    for row, rejected in zip(rows, holm(pvalues)):
        row["holm_rejects_at_0_05"] = rejected and complete


def wall_comparison(task, runs, complete):
    gate = [run["wall_s"] for run in runs[task, "gate"]]
    free = [run["wall_s"] for run in runs[task, "free"]]
    if not complete or not gate or not free:
        return None, None
    p_wall = mann_whitney_two_sided(gate, free)
    u, mean, _ = rank_moments(gate, free)
    return p_wall, u < mean and p_wall < ALPHA


def decision_status(complete, counts, cheaper, worse):
    if not complete:
        return "incomplete_campaign"
    if any(count / REPETITIONS > 0.1 for count in counts.values()):
        return "inconclusive_exclusions"
    if cheaper and worse is False:
        return "supported_lower_cost"
    return "not_established"


def task_decision(task, runs, excluded, rows, complete):
    counts = {arm: sum(excluded[task, arm].values()) for arm in ARMS}
    p_wall, worse = wall_comparison(task, runs, complete)
    cheaper = any(
        row["holm_rejects_at_0_05"]
        for row in rows
        if row["task"] == task and row["metric"] in ("turns", "usd")
    )
    return {
        "status": decision_status(complete, counts, cheaper, worse),
        "excluded": counts,
        "planned_per_arm": REPETITIONS,
        "p_wall_two_sided": p_wall,
        "wall_significantly_worse": worse,
    }


def report(bench):
    records, coverage = load(bench)
    runs, excluded = group_records(records)
    rows = [
        metric_row(task, name, runs, coverage["complete"])
        for task in TASKS
        for name, _ in METRICS
    ]
    correct_hypothesis_family(rows, coverage["complete"])
    decisions = {
        task: task_decision(task, runs, excluded, rows, coverage["complete"])
        for task in TASKS
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
        gate = [
            rng.randint(8, 20)  # NOSONAR(S2245)
            for _ in range(6)
        ]
        free = [
            rng.randint(10, 22)  # NOSONAR(S2245)
            for _ in range(6)
        ]
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
