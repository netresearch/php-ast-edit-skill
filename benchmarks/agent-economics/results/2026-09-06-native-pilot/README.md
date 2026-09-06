# Twelve observed native-agent runs

Read [REPORT.md](REPORT.md) for the bounded result: the complete skill used 75.70%
more input-plus-output tokens on these two small tasks. Both arms passed all six
runtime outcomes. Two recovered AST errors are included, not discarded.

## Verify without model calls

From the repository root, with Git history containing commit
`33f85b8ef83d8dda81491c82fa86d18046168063`, PHP, Python 3.12+ and jq installed:

```bash
python3 benchmarks/agent-economics/results/2026-09-06-native-pilot/verify.py
```

This verifies the published checksums, derives accounting from the sanitized
native events, recomputes the complete summary, applies all twelve diffs to their
original fixture bytes, and runs the grader and PHP oracles from the measured
commit. Temporary files stay outside the repository. It makes **zero model calls**.
It verifies retained evidence and behavior, not the provider's authorship or billing.

## Reproduce preparation, then optionally run a new experiment

`pilot.py` is a portable derivative of the original runner. Configuration
roots and executable selection were parameterized; formatting was normalized for
the repository and the existing subprocess `check=False` default made explicit.
The portable derivative also rejects missing or invalid required input/output/cache
counters, preserving raw evidence and stopping instead of filling them with zero.
Optional thinking-token detail is omitted from normalized totals if unavailable.
All twelve historical records contain the required fields; their numbers are unchanged.
The original executed runner is archived as
[runner-original.py.txt](runner-original.py.txt), with identifying path constants
replaced. The original byte hash is in [source-provenance.json](source-provenance.json).

Set a fresh output directory and a source checkout containing the measured commit
and installed `vendor/` dependencies. From the repository root:

```bash
export PHP_AST_PILOT_SOURCE="$PWD"
export PHP_AST_PILOT_OUTPUT="$(mktemp -d /tmp/php-ast-pilot-reproduction.XXXXXX)"
export PHP_AST_PILOT_CLAUDE=claude
python3 benchmarks/agent-economics/results/2026-09-06-native-pilot/pilot.py prepare
```

Preparation makes no model calls. It extracts the pinned engine, skill and grader,
copies existing dependencies, verifies identical paired fixtures, and records a
seeded schedule and complete prompts. It refuses to reset existing evidence.
The measured parser was `nikic/php-parser` v5.8.0 at source reference
`044a6a392ff8ad0d61f14370a5fbbd0a0107152f`; see [dependencies.json](dependencies.json)
and [runtime-sha256.json](runtime-sha256.json). Compare recorded runtime hashes;
different dependency bytes are a different environment. No dependencies are installed
or user configuration edited by this runner.

Only an operator who intends another twelve model calls should run:

```bash
python3 benchmarks/agent-economics/results/2026-09-06-native-pilot/pilot.py run
```

That command uses existing CLI authentication and invokes Claude sequentially with
the recorded model, effort, tools and limits. Each call is capped at USD 0.75 in
native list-price estimates and 120 seconds. Fresh processes do not establish a
cold provider cache. A new provider serving build, CLI version, cache state or
dependency set can change results; this command cannot guarantee historical tokens.
Review every new diff and retained failure separately. The checked-in observations
are never overwritten.

## Retained and omitted fields

[config.json](config.json), [schedule.json](schedule.json) and per-run prompts retain
the actual instructions and order. `{PILOT_ROOT}`, `{SOURCE_ROOT}` and `{CLAUDE_CLI}`
replace the original absolute paths. `initial-fixtures.json` stores exact initial
PHP bytes as data; each run retains its diff, initial/final hashes and oracle JSON.
[task-source.json](task-source.json) holds the two task records from the pinned
manifest, including evaluator answers; never supply it to a candidate.

Each `runs/runNN/native.jsonl` is an explicit allowlist export of the native CLI
stream. It retains init model/tool/isolation fields, assistant text and tool calls,
tool outcomes, assistant usage, and the final native usage/modelUsage, turns,
durations and list-price estimate. Numerical accounting values are unchanged.
Response and tool IDs are replaced with stable per-run `response-NN` and `tool-NN`
values, preserving request/tool counts and tool-result linkage.

Session IDs, UUIDs, transport request IDs, sockets, auth-source fields, timestamps,
account/rate-limit events, internal diagnostic/thinking blocks and duplicate tool
result metadata are omitted. Original streams, native result files and runner
remain with the operator outside the repository. Their hashes are retained separately
from the published hashes. Existing `config_sha256` fields refer to the original
pre-redaction config bytes; [SHA256SUMS](SHA256SUMS) covers the published files.
The scoped `.gitattributes` preserves blank context-line bytes in the actual patch
evidence; other whitespace rules remain enabled. The Markdown review bundle trims
presentation whitespace and is not the canonical patch source.

The initial capability smoke is excluded from the twelve-run comparison. It
reported an auxiliary model call; all twelve campaign modelUsage objects contain
only the requested Sonnet model, so primary and all-model totals coincide.

## Review and execution boundary

Both the pilot operator AI and an independent root AI reviewed all twelve final
diffs and explanations and accepted the output scope. **Human review is pending.**
These are not accepted records for the older cold/warm-and-human-review importer.
No claim of general savings, statistical representativeness or provider billing
authentication follows from this small pilot.

The runner isolates supplied context, not operating-system access. One candidate
used `/tmp/edits.json` as its transaction payload; its commands remain in the trace.
The runtime oracle executes trusted repository-owned PHP in disposable directories.
The verifier and runner accept operator-selected local paths and executable argv,
not remote jobs. This follows the [existing evaluator trust boundary](../../../TRUST.md).
Do not use these scripts as an adversarial sandbox or expose them as a service.
