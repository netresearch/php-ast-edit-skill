# php-ast-edit — AST-based PHP edits for coding agents

## What this skill solves

Select a PHP symbol, apply a typed change, and review the resulting diff. `php-ast-edit` supports guarded, multi-file transactions, preserves existing formatting by default, and reports the checks it actually ran.

| Name | What it is |
| --- | --- |
| `netresearch/php-ast-edit-skill` | This repository and Composer package |
| `php-ast-edit` | The PHP command-line editor |
| `php-structured-edit` | Agent instructions and a wrapper for that editor |

## Measured: up to 90% fewer tokens

On a six-file rename in a public PHP project, with the project's 17 existing tests actually executed on every final result, the semantic-plus-verified route used **90.2% fewer tokens** than text edits with a separate checking step — median 12,212 against 124,133.5, counting cache use. One tool call instead of 16, two model rounds instead of 13, 16.4 seconds instead of 37.8. All thirty attempts across the three arms produced correct code.

That figure is two effects, and both are worth knowing separately:

| | |
| --- | --- |
| Editing by symbol instead of by text | **−75.5%** |
| Letting the tool run the project's checks and report the verdict | **−59.9%** on top |

**What the number is, exactly.** Medians of one task, ten repetitions per arm. Combined tokens including cache reads, which are neither priced nor processed like fresh input — the native **list price fell 66.4%**, not 90.2%. Fresh uncached input barely moved: 92.6% of the difference is cached context the model no longer had to be handed again.

**Where it does not hold.** At fifty files, plain Phpactor refactoring beat the composed route on tokens, time and cost. A small local rename on Haiku cost 66.6% *more*. The arithmetic above [recomputes in the test suite](benchmarks/symbol-intent/results/2026-09-07-real-php/recompute/) from the report's own tables, and the [raw runs and evidence archive](benchmarks/symbol-intent/results/2026-09-07-real-php/) ship with checksums. Every result, including the ones that went the other way, is in [Does this save tokens, calls, or time](#does-this-save-tokens-calls-or-time) below.

## Installation

The source checkout below follows development `main`. Published v0.7.0 archives
remain unchanged; repaired release assets require a subsequent publication.

Requirements: PHP 8.2+ with JSON and tokenizer, Composer 2.2+, and Git. The executable example also uses Bash and `jq`. Installation needs network access; local editing does not.

```bash
git clone https://github.com/netresearch/php-ast-edit-skill.git
cd php-ast-edit-skill
composer install --no-interaction
bin/php-ast-edit help
bash docs/quickstart.sh
```

The example creates a temporary PHP class **through the CLI**, adds a method using a named selector, checks the return value at runtime, and displays the diff. It removes its temporary files afterwards. No repository-wide formatting setup is required.

Use `bin/php-ast-edit` inside a source checkout. Use `vendor/bin/php-ast-edit` when installed into another project through Composer. Installing agent instructions alone does not necessarily install the executable. See [installation](docs/installation.md) for Composer VCS, release archives, and skill setup.

## Context requirements

Provide the file paths, intended change, and any source snapshot used to select targets.
The engine requires a writable working tree and the local dependencies above. Project
formatting and verification commands are optional configuration.

## Expected outputs

A guarded source edit, a measured diff, operation effects, accumulated warnings, and
separate parser, lint, and project-check statuses. Inspect requests return node ancestry
and the source hash; rejected requests return machine-readable errors.

## Example prompts

- “Add a `now()` method returning `\DateTimeImmutable` to `App\Clock`.”
- “Rename `$nonce` inside `Cache::key()`; preserve the property and log strings.”
- “Replace the third argument in this factory call with `$this->context`.”

## Apply several changes in one call

Suppose `src/Clock.php` contains:

```php
<?php
namespace App;
final class Clock {}
```

Send this JSON to `php-ast-edit apply --input edits.json`:

```json
{
  "files": [{
    "path": "src/Clock.php",
    "edits": [{
      "target": {"select": "class:Clock"},
      "operation": "add_member",
      "php": "public function now(): \\DateTimeImmutable { return new \\DateTimeImmutable(); }"
    }, {
      "target": {"select": "class:Clock"},
      "operation": "add_member",
      "php": "public const TIMEZONE = 'UTC';"
    }]
  }]
}
```

Use a file-level `sha256` guard when editing a previously read snapshot. Selectors identify named declarations without a coordinate lookup. For an expression or statement, `inspect --file src/Clock.php --line 4 --column 10` returns node ancestry, structural refs, and the snapshot hash. Ambiguous selectors fail rather than choosing the first match. Related changes across files belong in the same `files` array.

