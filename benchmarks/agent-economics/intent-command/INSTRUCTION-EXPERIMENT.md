# Prospective instruction ablation

This is a new experiment on the current direct rename command, after the two
completed command campaigns. It does not extend their exhausted refinement budget
or pool their observations. The engine is identical across the two AST arms.

## Hypothesis and arms

The complete skill may cost more context and orchestration decisions than these
supported method-renaming tasks need. A short, task-independent instruction for
the existing intent command may reduce total session tokens and follow-up calls.
This tests instruction scope, not a new writer, receipt store, or MCP interface.

| Arm | Instructions | Available tools and source |
| --- | --- | --- |
| `contextual_patch` | Existing competent ordinary-editing control | Unchanged Bash, Read, Edit, Write |
| `full_skill` | Complete current skill from the frozen source | Same tools; PHP writes through the same AST engine |
| `minimal_intent` | Short command contract, frozen in the controller | Same tools and AST engine; normal source discovery |

Use the existing `method-and-literal` and `cross-file-rename-clarified` task
manifest, including protected check/configuration files. Each task prompt,
starting file, checker, oracle, runtime dependency and report implementation is
identical across arms. The minimal instructions contain no task-specific names,
paths, expected counts or oracle knowledge. The direct command keeps its compact
report, guards, project resolution and integrated verification in both AST arms.

The primary comparison is `minimal_intent` against contemporaneous `full_skill`.
The contextual control determines whether any improvement also closes the actual
gap to ordinary editing. Earlier campaigns are background only.

## Frozen schedule and budget

Two tasks × three arms × three repetitions = 18 attempts. Use pinned
`claude-haiku-4-5-20251001`, no effort override or fallback, seed `20260913`,
120 seconds per attempt and the existing USD 0.75 per-run reservation. The combined
planning ceiling for this campaign and at most one later refinement is USD 3.
Native cost replaces the reservation after each completely accounted attempt.

Use the existing runner's serial lock, private fresh workspaces, empty skills,
plugins and MCP settings, native accounting and retained failed attempts. Its
existing default arms remain unchanged; `minimal_intent` is opt-in. No candidate
calls occur during preparation or validation. Commit the instructions, controller
and this protocol before preparing the frozen campaign. Record source commit,
manifest/controller/instruction hashes, CLI/PHP identities and pinned resolver
digest. Never rerun or replace an attempted candidate. Stop for offline diagnosis
on missing accounting, timeout, unexpected model, isolation mismatch or budget
violation.

## Quality and outcomes

Run the existing task-generator/oracle tests before execution: initial fixtures
must fail, reference edits pass, and support-file tampering fail. Review every
candidate for final oracle correctness, actual successful candidate verification,
route adherence and unsupported completion claims. All three repetitions of both
task cells must satisfy these gates before calling an arm successful. A safe
refusal is reported separately from completing the requested task.

Report all native input categories (fresh, cache creation and cache read), output,
total tokens, cost, visible model rounds, tool calls, failures and candidate wall
time. Thinking is already part of output where reported. Cache billing state is
unknown. Tool execution time remains unknown without complete interval coverage.
Also inspect post-write reads, redundant checks, direct intent calls, report bytes
and fallback routes. Do not infer task correctness from the candidate's own check.

A promising instruction improvement requires at least 15% lower median total
tokens than `full_skill`, no higher median wall time and no quality regression on
both tasks. Report comparisons to contextual editing separately. Three samples
per cell are exploratory and do not establish a general savings rate. Improving
one task while worsening the other is a mixed result, not an overall win.

One refinement of at most 12 additional attempts may follow only if these traces
identify one concrete change worth testing. Write its contract and criterion,
freeze a new source/controller identity and obtain an independent design review
before execution. Keep the initial 18 attempts unchanged and report the campaigns
separately. No additional attempts belong to this protocol.

## Commands

