# Prospective evidence-bound final-response experiment

The shared-report campaign produced correct code in all 24 sessions but unsupported
final explanations in five. Its single-file A/A comparison also showed large
session variation, including different actions before any report was presented.
This experiment tests one short instruction about evidence and final-response
scope. It introduces no report transformation and reuses no earlier observation
as a control. Forty sessions on two new fixtures measure consistency on those
tasks, not breadth across PHP maintenance work.

## One intervention

Both arms receive the same delegated exact-command instructions plus the existing
[check-reuse paragraph](CHECK-REUSE.md). Task prompts, selected intents, complete
commands, fixtures, tools, engine and checks are identical within each pair. Both
receive original compact output, retaining inline diffs and all warnings; run-local
paths refer to each session's own workspace. There are no shared report defaults,
excerpts, snapshots, new tool restrictions or changes to PHP writes.

| Arm | Final-response instruction |
| --- | --- |
| `final_guidance_control` | No additional paragraph |
| `final_guidance_bounded` | The paragraph below |

> Keep the final response to the requested changes, observed check results and
> remaining requirements or warnings. Ground every name or value in a specific
> observed source or report entry. A passing check does not prove unchanged file
> bytes or complete correctness. Use existing evidence; do not reread files merely
> to decorate the final response with extra details. Preserve necessary investigation
> and disclose unresolved limitations.

All added instruction tokens count toward treatment cost. This is a generic scope
and evidence instruction, without fixture-specific answers. It does not replace
the candidate's explanation or exempt it from investigation, warning review or
required verification. This compares short AST-agent instructions; it does not
compare AST with text editing or establish an improvement over the installed skill.

## Freeze, inputs and execution

Use the new `ledger-method-rename` and `transport-contract-rename` tasks: one
same-file rename and one project rename, each with a deterministic behavioral
oracle and protected files. Freeze their requirements and complete final-response
rubric before paid calls. Repeated sessions use identical task instances; these
are two tasks, not forty independent real-world maintenance problems.

Run two tasks × two arms × ten paired repetitions: **40 new attempts**. Use seed
`20260920`, shuffle task/repetition blocks and keep the two sessions of each pair
adjacent, with five pairs per task starting with each arm. The seed fixes scheduling,
not model sampling. Task/fixture bytes match within pairs; appended system prompts
differ only by the paragraph above. Keep run IDs out of the appended instructions
and task prompts. Do not reuse a session or conversation history between candidates.

Pin `claude-haiku-4-5-20251001`, no effort or fallback override, Claude Code 2.1.268
through its explicit versioned executable, PHP 8.5.10 and Phpactor 2026.07.22.0 with
the same runtime dependencies as the prior campaign. Record native initialization
and validate the model, tools and absence of plugins, skills and MCP services.
Freeze and push signed source, this protocol, both instruction texts, fixtures,
controller and comparator before paid calls. Record hashes for all paired inputs,
CLI, resolver and runtime. Independent review, offline comparator/isolation tests
and actual task/arm preflights must pass first; preflights are not observations.

Use fresh private workspaces, serial runs, a 120-second timeout, a **USD 3** campaign
ceiling and a **USD 0.75** reservation for only the next imminent attempt. Replace
that reservation with the actual native estimated cost after accounting. Retain
all attempts, including failures. Do not rerun, replace, refine, drop or add paid
candidates under this protocol. Stop after preserving evidence and accounting on
missing cost, timeout, model drift, isolation error or budget violation. A partial
campaign cannot pass the criterion. Run no competing local tests during timing.

## Variation and uncontrolled context

This study has no simultaneous A/A arm. Ten pairs and a stronger consistency gate
address the earlier variation; they do not explain or eliminate it. Publish all pair
ratios, ranges and run order, including first-versus-second position within a pair.
Never subtract the previous A/A difference, pool previous campaigns or select only
successful sessions to calculate efficiency.

Fresh sessions do not establish a cold provider cache. Retain each run's initial
fresh/cache-creation/cache-read counts, all token categories and native retries.
Identify the first campaign session and describe observed cache differences without
excluding it or claiming the cache was reset. Report pre-write actions as well as
later reads/checks; a final-response instruction can affect the whole session.

