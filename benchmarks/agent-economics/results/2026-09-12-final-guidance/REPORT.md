# Evidence-bound finals: a short instruction does not produce a reliable saving

**The preregistered efficiency and quality gates both fail.** On the cross-file
rename, median paired ratios improve by 16.8% for total tokens, 12.4% for wall time
and 13.4% for calls. However, only seven of ten pairs save tokens, below the required
nine. Across those same ten pairs, total tokens instead rise **3.0%** and calls stay
**67→67**: long treatment sessions offset savings elsewhere. On the small rename,
paired tokens rise 1.4%, wall time 7.0% and calls are unchanged; total tokens rise
21.4% and total calls 14→20. These are different descriptive statistics, not
interchangeable estimates of a stable effect.

All **40 code states, protected-file checks, actual project checks and AST write
routes pass**. Only **13/20 treatment finals** are both supported and complete,
compared with **10/20 control finals**. That difference does not establish a reliable
reduction in explanation errors. All 40 new Haiku sessions cost **USD 0.9804776** in
native estimates, not invoices. Retain this as a failed experiment; the production
CLI and installed skill defaults do not change.

## Intervention and frozen provenance

The [prospective protocol](../../intent-command/FINAL-GUIDANCE.md), comparator,
fixture generator, runner and exact instructions were signed and pushed before paid
calls at [`f165476`](https://github.com/netresearch/php-ast-edit-skill/commit/f165476a3f08ec85fd9d66d81cf5c8ea554d8219).
Earlier campaigns motivate the hypothesis; none are pooled or reused as controls.

Both arms inherit the same short delegated exact-command instructions and existing
check-reuse paragraph. The treatment adds exactly 64 words limiting finals to
requested changes, observed checks and remaining requirements; grounding names and
values in observed evidence; and distinguishing passed checks from byte-preservation
or universal-correctness proofs. It preserves necessary investigation and warning
review. All added instruction tokens count toward usage. Neither arm changes engine
stdout, captures extra source context, restricts tools or factors report metadata.

Two new synthetic instances exercise the same broad rename shapes as the earlier
studies; they are not independently sampled real repositories or forty distinct
maintenance tasks. `ledger-method-rename` renames `Catalog::findSku` and its internal
call while preserving literals and the checker's negative reflection assertion.
`transport-contract-rename` renames an interface, two implementations and the typed
caller while preserving a separate legacy family and configuration label. Each has
protected support-file hashes, a behavioral oracle and a real project check.
Operator-supplied targets and ready-to-run commands exclude autonomous discovery cost.

- Two tasks × two arms × ten paired repetitions: all **40** retained.
- Seed `20260920`; adjacent pairs, five per task starting with each arm.
- Pinned `claude-haiku-4-5-20251001`, no effort/fallback override, Claude Code 2.1.268
  through its explicit versioned executable; PHP 8.5.10, php-parser 5.8.0 and
  Phpactor 2026.07.22.0, selected explicitly in both arms.
- Fresh isolated workspaces, serial runs, 120-second timeout, USD 3 ceiling and
  USD 0.75 reservation for only the next imminent attempt, replaced by native cost.
- Independent pairing audit confirms equal task prompts and initial source bytes,
  with exactly the 64-word appended-system delta. Every previous arm's full appended
  instructions remains identical in regression tests.

Before execution, 33 assessment checks, 111 efficiency tests, 34 intent/comparator
and fixture tests, independent design/code review and four real task/arm preflights
passed. Initial oracles fail; actual AST commands, integrated checks and final
oracles pass. Preflights are unpaid development evidence. No competing local tests
ran during candidate timing. No attempt was replaced, refined, dropped or added.

## Registered paired comparison

Ratios are treatment/control; below one favors treatment. The median of paired
ratios is not the ratio of two cell medians or the ratio of total usage. Each task
requires tokens ≤0.85, wall ≤1.0, calls ≤1.0 and at least nine strict token wins.
Decisions use exact rational token/count ratios and serialized decimal wall values;
display rounding does not determine the verdict. Ties count as nonwins.

| Task | Paired tokens | Paired wall | Paired calls | Token-saving pairs | Numeric gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Small rename | 1.014 | 1.070 | 1.000 | 3/10 | fail |
| Cross-file rename | 0.832 | 0.876 | 0.866 | 7/10 | fail |

Total tokens include fresh input, cache creation, cache reads and output. Thinking
is already included in output. All categories, failed attempts and exact metrics
remain in [report.json](report.json) and [comparison.json](comparison.json).
The small task has three strict wins; cross-file has seven. Their binomial fair-win
tail references are 0.9453125 and 0.171875; two-task Bonferroni references are 1.0
and 0.34375. These are descriptive sensitivity references, not confirmatory
p-values: session independence and controlled provider routing/cache are unproven.
Unlike the conventional [NIST sign test](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/signtest.htm),
this conservative reference keeps ties as nonwins.

| Task | Pair | Control / treatment | Tokens | Wall | Calls |
| --- | ---: | --- | ---: | ---: | ---: |
| Small rename | 1 | run022 / run021 | 0.643 | 0.809 | 0.500 |
| Small rename | 2 | run004 / run003 | 1.013 | 1.072 | 1.000 |
| Small rename | 3 | run020 / run019 | 1.020 | 1.319 | 1.000 |
| Small rename | 4 | run028 / run027 | 1.428 | 1.603 | 1.500 |
| Small rename | 5 | run035 / run036 | 2.150 | 1.210 | 5.000 |
| Small rename | 6 | run030 / run029 | 1.012 | 1.015 | 1.000 |
| Small rename | 7 | run013 / run014 | 0.998 | 1.049 | 0.667 |
| Small rename | 8 | run025 / run026 | 2.196 | 1.470 | 4.000 |
| Small rename | 9 | run037 / run038 | 1.015 | 1.068 | 1.000 |
| Small rename | 10 | run001 / run002 | 0.998 | 1.018 | 1.000 |
| Cross-file rename | 1 | run009 / run010 | 1.004 | 1.020 | 0.833 |
| Cross-file rename | 2 | run006 / run005 | 0.843 | 0.884 | 1.167 |
| Cross-file rename | 3 | run015 / run016 | 0.818 | 0.867 | 0.875 |
| Cross-file rename | 4 | run032 / run031 | 2.596 | 1.252 | 1.833 |
| Cross-file rename | 5 | run033 / run034 | 0.983 | 0.815 | 0.833 |
| Cross-file rename | 6 | run012 / run011 | 0.547 | 0.756 | 0.857 |
| Cross-file rename | 7 | run024 / run023 | 0.821 | 0.987 | 1.000 |
| Cross-file rename | 8 | run017 / run018 | 4.342 | 2.070 | 2.000 |
| Cross-file rename | 9 | run039 / run040 | 0.401 | 0.636 | 0.625 |
| Cross-file rename | 10 | run008 / run007 | 0.545 | 0.755 | 0.556 |

The lower-numbered run in each pair ran first. Small-task token ratios range from
0.643 to 2.196; cross-file ratios range from 0.401 to 4.342.
Cross-file pair 8 uses 4.342× the control tokens and pair 4 uses 2.596×. A favorable
median does not account for the magnitude of these long sessions. This is why the
following complete-task totals are reported prominently alongside the registered
paired gate. Neither task can be replaced by a pooled favorable result.

## Complete-session medians and totals

Each cell includes all ten attempts. Component medians need not sum to median total
tokens. Native cost includes differently priced fresh/cache/output categories.

| Task | Arm | Tokens | Rounds | Calls | Wall seconds | Native USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Small rename | control | 21,803.0 | 2 | 1 | 16.07 | 0.013479 |
| Small rename | guidance | 21,991.0 | 2 | 1 | 18.20 | 0.015026 |
| Cross-file rename | control | 80,638.5 | 6 | 6 | 31.40 | 0.033016 |
| Cross-file rename | guidance | 66,385.0 | 5 | 6 | 26.72 | 0.030889 |

| Task | Arm | Total tokens | Total calls | Total wall seconds | Native USD |
| --- | --- | ---: | ---: | ---: | ---: |
| Small rename | control | 253,387 | 14 | 164.90 | 0.156231 |
| Small rename | guidance | 307,636 | 20 | 188.28 | 0.164647 |
| Cross-file rename | control | 801,623 | 67 | 305.66 | 0.330163 |
| Cross-file rename | guidance | 825,537 | 67 | 290.09 | 0.329437 |

## Correctness and final-response review

Two independent reviewers audited disjoint halves of the native traces and
cross-reviewed disputed phrasing. The same truth/support and completeness rubric
applies to both arms. Final completeness requires the requested outcome, actual
verification with its proper scope, and disclosure of material remaining warnings
or requirements. A false warning classification fails the claims gate; it does not
automatically also fail coverage. A bare completion claim cannot pass by being short.

| Task | Arm | Code | Supported final | Complete final | Both final gates |
| --- | --- | ---: | ---: | ---: | ---: |
| Small rename | control | 10/10 | 3/10 | 6/10 | 0/10 |
| Small rename | guidance | 10/10 | 5/10 | 8/10 | 3/10 |
| Cross-file rename | control | 10/10 | 10/10 | 10/10 | 10/10 |
| Cross-file rename | guidance | 10/10 | 10/10 | 10/10 | 10/10 |

Across both arms, 28/40 finals have supported claims, 34/40 are complete, and 23/40
pass both gates. All 20 cross-file finals pass both; all final-quality failures are
on the small task. Treatment meets both final gates on only 3/10 small-task runs,
so the required 20/20 treatment quality gate fails. Control explanation failures
remain published but do not themselves veto treatment improvement.

The complete [audit.json](audit.json) records each verdict and source/trace line:

- Runs001/002/019/020/021/025/030/035/036/037 classify all five old-name PHP literals
  as unrelated data or not method references. `check.php:12` is a reflective
  negative assertion, so preserving its old name is correct but that explanation is
  false. Some runs add false line or verification-ID details.
- Treatment003 claims there are no unresolved cases while the report explicitly
  leaves checker literal classification open. Control004 and treatment019 invent
  check ID `verified-1`; the actual value is `verify-1`.
- Control004/013/022/028 and treatment014/038 omit material checker-literal warnings.
  These coverage failures are separate from truth/support.
- Treatment029 correctly calls the literals data labels and test references in
  non-method-call contexts. This narrow description passes, including with only
  one tool call; the audit adds no implicit source-Read requirement.
- Treatment036 reads the complete checker before the write and still describes the
  literals incorrectly. Cross-file run011 corrects an intermediate mistaken member
  name before its final response and passes the final gate.

All original reports match native delivery except native Bash's terminal-newline
handling. The actual project check runs successfully in every AST command. Every
protected file and reported changed-file hash is independently checked. There are
no timeouts, failed native tool calls, model/isolation/accounting errors or report
presentation changes. Each task's final diffs are identical across all its runs.

## Observed mechanism and limits

| Task | Arm | Pre-write calls | Post-write calls | Post-write Reads | Repeated checks | Median final words |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Small rename | control | 0 | 4 | 3 | 1 | 96 |
| Small rename | guidance | 3 | 7 | 6 | 1 | 107.5 |
| Cross-file rename | control | 0 | 57 | 48 | 7 | 85 |
| Cross-file rename | guidance | 0 | 57 | 48 | 7 | 78.5 |

For the cross-file task, total calls, post-write Reads and repeated checks are identical
between arms, despite the favorable paired medians. Small-task treatment adds three
pre-write Reads and more subsequent work. There are thirteen one-call sessions;
only treatment029 passes all final-quality gates. Fast completion is possible, but
one call and correct code alone do not establish a reliable explanation.

More source is not sufficient: run036 had the relevant checker and still invented
its meaning. A deterministic literal-use description, such as function argument
versus array key/value, is a possible next offline investigation. Such syntax facts
would still not establish target binding or whether a reference should be renamed.
This is a hypothesis, not a measured saving or a reason to add another prompt rule.

Provider cache/routing state and hidden default-system inputs are not controlled.
Native session IDs and working directories differ, and serial service variation
may remain. All initial and aggregate usage is retained. No complete tool-execution
interval coverage is available. Forty sessions on these two instances do not prove
broad task generalization, a causal effect size or an installed-skill/text-edit ROI.

The first request of run001 records 9 fresh input tokens, 9,456 cache-creation tokens
and zero cache reads. Run002 records 9, 2,625 and 6,909 respectively. From run003,
the initial requests show separate warm prefixes: 8,330 cache-read tokens for
treatment and 8,252 for control. Within matched task pairs, treatment's initial
input total is 78 tokens larger. All 40 native session IDs are unique. These are
observed counters, not evidence that provider cache state was experimentally reset.

## Evidence and reproduction

[SHA256SUMS](SHA256SUMS) covers this report, native-derived metrics, comparison,
manual audit and evidence archive. The archive contains 1,221 allowlisted files plus
`export-sha256.json`: synthetic inputs, native streams, snapshots and frozen
controller sources. Private sessions, credentials, binaries and dependencies are
excluded; runtime identities remain recorded. Relocation changes evidence-path
metadata, not the comparison results.

```bash
(cd benchmarks/agent-economics/results/2026-09-12-final-guidance && sha256sum -c SHA256SUMS)
evidence_dir=$(mktemp -d /tmp/final-guidance-evidence.XXXXXX)
tar -xzf benchmarks/agent-economics/results/2026-09-12-final-guidance/evidence.tar.gz -C "$evidence_dir"
python3 benchmarks/agent-economics/intent-command/summarize.py "$evidence_dir" > /tmp/final-guidance-summary.json
comparator_dir=$(mktemp -d /tmp/final-guidance-comparator.XXXXXX)
git show f165476a3f08ec85fd9d66d81cf5c8ea554d8219:benchmarks/agent-economics/intent-command/unchanged_compare.py > "$comparator_dir/unchanged_compare.py"
git show f165476a3f08ec85fd9d66d81cf5c8ea554d8219:benchmarks/agent-economics/intent-command/final_compare.py > "$comparator_dir/final_compare.py"
python3 "$comparator_dir/final_compare.py" /tmp/final-guidance-summary.json > /tmp/final-guidance-comparison.json
```

Post-freeze publication changes clarify assertion order and extract identical fixture
path constants for static analysis. They change neither the measured controller nor
the fixture manifest bytes, instructions or comparator. All 111 efficiency and 34
intent tests pass again after measurement, using the frozen runtime for new-fixture
preflight tests. No production default or new savings claim follows from this study.
