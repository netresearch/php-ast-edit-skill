# Agent efficiency experiment

This prospective experiment separates a compact tool interface from a focused code
view. Preparation and validation make no model calls. Historical pilot evidence is
immutable and is not used as a new observation.

The [completed 120-attempt report](../results/2026-09-06-efficiency/REPORT.md) and
its evidence bundle retain the original protocol snapshots and every amendment.
The limits below describe the initial plan: before Phase 3, a separately recorded
operator amendment raised the shared planning allowance from USD 8 to USD 12.
Four reviewed timeouts retain unknown token/cost totals and separate planning
reservations; no failed attempt was rerun or removed.

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

## The check arms

Two later arms, `check_manual` and `check_integrated`, ask a separate question: with
the project's check declared, does the model still run it by hand after an `apply`
that already ran and passed it? They share the whole treatment above and both use the
complete current `SKILL.md`, unchanged and identical between them.

| Assigned arm | Fixture | Task clause |
| --- | --- | --- |
| `check_manual` | `check.php` | `Make sure \`php check.php\` still passes.` |
| `check_integrated` | `check.php` and a `.php-ast-edit.json` declaring `{"verify": [{"scope": "project", "command": ["php", "check.php"]}]}` | the same clause |

The arms differ in that one file. No instruction text and no prompt clause names the
declaration, the report field or the engine's checking at all: what the integrated
arm's model learns about the check having run, it learns from the report `apply`
returns, which is the deployed situation. `check.php` parses every PHP file in the
tree in-process and exits non-zero on the first file that does not; both fixture
files enter the fixture commit, so neither can appear in `diff.patch` as something a
model left behind.

The check is cheap on purpose. This measures whether the report stops the repeat run,
not what a repeat run of a real static analyser would have cost.

Report, in this order: the share of integrated runs whose `apply` reports actually
carried `alreadyRun` — a run without it received no treatment and is named, not
silently dropped; then the share of runs per arm that invoked `php check.php` after
their last passing `apply`, and the count per run; then rounds, tokens and wall time.

`--models` restricts the schedule to named model keys, so a pilot can run one model
before the pair.

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

### Accounting amendment after Phase 1 run004

The original controller stopped after run004 because visible response input sums
were smaller than final native totals. Its raw trace explicitly contains the native
synthetic message that a previous response had no visible output. Terminal `usage`
and summed `modelUsage` agree; aggregate input, output and cost remain known.
The amendment checks that agreement independently and accepts a positive visible
input remainder only with that exact synthetic retry event between assistant events.
Negative remainders, missing counters and unexplained gaps still stop execution.
It records `response_input_coverage`, all three `visible_response_input_remainder`
counters and the retry event indexes. `primary_model_rounds` counts only visible
response IDs; `primary_model_rounds_exact` is false with incomplete coverage. No
missing response, hidden round count or per-response output/cost is fabricated.

The original source commit, engine, prompts, task files, schedule, frozen controller
and `measurement.json` remain unchanged. A separately committed controller is copied
to `controller-amendment-v1/` with `runner.py`, `native.py` and this protocol. Its
`amendment-provenance.json` records the amendment source commit, original source
commit, unchanged campaign config hash and SHA-256 for those three files. Execution
verifies that manifest and records its hash and source commit in subsequent rows.
The original campaign's `frozen-sha256.json` continues to validate unchanged inputs.

Before resuming, run the new controller's `recover --output CAMPAIGN --run-id run004`
offline. It writes a separate `measurement-recovered.json` containing the raw and
original measurement hashes, original accounting error and amendment provenance.
It changes only the accounting interpretation, retaining grading and process data.
Budget resumption recomputes this sidecar from the original trace and requires an
exact match. Completed attempts are skipped and never rerun. Recovery and validation
make no model calls; the operator reviews the amendment before resuming execution.

### Reviewed timeout planning reservation after Phase 2 run020

The original stop policy halted Phase 2 after run020 reached 120 seconds without a
native terminal result. The attempt failed its output oracle and retains its original
measurement, trace, wall time, tool failures and unknown aggregate usage/cost. It is
never rerun or assigned zero usage. Operator and independent AI review confirmed the
unchanged source and the failed apply attempts before authorizing a planning-only
reservation of its previously allocated USD 0.75. This is **not observed cost or a
proven actual spending ceiling**. The USD 8 allowance is an operator planning limit;
neither the original CLI cap nor this reservation guarantees provider billing.

A separate `controller-amendment-v2/` keeps both earlier frozen controllers intact.
Its hashed `amendment-provenance.json` records individually approved timeout reviews,
keyed by run ID and bound to config, raw trace and original measurement SHA-256.
Each review includes approved operator and independent-reviewer attestations and
notes. These are review records, not cryptographic authentication of authorship.
The controller accepts only timed-out, well-formed traces with the exact missing
terminal error, correct model/isolation and complete observed tool-result linkage.
It does not turn their incomplete input/output snapshots into aggregate metrics.

`reserve-timeout --output CAMPAIGN --run-id run020` writes a separate
`timeout-reservation.json` offline. The native observed cost is explicitly null;
the planning reservation is a separate field. Resumption recomputes the complete
sidecar against the individually approved manifest and immutable evidence, then
skips the original attempt. Every new unknown-cost attempt still stops for its own
review; the command never grants a campaign-wide exception.

`budget_so_far` returns the known native subtotal, reserved unknown amount and their
planning allocation. `spent_so_far` remains the known native subtotal only. Progress
retains `spent_native_list_usd` for that known subtotal and adds
`reserved_unknown_usd` and `allocated_budget_usd`; reservations never enter a field
claiming observed native spend. Later phases deduct both known costs and reservations
from the shared planning allowance. All unresolved costs remain visibly unknown in
the results even when the operator authorizes continued experimentation.

Phase 2 run031 subsequently reached the same deadline without a terminal result.
It stopped independently and received its own operator/AI review and planning-only
reservation; the run020 approval did not authorize continuation automatically.
Successive immutable `controller-amendment-vN/` directories are supported, with a
positive numeric version and a resolved location directly inside the campaign.
Every existing sidecar is revalidated against its own recorded archived controller,
manifest and individual approval. A newer controller can therefore retain the exact
run020 v2 sidecar while adding run031 under v3, without rewriting prior manifests or
measurements. Each future unknown still stops and needs an individually linked review.

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

### Separate directed-read ablation

The original four arms' observations retain the agent's own selector choices, including
whole-class selections that do not test a narrow projection. A separate, predeclared
follow-up can add an exact initial method selector to each public task prompt, with
the same addition in both compact arms and no operation or recovery hints. It retains
the original observations rather than replacing or selecting successful trials.

Use `--arms compact_full,compact_focused` with a separate frozen task manifest and
output directory. Two tasks, two models and three repetitions then produce 24 runs.
Preparation accepts any nonempty, duplicate-free subset of the declared arms;
the default schedule is unchanged. Selected arms are recorded in config,
and arm rotations remain balanced across task/model/repetition blocks. The runtime
and adapter bytes must match the prior phases, and the remaining aggregate budget
must be supplied explicitly. Preparing this follow-up does not authorize execution.
