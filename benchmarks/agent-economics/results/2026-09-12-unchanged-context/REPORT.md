# Unchanged-file excerpts: a negative matched Haiku experiment

Restricting extra rename-review context to unchanged files did **not** save tokens
against original AST reports in this campaign. Median paired treatment/control
ratios increased tokens **36.2%** and wall time **27.3%** on the small task; across
files they increased tokens **13.2%** and wall time **40.0%**. No small-task pair
saved tokens; three of six cross-file pairs did. All **24 final code states** were
correct, while **23/24 final explanations** were supported. Total native estimated
cost was **USD 0.7539534**, not an invoice.

Both per-task numerical gates and the all-attempt quality gate fail. The additional
context remains a benchmark prototype. This result does not justify enabling it in
the public CLI or loaded skill, and does not measure AST against ordinary text edits.

## Protocol and provenance

The [prospective protocol](../../intent-command/UNCHANGED-CONTEXT.md), comparator,
helper and controller were signed and pushed before paid calls at
[`d3151ae`](https://github.com/netresearch/php-ast-edit-skill/commit/d3151aed8080fd99f3b65e4cf7de6690284797cc).
This is a new campaign following [PR #85's excerpt study](../2026-09-12-review-context/REPORT.md).
Earlier observations motivate the experiment but are neither pooled nor used as
contemporaneous controls. There is no full-excerpt third arm, so the campaign does
not isolate filtering's effect relative to that earlier prototype.

- Two unchanged synthetic tasks × two arms × six paired repetitions = 24 attempts.
- Seed `20260917`; each task has three pairs beginning with each arm.
- `claude-haiku-4-5-20251001`, no effort or fallback override; Claude Code 2.1.268
  selected through its explicit versioned executable.
- PHP 8.5.10, php-parser 5.8.0 and pinned Phpactor 2026.07.22.0.
- Identical selected intent, ready-to-run command, instructions, initial hashes,
  native tools and independent oracles within each pair; all twelve pairs verified.
- Fresh workspaces, serial runs, 120-second timeout, USD 3 ceiling and a USD 0.75
  reservation for only the next imminent run, replaced by its actual native cost.

The operator supplies both arms' target and complete command. Autonomous target
selection cost is excluded. `unchanged_locations` returns original report bytes;
`unchanged_excerpts` adds bounded source context. Both arms capture and select the
same context; only its presentation differs. Original warning, diff, verification
and count bytes remain intact.

The proxy captures allowlisted files before the command. It excludes warning lines
from files explicitly marked changed in the original engine results, except dry
runs. Missing transaction entries remain eligible. Safe paths are normalized within
the fixture root, duplicate warning locations are counted once, and malformed
classification data stop the experiment. The new context names its unchanged-file
scope and separately counts changed-file exclusions and other omissions.

Context remains raw, untrusted, pre-command source evidence, not semantic
classification or current write coordinates. Its limits are 20 entries, 240 UTF-8
bytes per line and 8,192 serialized bytes including metadata. Snapshot limits are
200 files, 1 MiB per file and 4 MiB total. This does not establish production-scale
snapshot performance. Actual treatment contexts contain two entries: 741 bytes
with one changed-file exclusion on the small task, and 736 bytes with none across
files. There are no omissions or truncated entries.

Before paid execution, 33 repository assessment checks, 87 efficiency tests, the
13 existing intent/oracle tests and seven comparator tests passed. Four unpaid
real-command preflights covered both tasks and both arms. Independent reviewers
approved selection, proxy/adapter propagation, protocol and comparator. One earlier
24-slot preparation at `94e1a96` had zero model calls and was retained separately;
it was replaced before execution to correct exact threshold arithmetic. No paid
attempt was replaced, rerun, dropped or added. No competing local test suite ran
during candidate timing; the operator performed lightweight progress and trace reads.

## Preregistered paired result

The primary criterion requires, **on each task**, a median paired total-token
ratio ≤0.85, median paired wall-time ratio ≤1.0, and at least four of six pairs
saving tokens. All 24 code, protected-file, candidate-check, AST-route and supported
final-claim gates must also pass. Fractions preserve the exact threshold arithmetic;
display rounding does not determine the verdict.

| Task | Pairs | Median token ratio | Median wall ratio | Median call ratio | Token-saving pairs | Numeric gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Small rename | 6 | 1.362 | 1.273 | 1.167 | 0/6 | fail |
| Cross-file rename | 6 | 1.132 | 1.400 | 1.169 | 3/6 | fail |

Ratios are treatment/control: below one favors treatment. Every pair remains in
the denominator. [comparison.json](comparison.json) retains full precision and
was generated with the frozen prospective comparator.

| Task | Repetition | Control / treatment | Token ratio | Wall ratio | Call ratio |
| --- | ---: | --- | ---: | ---: | ---: |
| Small | 1 | run014 / run013 | 1.280 | 1.187 | 1.000 |
| Small | 2 | run011 / run012 | 1.848 | 1.324 | 2.250 |
| Small | 3 | run021 / run022 | 1.798 | 1.309 | 1.333 |
| Small | 4 | run016 / run015 | 1.004 | 0.921 | 0.857 |
| Small | 5 | run019 / run020 | 1.443 | 1.441 | 1.667 |
| Small | 6 | run002 / run001 | 1.006 | 1.237 | 0.714 |
| Cross-file | 1 | run003 / run004 | 1.520 | 1.397 | 1.429 |
| Cross-file | 2 | run006 / run005 | 0.764 | 0.987 | 0.909 |
| Cross-file | 3 | run007 / run008 | 0.681 | 1.402 | 0.500 |
| Cross-file | 4 | run024 / run023 | 0.581 | 0.873 | 0.769 |
| Cross-file | 5 | run010 / run009 | 1.500 | 1.848 | 2.167 |
| Cross-file | 6 | run017 / run018 | 2.590 | 1.596 | 1.857 |

## Complete-session cell medians

These descriptive medians use all six attempts per cell. They are not substitutes
for the median paired ratios above. Total tokens include fresh input, cache creation,
cache reads and output; thinking is already included in output. All components and
native failures remain in [report.json](report.json).

| Task | Arm | Tokens | Visible rounds | Calls | Wall seconds | Native cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Small | unchanged_locations | 39,342.5 | 3.5 | 4 | 17.83 | 0.018066 |
| Small | unchanged_excerpts | 52,946.5 | 4.5 | 5 | 21.46 | 0.023074 |
| Cross-file | unchanged_locations | 100,357.5 | 7.5 | 8.5 | 33.29 | 0.036207 |
| Cross-file | unchanged_excerpts | 113,554 | 7.5 | 10 | 42.05 | 0.043353 |

Ratios of these token medians are 1.346 and 1.131; ratios of wall-time medians are
1.204 and 1.263. Those differ from the registered paired statistics. Cache state is
unknown, the model is stochastic and six pairs per task remain exploratory. Results
do not establish a general penalty for AST editing or larger PHP repositories.
Tool execution time is unknown without complete interval coverage.

## What the traces show

Independent [audit.json](audit.json) covers all 24 native traces, final responses,
source hashes and original/presented engine output. Each run executes exactly one
successful supplied rename with `--file`. Actual engine changes, context exclusions,
unchanged source excerpts and native delivery match. All final diffs are byte-identical
within each task, and all protected files remain unchanged. The fixture diffs also
retain deterministic printer newline changes; these are not additional rename errors.

| Observed count over 12 runs per arm | Control | Treatment |
| --- | ---: | ---: |
| Native tool calls | 82 | 94 |
| Calls after the write | 64 | 72 |
| Native Reads of changed files after the write | 18 | 24 |
| Native Reads of unchanged files after the write | 22 | 24 |
| Native Reads of warned files after the write | 18 | 14 |
| Reads of warned unchanged files eligible for excerpts | 12 | 10 |
| Reads of the excluded changed file | 6 | 4 |
| Repetitions of the already-passed project check | 11 | 14 |
| Runs repeating that passed check | 10 | 11 |
| Native failed tool calls | 0 | 1 |

Warned-file Reads decrease, but other Reads and repeated checks increase in these
attempts. For cross-file warning sources, the native Read count is unchanged at
8→8; on the small task it falls 4→2. These are observed counts, not proof that every
source review was redundant or that the filter caused each behavioral difference.
Git diff/status calls are counted separately from native source Reads. No run ends
with only the engine call. Treatment run012's directory Read fails before the
successful rename; that failure remains in all reported totals.

Code correctness does not make every explanation accurate. Treatment **run018**
states `Service label 'fetch service' in config/services.yaml` in its final response
(`raw.jsonl:70`). The actual protected YAML contains `label: fetch`. Its correct
content was both delivered as an excerpt and read again (`raw.jsonl:46`). Thus
control final claims pass 12/12 and treatment 11/12. Four intermediate mistaken
statements are recorded separately; their finals do not repeat those mistakes, so
they do not fail the preregistered final-response gate.

The evidence does not support further promotion of this excerpt optimization.
Review and completion behavior remain candidate bottlenecks even after a correct
single-call write. A separately registered intervention aimed at redundant checks
or final-response grounding would test a different hypothesis; neither is measured
by this campaign. The existing public skill behavior remains unchanged.

## Reproduce and audit

[SHA256SUMS](SHA256SUMS) covers this document, the native-derived report, frozen
comparison, manual audit and evidence archive. The archive contains 788 allowlisted
files plus `export-sha256.json`: all native streams, fixtures, checks, oracles and
frozen controller/helper sources. Private sessions, credentials, dependencies and
binaries are excluded; runtime identities remain recorded. Relocating the export
changes only the summary's `campaign` and per-run `evidence_path` metadata; the rest
of the recomputed report is identical.

From the repository root:

```bash
(cd benchmarks/agent-economics/results/2026-09-12-unchanged-context && sha256sum -c SHA256SUMS)
evidence_dir=$(mktemp -d /tmp/unchanged-context-evidence.XXXXXX)
tar -xzf benchmarks/agent-economics/results/2026-09-12-unchanged-context/evidence.tar.gz \
  -C "$evidence_dir"
python3 benchmarks/agent-economics/intent-command/summarize.py \
  "$evidence_dir" > /tmp/unchanged-context-summary.json
git show d3151aed8080fd99f3b65e4cf7de6690284797cc:benchmarks/agent-economics/intent-command/unchanged_compare.py \
  > /tmp/unchanged-context-frozen-comparator.py
python3 /tmp/unchanged-context-frozen-comparator.py \
  /tmp/unchanged-context-summary.json > /tmp/unchanged-context-comparison.json
```

The publication branch subsequently tightens comparator import validation to
require the registered Haiku identity and preserve arbitrary serialized decimal
precision. The campaign itself used the frozen source above. Native model identities
and wall-time values in these 24 records already satisfy those constraints; those
publication fixes do not change the registered decision or any candidate evidence.
