# Compact PHP editing: native agent efficiency experiments

Measured on 6 September 2026; 120 completed attempts, including all failures and timeouts.

The compact interface demonstrates useful, task-dependent savings. It does not establish
that AST editing is generally cheaper or more reliable than contextual editing. Batching
and a smaller instruction/result interface help when a supported operation expresses the
requested change directly. Conservative refusals followed by schema guessing can outweigh
those savings, especially for the smaller model.

The experimental adapter remains benchmark tooling. The installed skill and production
CLI do not acquire this interface from this report. The original negative twelve-run
pilot is retained separately and is not pooled with these observations.

## Design and interpretation

The study contains 120 prospective candidates: 48 on two original seed tasks, 48 on
two public TYPO3 maintenance tasks, and a separate 24-run directed-read comparison. Each
phase uses three repetitions per task/model/arm. Trials are serial, with a seeded order
that rotates the arms. All attempts, failures and deviations remain in their assigned
arms; passing the final oracle does not establish adherence to the AST workflow.

| Arm | Instructions and write interface | Read interface |
| --- | --- | --- |
| Contextual patch | Competent ordinary Claude Code editing | Ordinary source reads |
| Full skill | Unchanged 566-word skill; normal CLI and reports | Ordinary source reads |
| Compact full | 118-word adapter instructions, stdin requests, compact reports and mandatory snapshot revisions | Complete PHP source |
| Compact focused | Same adapter and instructions, changing the read-mode word | Selected complete PHP declaration plus comments, context and outline; full fallback |

The compact/full-skill comparison changes a bundle of interface features. It does not
isolate the effect of word count, report size, stdin use or revisions individually.
Both baseline and treatment may batch shell work. The observed Claude native Edit
workflow is a baseline, not a lower bound on what every patch-based harness could do.

Models are `claude-sonnet-4-6` at medium effort and `claude-haiku-4-5-20251001` without an
effort flag. Comparisons are within each model. Native init and response IDs verify the
pinned models and empty global settings, skills, plugins and MCP connections. Every arm
has the same Bash/Read/Edit/Write tools. There is no OS sandbox or enforced AST-only hook;
observed text-write bypasses are outcomes, not removed observations.

The phase-one/two source is `25bb90a82dbf4425d2d5a712079c9a507a82c82f`. Phase three is
prepared from `fd4ce4018055828530c5f47bc8e25b723b4d8109`; all 1,810 runtime file hashes and
modes, including the engine, dependencies, skill and adapter, match phase two. The
separately recorded controller changes handle native usage accounting and immutable
planning reservations; they do not change candidate prompts or engine behavior.

## Where the compact interface helped, and where it did not

All numbers below are medians of three attempts. Tokens mean fresh input plus cache-read
input plus cache-created input plus output, using native final counters. Percent changes
compare group medians; they are not confidence intervals or population estimates.

| Task | Model | Contextual tokens | Compact-full tokens | Change | Tool calls | Candidate wall seconds |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Add a constant to two seed classes | Sonnet | 23,715 | 14,449 | -39.1% | 6 → 2 | 14.79 → 11.63 |
| Add a constant to two seed classes | Haiku | 26,665 | 20,794 | -22.0% | 6 → 3 | 14.39 → 13.79 |
| Small local/capture rename | Sonnet | 12,988 | 14,033 | +8.0% | 2 → 2 | 8.93 → 8.83 |
| Small local/capture rename | Haiku | 20,244 | 33,735 | +66.6% | 3 → 5 | 11.69 → 18.50 |
| Delete the obsolete TYPO3 helper | Sonnet | 42,310 | 26,032 | -38.5% | 4 → 2 | 16.84 → 12.39 |
| Delete the obsolete TYPO3 helper | Haiku | 64,572 | 109,327 | +69.3% | 6 → 8 | 19.55 → 29.58 |

Every compact-full result in those six cells passes the task oracle and uses guarded
AST writes. This table includes both gains and regressions; [TABLES.md](TABLES.md) also
contains the unchanged full-skill arm, focused arms and the problematic Passkeys task.

For the Passkeys local rename, the convenience operation rejects `$GLOBALS` in the
selected method. A valid general AST replacement exists, but candidates must find its
schema and preserve the complete requested scope. The Sonnet compact-full arm finishes
only one of three attempts; two hit the 120-second deadline with unchanged source.
Its median observed wall time is 120.26 seconds versus 14.69 for contextual edits. The
complete token/cost median is unknown because neither timeout has terminal usage.