```bash
python3 benchmarks/agent-economics/intent-command/tasks.py --output /tmp/intent-instruction-tasks.json
python3 -m unittest discover -s benchmarks/agent-economics/intent-command -p 'test_*.py'
python3 benchmarks/agent-economics/efficiency/test_harness.py
python3 benchmarks/agent-economics/efficiency/runner.py prepare \
  --source "$PWD" --source-ref <FROZEN_COMMIT> --vendor <PINNED_VENDOR> \
  --manifest /tmp/intent-instruction-tasks.json \
  --tasks method-and-literal,cross-file-rename-clarified \
  --arms contextual_patch,full_skill,minimal_intent --models haiku --seed 20260913 \
  --campaign-budget-usd 3 --output /tmp/php-ast-intent-instruction-campaign-20260911
python3 /tmp/php-ast-intent-instruction-campaign-20260911/controller/efficiency/runner.py \
  run --output /tmp/php-ast-intent-instruction-campaign-20260911 --execute-models
python3 benchmarks/agent-economics/intent-command/summarize.py \
  /tmp/php-ast-intent-instruction-campaign-20260911
```

## Single refinement: delegate family discovery

The initial 18 attempts completed without accounting errors, for a native list-price
estimate of USD 0.7160165. All final oracles passed. Shortening instructions alone
did not meet the prospective criterion: small-task median tokens increased from
61,734 to 82,944; cross-file tokens decreased from 204,758 to 154,635.
Independent trace review also rejects run005's general type-safety claim; that
run fails the completion-claims gate despite its correct fixture outcome.

The initial common contract required the model to read source before editing.
Every AST candidate therefore did discovery that the guarded rename command can
perform itself. In minimal run005, the model queued Contract, Base and Child
renames together: Contract succeeded first, then the two redundant calls failed
because that transaction had already renamed the family. These failures remain
in the initial totals.

Test one workflow change: delegate the complete supported family rename to the
intent command, including its initial discovery. Compare unchanged `minimal_intent`
with opt-in `delegated_intent`. The latter appends this generic instruction:

> When the task names the class and method to rename, invoke the command before
> reading or searching PHP for declaration or caller discovery. Invoke it once for
> the named method family; it handles supported declarations and callers
> together. Do not queue separate renames for each implementation or caller. Read
> source yourself only when needed for another requirement, a failed command, or
> unresolved warnings.

Only for this arm, replace the common sentence "Read relevant source before
editing." with "Ensure relevant source is read before editing; for a supported
method rename, the command performs this discovery." Record each arm's actual
common instructions. This is a disclosed compound instruction about one workflow;
do not attribute any difference separately to its individual phrases. It does not
weaken source guards, resolution requirements, verification, diff review or the
independent oracle. Failed discovery and unresolved cases still require diagnosis.

Use the same two tasks, three repetitions, pinned Haiku, tool set, runtime and
checks: 12 attempts, seed `20260914`. Freeze a new commit before preparation and
obtain independent design review before execution. The remaining campaign ceiling
is USD 2.2839835 (USD 3 less the initial cost), still reserving USD 0.75 before each
attempt. The same stop rules and all-attempt reporting apply. No further refinement
or replacement attempts are allowed under this protocol.

The primary comparison is now delegated versus contemporaneous minimal. A promising
result requires at least 15% lower median total tokens, no higher median wall time,
and all quality gates passing on both tasks. Earlier full-skill and contextual
cells are separate historical context, not contemporaneous controls for this
refinement. Inspect pre-write source reads and queued family calls to determine
whether the intended mechanism actually occurred. Report mixed or negative results
and instruction non-adherence. Three repetitions are exploratory.

```bash
python3 benchmarks/agent-economics/efficiency/runner.py prepare \
  --source "$PWD" --source-ref <REFINEMENT_FROZEN_COMMIT> --vendor <PINNED_VENDOR> \
  --manifest /tmp/intent-instruction-tasks.json \
  --tasks method-and-literal,cross-file-rename-clarified \
  --arms minimal_intent,delegated_intent --models haiku --seed 20260914 \
  --campaign-budget-usd 2.2839835 --output /tmp/php-ast-delegated-intent-campaign-20260911
PHP_AST_EDIT_PHPACTOR=/tmp/php-ast-delegated-intent-campaign-20260911/runtime/vendor/phpactor.phar \
python3 /tmp/php-ast-delegated-intent-campaign-20260911/controller/efficiency/runner.py \
  run --output /tmp/php-ast-delegated-intent-campaign-20260911 --execute-models
python3 benchmarks/agent-economics/intent-command/summarize.py \
  /tmp/php-ast-delegated-intent-campaign-20260911
```

`<PINNED_VENDOR>` includes the same verified Phpactor PHAR under `phpactor.phar`;
record its digest and the environment selection in operator provenance. The PHAR
is therefore also covered by the frozen runtime checksum manifest.
