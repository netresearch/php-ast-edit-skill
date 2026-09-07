# Additional rename guidance did not reduce continuation

This twenty-run Haiku experiment found **no additional efficiency benefit** from
the opt-in guidance output bundle on the selected public PHP rename. Both arms
used a median three tool calls after the successful rename and integrated tests.
Guidance had higher observed token, call, round, time and cost medians. All twenty
candidates made the exact required edits and ran the original tests on final bytes.
The guidance remains experimental and opt-in; these results do not justify making
it the default or marketing it as a token-saving improvement.

This is a new comparison of two AST result presentations. It does not repeat or
pool the earlier [thirty-run text-versus-AST study](../2026-09-07-real-php/REPORT.md).

## Results

Ten fresh candidate processes per arm. `compact` uses `--evidence`; `guidance`
adds `--guidance`. Both receive the same integrated-test prompt, engine, neutral
format-preserving warning, resolver and checker. The treatment changes the whole
result bundle, including syntactic role counts and scoped continuation advice.
Skill files are not loaded, so this experiment measures neither the shortened
skill nor the warning change shared by both arms.

The primary descriptive metric was fixed before execution: distinct tool calls
after the first parseable successful rename result. It is an observation of
continuation, not an automatic classification of unnecessary work.

| Median per candidate | Compact | Guidance | Change in arm medians |
| --- | ---: | ---: | ---: |
| Later tool calls, primary metric | 3 | 3 | 0% |
| Whole-call tokens, including cache | 21,999 | 32,204 | +46.4% |
| All tool calls | 4 | 5.5 | +37.5% |
| Model rounds | 3 | 4 | +33.3% |
| Candidate seconds | 21.36 | 26.87 | +25.8% |
| Native list-price USD | 0.029060 | 0.034111 | +17.4% |
| Duplicate successful final-byte checks | 0 | 0 | — |

All 10/10 candidates in each arm completed normally, passed the exact-scope oracle,
passed independent behavior checks and obtained a successful candidate check on
final bytes. There were no missing attempts, timeouts, substitutions or reruns.
All twenty native accounting records are valid.

Full primary-metric distributions, in execution order within each arm:

| Arm | Later calls | Total later calls | Zero-later-call candidates | Duplicate final-byte checks |
| --- | --- | ---: | ---: | ---: |
| Compact | 0, 1, 3, 3, 0, 4, 3, 0, 4, 4 | 22 | 3/10 | 4 |
| Guidance | 0, 3, 4, 0, 0, 4, 3, 4, 3, 4 | 25 | 3/10 | 3 |

The ten prospective pairs are all retained in [the complete summary](real-summary.json).
For later calls, guidance is lower in two pairs, equal in five and higher in three;
the median paired difference is zero. The median paired differences for secondary
metrics are +5,976.5 tokens, +1.5 calls, +0.5 rounds, +2.36 seconds and +USD 0.006053.
These are medians of within-pair differences, distinct from ratios of arm medians.
The one fewer duplicate checker is not convincing evidence of an improvement in
this small sample, especially with unchanged primary medians and more later calls.

Tokens range from 12,080–109,954 for compact and 12,207–193,042 for guidance.
Three candidates per arm finish with one total tool call. Every observation,
including expensive runs, remains in [the run records](real-runs.json).

## What the trace audit found

AI reviewers inspected all **109 tool calls and twenty final answers** under the
prospective manual-audit rubric: [001–005](audit-001-005.md), [006–010](audit-006-010.md),
[011–015](audit-011-015.md) and [016–020](audit-016-020.md). These notes retain
tool-use IDs, one-based native line references, disputed wording and receipt checks.

The 47 later calls comprise 39 source Read calls, one grep readback and seven
repeated behavior checks. The source inspections revisit already reported edits;
the audits classify them as reconfirmation from their stated purpose and targets.
Guidance019's grep recovers the already reported caller omitted by its preceding
limited Read. None of these later calls repairs PHP, verifies changed bytes or
investigates a newly identified unresolved reference. This manual classification
is separate from the controller's automatic continuation count.

Compact004,012,017,020 and guidance006,011,015 repeat the successful checker without
intervening mutations. All 27 candidate receipts have before and after inventories
equal to final bytes and report **17 tests and 20 assertions**. The integrated
command already returned the named check as passed. Guidance does not reliably
prevent agents from repeating it or reading the three changed files again.

There are also 14 pre-rename calls in compact and 28 in guidance. Those occur before
the candidate receives the differing output. In particular, guidance015 reads all
six PHP files, including the 534-line validator and 227-line schema subset, before
renaming, then makes four reconfirmatory calls. These observed pre-output differences
cannot be attributed to the unseen guidance response. Consequently, the higher
whole-run medians are a descriptive result, not proof that extra output alone
caused the entire increase. Provider caching and model variation are uncontrolled.

No candidate needed a PHP repair, retried the rename, used a forbidden mutation
route, or read the controller, evaluator, home sessions or receipt store. Native
traces flag two errors: directory Read misuse in guidance006 and compact012.
Guidance011 additionally has a visible invalid grep hidden by a pipeline's exit
status. Guidance014 suppresses the diagnostic/status of a leading-dash grep
pattern; its exact subcommand outcome is unknown. Thus native error flags are not
an edit-failure count, and this trial does not demonstrate avoided broken patches.