Correct final PHP can hide substantial recovery cost. Several compact candidates bypass
AST writes through native Edit. Another uses Git to restore a bad intermediate AST edit.
These retain their assigned-arm token/time/outcome measurements but fail the guarded AST
write-workflow measure. A native tool error is also not necessarily an editing mistake:
a grep that correctly finds no obsolete method can return exit 1.

## Does selecting a method reduce model input?

Phase two leaves selector choice to the agent. A focused read of a class returns the
whole class, so the mode name alone does not test a small method view. The separately
predeclared phase three gives both compact arms an identical initial method selector,
without suggesting an operation or recovery strategy. Source bytes, expected changes,
models, limits, adapter and engine remain unchanged.

| Directed task | Model | Full-source tokens | Focused tokens | Change | Tool calls | Guarded AST write successes, full/focused |
| --- | --- | ---: | ---: | --- | --- | --- |
| Remove obsolete helper | Sonnet | 26,081 | 16,892 | -35.2% | 2 → 2 | 3/3 / 3/3 |
| Remove obsolete helper | Haiku | 99,359 | 63,866 | -35.7% | 7 → 7 | 3/3 / 2/3 |
| Local rename with `$GLOBALS` | Sonnet | unknown | 53,798 | unknown | 23 → 7 | 1/3 / 2/3 |
| Local rename with `$GLOBALS` | Haiku | 116,088 | 273,604 | +135.7% | 9 → 18 | 0/3 / 1/3 |

This is a separate comparison with changed instructions and timing. It does not replace
phase-two observations or measure free autonomous discovery of the correct selector.
Follow-up source reads, trial-and-error operations and write-route violations remain in
the totals. A narrower initial view can save input while the rest of the task remains
inefficient or noncompliant.

## A whole AST is not automatically a compact model representation

The local size study used PHP 8.5.10 and PHP-Parser 5.8.0. It made no model calls.

| Preserved sample | PHP source bytes | Default AST dump bytes | Compact AST JSON bytes | Selected method bytes |
| --- | ---: | ---: | ---: | ---: |
| Seed Cache class | 330 | 4,166 | 1,680 | 174 |
| RenameVariable implementation | 6,848 | 131,754 | 34,761 | 740 |

Default dumps are 12.6–19.2 times as large in these two examples; even the minified tree
without attributes is about 5.1 times as large. These are bytes, **not LLM token counts**.
No candidate arm used a whole AST dump. The study therefore does not establish a measured
model-token disadvantage for every possible AST encoding.

The implemented experiment uses the parser to select relevant PHP source. The full
selected body and comments remain available, with namespace/import/class context and an
explicitly incomplete outline. The smaller representation comes from selecting information;
it is not a lossless compression of the entire program. A serialized AST also does not
supply project-wide type information, runtime values or complete dynamic dispatch semantics.

## What the old sessions established

A separate read-only analysis of 1,419 local Claude JSONL files found 3,042 paired native
PHP Edit requests and 18 reported errors, or 0.59%: 13 missing search strings, one ambiguous
match, one stale-source rejection, one no-op and two permission/hook rejections. This is
an archive observation on different recorded models and workloads, not the failure
probability of Sonnet or Haiku in this experiment.

The direct Edit rate excludes shell writes, semantic mistakes and failures discovered
by later checks. A reviewed historical shell extraction produced an unterminated PHP
comment and needed four subsequent calls before successful lint, spanning 53.996 seconds.
Other episodes involved ambiguous replacements and stale reads. The elapsed intervals are
correlations in a session, not isolated causal repair overhead or complete task acceptance.

The two public tasks preserve source provenance and GPL-2.0-or-later notices. Passkeys
uses exact public source at commit `51b41bfaa4e09778ae16c61c865bee2837cf57d5`; its rename is
prospectively designed, not replayed from a failed historical rename. The helper task
reconstructs an intermediate state from public LLM-extension commit
`c304598ca9c0f734f1521d9b7dd71341abff5b86` and its parent. It was inspired by a historical
delete failure; it does not recreate that session byte-for-byte or force its failed
search text on the baseline. Private historical transcripts and indexes are not exported.

