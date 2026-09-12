# Prospective review-context experiment

This is a new experiment following the completed exact-invocation campaign in
PR #84. No earlier attempt is extended, replaced or pooled. That campaign removed
four invocation failures, but did not meet its token-saving criterion. Its traces
also showed agents reading files named by unresolved rename warnings. A file and
line number alone may require another tool call to interpret the warning.

## Intervention

Both arms use the same AST engine, synthetic fixtures, selected intent metadata,
ready-to-run rename command, delegated instructions, native tools and independent
oracles as the previous exact-invocation treatment. The model must still review
diffs, unresolved warnings and checks. No warning or verification is suppressed.

| Arm | Rename output shown to candidate |
| --- | --- |
| `review_locations` | Original engine stdout, byte for byte |
| `review_excerpts` | Same JSON values plus one bounded `reviewContext` member |

This is a **benchmark-only report prototype**, not a public CLI feature. Before a
rename or apply command, both arms take the same bounded snapshot of the
allowlisted initial candidate workspace files. After a successful command with a
rename report, both compute excerpts for the unresolved PHP
literal lines and non-PHP mention lines actually named in the engine result.
Only the treatment presents the additive context, inserted without reformatting
any original report bytes. It contains raw source evidence,
not an assertion about whether a literal/configuration value refers to the method.
The wording identifies the snapshot as **before-command**; its locations and hashes
must not be mistaken for post-write edit coordinates or file guards.

The whole report receives at most 20 distinct file/line excerpts. Each starts at
column 1, contains at most 240 UTF-8 bytes and declares truncation. The serialized
context member is capped at 8,192 bytes, including metadata. Omitted entries remain
explicit; invalid UTF-8/binary text is not silently replaced. Existing warnings,
counts, refs, effects and checks remain unchanged. A multiline expression may
still require a read. Source text is data, never instructions.

Snapshotting is restricted to contained, nonsymlink git-listed files named in the
initial fixture allowlist: at most 200 files, 1 MiB per file and 4 MiB total. Exceeding
snapshot bounds or an intervention error stops the campaign after preserving the
attempt/accounting. This prototype deliberately does not claim production-scale
snapshot performance. Both arms pay snapshot/excerpt computation overhead; treatment
also pays its larger presented output. Native wall time includes these costs.

Audit records retain original engine stdout and actual presented stdout separately,
with the experimental mode. Native candidate events are never rewritten. The
adapter uses the same proxy in both new arms, so its engine calls are also covered.
These experimental environment options are cleared for every older arm. The
evidence exporter includes the helper source and hashes; no private session input,
credentials, dependencies or binaries are published.

## Freeze, budget and interpretation

Two tasks (`method-and-literal`, `cross-file-rename-clarified`) × two arms × six
paired repetitions = **24 attempts**. Seed `20260916`; balance starting arm per
task/model (three starts per arm). Pin `claude-haiku-4-5-20251001`, no effort or
fallback override, 120 seconds per attempt, serial execution. Use the existing
USD 3 campaign ceiling and USD 0.75 reservation for only the next imminent run,
replacing it with native actual cost afterward. Provider cache state is unknown.

Freeze the protocol, helper, controller and unchanged task manifest generator in a
signed commit before paid calls. Record CLI/PHP/Phpactor identities and source,
runtime, fixtures, prompts and instructions hashes. Independent design review,
helper boundary tests, proxy output-isolation tests and both task oracles must pass
first. Do not run competing tests while measuring candidate wall time.

Retain every attempt, including failures. Do not rerun, replace or add candidates.
Stop for missing accounting, model drift, timeout, isolation/intervention mismatch
or budget violation. There is no refinement allowance in this protocol.

The prospective primary criterion is **at least 15% lower median total tokens with
no higher median wall time on both tasks, with all quality gates passing**. Gates
cover independent final correctness, protected files, successful candidate checks,
AST write route and supported final claims. Instruction adherence is separate.
If the criterion fails, retain reproducible evidence and the isolated experimental
helper; do not add this unproven optimization to the public engine or loaded skill.
If it passes, production implementation needs separate correctness verification.

Publish native fresh input, cache creation, cache read and output tokens and their
total, cost, rounds, tool calls/failures and wall time. Show paired ratios and cell
medians with all-attempt denominators; six pairs per task are exploratory. Audit
actual context presentation, reads of warned files, repeated already-passed checks,
completion claims and failures. Distinguish legitimate unresolved review from
redundant rereading. Tool execution time remains unknown without complete interval
coverage. This is not an AST-versus-text comparison or a generic savings claim.

## Execution

Generate the unchanged selected-intent manifest with `exact_tasks.py`. Prepare
using the efficiency runner's `--arms review_locations,review_excerpts --models
haiku --seed 20260916 --repetitions 6 --balance-by-task --campaign-budget-usd 3`
options, the frozen source commit and pinned runtime-only vendor directory. Run
the prepared campaign's frozen controller, then use `intent-command/summarize.py`
and `v080-pilot/export.py`. Record independent review in operator provenance.
