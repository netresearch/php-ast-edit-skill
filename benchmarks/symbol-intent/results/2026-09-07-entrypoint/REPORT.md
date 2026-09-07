# A direct-rename instruction did not meet the adoption rule

This twenty-run Haiku experiment found **no reduction in median preparatory calls**
from explaining before editing that an explicitly named rename can be invoked directly.
Both arms already needed median zero preparatory calls and one total tool call.
The paragraph did not meet the prospective adoption rule, so the existing entrypoint
stays unchanged. All twenty candidates made the exact required changes and ran the
17 original tests on their final bytes.

This is a separate comparison of two instructions for the same experimental AST
workflow. It neither repeats nor pools the earlier
[thirty-run text-versus-AST study](../2026-09-07-real-php/REPORT.md) or
[twenty-run result-guidance study](../2026-09-07-guidance/REPORT.md).

## Results and adoption decision

Ten fresh candidate processes per arm. `compact` receives the existing integrated
rename prompt; `intent-first` receives that prompt plus the exact capability
paragraph in the [prospective protocol](../../ENTRYPOINT_PROTOCOL.md). Both use
the same resolver, AST engine, compact `--evidence` response and integrated checker.
Neither receives `--guidance`; no skill files are loaded. The treatment adds no
source facts, expected edit inventory, call sites or replacement text.

The primary observation was fixed before execution: unique native tool-use IDs
before the first assigned rename invocation, including a failed first attempt.
Calls sharing the invocation's assistant event are counted as peers, not ordered
before it. These are trace observations, not automatic judgments of redundant work.

| Median per candidate | Compact | Intent-first | Change in arm medians |
| --- | ---: | ---: | ---: |
| Preparatory tool calls, primary metric | 0 | 0 | 0 calls |
| Whole-call tokens, including cache | 12,151 | 12,426.5 | +2.3% |
| All tool calls | 1 | 1 | 0% |
| Model rounds | 2 | 2 | 0% |
| Candidate seconds | 16.55 | 17.14 | +3.5% |
| Native list-price USD | 0.018020 | 0.018499 | +2.7% |
| Later tool calls | 0 | 0 | 0 calls |
| Duplicate successful final-byte checks | 0 | 0 | 0 checks |

All 10/10 candidates in each arm completed normally, passed the exact-scope oracle,
passed independent behavior checks and obtained a successful candidate check on
final bytes. All twenty native accounting and primary observations are known;
all ten pairs are complete. There are no unattempted rows, timeouts, replacements
or reruns. The [run records](real-runs.json) and [complete summary](real-summary.json)
retain every observation, including the more expensive candidates.

Full distributions below are in execution order within each arm:

| Arm | Preparatory calls | Later calls | Total calls | Duplicate final-byte checks |
| --- | --- | --- | --- | --- |
| Compact | 0, 0, 0, 0, 0, 0, 0, 4, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 4, 0, 0 | 1, 1, 1, 1, 1, 1, 1, 9, 1, 1 | 0, 0, 0, 0, 0, 0, 0, 1, 0, 0 |
| Intent-first | 0, 0, 0, 0, 0, 1, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 4, 3, 0 | 1, 1, 1, 1, 1, 2, 1, 5, 4, 1 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |

Every peer count is zero. Nine compact candidates and seven intent-first candidates
finish with one total call. The arms use eighteen calls each in total: compact has
four preparatory and four later calls; intent-first has one preparatory and seven
later calls. Preparatory calls are lower with intent-first in **one of ten pairs**,
equal in eight and higher in one. The median paired difference is zero.

The ten pre-call deltas, intent-first minus compact in repetition order 0–9, are
`-4, 0, 0, 0, 0, 0, 0, 1, 0, 0`. The complete summary retains every paired delta for
every metric. Median paired differences for secondary metrics are +257.5 tokens,
zero total calls, zero rounds, +0.384 seconds and +USD 0.00038145. These are medians
of within-pair differences, distinct from differences or ratios of arm medians.

The predeclared rule required at least one fewer preparatory call in the arm
medians, improvement in at least six of ten pairs, and no increase in token or
candidate-time medians, alongside correctness, verification, coverage and reporting
conditions. **All four efficiency conditions fail.** The zero-median floor is
retained as the primary finding; fewer aggregate preparatory calls, one avoided
duplicate checker, or lower aggregate tokens do not replace that decision rule.
This is a conservative engineering rule, not a statistical significance test.

