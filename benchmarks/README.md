# Measuring PHP AST editing: CLI performance and complete agent tasks

The CLI microbenchmark measures local processes. The agent harness measures whether a
complete task passes its oracle and imports actual model usage. Neither substitutes for
the other. The offline task harness does not invoke models or invent usage data.
The optional [native efficiency runner](agent-economics/efficiency/PROTOCOL.md) can
invoke Claude Code only through an explicit `run --execute-models` command.
Read the [execution and trust boundaries](TRUST.md) before grading candidate code or
importing evidence; they also record the narrowly scoped static-analysis decisions.

## Reproduce the local comparison

Requirements: installed project dependencies, PHP, Python 3.10+, and Git.

```bash
XDEBUG_MODE=off python3 benchmarks/cli_microbenchmark.py --repetitions 30 --include-operation-help --output /tmp/php-ast-cli.json
jq '.environment, .parameters, .summary' /tmp/php-ast-cli.json
```

The script materializes fixtures through the AST CLI in a temporary directory. The
contextual patch baseline applies only to these disposable copies, uses `git apply` with
context, and runs `php -l`. On PHP 8.3+, the batched patch arm lints all changed files in
one interpreter invocation (`php -l file1.php file2.php ...`), so it uses two harness
commands: one patch application and one lint call. PHP 8.2 uses one lint call per file.
The runner detects the host version once outside the timer and records `php_version_id`
and `patch_lint_mode` with the resulting command counts. Each sample must produce
byte-identical output to the prepared AST result. The fixture's return value and declared
return type are independently checked before measurement.

Measured arms: one AST edit; one contextual patch plus lint; ten AST edits in one
transaction; ten patches in one application plus lint; ten separate AST invocations;
`inspect`; and `contexts`. Add `--include-operation-help` for the eighth arm,
`contexts --operation rename_variable`, reported as `contexts_operation`. Omit that flag
when testing versions that do not support compact operation help. The order is shuffled with a recorded seed each iteration.
Two warmups precede 30 recorded samples by default. Setup and exact fixture restoration
are outside the timer; process startup and output collection are inside it.

Output includes raw samples, median, nearest-rank p95, command counts, output bytes,
commit, dirty-tree flag, PHP/parser/Python/platform information, and Xdebug status.
`source_root` and `source_commit` identify the benchmark checkout; `executable_path` and
`executable_sha256` identify the actual selected executable, including custom `--bin` runs.
Retain the build/source provenance for a custom binary; the checkout commit alone does
not identify an arbitrary PHAR. Nested
processes started internally by the engine are included in elapsed time; the process-count
column counts harness commands, not all child processes or agent tool calls. Do not
compare dirty-tree results without retaining the patch that identifies the code tested.

Storage location affects startup costs, especially when PHP loads many source files. Under
WSL, a Windows-mounted checkout can behave very differently from a Linux-filesystem
checkout. Record where the engine, dependencies, and temporary fixtures reside; preserve
that setup when comparing runs. Run timed trials without concurrent local test/build work.

Output byte length is not a token count. No model latency, instruction load, model round,
cache use, or billed tokens are measured here. Both AST and patch paths can batch edits.
A speedup over separate AST calls does not establish a speedup over a competent patch
workflow. [Published local samples](results/README.md) record the measured version.

## Executable task fixtures and outcome oracles

```bash
python3 benchmarks/agent_benchmark.py self-test
python3 benchmarks/agent_benchmark.py prepare add-clock-method \
  --work /tmp/php-agent-run --state /tmp/php-agent-run.state.json
# Give the returned prompt and workspace to the agent variant being measured.
python3 benchmarks/agent_benchmark.py grade add-clock-method \
  --work /tmp/php-agent-run --state /tmp/php-agent-run.state.json \
  --output /tmp/php-agent-run.oracle.json
```

