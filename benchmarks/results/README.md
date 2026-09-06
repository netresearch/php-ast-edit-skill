# Recorded measurements

## CLI comparison — 6 September 2026

[Raw samples and environment](cli-2026-09-06.json) were collected from clean commit
[`da7934543231ccd55cd6be8e54a69ffa53de927c`](https://github.com/netresearch/php-ast-edit-skill/commit/da7934543231ccd55cd6be8e54a69ffa53de927c).
The engine, dependencies, and temporary fixtures were on the Linux filesystem under WSL2.
The run used PHP 8.5.10, nikic/php-parser 5.8.0, and Python 3.12.3. Xdebug was loaded with
all modes disabled through `XDEBUG_MODE=off`; the recorded active mode list is `[]`.

Each arm has 30 timed samples after two warmups, with shuffled order and seed `76491`.
The batch size is ten files. Every sample passed the byte-for-byte output oracle; the
fixture's return value and requested return type were independently checked before timing.

| Operation | Median | p95 | Harness commands | Output bytes |
| --- | ---: | ---: | ---: | ---: |
| One AST edit | 30.613 ms | 33.572 ms | 1 | 1,182 |
| One contextual patch + lint | 17.555 ms | 19.026 ms | 2 | 39 |
| Ten files in one AST transaction | 73.391 ms | 75.243 ms | 1 | 11,370 |
| Ten files in one patch + combined lint | 18.279 ms | 19.919 ms | 2 | 390 |
| Ten separate AST invocations | 311.242 ms | 322.930 ms | 10 | 11,820 |
| `inspect` | 22.579 ms | 23.722 ms | 1 | 1,787 |
| Full `contexts` catalog | 21.492 ms | 23.058 ms | 1 | 5,628 |
| `contexts --operation rename_variable` | 17.903 ms | 19.646 ms | 1 | 158 |

Output bytes are the median captured output size. Harness commands count explicit process
launches by this benchmark; they are neither agent tool calls nor a count of all internal
child processes. The batched patch baseline uses one `git apply` and one multi-file
`php -l` invocation, supported by the measured PHP runtime.

The AST batch completes in 23.6% of the time required by ten separate AST invocations,
a **4.24× speedup** within this fixture. The batched AST path still takes **4.02× as long** as the contextual batch
patch plus combined lint. The single AST edit takes **1.74× as long** as its patch baseline.
These results support batching when using the AST tool; they do not establish a general
speed advantage over a competent patch workflow.

The operation-specific help emits **97.2% fewer bytes** than the complete catalog
(158 versus 5,628). It answers one operation question and omits the rest of the catalog.
This is an output-size comparison, not a measurement of tokenizer counts or model billing.

## Reproduce this configuration

Use a clean checkout of the linked commit on the Linux filesystem with the recorded PHP
and parser versions installed. Keep dependencies in that same filesystem and avoid
concurrent local test or build work. Write the result outside the checkout so provenance
remains clean:

```bash
XDEBUG_MODE=off python3 benchmarks/cli_microbenchmark.py \
  --repetitions 30 --warmups 2 --files 10 --seed 76491 \
  --include-operation-help --output /tmp/php-ast-cli.json
jq '.source_commit, .working_tree_dirty, .environment, .parameters, .summary' /tmp/php-ast-cli.json
```

The timer includes process startup, command execution, and output capture. Fixture setup,
restoration, and the independent output comparison are outside it. The JSON retains every
sample, actual executable path and hash, runtime versions, and lint mode. Storage and
runtime configuration affect these measurements; a Windows-mounted engine checkout can
have substantially different startup costs. See the [full protocol](../README.md).

## What remains unmeasured

No completed model A/B campaign is represented here. Model requests, instruction loading,
cache usage, billed tokens, repair loops, and time until a real project task is accepted
require separate agent runs. The executable tasks and oracle self-tests provide evaluation
infrastructure. They do not establish token savings, fewer model rounds, or general
application correctness.