Three response shapes. Omitting `report`, or choosing `"full"`, keeps the per-file `verify` layout and the `diff` — the default, and the right one when you want to see the change. `"report": "compact"` emits each verification run once in top-level `verify`, linked from each file's `checkIds`. `"report": "agent"` states what the write did and what it left open — `outcome`, a `checks` tri-state where `none_declared` is not `passed`, failing check output, a per-file `open` list, and `verifications` naming every execution — and carries no diff. Reach for it when a declared check's verdict is what you need; [measured](benchmarks/agent-economics/results/2026-09-10-agent-report/REPORT.md) on an edit with no declared checks, fetching the dropped diff back cost more than it saved. All three report the same checks and outcomes. A successful parse is not proof of correct behavior; run the relevant project tests if they have not already run through configured `verify` commands.

Use `scope: "project"` for checks such as PHPStan that should use their configured project paths, including after file deletions. Use `scope: "changed_files"` for commands that accept the changed, existing file paths through `{files}`. Configure these in `.php-ast-edit.json`; see the [verification contract](skills/php-structured-edit/references/operations.md#verification-configuration).

## Use when

- Add a member, parameter, type, attribute, statement, or argument without locating text ranges.
- Edit several symbols or files with shared preconditions and one CLI startup.
- Change a PHP string literal without modifying neighboring PHP syntax.
- Reject stale source, ambiguous targets, malformed snippets, and recognized unsafe rename cases before writing.
- Create and delete files through the same transaction API.

Search remains your choice: ripgrep, ast-grep, an LSP, or normal code reading. The [operation reference](skills/php-structured-edit/references/operations.md) lists all primitives, shorthands, selectors, and snippet contexts. `php-ast-edit contexts` is the executable catalog.

## Guarantees and limits

| Check | What it establishes |
| --- | --- |
| SHA-256 and target guards | The selected snapshot and expected syntax still match |
| Parser validation | Output can be parsed by the configured PHP parser |
| Host PHP lint, when reported as passed | Output passes `php -l` on the reported runtime |
| Configured `verify` results | The named project commands passed or failed |
| Runtime tests | Only the behavior those tests exercise |

All files are prepared and parsed before the first write. Files are rechecked against their snapshots before writing. Each file uses a temporary file and rename; failures during writing or formatting trigger rollback. This is **not** an operating-system-wide atomic commit: concurrent readers can observe intermediate file states, and external command side effects are outside the rollback boundary. Verification failures leave the edit available for repair and make the CLI fail.

Method renaming is scoped to a declaration and structurally attributable calls in the same file. It is not project-wide type resolution. Dynamic dispatch, reflection, external callers, inheritance, and variable binding require care; read the [limits and alternatives](docs/limits-and-alternatives.md).

Existing files use format-preserving printing unless the repository declares canonical formatting or the request explicitly selects a printer. Some changed subtrees may still be reprinted. Review the measured diff. [Canonical formatting](skills/php-structured-edit/references/formatting-contract.md) is an optional project-wide choice.

## Does this save tokens, calls, or time

Batching reduces CLI startups. Named selectors can eliminate an `inspect` call. Compact reports avoid repeating the same verification command and diagnostics for every file; they do not shorten the checks themselves. Integrated reports and configured checks can avoid redundant reads and validation. These are capabilities, not a universal cost guarantee.

A contextual patch is a valid baseline and can also batch changes. Small edits may cost more through an AST tool. Full agent savings depend on instruction loading, model output, tool latency, retries, correctness, and caching. [Benchmarks](benchmarks/README.md) provides a reproducible local comparison and a separate protocol for measuring complete agent tasks. No general token or model-round reduction is claimed from a CLI microbenchmark.

The [30-run public-source verification experiment](benchmarks/symbol-intent/results/2026-09-07-real-php/REPORT.md) compares an **experimental semantic rename workflow** with text edits on one six-file PHP extraction. With the same 17 existing tests actually executed on every final result, the integrated workflow used median 1 versus 16 tool calls, 12,212 versus 124,133.5 tokens including cache use, and 16.43 versus 37.76 seconds. All thirty changes were correct; native median list-price cost fell 66.4%. Fresh uncached input was nearly unchanged. These gains apply to this composite resolver, AST and verification experiment, not the installed skill in arbitrary PHP projects. The 90.2% splits into −75.5% from semantic editing and a further −59.9% from integrating the project's checks, so neither half accounts for it alone. The [recomputation](benchmarks/symbol-intent/results/2026-09-07-real-php/recompute/) runs in the test suite and fails if these figures stop following from the report's own tables.

At fifty files the same table reports the opposite: plain Phpactor CLI refactoring used 78,261 tokens against the composed route's 103,123, and won on wall time and cost as well. Reference discovery is worth delegating; building a resolver is not established. See [why the resolver is Phpactor](benchmarks/symbol-intent/README.md).

A [twelve-session trial](benchmarks/agent-economics/results/2026-09-10-agent-report/REPORT.md) tested whether recommending the compact `report: "agent"` response shape saves anything. It does not, on an edit with no declared checks: Sonnet paid 71% more tokens and 67% more model rounds, because the mode withholds the diff and the model fetched it back with an extra call. The recommendation was withdrawn; the mode stays for the case it is for.

The separate [20-run result-guidance trial](benchmarks/symbol-intent/results/2026-09-07-guidance/REPORT.md) found **no additional savings** from extra continuation advice: median later calls stayed at three, while observed token and time medians rose 46.4% and 25.8%. All twenty edits and final test runs passed. The optional output bundle remains experimental; this trial did not load or measure the revised skill.

A further [20-run entrypoint trial](benchmarks/symbol-intent/results/2026-09-07-entrypoint/REPORT.md) tested a short instruction explaining that the agent can request a named rename directly. Both arms already needed median zero preparatory calls and one total tool call. The added paragraph did not meet the prospective adoption rule; observed token and time medians were 2.3% and 3.5% higher. All twenty changes and final test runs passed. The current entrypoint remains unchanged, and this selected task does not measure the installed skill or generalize to other edits.

The [follow-up experiments](benchmarks/agent-economics/results/2026-09-06-efficiency/REPORT.md) test an **experimental compact adapter**, including mandatory read-bound revisions. On the two-file seed task, Sonnet used a median 14,449 versus 23,715 tokens (**39% fewer**) and two versus six tool calls. Small local renames used more tokens; a public TYPO3 rename also exposed costly recovery loops and four timeouts across the two public-task phases. Results depend on task and model. The report retains every failure and separates correct output from guarded AST workflow adherence. The adapter is benchmark tooling, not the installed skill's default interface.

The [first native agent pilot](benchmarks/agent-economics/results/2026-09-06-native-pilot/REPORT.md) remains unchanged: the complete skill used **75.7% more tokens** than contextual edits across six runs per arm. All twelve outputs passed their task oracles, but all six skill runs omitted snapshot hashes. Both studies use three repetitions per task/model/arm, include cache reads and writes, and have unknown provider cache conditions. Independent AI review is recorded separately from pending human acceptance; neither study establishes a general savings percentage.

## Why this is a skill (model delta)

Value categories: tool-boundary discipline and failure recovery. An agent unfamiliar with this CLI may guess operation arguments or omit snapshot guards; the [task evals](skills/php-structured-edit/evals/evals.json) test these behaviors. They are evaluation definitions, not measured model deltas.

The [skill](skills/php-structured-edit/SKILL.md) gives a short selector-first workflow and loads detailed references only when needed. It requires AST writes when active; decide whether that workflow suits your project. The optional [enforcement hook](skills/php-structured-edit/references/enforcement.md) catches common text-edit patterns. It is a linter-like aid that can be bypassed, not a security sandbox.

The skill's [task evaluations](skills/php-structured-edit/evals/evals.json) assess outcomes and guards without prescribing redundant inspection or formatting calls. [Executable fixture cases](benchmarks/tasks.json) supply runtime oracles; [routing cases](skills/php-structured-edit/evals/eval_queries.json) include tasks that should not activate the skill. These definitions are not results of completed model evaluations.

## Documentation

- [Installation and troubleshooting](docs/installation.md)
- [Executable quickstart](docs/quickstart.sh)
- [Frequently asked questions](docs/faq.md)
- [Limits and comparison with patch, LSP, and Rector](docs/limits-and-alternatives.md)
- [Measurements and agent evaluation protocol](benchmarks/README.md)
- [Full operation reference](skills/php-structured-edit/references/operations.md)

## Contributing

```bash
bash tests/run.sh
python3 benchmarks/agent_benchmark.py self-test
python3 benchmarks/cli_microbenchmark.py --repetitions 30 --output /tmp/php-ast-benchmark.json
```

The suite includes grammar, semantic regression, transaction, formatting, CLI, distribution, and documentation examples. Supported host runtimes are PHP 8.2–8.5; newer target syntax still needs validation on its intended runtime. See [AGENTS.md](AGENTS.md), [CHANGELOG.md](CHANGELOG.md), and the [contribution template](.github/pull_request_template.md).

## Related skills

 [php-modernization](https://github.com/netresearch/php-modernization-skill) for modernization decisions and [file-search](https://github.com/netresearch/file-search-skill) for discovery.

Classification: `action_level: modifies_files`; `risk_level: medium`.

Checkpoints: none (justified — workflow adherence requires tool traces; executable fixtures
and distribution tests cover observable outcomes). When discovery descriptions change,
update the [marketplace](https://github.com/netresearch/claude-code-marketplace) entry in
the corresponding release process.

## License

Project code, including benchmark tooling, workflows and executable tests: [MIT](LICENSE-MIT). Documentation and skill content: [CC-BY-SA-4.0](LICENSE-CC-BY-SA-4.0). Public TYPO3 extension source and encoded reference source in the benchmark evidence retain **GPL-2.0-or-later**, with original notices and license copies in the evidence bundle.

Developed and maintained by [Netresearch DTT GmbH](https://www.netresearch.de/).
