# Native Claude pilot: full PHP AST skill versus contextual editing

In this pilot, the full skill did not save tokens. Across six matched pairs, it
used 195,701 input-plus-output tokens versus 111,385 for ordinary contextual
editing: **75.70% more**. Every individual pair used more tokens with the skill.
This describes two tiny seed tasks, not arbitrary PHP maintenance work.

| Measured quantity, six runs per arm | Contextual editing | Full skill + CLI |
| --- | ---: | ---: |
| Input, including cache reads and writes | 107,950 | 191,100 |
| Of which cache reads | 95,338 | 170,499 |
| Of which cache writes | 12,582 | 20,563 |
| Fresh uncached input | 30 | 38 |
| Generated output, native provider semantics | 3,435 | 4,601 |
| Input plus output | 111,385 | 195,701 |
| Native tool invocations | 24 | 29 |
| Failed tool invocations, retained in all totals | 0 | 2 |
| Explicit AST editor invocations, transcript-reviewed | 0 | 8 |
| Unique primary response IDs | 24 | 32 |
| Native CLI `num_turns` sum | 30 | 35 |
| Candidate wall seconds | 85.343 | 111.288 |
| Mean candidate wall seconds | 14.224 | 18.548 |
| Native list-price USD estimate | 0.1557084 | 0.2436567 |
| External lint, scope and runtime oracle passes | 6/6 | 6/6 |
| Timeouts | 0 | 0 |

The native USD estimate was 56.48% higher and observed candidate wall time 30.40%
higher with the skill. These are native list-price estimates under a Claude Max
subscription, not proof of additional charges. All twelve task runs together
reported USD 0.3993651 and 196.631 seconds of candidate wall time. A separate
capability smoke reported USD 0.009033; it is excluded from paired task results.

| Task, three repetitions per arm | Contextual tokens | Full-skill tokens | Skill difference |
| --- | ---: | ---: | ---: |
| Rename local variable and closure capture | 54,572 | 88,878 | +62.86% |
| Add a constant in two files | 56,813 | 106,823 | +88.03% |

Paired differences ranged from +61.72% to +135.25%. The two recovered errors both
came from guessing `position: "first"` for `add_member`; the engine rejected this
and the agent retried with `"start"`. They remain in all totals. The local rename
had no failed tool calls in either arm and still used more tokens with the skill.
The complete skill was supplied in the initial context; none of the twelve
candidates loaded an additional reference file. These are observations about this
instruction-and-CLI workflow, including onboarding and repair overhead.

## Controls and evidence

- Source and task oracle snapshot:
  `33f85b8ef83d8dda81491c82fa86d18046168063`. The engine, complete skill and
  reference files were copied from that commit. Existing vendor dependencies were
  copied, not reinstalled. Runtime file hashes are retained.
- Claude Code 2.1.261, requested and reported `claude-sonnet-4-6`, effort `medium`.
  A finer serving snapshot is not exposed by the native CLI.
- Fresh process and Git fixture workspace for each observation. Every repetition
  of a task started with the same SHA-256 source hashes. Two tasks times two arms
  times three repetitions gave twelve calls; seeded order balanced which arm
  started each of the six pairs.
- Identical Bash, Edit, Read and Write tools. Every native init event confirms
  empty plugins, automatically loaded skills and MCP servers. Safe mode disabled
  global hooks and instruction discovery. The treatment received the complete
  SKILL.md explicitly; the baseline explicitly allowed contextual editing.
- Runtime and fixtures were on the Linux filesystem. Runs were sequential and
  started after the concurrent packaging tests finished. Preparation took 29.224
  seconds, recorded separately; external grading and AI review are also outside
  candidate wall time. No complete native tool execution intervals were exposed,
  so no invented tool-duration metric is reported.
- Limit per candidate: USD 0.75 native list estimate and 120 seconds. All
  candidates completed before either limit. Exit codes, native terminal result,
  raw JSON stream, stderr, prompts, argv, hashes, diffs and external oracle JSON
  are retained for every run.
- Final native `modelUsage` values supply the token counts. Input is fresh input
  plus cache-read plus cache-created input; cache reads are not added twice.
  Output uses the provider's generated-output counter; thinking-token detail is
  retained but is not added again. All twelve campaign records contain only the
  requested Sonnet model, so primary-model and all-model totals are identical.
  The isolated smoke also reported an auxiliary Haiku call; its raw usage was
  retained and excluded from the task comparison. Both campaign arms used the
  same explicit name and disabled prompt suggestions.

## Acceptance and limits

All twelve independent runtime oracles passed. The pilot operator's AI review of
all diffs confirms the requested local rename, including closure capture, while
preserving the named property, method and literal. For the two-file task, both
classes receive a public constant of value 2 and retain their original `id()`
return values. Contextual edits add a blank separator line; AST edits place the
constant at the start or end without that extra blank. These changes are confined
to the request. The independent root-agent AI review also accepts all twelve outputs.
**Human acceptance remains pending; AI review is not human review.**

Provider cache state was not controlled and is **unknown**, despite fresh sessions.
Actual cache counters are supplied. This is not a documented warm-cache experiment
or an assertion of cold onboarding. No official importer record was fabricated:
its schema requires a cold/warm label and accepted human review, which these
observations cannot honestly supply yet.

The surrounding harness isolated candidate context, not operating-system access.
No candidate was given evaluator paths or answer keys; tool transcripts show no
attempt to read them. One candidate (`run05`) used `/tmp/edits.json` for its own
transaction payload; the exact payload is retained as external scratch evidence.
This limits any claim of a strict filesystem sandbox.

Three repetitions on two seed tasks do not establish a general efficiency
percentage, a production performance forecast, or a statistically representative
comparison. There is no CLI-reference-only arm, no larger repository task, and no
alternative model in this pilot. The results also do not measure prevention of
concurrency mistakes or unsafe structural edits. They do show that the full skill
cannot presently claim token savings for these measured simple tasks.

See [README.md](README.md) for published evidence, redactions and reproduction.
