# php-ast-edit — AST-based PHP edits for coding agents

## What this skill solves

Select a PHP symbol, apply a typed change, and review the resulting diff. `php-ast-edit` supports guarded, multi-file transactions, preserves existing formatting by default, and reports the checks it actually ran.

| Name | What it is |
| --- | --- |
| `netresearch/php-ast-edit-skill` | This repository and Composer package |
| `php-ast-edit` | The PHP command-line editor |
| `php-structured-edit` | Agent instructions and a wrapper for that editor |

## Measured: up to 90% fewer tokens

In an **experimental resolver, AST and verification workflow**, a six-file rename in a public PHP project used **90.2% fewer tokens** than text edits with a separate checking step — median 12,212 against 124,133.5, counting cache use. The project's 17 existing tests executed on every final result. One tool call instead of 16, two model rounds instead of 13, 16.4 seconds instead of 37.8. All thirty attempts across the three arms produced correct code. This measures that workflow; it does not establish the same savings for the installed skill or the engine's newer project rename implementation.

That figure is two effects, and both are worth knowing separately:

| | |
| --- | --- |
| Editing by symbol instead of by text | **−75.5%** |
| Letting the tool run the project's checks and report the verdict | **−59.9%** on top |

**What the number is, exactly.** Medians of one task, ten repetitions per arm. Combined tokens including cache reads, which are neither priced nor processed like fresh input — the native **list price fell 66.4%**, not 90.2%. Fresh uncached input barely moved: 92.6% of the difference is cached context the model no longer had to be handed again.

**Where it does not hold.** At fifty files, plain Phpactor refactoring beat the composed route on tokens, time and cost. A small local rename on Haiku cost 66.6% *more*. The arithmetic above [recomputes in the test suite](benchmarks/symbol-intent/results/2026-09-07-real-php/recompute/) from the report's own tables, and the [raw runs and evidence archive](benchmarks/symbol-intent/results/2026-09-07-real-php/) ship with checksums. Every result, including the ones that went the other way, is in [Does this save tokens, calls, or time](#does-this-save-tokens-calls-or-time) below.

## Installation

The source checkout below follows development `main`. Release archives are versioned
snapshots; changes listed as Unreleased require a source checkout until published.

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

## Rename a method by intention

Available on development `main`:

```bash
bin/php-ast-edit rename --method 'App\Checkout::submit' --to placeOrder
```

The command discovers the declaration and submits one guarded transaction. Non-private
methods resolve their hierarchy and callers through the configured Phpactor resolver,
including public methods in final classes. Project checks run through the existing
write pipeline. The default compact report carries the diff, check verdicts and unresolved mentions;
use `--report agent` when an inline diff is unnecessary.

