# Shared metadata in multi-file rename reports

The primary cross-file comparison uses **43.7% fewer total tokens, 30.9% less wall
time and 14.1% fewer tool calls** in median paired ratios. Four of six pairs save
tokens, satisfying the preregistered numeric gate. Native paired cost falls 22.9%
and visible rounds 36.5%. All 24 final code states are correct.

**The overall criterion fails:** only **19/24 final explanations** are supported.
The unchanged single-file A/A comparison also varies substantially: its nominal
treatment label uses 65.3% more paired tokens, 21.9% more time and 75.0% more calls,
although no report transformation occurs there. These six primary pairs support a
further hypothesis, not a stable causal effect size or general AST savings rate.
The projection remains benchmark-only; the production CLI and loaded skill do not
change. The 24 new attempts cost **USD 0.7140069** in native estimates, not invoices.

## Design and provenance

The [prospective protocol](../../intent-command/SHARED-REPORT.md), implementation and
comparator were signed and pushed before paid calls at
[`9367706`](https://github.com/netresearch/php-ast-edit-skill/commit/9367706319020e7a5bb6e096bfaf66fca08aada7).
The base is v0.9.0, whose release metadata followed the previous campaign. Earlier
observations motivate this experiment; none are reused as controls or pooled.

- Two unchanged tasks × two arms × six paired repetitions: all **24** retained.
- Seed `20260919`, with three pairs per task beginning with each arm.
- Pinned `claude-haiku-4-5-20251001`, no effort or fallback override; Claude Code
  2.1.268 through its explicit versioned executable.
- PHP 8.5.10, php-parser 5.8.0 and Phpactor 2026.07.22.0; resolver PHAR selected
  explicitly for both arms and identities retained in operator provenance.
- Fresh isolated workspaces, serial execution, 120-second timeout, USD 3 ceiling
  and USD 0.75 reservation for only the next imminent attempt.
- Identical task prompts, short delegated system instructions, selected intent,
  complete command, fixtures, native tools, engine, guards and project checks.

Operator-selected declarations and commands exclude autonomous target-selection
cost. This compares two AST report presentations, not AST against ordinary text
editing or the installed full skill against another workflow. No new check-reuse
instruction, warning excerpt, source snapshot or tool restriction is introduced.

`shared_report_control` forwards original stdout bytes. Both arms compute the same
projection, so that work is included in both timings. `shared_report_factored`
collects strictly identical whitelisted metadata from every reported file into
`fileDefaults`, with an explicit per-file inheritance explanation. This does not
merge check executions or create a global validation claim. Paths, modes, hashes,
diffs, code, effects and counts remain per-file. Unknown and distinct values remain.

Every original JSON key and value can be reconstructed, including warning aliases,
check IDs, validation status and all diff strings. Boolean/number types and array
order are checked. Reserved-key collisions, ambiguous overrides and malformed or
precision-losing inputs fail the intervention rather than silently losing evidence.
Both presentations retain four-space, unescaped UTF-8 JSON; there is no extra
minification. A single-file report returns the original bytes.

Four final-source unpaid task/arm preflights ran the actual rename, project check
and independent oracle. Their cross-file reports shrank 7,315→5,334 bytes, exceeding
the 25% spending prerequisite; single-file output stayed at 4,130 bytes. An earlier
development preflight is kept separately. Path length explains the different byte
totals in preflight and paid workspaces. Before measurement, 33 clean-source
assessment checks, 105 efficiency tests, 27 intent/comparator tests and two exporter
tests passed. No competing local tests ran during paid timing.

Independent review before the freeze caught an eligibility guard omission: the
controller now checks whether projection was required from the actual request argv
and exit code. A narrowly fixed mixed Decimal/integer timing import also belongs
to the frozen source; prior real comparison outputs remain byte-identical.

## Primary paired results and A/A control

Ratios are treatment/control; below one favors the treatment label. Total tokens
include fresh input, cache creation, cache reads and output. Thinking is already
part of output. Visible model rounds are not native tool-call counts.

| Task | Pairs | Token ratio | Wall ratio | Call ratio | Token-saving pairs | Numeric gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Cross-file, primary | 6 | 0.563 | 0.691 | 0.859 | 4/6 | pass |
| Small, unchanged A/A | 6 | 1.653 | 1.219 | 1.750 | 2/6 | not applicable |

The cross-file gate requires paired tokens ≤0.85, wall time ≤1.0, calls ≤1.0 and
at least four token-saving pairs. Exact rational and serialized decimal arithmetic
determines the decision. Small-task `numeric_criterion_passed` is `null`: there is
no presentation intervention to evaluate. Its variation is neither subtracted
from the primary result nor pooled to produce a favorable aggregate.

| Task | Pair | Control / treatment | Tokens | Wall time | Calls |
| --- | ---: | --- | ---: | ---: | ---: |
| Cross-file | 1 | run003 / run004 | 0.618 | 0.652 | 0.750 |
| Cross-file | 2 | run012 / run011 | 0.422 | 0.465 | 0.200 |
| Cross-file | 3 | run008 / run007 | 1.298 | 1.390 | 0.900 |
| Cross-file | 4 | run015 / run016 | 1.550 | 1.365 | 1.000 |
| Cross-file | 5 | run023 / run024 | 0.508 | 0.668 | 0.818 |
| Cross-file | 6 | run002 / run001 | 0.464 | 0.714 | 1.300 |
| Small A/A | 1 | run005 / run006 | 1.958 | 1.117 | 2.000 |
| Small A/A | 2 | run022 / run021 | 3.951 | 1.595 | 7.000 |
| Small A/A | 3 | run018 / run017 | 1.348 | 1.322 | 1.500 |
| Small A/A | 4 | run013 / run014 | 2.828 | 1.734 | 6.000 |
| Small A/A | 5 | run009 / run010 | 0.969 | 1.113 | 1.200 |
| Small A/A | 6 | run020 / run019 | 0.720 | 0.835 | 0.600 |

## Complete-session descriptive medians

All six attempts remain in each cell. These cell medians are not substitutes for
the paired statistics above. Component medians need not sum to the median total.
Full categories, failures and precision remain in [report.json](report.json) and
[comparison.json](comparison.json).

| Task | Arm | Correct code | Tokens | Rounds | Calls | Wall seconds | Native USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cross-file | control | 6/6 | 103,057.5 | 7.5 | 10.5 | 35.13 | 0.040498 |
| Cross-file | factored | 6/6 | 70,783.5 | 5.5 | 9 | 28.37 | 0.037186 |
| Small A/A | control | 6/6 | 34,078 | 3 | 4 | 19.03 | 0.019098 |
| Small A/A | factored label | 6/6 | 52,754.5 | 4.5 | 6 | 23.38 | 0.023198 |

The primary paired token reduction exceeds the deterministic report-byte reduction.
Session behavior, output length, cache use and round structure also vary; this
study does not separate their causal contributions. Provider cache state is unknown,
and complete tool-execution intervals are unavailable. No statistical significance,
general multi-file guarantee or installed-skill ROI is claimed.

## Correctness, delivery and observed work

The independent [audit.json](audit.json) covers all 24 native traces, actual command
argv, outputs, final responses and source snapshots. Every run has one successful
supplied AST rename, actual integrated project verification, correct final code and
unchanged protected files. Within each task, all final diffs are byte-identical,
including the existing deterministic printer newline changes. There are no
accounting, timeout, isolation, engine or report-delivery errors.

All six cross-file treatment reports shrink **7,280→5,299 UTF-8 bytes (27.2%)**.
Every shared value and original unique fact reconstructs with strict JSON types.
All control outputs remain original bytes; all twelve small reports are unchanged
at 4,116 bytes. Native delivery agrees with the recorded original/presented output.

| Observation, six runs per task/arm | Cross control | Cross factored | Small control | Small factored label |
| --- | ---: | ---: | ---: | ---: |
| Native tool calls | 64 | 53 | 20 | 36 |
| Calls after the write | 58 | 47 | 14 | 19 |
| Native changed-file Reads after write | 22 | 20 | 4 | 6 |
| Native unchanged-file Reads after write | 21 | 19 | 8 | 5 |
| Reads of warned files after write | 9 | 6 | 8 | 9 |
| Repeated already-passed check executions | 7 | 6 | 2 | 5 |
| Supported final explanations | 5/6 | 4/6 | 6/6 | 4/6 |

Observed Reads are not automatically redundant. All six cross-file runs in each
arm repeat the already-passed check; one control repeats it twice. The only failed
native call is a directory Read in small-task run006, retained in all metrics.
The small nominal treatment arm makes eleven pre-write calls, including six PHP
Reads, despite identical
delegated instructions. Small control runs013 and022 finish correctly in one call.
These behaviors occur without a presentation change on that task.

Five final explanations fail their separate quality gate:

- Treatment run004 invents `OtherConsumer::fetch()`; the actual caller is `run()`.
- Treatment run011 and control run015 call the YAML value `fetch service`; it is
  `label: fetch`.
- Treatment run010 says the checker only verifies the new method name. It also
  checks the result/log label and absence of the old method.
- Treatment run019 says checker preservation was validated by passing checks.
  The file is preserved, but passing a runtime check does not prove unchanged bytes.

The last two are unsupported descriptions of verification, distinct from an
incorrect source mutation. Run016's ambiguous seven-line statement is not counted
as false: the surrounding unchanged class occupies seven lines. The audit records
the interpretation and exact evidence for all decisions. Final explanations pass
11/12 control and 8/12 treatment runs; some failures occur in the unchanged A/A
task, so this does not establish that factoring caused the quality difference.

## Decision and reproduction

Lossless shared metadata achieves the deterministic size prerequisite and the
primary numeric gate in these runs. The all-run quality gate fails. Retain the
prototype and evidence without introducing a public report mode or changing defaults.
Any confirmation needs new preregistration and must account for the large A/A
variation and unsupported final explanations.

[SHA256SUMS](SHA256SUMS) covers this report, native-derived summary, comparison,
manual audit and evidence archive. The archive has 789 allowlisted files plus
`export-sha256.json`: synthetic inputs, native streams, original/presented reports
and frozen controller/helper sources. Credentials, private sessions, binaries and
dependencies are excluded; runtime identities remain recorded. Export relocation
changes the summary's campaign/evidence paths, not economics or comparison results.

```bash
(cd benchmarks/agent-economics/results/2026-09-12-shared-report && sha256sum -c SHA256SUMS)
evidence_dir=$(mktemp -d /tmp/shared-report-evidence.XXXXXX)
tar -xzf benchmarks/agent-economics/results/2026-09-12-shared-report/evidence.tar.gz \
  -C "$evidence_dir"
python3 benchmarks/agent-economics/intent-command/summarize.py \
  "$evidence_dir" > /tmp/shared-report-summary.json
comparator_dir=$(mktemp -d /tmp/shared-report-comparator.XXXXXX)
git show 9367706319020e7a5bb6e096bfaf66fca08aada7:benchmarks/agent-economics/intent-command/unchanged_compare.py \
  > "$comparator_dir/unchanged_compare.py"
git show 9367706319020e7a5bb6e096bfaf66fca08aada7:benchmarks/agent-economics/intent-command/shared_compare.py \
  > "$comparator_dir/shared_compare.py"
python3 "$comparator_dir/shared_compare.py" /tmp/shared-report-summary.json \
  > /tmp/shared-report-comparison.json
```

Post-measurement publication fixes make the comparison CLI executable, simplify
equivalent proxy/validator control flow and tighten two test assertions for CI.
Additional single-file collision tests preserve the preregistered reserved-key
rejection: byte identity applies to legitimate reports, not namespace conflicts.
They do not alter the frozen campaign, its evidence or registered comparison.
