# Public PHP rename with observed behavior verification

In this one public-source task, semantic AST editing reduced Haiku's observed
token use, calls and elapsed time while retaining actual behavior verification.
All thirty candidates made the exact required change and ran the existing tests
on their final bytes. The integrated arm used a median **one call**, compared with
**sixteen** for text edits. This is a six-file extraction with three rename sites,
not evidence of general savings or full TYPO3 application support.

## Results

Ten fresh candidate processes per arm; medians include every attempt. Tokens are
whole-call input, cache-read input, cache-created input and output combined.
Rounds are visible primary-model responses, distinct from native turn counters.
Cost is the CLI's native list-price estimate, not a subscription invoice.

| Mutation and verification | Tokens | Tool calls | Rounds | Candidate seconds | USD | Correct and candidate-verified |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Text edits, manual checker | 124,133.5 | 16 | 13 | 37.76 | 0.054360 | 10/10 |
| Semantic AST, manual checker | 30,472.5 | 3.5 | 4.5 | 22.93 | 0.026171 | 10/10 |
| Semantic AST, integrated checker | 12,212 | 1 | 2 | 16.43 | 0.018277 | 10/10 |

Relative changes in these arm medians:

| Comparison | Tokens | Calls | Rounds | Seconds | USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| AST/manual versus text/manual | -75.5% | -78.1% | -65.4% | -39.3% | -51.9% |
| AST/integrated versus text/manual | -90.2% | -93.8% | -84.6% | -56.5% | -66.4% |
| AST/integrated versus AST/manual | -59.9% | -71.4% | -55.6% | -28.3% | -30.2% |

These ratios of medians differ from medians of paired differences. The prospective
within-repetition comparisons are retained in [the complete summary](real-summary.json):

| Paired difference, after minus before | Tokens | Calls | Rounds | Seconds | USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| AST/manual minus text/manual | -78,717.5 | -8.5 | -7.5 | -10.65 | -0.016633 |
| AST/integrated minus AST/manual | -6,418 | -1.5 | -1 | -2.15 | -0.003246 |

Variability remains substantial. Tokens ranged from 61,402–209,161 for text,
17,832–53,489 for AST/manual and 11,855–42,489 for AST/integrated. Six of ten
integrated candidates finished with one tool call; the other four used 5–7 calls.
The complete distributions and individual [run records](real-runs.json) are public.

## What was actually tested

