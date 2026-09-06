# Four-arm agent efficiency experiment

This prospective experiment separates a compact tool interface from a focused code
view. Preparation and validation make no model calls. Historical pilot evidence is
immutable and is not used as a new observation.

## Phase 1 and treatments

The initial phase is two original tasks (`local-variable`, `multi-file-members`),
four arms, two models and three repetitions: **48 candidate runs**. Every task starts
with identical file bytes across arms, models and repetitions.

| Assigned arm | Instructions and edit route | Source view |
| --- | --- | --- |
| `contextual_patch` | Competent contextual Edit/patch baseline | Ordinary source reads |
| `full_skill` | Complete current SKILL.md, unchanged; ordinary engine CLI output | Ordinary source reads |
| `compact_full` | Concise adapter instructions, stdin apply, compact result, mandatory bound revisions | Complete source returned by adapter |
| `compact_focused` | Same adapter and instructions; only read mode changes | Selected source with surrounding context/outline; explicit full-source fallback when no selector is supplied |

The complete skill control remains unchanged even if a shorter instruction budget
would be preferable. Record its exact hash and word count, the complete initial
prompts, adapter/helper hashes and actual initial native input counters. The compact
arms differ in one read-mode word; they use the same API, result format and revision
validation. Neither compact arm is an AST dump. Any fallback or out-of-arm action
must be disclosed in adherence review rather than silently excluded.

Sonnet uses `claude-sonnet-4-6` and `--effort medium`. Haiku uses the pinned
`claude-haiku-4-5-20251001`, with effort recorded as null/not_supported and **no effort
flag**. The inherited effort override is removed. Comparisons are within each model;
the models are not claimed to have identical reasoning settings. Every init and
primary response must report the exact requested ID. Auxiliary native model usage,
if present, remains included in all-model totals and is shown separately.

## Isolation, order and limits

All candidates receive the same competent common prompt and Bash/Read/Edit/Write
tool set. Claude runs with safe mode, slash commands disabled, empty explicit
settings and setting sources, an empty strict MCP configuration, no persisted
session and prompt suggestions disabled. Native init must confirm empty skills,
plugins and MCP servers. Existing authentication is used without exposing it.
No home/global instructions are supplied or sought; the common prompt prohibits
reading home, controller, evaluator, answer-key and adapter-state files.

Each candidate has a fresh process and Git fixture workspace under Linux `/tmp`.
The seeded schedule shuffles task/model/repetition blocks and rotates the four arms
with balanced starting positions across the phase. Runs are serial; a controller
lock prevents two campaigns from running against the same output. The operator
also avoids concurrent heavy local work. Provider cache state remains **unknown**;
fresh sessions do not establish a cold cache. Retain actual cache counters.

Each run has a 120-second process deadline and a USD 0.75 native CLI budget. Before
starting a run, the controller reserves its entire USD 0.75 against the campaign's
USD 8 native-list-price ceiling. It refuses another start if that reservation cannot
fit. A timeout, malformed/missing native usage, unknown cost, unexpected model or
isolation mismatch stops subsequent calls. Observed native cap overruns also stop
the campaign. The CLI reports cost after work occurs; these controls cannot prove
a provider billing limit or retroactively prevent an unexpectedly oversized native
request. Native estimates under subscription authentication are not charged dollars.
For a later phase, pass `--campaign-budget-usd` with the remaining aggregate allowance;
the initial USD 8 budget is shared across phases rather than reset for each phase.

The runner isolates context and data layout, **not operating-system access**.
Adapter state lives outside the task and the adapter rejects unknown/stale revisions;
this is not an adversarial sandbox against a candidate that deliberately accesses
the state directory. Do not expose this local evaluator as a service.

## Retained evidence and grading

For every attempted run retain argv, complete prompts, native JSONL and stderr,
process wall time/exit/timeout, original and final source hashes, Git diff/status,
every oracle outcome, native model usage and list-price cost. Never replace a raw
run or discard a failure. An interrupted raw run requires offline recovery and
review, not another candidate invocation.

