# Prospective direct intent-command economics

This is a bounded exploratory campaign for the new direct method-rename command.
It reuses the existing `method-and-literal` and clarified cross-file fixtures. No
new behavioral task is introduced. The earlier 36-run v0.8 report is historical
context, not a concurrent control.

## Question and treatments

Does a direct command accepting a method symbol and destination name reduce agent
orchestration work while preserving the existing guarded transaction and project
verification behavior?

The campaign has two tasks, two arms and three repetitions: twelve fresh candidate
processes. Each task starts from byte-identical files in every arm and repetition.
The model is pinned `claude-haiku-4-5-20251001`, with no effort flag or fallback.

| Arm | Candidate instruction | Write route |
| --- | --- | --- |
| `contextual_patch` | Existing competent ordinary editing instruction | Normal reads and text edits |
| `full_skill` | The current real revised skill from the same frozen source | Direct intent command and existing guarded engine |

The direct intent command is supplied as the new engine interface in the frozen
source, with the syntax `rename --method Class::old --to new` and optional
`--file`, `--path`, `--sha256`, `--report`, `--mocks` and `--dry-run` options. Its minimal
instruction contract says that it discovers the declaration and project callers,
submits one guarded transaction, runs configured verification and reports unresolved
or open facts. It does not supply task-specific paths, expected edit counts, oracle
facts or a second source view. The new engine and revised skill are frozen together.
This is a bundled intervention; the campaign does not isolate the command from the
skill wording.

The task prompt is identical across arms for each task. It names the requested
rename, preservation requirements and `php check.php`; it does not name a tool,
operation schema, expected references or result fields. The support checker and
configuration are protected by the independent oracle. A successful configured
check is evidence for that command only; it does not prove complete reference
resolution.

## Schedule, limits and execution

Use the unchanged efficiency runner. Its USD 0.75 per-run cap is a transient
reservation before a candidate and is replaced by the observed native cost after a
successful attempt. The campaign planning ceiling is USD 5 across this campaign
and any separately prepared refinement. A refinement may contain at most twelve
additional candidates and requires a new frozen source/protocol identity after
review of the first campaign. It must address one concrete trace-supported
interface problem; it may not tune prompts to an individual failed run.

Keep the existing 120-second deadline, serial campaign lock, fresh Git workspaces,
empty skills/plugins/MCP settings and Bash/Read/Edit/Write tool set. Preparation and
validation make no model calls. Never rerun, replace or discard an attempted
candidate. Unknown accounting, timeout, unexpected model, isolation mismatch or
cap violation stops execution for offline review.

The fixed schedule seed is `20260911-intent-command-v1` represented by the integer
`20260911`. Every task/arm/repetition cell has three attempts. Record the exact
source commit, current skill hash, CLI version, PHP/runtime identities, manifest
hash, schedule, prompts and all frozen controller/runtime files.

## Correctness and evidence

Before execution, the original fixture must fail its independent oracle, the
reference edits must pass, and mutating either protected check/configuration file
must fail. The reference path is only an offline preflight; it is not a candidate
run. The oracle checks requested identifier bytes, preserved literals/decoys,
complete file scope, PHP lint and runtime behavior. The configured checker exercises
the task's final bytes. Neither establishes resolver completeness outside the
fixture.

The implementation bundle also corrects the literal warning wording:
`Not finished` becomes `Review method-name literals`. Preserved literals may
be data rather than method references, so retain every literal count, entry and
path in the report while leaving the classification for review. This label does
not turn a passing check into a failure or claim that the literals were resolved.

The runner must retain each raw native trace, stderr, argv, process exit/timeout,
initial/final hashes, Git diff/status, oracle output and measurement. Report every
attempt, including failures and unknown values. Report fresh, cache-read,
cache-created and output tokens, total tokens, visible rounds, native turns, tool
calls, failed tool calls, candidate wall time, native list-price estimate and
changed lines. Cache state is unknown and list-price cost is not an invoice.

The passive proxy already records direct rename argv/results. Summary code must count
intent command invocations independently from `apply` events; an intent invocation
is not an `apply` event merely because it delegates internally. Review native traces
for route adherence, command failures, repairs and unsupported claims. Tool timing
stays unknown unless native intervals cover every tool call.

Primary success is a 3/3 oracle and candidate-verification result in each cell. Call
the intent interface a promising improvement only if, on both tasks, its median
total tokens are at least 15% below the contemporaneous contextual-edit control, median wall time
is no higher, and it has no correctness, verification, route-adherence or repair
regression. Otherwise publish the descriptive result and, only if traces identify
one concrete repairable interface problem, prepare one separate refinement. Three
repetitions support a hypothesis, not a general ROI or significance claim.

## Reproduction

Generate and inspect the manifest offline:

```bash
python3 benchmarks/agent-economics/intent-command/tasks.py \
  --output /tmp/intent-command-tasks.json
python3 -m unittest discover \
  -s benchmarks/agent-economics/intent-command -p 'test_*.py'
```

Prepare from the implementation/controller commit after its independent review:

```bash
python3 benchmarks/agent-economics/efficiency/runner.py prepare \
  --source "$PWD" --source-ref <FROZEN_COMMIT> \
  --vendor <PINNED_VENDOR> \
  --manifest /tmp/intent-command-tasks.json \
  --tasks method-and-literal,cross-file-rename-clarified \
  --arms contextual_patch,full_skill \
  --models haiku --seed 20260911 \
  --campaign-budget-usd 5 \
  --output /tmp/php-ast-intent-command-campaign

python3 benchmarks/agent-economics/efficiency/runner.py \
  validate --output /tmp/php-ast-intent-command-campaign
```

After the frozen files and fixture preflight are reviewed, execute only the frozen
controller copy:

```bash
python3 /tmp/php-ast-intent-command-campaign/controller/efficiency/runner.py \
  run --output /tmp/php-ast-intent-command-campaign --execute-models

python3 benchmarks/agent-economics/intent-command/summarize.py \
  /tmp/php-ast-intent-command-campaign \
  > /tmp/php-ast-intent-command-campaign/report.json
```

The two existing comparison arms are the complete schedule. The full-skill arm is
the source/runtime route under test. No candidate call belongs in preparation,
validation or fixture tests.
