# Prospective check-reuse instruction experiment

PR #86 observed repeated project checks after a successful AST rename. The original
report already includes `alreadyRun` and a matching successful `verify` entry.
Several traces explicitly acknowledge that success and nevertheless execute the
same check after read-only review. The current full skill explains check reuse;
the short delegated instructions used by those exact-command experiments do not.

This campaign tests that omitted instruction, not a new AST writer or report. It
does not measure an improvement over the installed full skill or ordinary editing.
Earlier measurements motivate the hypothesis but are not pooled or reused as controls.

## One intervention

Both arms use the same original engine output, selected intent, complete command,
task prompt, files, check, resolver and native tool set. Neither adds source excerpts
or snapshot work. Both inherit the existing delegated exact-command instructions.

| Arm | Additional instruction |
| --- | --- |
| `check_reuse_control` | None |
| `check_reuse_guidance` | The check-reuse paragraph below |

> A requested check is satisfied by a successful project-scoped `verify` entry
> for the same command and working directory, together with `alreadyRun`.
> Do not execute that same check again merely to confirm
> it after read-only review. Reuse it only while its files, dependencies,
> configuration, tool and environment are unchanged. Failed, missing, differently
> scoped or stale checks still need action. Rerun when the task explicitly requires
> a fresh or independent execution. Review unresolved warnings separately;
> passing a check does not classify references or establish task completion.

This is a generic instruction about using evidence already returned by the writer.
It names no task class, fixture path, expected result or hidden oracle. All tokens
for the extra instruction count toward treatment cost. It does not prevent any
tool call or replace the model's final explanation. The program never converts a
passing check into a claim that all references are resolved.

## Frozen schedule and budget

Two unchanged tasks (`method-and-literal`, `cross-file-rename-clarified`) × two arms
× six paired repetitions = **24 new attempts**. Seed `20260918`, balanced so three
pairs per task start with each arm. Use pinned `claude-haiku-4-5-20251001`, no effort
or fallback override, Claude Code 2.1.268 via its versioned executable, PHP 8.5.10
and the previously pinned Phpactor 2026.07.22.0 runtime. Each pair starts from
byte-identical fixture and task-prompt inputs; only the system paragraph differs.

Freeze and push signed code, this protocol and comparator before paid calls.
Independent design/code review, preparation/isolation checks, both real task
oracles and the comparator regression suite must pass first. Preserve legacy arm
behavior and previously published comparisons. Record source, manifest, instruction,
controller, comparator, CLI and resolver hashes and verify all twelve paired inputs.

Use fresh private workspaces, serial runs, 120 seconds per attempt, a USD 3 campaign
ceiling and a USD 0.75 reservation for only the next imminent run. Replace that
reservation with the actual native estimated cost after accounting. No competing
local test suite runs during candidate timing. Provider cache state is unknown.
Retain every attempt, including failures. Never rerun, replace, refine or add paid
candidates under this protocol. Stop after preserving evidence/accounting on missing
cost, timeout, model drift, isolation error or budget violation. Offline preflights
are separate from paid observations.

## Preregistered decision and quality

On **each task**, require a median paired treatment/control total-token ratio at
most 0.85, median paired wall-time ratio at most 1.0 and at least four of six pairs
saving tokens. Compute threshold decisions with exact rational token and serialized
decimal wall-time ratios. Cell medians are descriptive, not the registered gate.

All 24 final code, protected-file, actual candidate-check, AST-route and supported
final-claim gates must pass. The independent task oracle is separate from the
candidate's own check. Trace review must verify that the reported check actually
ran and passed on the final inputs, not merely that the agent says it did.
Count instruction adherence separately from correctness. A skipped necessary check
fails the quality gate; avoiding a repeat after an already successful check does not.

The mechanism criterion additionally requires fewer repeated already-passed check
executions in treatment on each task. Count actual equivalent executions of the
declared command inside native Bash calls after integrated success, with no
intervening relevant write/input change. Record separate statements within one Bash
call as separate executions, including combined read/check calls. Do not classify
syntax lint, git reads, a different check or a check after a write as a repeat.
Report the number of containing Bash calls separately from executions.

These fixtures exercise successful integrated checks and unresolved-warning review.
They do not measure model behavior after a failed/missing check or an external input
change. Six pairs per task remain exploratory. Keep this instruction variant in the
benchmark regardless of the result; production adoption would require a separately
registered confirmation including those conditions and the installed workflow.

## Reporting and reproduction

Publish all native input categories, output, totals, cost, rounds, tool calls and
failures, wall time, paired ratios and cell medians. Thinking is already part of
output. Native cost is an estimate, not an invoice. Tool execution time is unknown
without complete interval coverage. Audit pre/post-write reads, repeated check
executions, actual successful verification, warning review and complete final claims.

Operator-selected targets and commands exclude autonomous discovery cost. Keep all
earlier campaigns separate. Publish only allowlisted synthetic fixtures and raw run
evidence with checksums; exclude credentials, private sessions and dependencies.

Generate the unchanged manifest with `exact_tasks.py`, then prepare the existing
runner with `--arms check_reuse_control,check_reuse_guidance --models haiku --seed
20260918 --repetitions 6 --balance-by-task --campaign-budget-usd 3`, frozen source,
pinned vendor and explicit versioned Claude executable. Execute the frozen runner,
summarize with `summarize.py`, compare with `check_reuse_compare.py`, and export with
the existing pilot exporter. Manual quality and mechanism review remain separate.