`prepare` refuses a nonempty workspace and keeps evaluator state outside it. It outputs
only the user prompt and fixture paths. Keep the task manifest, reference edits, oracle,
and evaluator state outside the agent's supplied context. They are answer keys, not task
instructions. The source repository includes them for reproducibility; execution isolation
is the responsibility of the surrounding agent harness.

Eight seed tasks cover namespaced construction, method/literal distinction, a capture
collision, inherited dispatch, an SQL literal, local variable/capture rename, argument
removal, and two-file edits. Runtime assertions check requested behavior and selected
unchanged behavior. The evaluator also checks lint, file scope, and expected mutation or
refusal. `self-test` exercises each reference solution and checks that deleting a required
file makes its oracle fail. It runs no model.

For an explicit refusal, unchanged output and preserved runtime behavior are necessary
but insufficient: a reviewer must confirm the agent explained the relevant collision or
inheritance limit. The inheritance task accepts either a correct child-only rename or a
justified refusal; it does not penalize a baseline capable of resolving that local example. For changed tasks, review the diff for incidental edits
outside the oracle's coverage. A small seed corpus is useful infrastructure, not proof of
performance on arbitrary PHP projects. Expand it with real project tasks before broad
claims; a useful initial study has at least 24 tasks and five repetitions per variant.

## Fair agent comparison

Compare the same model and harness in three conditions:

1. **`contextual_patch`**: a competent agent using contextual patches, ordinary search,
   batching, and the same project checks. Do not inject the AST-only repository rule into
   this baseline's workspace or system prompt.
2. **`cli_reference`**: the CLI plus a short operation/schema reference.
3. **`full_skill`**: the CLI plus the complete skill and references loaded on demand.

Hold task source, model snapshot, reasoning configuration, tool access/latency, limits,
and acceptance criteria fixed. Randomize variant order and preserve all failed runs.
Separate cold onboarding (installation and first instruction load) from warm usage.
Report setup time explicitly, and state whether it is included in elapsed time. A warm
run must have a documented, repeatable cache procedure; cache state is not inferred from
an inexpensive response.

## Import actual run evidence

Capture model usage and tool events from the harness, not estimates from transcript size.
A run record must conform to [run.schema.json](run.schema.json). Save it next to its
transcript and the oracle JSON, with SHA-256 values for both evidence files. Then:

```bash
python3 benchmarks/agent_benchmark.py import /path/to/run.json --results /tmp/runs.jsonl
python3 benchmarks/agent_benchmark.py summarize /tmp/runs.jsonl
```

The importer validates the record, evidence checksums, oracle/task identity, human review,
cached-token accounting, first-attempt consistency, and duplicate run identity. It cannot
independently verify a provider's billing from a prose transcript; retain native usage
records and review them before publishing cost claims. Never fill missing measurements
with zero. `cost_usd` may be null when no reliable cost is available. Optional metrics
are omitted when unavailable; existing records without them remain valid.

| Field | Definition |
| --- | --- |
| `tokens.input` | Total input tokens, including cache reads and cache writes; normalize provider-specific counters without double-counting |
| `tokens.cached_input` | Cache-read subset of input, never added again to total |
| `tokens.cache_write_input` | Optional cache-write subset, distinct from cache reads; retain the native usage record |
| `tokens.output` | Reported generated tokens, using provider semantics documented in the harness config |
| `tool_calls` | Actual harness tool invocations; a shell call containing ten commands is one tool call |
| `failed_tool_calls` | Optional count of tool invocations ending in an error, bounded by `tool_calls`; use native tool outcomes |
| `tool_timing.execution_sum_ms` | Optional sum of measured execution durations; concurrent calls overlap in this sum |
| `tool_timing.busy_wall_ms` | Optional union of execution intervals: wall time with at least one tool executing |
| `cli_invocations` | Explicit editor invocations, independently of tool calls |
| `model_rounds` | Actual model request/response cycles |
| `repair_attempts` | Attempts after the first candidate fails a tool or outcome check |
| `elapsed_ms` | Entire task duration through acceptance or stopping, including failed attempts |
| `setup_elapsed_ms` | Recorded onboarding/setup component; document inclusion in total |
| `success` | Independent oracle passes and human review accepts the result |
| `first_attempt_success` | Success without a failed candidate or repair |
| `harness_config_sha256` | Hash of the retained common model/tool/limit setup; record variant instructions separately in the trace |