## Reliability changes made during the investigation

The investigation also found a production semantic defect: an imported alias of `compact`
could evade the variable-rename guard, leaving its string lookup unchanged while renaming
the local variable. Callback forwarding exposed the same class of problem. [PR #31](https://github.com/netresearch/php-ast-edit-skill/pull/31)
resolves function imports on a cloned analysis tree and conservatively rejects affected
symbol-table/callback scopes. It preserves printable source spelling and the existing
`$GLOBALS` guard. Twenty-four regression assertions failed before the fix; 115 rename
checks and the complete suite passed afterward, including the supported PHP CI matrix.
The fix is merged; the experimental runtime remained frozen for comparability.

The compact adapter technically requires a revision obtained from an earlier read and
rejects stale or wrong-file revisions. The full skill asks for hashes in prose, and
candidates often omit them. This improves enforcement at the adapter entrypoint; it does
not prevent a candidate with ordinary Bash/Edit tools from taking another write route.
Syntax, output correctness, instruction adherence and access isolation are distinct claims.

## Accounting, review and limits

All 120 scheduled attempts and their independent AI reviews are retained. The task
oracles pass 114/120 attempts: phase one 46/48, phase two 46/48, and phase three 22/24.
These counts mix deliberately different task/arm designs and are not a population success
rate. The public summary separates guarded AST writes from those final outcomes.
The two phase-one failures left request JSON files outside the allowed task scope;
their PHP changes were correct. The other four failures were timeouts without the
requested final source change.

Final native token accounting is known for 116/120 attempts, totaling 7,830,443 tokens
in that known subset. Native list-price cost is known for 116/120 attempts, with a known
subtotal of USD 6.0526787. The remaining 4 attempts have unknown terminal cost. Complete
combined token and cost totals are therefore unknown; the known subtotal does not
substitute for them. [summary.json](summary.json) preserves fresh/cache/output counters,
metric-specific availability, group medians, paired comparisons and every outcome.

The original timeout measurements and traces remain unchanged. Full deadline time,
observed tool calls and failed outcomes are included; missing token/cost totals stay null.
Each reviewed timeout has a separate USD 0.75 planning reservation. It is neither an
observed cost nor a proven billing ceiling. The initial operator-selected aggregate
planning allowance of USD 8 was prospectively increased to USD 12 before phase three;
original phase-one/two configurations were not changed. Native USD estimates under
subscription authentication are not invoices.

Some native retries expose less per-response input than the final native aggregate.
The accounting amendment accepts this only with the recorded synthetic empty-response
retry and independently agreeing terminal counters. Original/recovered measurements are
separate, and visible response IDs remain a lower bound in those cases. Native `num_turns`
and visible assistant-response counts are retained separately. Early streaming output
snapshots are not added together; thinking detail is not added to output a second time.

Candidate wall time includes CLI startup and the complete attempt. It excludes tool
installation, experiment/adapter development, fixture preparation, external grading and
review. Runs used a shared WSL/Linux host with light review/check work and documented
pauses, not a dedicated isolated timing machine. Full suites/builds were avoided during
candidate execution; a short publication formatting/check command also ran on the host.
Provider load and cache state were uncontrolled. Wall-time differences need replication.
No complete native per-tool timing data was exposed, so tool-execution/orchestration
milliseconds are not inferred from API duration.

Every final diff and native tool trace receives independent AI review. Human acceptance
remains pending. Oracles cover exact requested source-token changes, comments, file scope
and PHP lint; seed tasks and the Passkeys fallback include bounded runtime assertions.
The helper task is not a full TYPO3 integration test. Candidates can leave their assigned
workspace: repeated external `/tmp` payload names caused an observed write precondition
failure in one run. There was no observed answer-key read or external fetch, but this
local evaluator does not enforce an adversarial filesystem boundary.

Three repetitions per cell and four maintenance tasks cannot establish organization-wide
ROI, a general reliability advantage, cold onboarding cost, or performance of every PHP
refactoring. The results support improving operation/recovery guidance, mandatory snapshot
handling and useful source selection before adding larger unconditional tool descriptions.
The complete [numeric tables](TABLES.md), [machine-readable summary](summary.json), and
[reproduction/evidence guide](README.md) keep the supporting and negative observations together.