Input accounting deduplicates streamed assistant events by response ID and checks
fresh, cache-read and cache-created input sums against final native model usage.
Final `modelUsage` supplies output totals; early output snapshots are not complete
per-response counts. Missing required counters remain errors, never invented zeros.
Thinking detail is retained when present and is not added to output a second time.
Explicit native per-tool millisecond durations are retained when exposed. Their sum
is reported only with complete tool coverage; otherwise `tool_execution_ms` is null
and coverage is marked partial/not_exposed. API duration is never subtracted from
process wall time to invent tool or orchestration timing.

The passive PATH engine launcher records full-skill apply payloads, SHA presence,
captured source hashes and native outcomes while preserving engine stdout/stderr.
The compact adapter records reads, modes/selectors, returned revisions and every
apply attempt with resolved SHA and outcomes. Logs are evidence, not automatic
proof of complete instruction compliance: inspect native tool traces for bypasses,
fallbacks and unlogged direct executable calls. Retain assigned arms and all attempts
(intention-to-treat); report guard adherence separately from output correctness.

The pinned existing grader checks exact file scope, PHP lint, requested runtime
behavior and expected change/refusal. Review every final diff and explanation.
AI review and human acceptance have separate pending fields; neither is implied by
a passing oracle. No historical cold/warm-and-human-review import is fabricated.

## Prepare, validate, then execute only after review

Use an installed dependency tree; preparation does not install packages. The source
must contain the experiment, including adapter, in a clean frozen commit for actual
execution. `--development` permits dirty preparation but makes that output permanently
ineligible for model execution. Always choose a new output directory.

```bash
python3 benchmarks/agent-economics/efficiency/runner.py prepare \
  --source "$PWD" --source-ref HEAD --vendor /path/to/installed/vendor \
  --output /tmp/php-ast-efficiency-seed-observations
python3 benchmarks/agent-economics/efficiency/runner.py validate \
  --output /tmp/php-ast-efficiency-seed-observations
```

Preparation freezes the engine and skill from the selected commit, the experiment
and adapter, dependency bytes, grader, complete task manifest, schedule, instructions
and initial fixtures. `frozen-sha256.json` covers every runtime/controller/tool file
and prepared evidence file. Measurement rows link the source commit and config hash.
Later source-tree edits cannot change an already prepared runtime unnoticed.

After dry checks and explicit experiment authorization, the model-running command is:

```bash
python3 /tmp/php-ast-efficiency-seed-observations/controller/efficiency/runner.py run \
  --output /tmp/php-ast-efficiency-seed-observations --execute-models
```

The run command is intentionally separate. No model is invoked by default or by
preparation/validation. Raw traces remain private; any public export requires a
separate reviewed sanitization that preserves numerical evidence and tool linkage.

## Held-out extension

Use a separate output and task manifest, without adding held-out tasks to Phase 1:

```bash
python3 benchmarks/agent-economics/efficiency/runner.py prepare \
  --source "$PWD" --source-ref HEAD --vendor /path/to/installed/vendor \
  --tasks-json /path/to/public-task-manifest.json --tasks public-task-one,public-task-two \
  --output /tmp/php-ast-efficiency-heldout-observations
```

The external manifest uses the existing `benchmarks/tasks.json` schema: `id`, prompt,
`files` with path/PHP bytes, edits, oracle and expected outcome. Extra provenance
metadata remains in the frozen manifest. Set **`preserve_source: true`** on a public
task to retain its exact UTF-8 source bytes, including layout and line endings;
the original seed tasks continue using the legacy engine-created preparation.
Only source fixtures and the task prompt enter the candidate workspace; expected
edits and oracles stay in the controller. The copied grader reads the frozen manifest
from its normal relative path and enforces its hash. A new phase requires a separate
frozen manifest and operator review within the already authorized aggregate budget.