## What the complete trace audit found

Independent AI reviewers read all **36 tool calls and results and twenty final
answers**: [001–007](audit-001-007.md), [008–014](audit-008-014.md) and
[015–020](audit-015-020.md). The audits retain tool-use IDs, one-based native line
references, manual classifications, disputed wording and independent receipt checks.

Only two candidates make preparatory calls. Intent-first011 runs `pwd && git status`
in one Bash call to establish workspace state. Compact016 makes four initial calls,
including source/search work and a failed leading-dash grep followed by correction.
These activities are assessed individually in the audits; initial reads are not
automatically redundant or coordinate reconstruction. No same-event peer calls or
rename retries occur.

The eleven later calls are ten source Reads and one repeated behavior checker:
intent-first015 makes four Read calls over three files, including a second partial
read of the coercer to reach its call site; compact016 reads the three edited files and
repeats the checker; intent-first018 reads the three edited files. These revisit
the reported changes. None repairs PHP, verifies intervening mutations or follows
a newly identified unresolved reference. The audits classify their stated purposes
separately from the controller's automatic continuation count.

All 21 candidate checker receipts report **17 tests and 20 assertions**, with
before and after inventories equal to final bytes. Compact016 repeats an already
successful final-byte check without intervening changes. No candidate uses a
forbidden mutation route, reads the controller/evaluator or private home sessions,
or needs a PHP repair. Its failed grep is a search-command error, not a broken edit.
Consequently this trial does not demonstrate avoided text-edit correction loops.

Correct code and tests still coexist with overconfident final explanations. The
audits preserve explicit completeness assurances separately from ordinary bounded
completion wording, and distinguish overclaims about what passing tests prove.
The returned resolver contract remains `completeness: unknown`. Neither the exact
three-site fixture outcome nor the 17 tests turn it into exhaustive semantic
coverage. The claim categories below overlap and are not a single accuracy score:

| Explicit unsupported assurance | Compact runs | Intent-first runs |
| --- | --- | --- |
| Complete reference resolution/discovery | 004, 005, 008, 013, 016 (5) | 007, 015, 018, 019 (4) |
| Tests establish edit completeness | None | 018, 019 (2; overlap with reference assurances) |
| Tests establish all existing functionality | None | 003 (1) |

For 018, the resolver and test-based completeness assertions share one sentence;
for 019, they are separate sentences. Five final answers in each arm contain at
least one of these explicit assurances. The treatment has fewer resolver-assurance
finals but adds test-scope overclaims, so an accuracy benefit is not established.
Ambiguous update-outcome or purpose wording, including compact017 and
intent-first010/014, is retained separately rather than scored as exhaustive
discovery. No final explicitly misstates the numeric edit, test, assertion or
timing counts. The audits also preserve imprecise role and per-file check labels.

## Task and verification scope