The runner appends to the native default system prompt; it does not retain every
hidden provider input. Native session IDs and working directories differ. The
operator environment is shared rather than independently randomized. Freeze known
runtime settings and avoid arm-dependent environment changes, but do not claim
identical complete model contexts or controlled provider routing/cache state. Serial
service drift and dependence between observations remain possible. None of these
limitations is removed by a fixed schedule seed or an additional decimal place.

## Preregistered efficiency criterion

**Each task separately** must meet all four conditions:

- Median paired treatment/control total-token ratio **≤0.85**.
- Median paired wall-time ratio **≤1.0**.
- Median paired native tool-call ratio **≤1.0**.
- Treatment uses strictly fewer total tokens in **at least nine of ten pairs**.

Both tasks must pass; do not replace a failed task with a pooled result. Use exact
rational arithmetic for integer token/count ratios and exact serialized decimal
wall-time values. Ties are nonwins. Missing pairs or invalid measurements cannot
become favorable ratios; retain their evidence and fail the complete-study gate.
Cell medians, costs and final-word counts are descriptive, not substitutes for the
paired criterion. Total tokens include fresh input, cache creation, cache reads and
output; thinking already included in output is not counted again.

For transparency, report the binomial win-count tail
`sum(comb(10, k), k=wins..10) / 2**10`, and its two-comparison Bonferroni reference
`min(1, 2 * tail)`. At nine wins these are `11/1024` and `22/1024`. Ties remain
nonwins instead of being excluded as in a conventional sign test. These are
descriptive sensitivity references under a hypothetical independent fair-win model,
not confirmatory p-values: independence, exchangeability and absence of serial
provider effects have not been established. The nine-win threshold is an operational
consistency requirement, not a claim of statistical significance or a causal effect.

## Correctness, supported claims and completeness

All **40** final-code, protected-file, actual candidate-check and AST-route gates
must pass. A passing external oracle does not substitute for the candidate's check
execution or validate its description of that check. Report these gates separately.

All **20 treatment finals** must be both supported and complete. Apply the same
rubric to control finals and publish their failures; a control explanation failure
does not itself veto a treatment improvement. Annotate individual statements against
specific trace/source evidence before comparing arm totals. Record disputed wording
and the reason for its classification; do not silently change the rubric after runs.

A complete final identifies the requested change and its outcome, describes actual
verification with the appropriate scope, and discloses material unresolved warnings
or remaining requirements. A bare “done” cannot pass. Exact quotations, invented
symbols, descriptions of checker purpose and assertions of preserved bytes all need
support if included. Passing a check alone proves neither byte preservation nor
universal semantic correctness. Necessary caveats cannot disappear merely to make
the explanation shorter. Record intermediate misstatements separately from the
final-response gate; distinguish false claims from an honestly disclosed limitation.

Quality and efficiency remain separate: shorter explanations do not compensate for
missing required content, and twenty passing treatment finals do not prove a zero
future error rate. Publish both arms' truth and completeness counts. Final-output
words, source reads, repeated checks, pre-write calls and failed calls describe the
mechanism; no reduction in these counts is a separate success prerequisite.

## Publication and reproduction

Publish all attempts' token categories, native estimated cost, rounds, tool calls,
failures and wall time; estimates are not invoices. Show all twenty pairs, both task
decisions and complete-session descriptive medians. Preserve original/native reports,
final explanations, source snapshots, protected-file hashes and the independent
claim/completeness audit. Do not infer complete tool-execution time when intervals
are unavailable, or attribute all output-token differences to visible final prose.

Export only allowlisted synthetic inputs, raw evidence and frozen controller/helper
sources with checksums. Exclude private sessions, credentials, binaries and runtime
dependencies. Reproduction must use the frozen source, task generator, runner and
comparator; any later hardening is explicitly separate from measured behavior.

Even a complete pass supports only a further scoped confirmation of this instruction
on these tasks. It does not authorize default production adoption, establish an
AST-versus-text saving, or show that report factoring works. Earlier A/A and quality
failures remain published and are not overwritten by this experiment.
