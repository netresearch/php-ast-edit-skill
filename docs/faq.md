# PHP AST editing: frequently asked questions

## What does php-ast-edit do?

It edits PHP syntax trees through a command-line JSON API. Select a named symbol or an
inspected node, submit a typed operation, and receive the resulting diff and check results.
The `php-structured-edit` skill teaches an agent this workflow.

## Does it reduce tokens and tool calls?

It can remove coordinate inspection when a symbol selector suffices, and it can combine
multiple edits in one invocation. Those features do not prove lower total token use.
Instructions, JSON responses, retries, and caching also affect cost. See the
[measurement protocol and local results](../benchmarks/README.md); complete agent A/B
measurements must be reported separately from process timings.

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

## Does rename_method find all references?

No. It operates on the selected declaration and structurally attributable calls in the
same file. Other receivers, inheritance relationships, dynamic names, and callers in other
files require further analysis. Read the effect report and use an appropriate LSP or
project-wide refactoring tool for broader symbol resolution.

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
