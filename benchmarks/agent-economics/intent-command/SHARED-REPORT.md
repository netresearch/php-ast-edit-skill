# Prospective shared-file metadata experiment

Repeated per-file metadata makes multi-file compact reports larger without adding
different facts. This campaign tests one lossless presentation change: represent
identical metadata once with an explicit scope covering every reported file. The
hypothesis is lower report and subsequent context-token cost, not necessarily fewer
source reads. Unlike the earlier agent report, this intervention retains every
inline diff. Earlier campaigns motivate this experiment but are not pooled or used
as contemporaneous controls.

## One intervention

Both arms receive identical short delegated exact-command instructions, task prompts,
selected intents, commands, fixtures, native tools, AST engine and verification.
There is no added check-reuse guidance, snapshot, excerpt, write change or new
restriction on candidate calls. Both arms compute the same report projection to
include its overhead; only treatment presents the projected output.

| Arm | Candidate-visible output |
| --- | --- |
| `shared_report_control` | Original engine stdout bytes |
| `shared_report_factored` | Shared metadata for eligible multi-file reports; otherwise original bytes |

The benchmark-only `shared_report.py` may factor a field only when it exists in
**every** entry of a report containing at least two files and its values are
structurally identical with strict types. Booleans and numbers are not interchangeable;
array order matters. The complete whitelist is `changed`, `dryRun`, `printer`,
`warnings`, `warning`, `parsed`, `valid`, `validation` and `checkIds`.

Factored fields appear once in root `fileDefaults`. Root `fileDefaultsMeaning`
explains that these defaults apply to **every file**; an explicit per-file field
would override a default. The generator keeps defaults and per-file keys disjoint.
This is shared representation of separate file facts: it neither combines check
executions nor turns file validation into a global or semantic verdict.

Every original key and value, including compatibility aliases, must be recoverable
by expanding defaults into each file. Paths, modes, hashes, diffs, code, effects and
counts remain per-file. Unknown fields and all distinct warnings, validation states,
check references, unresolved locations and instructions remain intact. Diff and
other string values preserve their bytes. Whole-report byte identity is not claimed
for treatment: it retains the same four-space pretty JSON and unescaped UTF-8 style,
with no extra minification. Control always forwards the original bytes.

An existing `fileDefaults` or `fileDefaultsMeaning` is a reserved-field conflict and
stops the experiment. Malformed input or projection/inheritance failure is also an
experiment error; preserve original stdout and evidence, account for the attempt,
and stop before another candidate. Failed engine commands retain original stdout,
stderr and exit behavior. Legitimate outputs needing no projection, including
single-file reports, remain byte-identical in both arms.

## Freeze and offline prerequisite

Before paid calls, freeze and push signed source, this protocol, instructions,
controller, projection helper, comparator and unchanged task generator. Record their
hashes plus native CLI, resolver, manifest and every paired input identity. Independent
design/code review, preparation/isolation tests, actual task oracles and comparator
regressions must pass.

Offline preflights must demonstrate at least **25% fewer serialized UTF-8 report
bytes** on the cross-file task and exact reconstruction of all original JSON facts.
This is a prerequisite for spending on the campaign, not a token-saving claim.
Check type mismatches, mixed file values, missing fields, unknown additions, reserved
names, disjoint inheritance, warning aliases, failed/skipped checks, dry runs,
deletions, Unicode and complete diff preservation. Single-file output must be
byte-identical. Offline replay of prior reports is development evidence only;
it cannot become a new candidate observation.

## Frozen schedule and budget

Use the existing `method-and-literal` and `cross-file-rename-clarified` tasks, two
arms and six paired repetitions: **24 new attempts**. Seed `20260919`, with three
pairs per task starting with each arm. Each pair has identical fixture and task/
system prompt bytes. Operator-supplied targets and commands exclude autonomous
discovery cost.

Pin `claude-haiku-4-5-20251001`, no effort or fallback override, Claude Code 2.1.268
through its versioned executable, PHP 8.5.10 and Phpactor 2026.07.22.0 with the same
runtime dependencies as the preceding campaign. Use fresh private workspaces,
serial runs, 120 seconds per attempt, a USD 3 ceiling and a USD 0.75 reservation for
only the next imminent run. Replace that reservation with actual native estimated
cost. Provider cache state is unknown. Run no competing local tests during timing.

Retain every attempt, including failures. Do not rerun, replace, refine, drop or add
paid candidates under this protocol. Stop after retaining evidence and accounting
on missing cost, timeout, model drift, isolation/intervention error or budget
violation. Unpaid preflight activity remains separate.

## Preregistered decision

The **cross-file task alone** is the primary efficacy comparison. It must achieve
median paired treatment/control ratios of total tokens **≤0.85**, wall time **≤1.0**
and tool calls **≤1.0**, with at least **four of six** token-saving pairs. Compute
thresholds with exact rational token/count and serialized decimal wall-time ratios.
Cell medians remain descriptive and cannot replace these paired statistics.

The small task has one reported file and receives no presentation intervention.
Treat it as a descriptive A/A comparison of session variability, not an efficacy
gate or a basis for subtracting noise from the primary effect. Its numeric verdict
is `null`, not pass. Do not pool tasks to obtain a favorable result.

All **24** final-code, protected-file, actual candidate-check, AST-route and
supported-final-claim gates must pass. The independent oracle remains separate from
the candidate's actual verification. Audit the original and delivered report and
reconstruct every fact; a smaller response does not excuse omitted warnings or an
unsupported completion claim. Keep instruction adherence separate from correctness.

Read and repeated-check counts describe behavior; their reduction is not a required
mechanism gate. This experiment tests report representation and context cost, not
the specific check-reuse hypothesis. Six primary pairs remain exploratory even if
all gates pass. No default production adoption follows from this campaign; it would
require separate confirmation and review of the public interface and compatibility.

## Reporting and reproduction

Publish all attempts' fresh input, cache creation, cache reads, output, total tokens,
native cost, rounds, tool calls/failures and wall time; thinking is included in output.
Show primary paired ratios, all cell medians and the descriptive A/A results. Record
original/projected UTF-8 bytes, factored field names, all raw/presented outputs,
source reads, repeated checks and final claims. Do not infer equal savings in every
token category or complete tool-execution time when interval coverage is unavailable.
Native cost is an estimate, not an invoice.

Generate the unchanged manifest with `exact_tasks.py`. Prepare the frozen efficiency
runner with `--arms shared_report_control,shared_report_factored --models haiku
--seed 20260919 --repetitions 6 --balance-by-task --campaign-budget-usd 3`, frozen
source, pinned dependencies and the explicit Claude executable. Execute the frozen
controller, summarize all attempts with `summarize.py`, and run the frozen
`shared_compare.py`. Manual quality review remains a separate gate.

Export only allowlisted synthetic inputs, raw run evidence and frozen helper/
controller sources with checksums. Exclude private sessions, credentials,
dependencies and binaries. This compares two AST-report presentations, not AST with
text editing or the installed full skill with another workflow.
