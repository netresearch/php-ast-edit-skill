# PHP AST editing: frequently asked questions

## What does php-ast-edit do?

It edits PHP syntax trees through a command-line JSON API. Select a named symbol or an
inspected node, submit a typed operation, and receive the resulting diff and check results.
The `php-structured-edit` skill teaches an agent this workflow.

## Does it reduce tokens and tool calls?

Sometimes. A [24-session trial](../benchmarks/agent-economics/results/2026-09-10-integrated-checks/REPORT.md)
of configured project checks reduced median combined tokens from 60,443 to 45,499 and
model rounds from five to four. Models reran the check after the last edit in 12/12
manual-check sessions and 0/12 integrated-check sessions. The task oracle passed in
12/12 controls and 11/12 treatments; one treatment left a forbidden `edits.json` despite
correct PHP changes. This covers two small tasks, two models and three repetitions per
task/model/arm, with successful cheap checks.

In the earlier [follow-up experiments](../benchmarks/agent-economics/results/2026-09-06-efficiency/REPORT.md),
an experimental compact adapter reduced Sonnet's median token use by 39% and tool calls
from six to two on the two-file seed task. Small local renames cost more tokens, and a
public TYPO3 rename exposed recovery loops, timeouts and text-edit bypasses. The compact
adapter is benchmark tooling; these results are not a claim about the default skill.

Instructions, responses, retries and caching all affect the result. Three repetitions
per task/model/arm support descriptive comparisons only. Input includes cache reads and
writes; cache conditions are unknown. Correct output and guarded AST workflow adherence
are reported separately. The [original pilot](../benchmarks/agent-economics/results/2026-09-06-native-pilot/REPORT.md)
is retained: its complete-skill arm used 75.7% more tokens. See the
[measurement protocol](../benchmarks/README.md) before drawing broader conclusions.

## Should an agent read the whole AST instead of PHP source?

A serialized AST can be substantially larger than the source and still consumes model
tokens. The experimental adapter uses the parser to select a complete method, its
comments and declaration context, then returns PHP source plus a compact outline.
Full source remains available. A class selector still returns the whole class, so
focused mode alone does not guarantee a smaller view. The follow-up report separates
autonomous selector choices from a directed initial-method-read experiment.

## Is AST editing always safer than a patch?

It constrains edits to syntax nodes and can reject stale snapshots or unsupported
operations before writing. A contextual patch plus appropriate tests is also a valid
workflow. Neither syntax trees nor patches prove application behavior. Binding-aware
renames and project tests remain necessary for semantic changes.

## Does a successful result mean valid PHP?

`parsed` reports parser success. The legacy `valid` field is a deprecated alias for that
same check. `validation.lint` describes host-interpreter lint, including skips; `verify`
lists configured project checks. These fields must not be collapsed into a correctness
claim. Runtime tests establish only the behavior they cover.

## Must I reformat my project first?

No. Existing files use format-preserving printing by default. Review the diff because
changed subtrees may still reflow. Canonical formatting is optional and should be adopted
as a separately reviewed formatting change.

## Can I adopt it incrementally?

| Stage | Setup | What the agent gains |
| --- | --- | --- |
| Structured edits | Install the engine; preserve existing formatting | Named targets, typed changes and guarded batches |
| Integrated checks | Configure the project's formatter and `verify` commands | One report containing the edit and the checks actually run |
| Canonical repository | Explicitly adopt normalization and a formatting gate | A shared printer/formatter fixed point, when the project supports it |

The first stage does not require `doctor` or repository-wide normalization. Add later
stages when their benefits justify the setup and review cost for your project.

## Does it replace Rector or PHPStan?

No. Rector supplies migration and refactoring rules; PHPStan analyzes PHP programs.
`php-ast-edit` supplies structured write operations. Existing project checks can run through
`verify`, including PHPStan. Combining the calls does not eliminate their execution time.

## Does rename_method find all references?

It supports project-wide resolution, but does not guarantee that every runtime reference
is found. The lexical path changes the selected declaration and structurally attributable
calls in the same file. Methods needing hierarchy analysis use a project path when named
by selector and the pinned Phpactor is configured through `phpactor` in
`.php-ast-edit.json` or `PHP_AST_EDIT_PHPACTOR`. It combines project and Composer hierarchy
information with resolved call sites, then applies guarded edits in one transaction.

Missing ancestors, external method contracts, hierarchy name collisions and unresolved
receiver types can cause refusal. Strings, configuration and template mentions are
reported for review, and callers outside the project remain outside its scope. Optional
`mocks: true` changes matching PHPUnit mock strings without resolving the mocked class;
review same-named methods of other classes before enabling it. See the
[limits](limits-and-alternatives.md) and
[operation contract](../skills/php-structured-edit/references/operations.md#convenience-operations).

## Which installation should I choose?

Use a source checkout for development, a Composer dependency for a project toolchain, or
a PHAR/archive that bundles the engine for an agent environment. The
[installation guide](installation.md) distinguishes these paths and their version limits.

## Does the tool send my source code to a service?

The editor parses and changes files locally. It does not call a model service. Your coding
agent and any formatter or verification commands you configure have their own behavior.

## Can the hook prevent every text edit?

No. The optional hook recognizes common edit commands, has documented bypasses, and is
not a security boundary. It is a workflow aid; see the
[enforcement reference](../skills/php-structured-edit/references/enforcement.md).
