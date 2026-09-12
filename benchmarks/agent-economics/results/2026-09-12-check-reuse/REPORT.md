# Check-reuse guidance: lower tokens, incomplete mechanism

Adding 84 words about reusing successful project checks reduced median paired total
tokens by **11.8%** on a small rename and **31.3%** across files. Median paired wall
time fell **6.8%** and **4.9%**. Tool calls did not consistently decrease: the small-task
paired median was unchanged, while the cross-file value rose **17.0%**. All **24 code
outcomes** were correct; **23/24 final explanations** were supported. Total native
estimated cost was **USD 0.7817936**, not an invoice.

The registered overall criterion **fails**. Small-task token reduction misses the
15% threshold; repeated checks do not decrease on the cross-file task; one control
final explanation fails the all-attempt quality gate. These exploratory results
support further investigation, not adoption as a proven optimization.

## Intervention and provenance

The [prospective protocol](../../intent-command/CHECK-REUSE.md), instructions and
comparator were signed and pushed before paid calls at
[`4e7a574`](https://github.com/netresearch/php-ast-edit-skill/commit/4e7a57438e44f3c333c866e22c1b696131ee219e).
The prior [unchanged-excerpt experiment](../2026-09-12-unchanged-context/REPORT.md)
motivated this hypothesis. Earlier attempts are neither pooled nor reused as controls.

Both arms receive original AST reports with `alreadyRun`, successful `verify`
entries, diffs and unresolved warnings. Both inherit the short delegated exact-command
instructions. Only `check_reuse_guidance` adds the protocol's generic 84-word paragraph;
`check_reuse_control` adds nothing. There is no report rewriting, excerpt capture,
changed tool set or restriction on additional calls. All extra instruction tokens
count toward treatment usage.

The paragraph identifies when an existing check satisfies the requirement: same
command, working directory and relevant inputs, with successful project verification.
It preserves failed, missing, stale or differently scoped checks, explicit requests
for fresh independent execution, and unresolved-warning review. The full public
skill already contains this principle. This tests its omission from the short
benchmark instructions; it does not compare against the installed full skill or
against ordinary text editing.

- Two unchanged synthetic tasks × two arms × six paired repetitions = 24 attempts.
- Seed `20260918`; three pairs per task start with each arm. All twelve paired
  fixtures and task prompts are byte-identical; only the system paragraph differs.
  Operator-selected targets and complete commands exclude autonomous discovery cost.
- Pinned `claude-haiku-4-5-20251001`, no effort/fallback override, Claude Code 2.1.268
  via its versioned executable, PHP 8.5.10, php-parser 5.8.0 and pinned Phpactor
  2026.07.22.0, using the same runtime dependencies as the preceding campaign.
- Fresh private workspaces, serial runs, 120 seconds per attempt, USD 3 ceiling and
  USD 0.75 reservation for the next imminent run, replaced by actual native cost.
- Preflight: 33 assessment checks, 89 efficiency tests, 22 intent/comparator tests,
  four real task/arm edits with independent oracles, Ruff and independent design/code
  review. The new worktree's Composer autoload setup was corrected before these
  gates passed; no candidate had started during that setup work.

All 24 attempts completed without timeouts or accounting/isolation errors. No run
was replaced, rerun, refined, added or dropped. No competing local tests ran during
candidate timing; operator activity was lightweight progress and trace inspection.
The publication branch subsequently moves a test fixture constructor outside an
exception assertion to address a review finding. It changes no measured candidate,
controller, instruction, comparator arithmetic or published evidence.

## Preregistered paired outcome

Each task must achieve median paired treatment/control token ratio ≤0.85, median
wall-time ratio ≤1.0 and at least four of six token-saving pairs. Threshold decisions
use exact rational ratios of integer tokens and serialized decimal wall times.
All-attempt quality and fewer repeated check executions **on each task** are separate
required gates. Cell medians do not replace these registered paired statistics.

| Task | Token ratio | Wall ratio | Round ratio | Call ratio | Cost ratio | Token-saving pairs | Numeric gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Small rename | 0.882 | 0.932 | 0.900 | 1.000 | 0.953 | 5/6 | fail |
| Cross-file rename | 0.687 | 0.951 | 0.694 | 1.170 | 0.908 | 4/6 | pass |

Ratios below one favor treatment. Paired native-cost reductions are **4.7%** and
**9.2%**, substantially smaller than the total-token reductions. Total tokens include
fresh input, cache creation, cache reads and output; thinking is already part of
output. Provider cache state is unknown. [report.json](report.json) retains all
components, including much larger cache-read counts than fresh uncached input.
This does not establish the same reduction in every token category.

| Task | Repetition | Control / treatment | Token ratio | Wall ratio | Call ratio |
| --- | ---: | --- | ---: | ---: | ---: |
| Small | 1 | run018 / run017 | 0.581 | 0.670 | 0.667 |
| Small | 2 | run008 / run007 | 0.805 | 1.036 | 1.250 |
| Small | 3 | run021 / run022 | 0.983 | 0.890 | 1.200 |
| Small | 4 | run005 / run006 | 0.958 | 0.975 | 1.000 |
| Small | 5 | run024 / run023 | 1.315 | 1.438 | 1.000 |
| Small | 6 | run011 / run012 | 0.472 | 0.722 | 0.167 |
| Cross-file | 1 | run016 / run015 | 1.544 | 1.017 | 1.375 |
| Cross-file | 2 | run009 / run010 | 0.400 | 0.896 | 0.769 |
| Cross-file | 3 | run003 / run004 | 1.378 | 1.005 | 1.429 |
| Cross-file | 4 | run019 / run020 | 0.838 | 1.171 | 1.091 |
| Cross-file | 5 | run014 / run013 | 0.537 | 0.682 | 1.250 |
| Cross-file | 6 | run002 / run001 | 0.274 | 0.462 | 0.583 |

Every pair, including the incorrect control explanation, remains in the denominator.
[comparison.json](comparison.json) contains unrounded descriptive output and the
exactly evaluated numeric verdicts.

## Complete-session cell medians

These descriptive medians include all six attempts per cell. A ratio of two cell
medians differs from the median of six paired ratios above.

| Task | Arm | Tokens | Visible rounds | Calls | Wall seconds | Native cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Small | check_reuse_control | 52,391.5 | 4.5 | 5.5 | 21.28 | 0.022533 |
| Small | check_reuse_guidance | 46,387 | 4 | 5 | 19.85 | 0.022373 |
| Cross-file | check_reuse_control | 150,286.5 | 10.5 | 9.5 | 42.54 | 0.047030 |
| Cross-file | check_reuse_guidance | 96,042.5 | 7 | 10 | 38.84 | 0.038510 |

The cell-median token ratios are 0.885 and 0.639; wall ratios are 0.933 and 0.913.
The model is stochastic and six pairs per task remain exploratory. Tool execution
time is unknown without complete interval coverage. Lower round counts alongside
similar or higher call counts are a different observation from fewer tool calls.

## Mechanism and accuracy

Independent [audit.json](audit.json) reviews all native calls, complete final
responses, fixture hashes and original report delivery. Each candidate executes
one successful supplied rename; every declared project check actually runs and
passes. All code states and protected files pass the independent oracle. Native
Bash removes the terminal newline from stdout; report content is otherwise unchanged
in both arms. No context intervention is present.

| Observed count | Control | Guidance |
| --- | ---: | ---: |
| Repeated check executions, small task | 5 | 3 |
| Repeated check executions, cross-file task | 6 | 6 |
| Repeated check executions, total | 11 | 9 |
| Bash calls containing those repeats | 11 | 9 |
| Runs repeating an already-passed check | 11 | 8 |
| Native tool calls, total | 93 | 89 |
| Calls after the write | 72 | 67 |
| Successful native Reads of known files after the write | 47 | 52 |
| Native Reads of warned files after the write | 17 | 16 |
| Native tool-call failures | 0 | 2 |
| Supported final explanations | 11/12 | 12/12 |

Cross-file repeated checks do not decrease, so the mechanism gate fails. Its total
native calls also rise 59→60 despite fewer visible rounds and lower tokens. These
traces do not establish that avoiding checks caused the cross-file token reduction.
The aggregate 93→89 calls cannot replace either task's paired call statistic.

Actual check executions and containing Bash calls are counted separately. An `echo`
mentioning a command is not an execution. Guidance run015 executes the check twice
in separate calls (`raw.jsonl:25` and `:52`); the second combines it with echo and
Git status. No run executes multiple equivalent checks inside one Bash call.
Different checks, syntax lint and Git reads remain separate. A read of unresolved
source may still be warranted.

Guidance run012 completes the small task correctly with just the engine tool call.
Guidance runs006 and010 contain directory-Read failures; both recover and remain in
every total. The fixture diffs retain the same deterministic printer newline changes
as earlier campaigns, not additional rename errors. Preserved checker strings may
be semantic negative assertions or fallbacks; preservation does not classify them
as unrelated literals.

Control run003's final response (`raw.jsonl:49`) invents a preserved
`OtherConsumer::fetch()` caller and gives the YAML value as `fetch service`.
The actual caller is `OtherConsumer::run()` and the YAML is `label: fetch`.
Earlier reads include the correct source. Its code is correct but its final-claim
gate fails. Intermediate mistakes elsewhere are retained separately; a final that
corrects or omits them is assessed on that final response.

The combined criterion fails for three distinct reasons: small-task token threshold,
cross-file repeat-check mechanism, and control final accuracy. The new arms remain
benchmark-only. These tasks do not establish model adherence when a check fails,
is missing or becomes stale, or when a user explicitly demands a new independent
execution. Larger confirmation and those conditions would be required before
claiming general reliability or installed-workflow savings.

## Reproduce and audit

[SHA256SUMS](SHA256SUMS) covers this report, native-derived metrics, comparison,
manual audit and evidence archive. The archive contains 788 allowlisted files plus
`export-sha256.json`: native streams, fixtures, checks, oracles and frozen controller
sources. Private sessions, credentials, dependencies and binaries are excluded;
recorded runtime identities remain available.

From the repository root:

```bash
(cd benchmarks/agent-economics/results/2026-09-12-check-reuse && sha256sum -c SHA256SUMS)
evidence_dir=$(mktemp -d /tmp/check-reuse-evidence.XXXXXX)
tar -xzf benchmarks/agent-economics/results/2026-09-12-check-reuse/evidence.tar.gz \
  -C "$evidence_dir"
python3 benchmarks/agent-economics/intent-command/summarize.py \
  "$evidence_dir" > /tmp/check-reuse-summary.json
comparator_dir=$(mktemp -d /tmp/check-reuse-comparator.XXXXXX)
for name in unchanged_compare.py check_reuse_compare.py; do
  git show "4e7a57438e44f3c333c866e22c1b696131ee219e:benchmarks/agent-economics/intent-command/$name" \
    > "$comparator_dir/$name"
done
python3 "$comparator_dir/check_reuse_compare.py" \
  /tmp/check-reuse-summary.json > /tmp/check-reuse-comparison.json
```

Relocation changes only the summary's `campaign` and per-run `evidence_path`
metadata. The reproduced comparison is byte-identical to the published file.