The source is pinned to public
[`netresearch/t3x-nr-llm` commit b505c936935b99baa3088ce62ad222d2ba61cee0](https://github.com/netresearch/t3x-nr-llm/commit/b505c936935b99baa3088ce62ad222d2ba61cee0).
The extraction contains `SchemaPropertyClassifier`, `SchemaInputCoercer`,
`JsonSchemaValidator`, `StrictSchemaSubset` and the first two classes' original
test classes. Original copyright headers, GPL-2.0-or-later attribution, the upstream
license and source hashes accompany every workspace.

The requested change was `SchemaPropertyClassifier::classify` to `controlType`:
one declaration, one production caller and one direct test caller in three files.
All other bytes, including test assertions and inputs, had to remain unchanged.
The upstream TYPO3 UI consumer `WaitingRunViewFactory` is explicitly excluded.
There is no independent same-name runtime control in this extraction. See the
[fixture and dependency scope](../../REAL_FIXTURE.md).

Every arm received the same explicit final-byte verification obligation and the
same checker. Each candidate was allowed to batch reads, searches, edits and checks.
The text arm could use ordinary edits or scripts; all ten chose three individual
Edit calls. AST arms had to use the provided semantic mutation command. Only the
integrated arm's frozen project configuration automatically ran the checker.
This is observed Haiku behavior, not the minimum possible cost of a text script.

The checker ran the original **17 tests and 20 assertions** with pinned PHPUnit
12.5.31. Both unchanged baseline and correctly renamed source pass, so the checker
does not reveal or enforce the hidden expected rename. Separate negative controls
prove that an omitted production caller fails the tests, weakened assertions can
pass PHPUnit but fail the byte oracle, and checks on stale or changing files cannot
certify the final bytes.

All 30 final inventories match the independent exact-byte oracle. All 30 independent
post-candidate test runs pass. Crucially, all 30 also have a successful **candidate
check receipt** whose before and after inventories equal the final inventory.
The independent checks never create candidate receipts. No attempt timed out;
the campaign required no restart or rerun. All native completions and accounting
were valid.

## Where the difference came from

The model can express the desired symbol change and delegate reference coordinates
and individual writes to the semantic command. Phpactor resolves the references;
the AST layer validates their identifier slots and performs the guarded transaction.
Configured verification then runs the existing tests within that write operation.
This case supports the value of that complete workflow, including the shift from
locating and replacing text to requesting a symbol-level change.

It does **not** isolate AST syntax from semantic discovery. Both AST arms include
Phpactor resolution and compact evidence; the integrated comparison additionally
includes automatic test triggering and reporting. The earlier
[existing-Phpactor control](../2026-09-07-haiku/REPORT.md) remains separate and is not
pooled into these results. No complete AST JSON representation was given to the model.

All ten text candidates needed no PHP repair edits: their first three Edit calls
were correct. The savings here therefore do not demonstrate avoidance of broken
PHP patches. They mainly accompany less model-directed discovery, fewer individual
edits and fewer subsequent calls. Native traces contain 23 actual command-use
errors: 19 leading-dash grep-pattern errors and four Read-directory errors.
Three grep errors were hidden by a pipeline or `|| echo`. Conversely, two native
error flags were legitimate no-match grep results. Thus the **22 native error flags**
are not interchangeable with 22 failed edits or even 22 actual command mistakes.

## Remaining verification and reporting friction

There were 33 candidate test executions. Integrated runs012,023,030 repeated the
already successful checker on identical final bytes. Several AST candidates also
read changed files after receiving exact-byte evidence. The unchanged engine warning
still says `NOT_CANONICAL: ... inspect changedLines and diff`; this may encourage
readbacks despite the common stop guidance. The experiment does not isolate that
warning's effect, and a source read is not automatically pointless.

Final-response quality is separate from code/test success. Run004 calls the
declaration a third caller. Runs004,005,012 explicitly attribute complete reference
coverage to the tool; runs023,029 similarly say it resolved all references. The
returned contract remains `completeness: unknown`. Some finals also describe the
test suite as proving all functionality, which exceeds the named tests' coverage.
The actual fixture changes are correct; this does not turn those statements into
general resolver or semantic guarantees. Concrete test counts and reported checker
durations were accurate; PHP 8.5 was not mistaken for a duration in these runs.

All 225 tool calls and thirty final answers were manually inspected across three
read-only reviews: [runs001–015](audit-first15.md), [runs016–023 and028–030](audit-last15.md),
and [runs024–027](audit-24-27.md). No forbidden evaluator/home/receipt reads, mutation
route violations, or unauthorized workspace changes were observed. Omission of the
completeness caveat alone was not scored as a false statement.

## Accounting and timing scope

The following are totals over ten candidates per arm, not medians:

| Arm | Fresh input | Cache-created input | Cache-read input | Output | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text/manual | 12,196 | 141,455 | 1,155,890 | 31,511 | 1,341,052 |
| AST/manual | 12,400 | 82,719 | 202,411 | 16,636 | 314,166 |
| AST/integrated | 12,328 | 75,717 | 123,622 | 14,246 | 225,913 |

Fresh uncached input is nearly unchanged. Much of the total-token reduction is
less repeated cached context, with lower cache creation and output as well.
Therefore “90.2% fewer tokens” here means the stated combined whole-call metric,
not 90.2% less fresh input or 90.2% lower billing. Thinking tokens are a subset of
output and are not added again. Whole-call modelUsage and main-loop usage remain
separate in every record; no cause is invented for their difference.

All thirty candidates used **1,881,131 total tokens** and **USD 1.0968633** at native
list prices. Median recorded checker duration was about 95 ms in each arm; integrated
runs with duplicate checks retain both durations. Candidate wall time includes
their checker work and excludes the controller's subsequent hidden check. Total
tool-execution timing is not exposed by these traces and remains null. No residual
orchestration time is inferred by subtracting unrelated timing counters.

## Frozen inputs and reproduction

- Prospective [protocol](../../REAL_PROTOCOL.md), frozen before model execution.
- Controller/engine source commit: `dc2a44a00ce4d7492293f23f29734c0be26457aa`.
- Configuration SHA-256: `31eb372ac3ebe2d1e4b26f4a90d60c546155cf2e5b3d9d4310abb0602ce8005d`.
- Model: `claude-haiku-4-5-20251001`; Claude Code 2.1.263; no effort flag.
- PHP 8.5.10; Python 3.12.3; pinned Phpactor 2026.07.22.0 and PHPUnit 12.5.31 PHARs.
- Ten shuffled repetition blocks, rotating arm order; no substitutions or reruns.
- Native startup confirms the requested model and isolated tool/plugin/skill/MCP settings.

The [evidence archive](evidence.tar.gz) contains 832 hashed files: original traces,
prompts, wrappers, source helpers, process/accounting records, final public PHP
snapshots, resolver reports and all candidate receipts. It excludes PHAR binaries,
vendor trees, Git metadata and private home sessions. See [the manifest](evidence-manifest.json)
and [SHA256SUMS](SHA256SUMS). Its SHA-256 is
`ecbebfeb728a5b17919672977bd10c8043a37821dfbc88fc0a160483688f02d5`.

Both export utilities are inside the archive. From this result directory, extract
the verifier and run the offline accounting and evidence check:

```bash
tar -xzf evidence.tar.gz exporter/php-real-verify-export.py
python3 exporter/php-real-verify-export.py --export "$PWD"
```

It rechecks all archive hashes, 21 frozen source helpers, thirty native ledgers,
thirty candidate-verification outcomes, all final byte oracles and the complete
summary. Recorded hidden PHPUnit outcomes are checked against final manifests;
PHPUnit itself is not rerun without the excluded pinned PHAR. Floating-point cost
totals use a 1e-12 tolerance for summation-order rounding. The measured campaign
was never amended; subsequent repository changes simplify analysis and harden
unknown-evidence handling without changing the frozen experiment.

The frozen checker defaulted missing JUnit counter attributes to zero; current
code rejects incomplete counter metadata. All 33 candidate receipts and 30 hidden
checks record 17 tests, 20 assertions and zero errors, failures and skips. Original
temporary XML reports are not archived, so this is an audit of stored counts,
not a retrospective XML reparse. The pinned PHPUnit integration also passes with
the stricter parser.

This is one selected small public-source task repeated ten times per arm, with
provider caching conditions uncontrolled. It establishes neither a broad accuracy
improvement nor production support for arbitrary repositories, dynamic dispatch,
inheritance, framework references, other models or other transformations.
