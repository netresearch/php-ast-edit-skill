# Does better rename output reduce agent work?

**In this 24-run synthetic Haiku pilot, the evidence response helped at 50 files,
while evidence alone made the 10-file median worse.** Combining evidence with
scoped verification guidance reduced both medians, but one very cheap run omitted
an explicitly required independent semantic assessment. This is evidence for a
useful optimization at larger scopes, not permission to stop checking semantics.

All 24 final PHP results passed file-scope, exact-byte, structure and runtime
oracles. No candidates were repeated, replaced, omitted or timed out. The study
used **1,308,108 whole-call tokens** and **USD 0.7864029 native list-price estimates**;
these estimates are not subscription invoices.

## Design and provenance

The [prospective protocol](../../POSTCHECK_PROTOCOL.md) crosses two factors:
legacy versus `--evidence` output, and current versus scoped verification wording.
There are three repetitions per cell at 10 and 50 PHP files. Each size/repetition
block contains all four arms; the recorded schedule rotates order. This is a new
within-study comparison; the [previous 27 runs](../2026-09-07-haiku/REPORT.md) are
motivation, not contemporaneous controls.

- Frozen source: `60467ecdc093f65a8206c183e921c1fc5088e178`.
- Model: `claude-haiku-4-5-20251001`; Claude Code `2.1.263`; no effort flag.
- Linux/WSL, PHP 8.5.10, fresh temporary Git workspace/process and isolated cold
  resolver index for every candidate. Exact dependency hashes are in `config.json`.
- Phpactor `2026.07.22.0`, SHA-256
  `8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d`.
- Bash/Read/Edit/Write, empty skills/plugins/MCP/settings, native safe mode and no
  persisted sessions. Context isolation is not an OS sandbox.
- The same task renames `Example\Provider::fetch` to `load`. Other::fetch, its
  callers and comments must stay unchanged. Receiver variable names alternate.
  One file contains both declarations; the other 9 or 49 files contain callers.
- The evidence treatment bundles grouped warnings, request/edit totals and an
  actual-disk byte comparison with hashes of validated name replacements. It does
  not isolate warning deduplication from the additional evidence.
- The scoped instruction trusts only reported facts, discourages duplicate checks,
  and still explicitly requires independent reference/behavior assessment. It does
  not expose the hidden oracle or prescribe a one-call solution.

All candidate prompts, wrappers, source bytes, fixtures, schedules and native traces
are retained. Preparation happened before any candidate execution. The frozen
controller ran all 24 candidates unchanged; no accounting recovery was needed.

## Cell medians

Tokens count fresh input, cache reads, cache creation and output across the whole
call. Rounds count visible main-loop model responses; auxiliary rounds are not
observed. Post calls are distinct later tool invocations after a parseable successful
rename result, **not a count of unnecessary checks**. All cells have three attempts.

| Files | Result | Guidance | Tokens | Calls | Rounds | Seconds | Post calls | USD |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | legacy | current | 50,886 | 8 | 8 | 23.03 | 4 | 0.029297 |
| 10 | evidence | current | 57,518 | 8 | 9 | 28.95 | 4 | 0.032782 |
| 10 | legacy | scoped | 43,351 | 7 | 6 | 23.98 | 6 | 0.030870 |
| 10 | evidence | scoped | 25,494 | 6 | 4 | 19.17 | 4 | 0.025303 |
| 50 | legacy | current | 92,248 | 10 | 11 | 30.85 | 5 | 0.043568 |
| 50 | evidence | current | 39,561 | 8 | 6 | 25.14 | 3 | 0.030102 |
| 50 | legacy | scoped | 49,580 | 7 | 5 | 23.33 | 5 | 0.036562 |
| 50 | evidence | scoped | 31,834 | 6 | 5 | 21.82 | 4 | 0.026471 |

Relative to legacy/current at the same size:

| Files | Treatment | Tokens | Calls | Rounds | Wall time | List-price estimate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 10 | Evidence alone | +13.0% | 0% | +12.5% | +25.7% | +11.9% |
| 10 | Guidance alone | -14.8% | -12.5% | -25.0% | +4.1% | +5.4% |
| 10 | Evidence + guidance | -49.9% | -25.0% | -50.0% | -16.8% | -13.6% |
| 50 | Evidence alone | -57.1% | -20.0% | -45.5% | -18.5% | -30.9% |
| 50 | Guidance alone | -46.3% | -30.0% | -54.5% | -24.4% | -16.1% |
| 50 | Evidence + guidance | -65.5% | -40.0% | -54.5% | -29.3% | -39.2% |

These percentages compare cell medians, not pooled averages or paired-effect
estimates. [summary.json](summary.json) also publishes within-block paired deltas,
individual observations and all denominators. Token totals and cost change
unequally because token categories have different prices.

The 50-file evidence/current token total was lower than its legacy/current pair in
all three blocks. At 10 files it was higher in two of three. The result therefore
does not justify making a general token-saving claim for evidence output alone.

## Correct code does not imply sound verification or reporting

Two separate agent reviewers inspected runs001–016; the operator agent inspected
runs017–024. The review used complete native calls/results and final responses,
not just cost counters. There was no independent replication or human acceptance.

