# Measuring PHP AST editing: CLI performance and complete agent tasks

The CLI microbenchmark measures local processes. The agent harness measures whether a
complete task passes its oracle and imports actual model usage. Neither substitutes for
the other. The harness does not call a paid model API or invent usage data.

## Reproduce the local comparison

Requirements: installed project dependencies, PHP, Python 3.10+, and Git.

```bash
python3 benchmarks/cli_microbenchmark.py --repetitions 30 --include-operation-help --output /tmp/php-ast-cli.json
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
with zero. `cost_usd` alone may be null when no reliable cost is available.

| Field | Definition |
| --- | --- |
| `tokens.input` | Total reported input tokens, including cached input |
| `tokens.cached_input` | Cached subset of input, never added again to total |
| `tokens.output` | Reported generated tokens, using provider semantics documented in the harness config |
| `tool_calls` | Actual harness tool invocations; a shell call containing ten commands is one tool call |
| `cli_invocations` | Explicit editor invocations, independently of tool calls |
| `model_rounds` | Actual model request/response cycles |
| `repair_attempts` | Attempts after the first candidate fails a tool or outcome check |
| `elapsed_ms` | Entire task duration through acceptance or stopping, including failed attempts |
| `setup_elapsed_ms` | Recorded onboarding/setup component; document inclusion in total |
| `success` | Independent oracle passes and human review accepts the result |
| `first_attempt_success` | Success without a failed candidate or repair |
| `harness_config_sha256` | Hash of the retained common model/tool/limit setup; record variant instructions separately in the trace |

The summary groups distinct commits, models, settings, and cache conditions separately.
It reports success rates and total tokens/calls including failures; cost per successful
task must include unsuccessful attempts. Check equal paired task coverage before comparing
variant aggregates. Report task-family results and confidence intervals when the sample
supports them. A few successful showcase tasks must not become a universal percentage.

No complete model A/B campaign is represented by these files. Publishing one requires
running the chosen models, retaining their native usage, and reviewing all outcomes.
