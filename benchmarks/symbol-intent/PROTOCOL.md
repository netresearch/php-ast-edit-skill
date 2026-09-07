# Prospective Haiku cross-file rename pilot

This new pilot does not amend or replace the completed 120-run efficiency study.
It asks whether delegating reference discovery and individual edits to a tool saves
model work, and whether an existing semantic refactoring tool achieves the same gain.

## Design frozen before model execution

- Model: `claude-haiku-4-5-20251001`; no effort flag. Record exact Claude CLI version.
- Workloads: rename `Example\Provider::fetch` to `load` in 2, 10 and 50 PHP files.
  Each caller also invokes an unrelated `Other::fetch`; variable bindings alternate
  across files. These are generated synthetic fixtures, not a representative corpus.
- Three arms: competent batched text editing; the experimental `rename_method` API;
  existing Phpactor `index:build` then `references:member --replace`. Each semantic
  route gets the same pinned resolver and a fresh isolated index. Agents can batch
  shell commands, redirect verbose output and run their own checks in every arm.
- Three repetitions per arm and size: 27 attempted candidates, all retained. A fixed
  seed shuffles size/repetition blocks and rotates arm order. Comparisons are within
  a size. Do not pool these into a general performance or success-rate claim.
- Common task, Bash/Read/Edit/Write tools and context isolation. Treatment-specific
  instructions and command paths are recorded in full; input overhead is measured.
  No full AST dump or mandatory inspect call. The text arm can use scripts, not just
  one Edit call per file. No production PHP files are modified by candidate agents.
- Native safe mode, empty settings/MCP, disabled slash commands and persisted
  sessions; native init must confirm model, tool set and absence of skills/plugins.
  Context isolation is not an OS sandbox. Controller, state and answer files are
  outside the task and candidates are instructed not to inspect them.

## Accounting and stop policy

Freeze this source commit, exact tool/dependency hashes, fixtures, full prompts and
schedule before calling a model. Verify the runtime before and after each candidate.
Use a fresh Git workspace and process each time. Provider cache warmth is unknown;
record fresh input, cache reads/writes and output independently from native totals.

This pilot has its own USD 4 native-list-price planning allowance, a USD 0.50 CLI
budget per run and a 120-second process deadline. Reserve a full run budget before
each start. Stop on timeout, unknown/malformed accounting, wrong model/isolation,
source drift or observed budget overrun. Preserve the failed attempt; no silent
replacement, rerun or imputation. These are operator planning controls, not a
guaranteed provider billing cap. Costs under subscription auth are list-price
estimates, not necessarily actual charges.

Reuse the strict native accounting parser from the earlier efficiency experiment.
Retain stream JSONL, stderr, process wall time, model usage, visible rounds, tool
calls/failures, initial/final hashes, diffs and oracle results for every attempt.
Native per-tool durations are reported only at their observed coverage. Never
subtract API time from wall time to invent orchestration time. Index/planning time
is included in candidate wall time; no warm-index claim is made.

## Outcome and interpretation

The oracle requires unchanged file scope, expected PHP structure (ignoring layout),
renamed declaration, all intended calls, unchanged unrelated calls and runtime
dispatch `[11, 22]` for every caller. Byte-exact output is a separate formatting
metric. Oracle inspection runs after the candidate and is excluded from candidate
wall time; any checks the agent runs itself remain included.

Publish medians and individual results for tokens, calls and wall time, plus every
failure and adherence deviation. A successful synthetic task does not prove that
the resolver finds all references in arbitrary projects. Manually review diffs and
native calls for bypasses; automatic correctness and instruction adherence remain
separate. Report the review actually performed, including any unavailable independent
review. Three repetitions are a pilot, not a statistically reliable general claim.

If Phpactor CLI matches or beats the AST intent route, attribute savings to delegated
semantic work rather than claiming the AST writer is the source of that saving.
The AST route adds transaction/reporting guards; it may cost additional tool time.

## Accounting scope amendment after run001

The first candidate completed correctly, but the inherited strict parser rejected
its terminal counters: main-loop `usage` reports 4,100 fresh input and 1,641 output
tokens; whole-call `modelUsage` reports 5,065 and 1,655. Both cache totals agree.
The original trace, measurement and stop are retained; the candidate is not rerun.

The [official SDK documentation](https://code.claude.com/docs/en/agent-sdk/cost-tracking#track-costs-for-a-query)
defines these fields with different scopes: `usage` covers the main loop, while
`modelUsage` and `total_cost_usd` include auxiliary/subagent work. The
[session documentation](https://code.claude.com/docs/en/sessions#name-your-sessions)
also documents background title generation for unnamed sessions. Attribution of
this particular difference to title generation is an inference, not a trace fact.

`accounting.py` validates each scope separately. Deduplicated visible main-loop
input counters must agree with terminal main-loop usage (retaining the earlier
explicit synthetic-retry rule). Whole-call counters must be nonnegative integers,
at least the main-loop totals; per-model costs must sum to terminal cost. Missing
fields, invalid counters, unexplained main-loop gaps and incomplete tool linkage
still stop execution. Whole-call minus main-loop counts are retained without
inventing auxiliary response counts or assigning their cause.

Offline `recover` writes a separate hash-bound `measurement-recovered.json`, leaving
the original measurement unchanged. After operator review, `run --resume-reviewed
--execute-models` skips that candidate and continues the original frozen schedule,
prompts, tools and runtime. It records the amended controller hashes and checks them
before and after each run. CLI flags remain unchanged, including session naming, so
the treatment does not change halfway through. The original USD 4 allowance includes
the recovered first run. There is no additional or replacement candidate.