- **24/24 code oracles passed**, including preserving unrelated methods and runtime
  dispatch. Each candidate invoked its assigned rename exactly once. No source-edit
  repair, direct alternative write, controller/state/answer read or candidate-directed
  external write was observed. The tool's authorized external state writes are separate.
- **None of the candidates ran a behavior test.** All tool results said project checks
  were `not_run`; the runtime oracle ran afterward and was not candidate-visible.
  Most candidates inspected receiver bindings and method bodies in source. Five
  displayed all caller bodies (007, 009, 010, 014, 015); most others used samples.
- There were **186 total tool calls and 112 post-rename calls**. Source inspection can
  supply semantic information that exact byte matching cannot. These 112 calls must
  not all be marketed as avoidable orchestration.
- **run013 (evidence/scoped)** used only one tool call and 11,617 tokens. It did no
  source inspection or independent semantic check, despite the scoped instruction.
  Its correct code and low cost are retained in the medians; this is not an
  unqualified efficiency success. Runs007 and016 instead repeated already-passed
  lint despite instructions to avoid doing so.
- **Verification repair loops remain:** leading-arrow grep patterns fail unless
  protected with `--` or an equivalent option. Runs007–009 and012 contain failed or
  uninformative searches followed by more checks. In run009, `|| echo` even printed
  a success message after an invalid grep. Native counters report nine failed tool
  calls, but successful pipelines hide additional failed subprocesses. These were
  failed checks, not failed rename transactions.
- **Final prose sometimes invents facts:** runs004, 006, 011 and013 convert PHP
  version `8.5` into milliseconds or seconds. Runs002, 005 and008 incorrectly count
  50 caller files instead of 49. Run008 claims every Other call uses `$second`, even
  though its own Caller25 read shows Other bound to `$first`.
- Several summaries attribute semantic targeting guarantees to exact byte matching.
  That check only establishes fidelity to the resolved, AST-validated ranges. It
  cannot establish that the resolver selected the right bindings or found every
  reference. Broad statements can match the later oracle in this fixture while
  expressing stronger assurance than the tool or sampled inspection establishes.
  Omitting a warning alone was not scored as a factual failure.

The practical improvement is to return compact, precise evidence and make the
remaining semantic obligations explicit. The experiment does not demonstrate that
prompt wording reliably enforces those obligations. Savings should be assessed
alongside code correctness, actual verification coverage and accuracy of final claims.

## Accounting and limits

Whole-call totals are 25,912 fresh input, 1,022,699 cache-read input, 213,088
cache-creation input and 46,409 output tokens. Main-loop totals are 1,283,291 tokens;
the remaining 24,817 belong to the broader whole-call accounting scope. Their
auxiliary cause and number of extra rounds are not inferred. Thinking counters,
where exposed, are not added to output a second time.

Per-tool execution duration is not exposed in all 24 traces and remains `null`.
Wall time includes model work, resolver indexing and candidate checks. No subtraction
of API duration is used to fabricate orchestration time. Provider cache warmth is
unobserved; all native category counters and recorded order are retained.

This is three repetitions on repeated, self-contained synthetic PHP. It says
nothing quantitative about large Composer projects, inheritance, dynamic calls,
framework references, TYPO3 configuration, full-AST model input or other models.
The nine/49 alternating caller fixtures are useful controls, not a representative
production corpus. There is no confidence interval or universal percentage claim.

## Subsequent engineering fixes and reproduction

After freezing the study, the working prototype changed lint's ambiguous `runtime`
field to `php_version` **inside evidence groups**. This addresses an observed naming
problem; its effect on LLM behavior was not measured here. The default/engine report
schema remains unchanged. Later trace-parser hardening and decomposition also leave
this frozen campaign untouched. Published results come from the archived controller.

[The raw evidence archive](evidence.tar.gz) contains 1,163 files: frozen controller
and prototype sources, accounting code, input/configuration manifests, prompts,
wrappers, native JSONL, process measurements, diffs, final sources, resolver traces,
plans, engine reports and readback inventories. It contains only these synthetic
fixtures; no home sessions, private extension sources, PHAR or dependency binaries.
The complete original source/dependency inventory and pinned PHAR digest remain in
`config.json`; rebuild dependencies separately for new candidate runs.

- [runs.json](runs.json): all 24 records, counters, post-call observations and trace hashes.
- [summary.json](summary.json): all cell distributions and paired effects.
- [evidence-manifest.json](evidence-manifest.json): SHA-256 for every archived member.
- [SHA256SUMS](SHA256SUMS): hashes of these public files, including this report.

For an offline check, extract the archive into a fresh directory, verify its members
against the manifest, and import its `source/benchmarks/symbol-intent/postcheck_pilot.py`.
`summarize_records(runs)` reproduces the summary after adding the SHA-256 of archived
`config.json`. The archived `accounting.summarize` and `post_calls` can independently
recompute each record from native traces; the original command prefix is
`/tmp/php-postcheck-pilot-20260907/runNNN/rename-tool`. No model invocation is needed.