The unchanged fixture comes from public
[`netresearch/t3x-nr-llm` commit b505c936935b99baa3088ce62ad222d2ba61cee0](https://github.com/netresearch/t3x-nr-llm/commit/b505c936935b99baa3088ce62ad222d2ba61cee0).
It contains six PHP files, 1,150 original lines and 38,610 original PHP bytes, plus
the original GPL-2.0-or-later license, provenance and project configuration. The
requested rename is `SchemaPropertyClassifier::classify` to `controlType`: one
declaration, one production call and one direct test call in three files. Every
other byte, including test assertions and inputs, must stay unchanged.

The TYPO3 UI caller `WaitingRunViewFactory` is excluded; there is no independent
same-name runtime control in this extraction. The unchanged baseline also passes
all 17 tests, so the separate exact-byte oracle is necessary to establish that the
rename occurred. See [REAL_FIXTURE.md](../../REAL_FIXTURE.md). These tests do not
establish arbitrary receiver binding, inheritance, dynamic dispatch, full TYPO3
application behavior or resolver completeness.

The assigned command composes Phpactor discovery, AST validation and guarded
mutation, integrated PHPUnit verification and exact-byte readback evidence. The
LLM can select the symbol and new name while the tool derives edit coordinates.
This architectural ability is shared by both arms; the experiment tests only
whether the additional instruction improves its use. It does not test giving the
LLM a raw AST instead of PHP, or the installed same-file `rename_method` operation.

Every candidate obtains its own successful final-byte receipt before the
controller's independent hidden checker. A hidden pass does not substitute for
candidate verification. Receipt attribution assumes cooperative isolated local
processes, not hostile attestation. Recorded outcomes and final hashes were audited;
the original temporary JUnit XML is not archived.

## Token and time accounting

Totals over ten candidates per arm, not medians:

| Arm | Fresh input | Cache-created input | Cache-read input | Output | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compact | 12,288 | 60,792 | 86,757 | 12,055 | 171,892 |
| Intent-first | 13,002 | 63,262 | 69,142 | 12,609 | 158,015 |

The campaign used **329,907 combined tokens** and **USD 0.4123079** in native
list-price estimates, not a subscription invoice. Combined tokens count fresh
input, cache creation, cache reads and output. Thinking is a subset of output and
is not added again. Whole-call and main-loop accounting remain separate.

Total tokens are lower with the paragraph despite its higher median, driven by
the expensive compact016 run. Token ranges are 11,888–62,631 for compact and
12,280–31,095 for intent-first. No outlier is removed. Provider caching and model
variation are uncontrolled; neither the small median increases nor aggregate
decreases establish a general instruction penalty or benefit.

Candidate wall time includes integrated and repeated checks but excludes the
controller's later hidden checker. Median cumulative candidate-checker duration
is 98.500 ms for compact and 96.667 ms for intent-first. This is not total AST tool
time. Total tool execution duration remains unavailable; no orchestration duration
is inferred by subtracting unrelated counters.

## Frozen inputs and offline reproduction

- [Prospective protocol](../../ENTRYPOINT_PROTOCOL.md), fixed before execution.
- Experiment: `real-php-entrypoint-v1`; ten balanced shuffled pairs, seed `20260911`.
- Frozen source commit: `793d8d596855c83eb6aaaf414ad86c64476ea034`.
- Configuration SHA-256: `0c54b41096a8207afe1949f1d1a6ff9340241c0cfe920a1da66a47985bcc44b9`.
- Model: `claude-haiku-4-5-20251001`; Claude Code 2.1.263; no effort flag.
- PHP 8.5.10; Python 3.12.3; pinned Phpactor 2026.07.22.0 and PHPUnit 12.5.31.
- Twenty fresh isolated processes; no adaptive prompts, exclusions or reruns.

The [evidence archive](evidence.tar.gz) contains **617 hashed files**: complete
native traces, prompts/configuration/wrappers, frozen source helpers, resolver
reports, final public PHP snapshots, measurements, all 21 candidate receipts and
the frozen source licenses. PHAR binaries, vendor trees, Git metadata and private
home sessions are excluded. See the [manifest](evidence-manifest.json) and
[SHA256SUMS](SHA256SUMS). Archive SHA-256:
`fb5d337f2b48f40181b85dbeaf2150f9b571178a67be63660f3348095eade416`.

The [independent export review](export-review.md) also compared all 615
campaign-derived members byte-for-byte with the original campaign and rehashed
its unchanged 2,063-file source/dependency inventory. The other two archive
members are the included exporter and verifier.

From this result directory, extract the included verifier and run it offline:

```bash
tar -xzf evidence.tar.gz exporter/php-entrypoint-verify-export.py
python3 exporter/php-entrypoint-verify-export.py --export "$PWD"
```

It verifies all archive hashes, 28 frozen source files, twenty native usage
ledgers, all twenty exact-scope and candidate-verification outcomes, all pre/peer
and later-call observations, duplicate final-byte check counts and the complete
regenerated summary. Recorded hidden PHPUnit outcomes are checked against final
manifests; PHPUnit is not rerun without the excluded pinned PHAR. Floating-point
cost totals allow 1e-12 for summation-order rounding. Publication prose is not
represented as measured source; the frozen campaign remains unchanged.

This is a selected task reused for a new prospective comparison, not held-out
validation. The earlier compact arm had median three later calls; this new compact
arm has zero. That cross-campaign difference is not an instruction treatment effect
and reinforces why the campaigns are kept separate. The current entrypoint stays
unchanged; broader adoption would need a separately frozen held-out workload.