Use one positional project root as an alias for `--path`, or use `--path` explicitly;
do not provide both. `--file` narrows declaration discovery, and `--dry-run` previews.
`--file` does not limit which resolved callers change.
Ambiguous declarations, stale hashes and unresolved reference types are refused.
Private methods retain the lexical scope and its reported limitations. See the
[command contract](skills/php-structured-edit/references/operations.md#direct-method-rename)
for options, mocks and verification semantics.

A [24-run Haiku experiment](benchmarks/agent-economics/results/2026-09-11-intent-command/REPORT.md)
tested this interface and then its default inline diff. In the final comparison,
median tokens fell 10.0% on the small rename and 5.5% across files; wall time rose
17.6% and 27.7%. All task oracles passed. With three repetitions per cell, this is
engineering feedback, not an overall efficiency or cost-saving claim.

## Context requirements

Provide the intended change and any source snapshot used to select targets. `rename`
accepts a method symbol; other operations use file paths and selectors or structural refs.
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

Three response shapes. For `apply`, omitting `report`, or choosing `"full"`, keeps the per-file `verify` layout and the `diff` — the default, and the right one when you want to see the change. `"report": "compact"` emits each verification run once in top-level `verify`, linked from each file's `checkIds`. `"report": "agent"` states what the write did and what it left open — `outcome`, a `checks` tri-state where `none_declared` is not `passed`, failing check output, a per-file `open` list, and `verifications` naming every execution — and carries no diff. Reach for it when a declared check's verdict is what you need; [measured](benchmarks/agent-economics/results/2026-09-10-agent-report/REPORT.md) on an edit with no declared checks, fetching the dropped diff back cost more than it saved. All three report the same checks and outcomes. A successful parse is not proof of correct behavior; run the relevant project tests if they have not already run through configured `verify` commands.

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

`rename_method` has two paths. The lexical path changes a declaration and structurally attributable calls in the same file. Methods needing hierarchy analysis use a project-wide path when selected by name and a pinned Phpactor is configured through `phpactor` in `.php-ast-edit.json` or `PHP_AST_EDIT_PHPACTOR`. It combines project and Composer hierarchy information with resolved call sites, checks each site against the AST, and applies guarded edits in one transaction. Missing ancestors, external method contracts, name collisions and unresolved receiver types can cause refusal. PHP strings and non-PHP mentions are reported for review; neither path proves every runtime reference was found. See the [operation contract](skills/php-structured-edit/references/operations.md#convenience-operations) and [limits and alternatives](docs/limits-and-alternatives.md).

Existing files use format-preserving printing unless the repository declares canonical formatting or the request explicitly selects a printer. Some changed subtrees may still be reprinted. Review the measured diff. [Canonical formatting](skills/php-structured-edit/references/formatting-contract.md) is an optional project-wide choice.

## Does this save tokens, calls, or time

Batching reduces CLI startups. Named selectors can eliminate an `inspect` call. Compact reports avoid repeating the same verification command and diagnostics for every file; they do not shorten the checks themselves. Integrated reports and configured checks can avoid redundant reads and validation. These are capabilities, not a universal cost guarantee.

A contextual patch is a valid baseline and can also batch changes. Small edits may cost more through an AST tool. Full agent savings depend on instruction loading, model output, tool latency, retries, correctness, and caching. [Benchmarks](benchmarks/README.md) provides a reproducible local comparison and a separate protocol for measuring complete agent tasks. No general token or model-round reduction is claimed from a CLI microbenchmark.

The [instruction and discovery experiments](benchmarks/agent-economics/results/2026-09-11-intent-instructions/REPORT.md)
test two ways to reduce the direct command's orchestration overhead: shorter
instructions and explicit delegation of method-family discovery. Neither meets
the prospective token-and-time criterion on both fixtures. Native traces show why
one successful write can still lead to an expensive session: source discovery,
rereads and repeated checks remain. Correct fixture output and faithful completion
claims are evaluated separately.

The [24-run prepared-invocation experiment](benchmarks/agent-economics/results/2026-09-11-exact-invocation/REPORT.md)
gives both AST arms the same selected target metadata, then supplies a complete
command to one. That removes four invocation errors, but median tokens fall 11.6%
on the small task and rise 29.2% across files; median tool calls stay unchanged.
It does not meet the adoption criterion or compare against ordinary text editing.
All 24 code states are correct; 22 final completion claims pass review (corrected
after a second claims audit on September 12).

The [24-run source-excerpt experiment](benchmarks/agent-economics/results/2026-09-12-review-context/REPORT.md)
adds bounded source lines to unresolved rename warnings. Across files, median
tokens fall 15.3%, wall time 16.0% and calls 10%; the small task instead uses 20.8%
more tokens and 4.3% more time. All 24 edits are correct, but only 19 final claims
pass review. These six pairs per task support further investigation, not default
adoption: the feature remains benchmark-only and does not compare AST with text editing.

The [24-run unchanged-file excerpt study](benchmarks/agent-economics/results/2026-09-12-unchanged-context/REPORT.md)
also fails: median paired tokens rise 36.2% on the small task and 13.2% across files;
paired wall time rises 27.3% and 40.0%. All 24 edits are correct, with 23 supported
final explanations. Fewer reads of warning locations are outweighed by more other
reads and repeated checks in these attempts. The filtered context stays experimental.

The [24-run check-reuse instruction study](benchmarks/agent-economics/results/2026-09-12-check-reuse/REPORT.md)
reduces median paired total tokens by 11.8% on the small rename and 31.3% across files;
wall time falls 6.8% and 4.9%. Tool calls are unchanged and 17.0% higher, respectively.
All 24 code outcomes and 23 final explanations pass. Cross-file repeated checks stay
at 6→6, so the proposed mechanism is unconfirmed. The overall registered
criterion fails; this compares short benchmark instructions, not the installed full skill.

The [24-run shared-metadata study](benchmarks/agent-economics/results/2026-09-12-shared-report/REPORT.md)
retains every diff and fact while factoring identical multi-file report metadata.
Cross-file median paired tokens fall 43.7%, wall time 30.9% and tool calls 14.1%.
However, the unchanged single-file A/A control varies sharply (+65.3% paired tokens),
and only 19/24 final explanations are supported despite 24 correct code outcomes.
The quality gate fails; the projection stays experimental and these are not general savings rates.

The [36-run v0.8.0 Haiku pilot](benchmarks/agent-economics/results/2026-09-11-v080-haiku/REPORT.md) shows why the installed workflow needs its own measurement. One small edit saved 31.1% of tokens, while three same-file changes used 38.6% more and an unambiguous cross-file rename used 33.2% more. A separate instruction follow-up also lost. The report retains failed completions, a corrected fixture ambiguity and all raw attempts; the extra method-rename instructions were withdrawn.

The [30-run public-source verification experiment](benchmarks/symbol-intent/results/2026-09-07-real-php/REPORT.md) compares an **experimental semantic rename workflow** with text edits on one six-file PHP extraction. With the same 17 existing tests actually executed on every final result, the integrated workflow used median 1 versus 16 tool calls, 12,212 versus 124,133.5 tokens including cache use, and 16.43 versus 37.76 seconds. All thirty changes were correct; native median list-price cost fell 66.4%. Fresh uncached input was nearly unchanged. These gains apply to this composite resolver, AST and verification experiment, not the installed skill in arbitrary PHP projects. The 90.2% splits into −75.5% from semantic editing and a further −59.9% from integrating the project's checks, so neither half accounts for it alone. The [recomputation](benchmarks/symbol-intent/results/2026-09-07-real-php/recompute/) runs in the test suite and fails if these figures stop following from the report's own tables.

At fifty files the same table reports the opposite: plain Phpactor CLI refactoring used 78,261 tokens against the composed route's 103,123, and won on wall time and cost as well. Reference discovery is worth delegating; building a resolver is not established. See [why the resolver is Phpactor](benchmarks/symbol-intent/README.md).

A [24-session integrated-check trial](benchmarks/agent-economics/results/2026-09-10-integrated-checks/REPORT.md) tested the engine's configured project checks on two small tasks with Haiku and Sonnet. The model ran the check again after its final edit in 12/12 manual-check sessions and 0/12 integrated-check sessions. Across these sessions, median combined tokens fell from 60,443 to 45,499, model rounds from five to four, and wall time from 17.3 to 13.0 seconds. All 12 controls passed the task oracle; 11/12 treatments passed. The remaining treatment made correct PHP edits but left a forbidden `edits.json` behind. These are three repetitions per task/model/arm, with a cheap successful check; they do not establish savings for failing or expensive checks, or for larger projects.

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