Correct code and passing tests do not ensure accurate final explanations.
Compact005,009,012,020 explicitly attribute complete reference resolution or
coverage assurance to the tool despite `completeness: unknown`. Guidance011's
statement that AST ensured proper scope handling for all references also exceeds
the returned assurance. The audit preserves ambiguous purpose wording separately,
including guidance002 and compact004; omission of a caveat alone is not scored as
a false universal claim. The actual three-site fixture edits are correct. No final
has an explicit incorrect numeric declaration/reference, test, assertion or timing
claim. The project-check labels in guidance014 and guidance018 mix per-file status with a
named checker but do not explicitly claim three checker executions. The bundle has
not eliminated reporting overclaims and does not establish a reporting-accuracy gain.

## Task and verification scope

The unchanged fixture comes from public
[`netresearch/t3x-nr-llm` commit b505c936935b99baa3088ce62ad222d2ba61cee0](https://github.com/netresearch/t3x-nr-llm/commit/b505c936935b99baa3088ce62ad222d2ba61cee0).
It contains six PHP files, 1,150 original lines and 38,610 original PHP bytes, plus
the original GPL-2.0-or-later license, provenance and frozen project configuration.
The requested rename is `SchemaPropertyClassifier::classify` to `controlType`:
one declaration, one production call and one direct test call in three files.
Every other byte, including test assertions and inputs, must remain unchanged.
The TYPO3 UI caller `WaitingRunViewFactory` is excluded; there is no independent
same-name runtime control in this extraction. See [REAL_FIXTURE.md](../../REAL_FIXTURE.md).

The assigned command composes Phpactor discovery, AST validation and guarded
mutation, integrated PHPUnit verification and exact-byte readback evidence.
Syntactic reference counts include first-class callable references in the general
prototype; they do not count runtime executions or distinct callers. This fixture
contains two ordinary call sites. Neither exact replacements nor the original tests
prove resolver completeness. The unchanged baseline also passes all 17 tests, so
the independent byte oracle is necessary to establish that the rename happened.

Candidate checks and the controller's later hidden checks remain separate. Every
candidate obtained its own successful receipt on final bytes before the controller
ran the independent checker. An independent post-run pass does not replace candidate
verification. Receipt attribution assumes cooperative isolated local processes,
not hostile attestation. Stored outcomes and final hashes were audited; the original
temporary JUnit XML is not archived. No claim covers the full TYPO3 application,
dynamic dispatch, inheritance or arbitrary repositories.

## Token and time accounting

Totals over ten candidates per arm, not medians:

| Arm | Fresh input | Cache-created input | Cache-read input | Output | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compact | 12,392 | 90,596 | 249,731 | 17,252 | 369,971 |
| Guidance | 12,520 | 113,717 | 451,147 | 20,757 | 598,141 |

The campaign used **968,112 combined tokens** and **USD 0.6936708** in native
list-price estimates, not a subscription invoice. The combined metric counts
fresh input, cache creation, cache reads and output. Thinking tokens are a subset
of output and are not added again. Main-loop and whole-call accounting remain
separate. Fresh input is nearly equal; most of the difference in combined totals
is additional cache replay. This does not isolate its causal source.

Candidate wall time includes its integrated and repeated checks but excludes the
controller's later hidden checker. Median cumulative candidate-checker time is
93.887 ms for compact and 92.311 ms for guidance; repeated checks are included.
This is not total AST execution time. Total tool time remains unavailable, and
no orchestration duration is inferred by subtracting unrelated timing counters.

## Frozen inputs and offline reproduction

- [Prospective protocol](../../GUIDANCE_PROTOCOL.md), fixed before execution.
- Experiment: `real-php-guidance-v1`; ten balanced, shuffled pairs, seed `20260910`.
- Frozen source commit: `887d1ea4068ffcbae609c89d4573b349c1fb9495`.
- Configuration SHA-256: `9f0d71403616cc0127294a72f26055bd029e2f6103d49253cfeda3d913e44116`.
- Model: `claude-haiku-4-5-20251001`; Claude Code 2.1.263; no effort flag.
- PHP 8.5.10; Python 3.12.3; pinned Phpactor 2026.07.22.0 and PHPUnit 12.5.31.
- Twenty fresh isolated processes; no adaptive prompts, exclusions, replacements or reruns.

The [evidence archive](evidence.tar.gz) contains **620 hashed files**: native traces,
frozen prompts/configuration/wrappers, source helpers, resolver reports, final public
PHP snapshots, measurements, all 27 candidate receipts and the frozen source licenses.
PHAR binaries, vendor
trees, Git metadata and private home sessions are excluded. See the
[manifest](evidence-manifest.json) and [SHA256SUMS](SHA256SUMS). Archive SHA-256:
`07db3e8a219fae814781710fb8e477d3528c6de5b0019182e3b5def183e1dae0`.

From this result directory, extract the included verifier and run it offline:

```bash
tar -xzf evidence.tar.gz exporter/php-guidance-verify-export.py
python3 exporter/php-guidance-verify-export.py --export "$PWD"
```

It verifies every archive hash, 25 frozen source files, twenty native usage
ledgers, all twenty final-byte oracles and candidate-verification outcomes,
the later-call observations and the complete regenerated summary. Recorded hidden
PHPUnit outcomes are checked against final manifests; PHPUnit itself is not rerun
without the excluded pinned PHAR. Floating-point cost totals allow 1e-12 for
summation-order rounding. The measured campaign is unchanged; later publication
and skill prose changes are not represented as the measured source.

This is one selected task with ten repetitions per arm. It supports keeping the
compact response as the experimental baseline and rejecting an additional savings
claim for guidance here. It does not establish a universal penalty for guidance,
the effect of loading the revised skill, or the best result format for other tasks.