When supplying `tool_timing`, also supply its `evidence` path and SHA-256. The evidence is
an export of native harness execution events, using one shared monotonic clock and offsets
from task start:

```json
{
  "origin": "native_harness_tool_execution",
  "clock": "monotonic_ms_from_task_start",
  "intervals": [
    {"call_id": "tool-1", "start_ms": 100, "end_ms": 300},
    {"call_id": "tool-2", "start_ms": 200, "end_ms": 400}
  ]
}
```

This illustrative overlap has `execution_sum_ms: 400` and `busy_wall_ms: 300`; it is not a
measured project run. The importer requires exactly one interval per counted tool call,
unique call IDs, intervals within `elapsed_ms`, and recomputes both timing values. Include
failed invocations in the timing export. Omit the entire timing block if complete native
start/end events are unavailable. Retain the original events in the transcript alongside
this normalized export, and document where execution starts and ends in the harness.

Summed execution time can exceed wall time during parallel work. Subtracting that sum
from total elapsed time does not give orchestration or model time. Even `elapsed_ms` minus
the interval union includes model requests, queues, harness overhead, and uninstrumented
waiting; this schema does not label that remainder as model time. Optional metric summaries
state how many runs supplied each measurement and use null totals when none did.

The summary groups distinct commits, models, settings, and cache conditions separately.
It reports success rates and total tokens/calls including failures; cost per successful
task must include unsuccessful attempts. Check equal paired task coverage before comparing
variant aggregates. Report task-family results and confidence intervals when the sample
supports them. A few successful showcase tasks must not become a universal percentage.

The [native agent pilot](agent-economics/README.md) records twelve actual model runs on
two seed tasks, with native usage, all failed tool calls, source provenance, and outcome
review. The full skill used more tokens in every pair; the report keeps that negative
result separate from the CLI timings. It is a small pilot, not the broader study described
above. Cache state is unknown and human acceptance is pending, so its records are retained
in a separate evidence format instead of inventing values required by the importer.

The [compact-workflow follow-up](agent-economics/results/2026-09-06-efficiency/REPORT.md)
adds Sonnet/Haiku comparisons, public TYPO3 maintenance tasks and a separate directed
source-view experiment. It retains negative results, unknown terminal usage and
instruction bypasses. The source/protocol and sanitized evidence allow independent
reaggregation; the adapter remains experimental benchmark tooling.

## Historical development measurements

The [v0.7.0 release](https://github.com/netresearch/php-ast-edit-skill/releases/tag/v0.7.0)
reports twelve controlled `claude -p` runs with identical worktrees and per-run JSON
usage. These are published first-party development observations. They compare successive
tool iterations: [PR #27](https://github.com/netresearch/php-ast-edit-skill/pull/27) reports
15 to 13 turns, 106 to 82 seconds, and $0.375 to $0.348; the
[later error-message change](https://github.com/netresearch/php-ast-edit-skill/commit/2789c54a46e5887338d8c5b00f7cfee5b0b62859)
reports 6 turns and $0.244. The 82-second result belongs to the intermediate 13-turn build.

The public tag tree, release assets, and linked PR materials inspected for this review did
not expose the underlying run JSON, full transcripts, and complete model/harness settings.
The linked Claude session was not readable with the review tools. This does not establish
that the runs never happened or that their author did not retain the evidence. The numbers
are attributable observations, not an independently reproduced comparison with a competent
patch baseline. They have not been imported as new measured rows in this benchmark ledger.
