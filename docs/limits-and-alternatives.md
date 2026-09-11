# Limits and alternatives for PHP refactoring

Choose the tool by the task and the evidence available in the project.

| Task | Useful approach | Limit to account for |
| --- | --- | --- |
| Small change with known textual context | Contextual patch plus project checks | Context can become stale; tests determine behavior |
| Typed member/argument/body change | php-ast-edit selector or inspected node | Some changed syntax is reprinted |
| Related local edits across files | One php-ast-edit transaction | Per-file atomic writes do not provide global reader isolation |
| Rename with project-wide symbol resolution | php-ast-edit's configured Phpactor path, or a PHP LSP/IDE | Resolution has project and type-information limits; reflection and dynamic dispatch may evade it |
| Repeatable framework/version migration | Rector rules and project tests | Rule applicability and target behavior need validation |
| Simple discovery or explanation | Search, LSP, or code reading | No edit engine is needed |

`set_name` changes a selected syntactic name; it is not a refactoring engine.
`rename_variable` adds lexical scope analysis. `rename_method` uses a lexical path for
a private method or a method in a final class, provided the class has no parent,
implemented interfaces or trait composition; that path changes only structurally
attributable calls in the same file. Methods needing
hierarchy analysis use the project path when selected by name (`method:Class::name`) and
the pinned Phpactor is configured through `phpactor` in `.php-ast-edit.json` or
`PHP_AST_EDIT_PHPACTOR`. The engine reads the project's sources and Composer class tables,
resolves call sites through Phpactor, checks their ranges against parsed nodes, and
prepares the declarations and calls as one guarded transaction.

The project path refuses recognized unsafe cases, including external method contracts,
missing ancestors, relevant trait declarations, hierarchy name collisions and calls whose
receiver type the resolver cannot determine. It operates on project files known to Git
outside the configured exclusions. PHP strings and non-PHP mentions are listed for review,
not automatically treated as references to the selected method. Opting into `mocks: true`
also changes matching PHPUnit mock method strings without resolving the mocked class;
another class's same-named method can therefore be affected. Review those edits explicitly.
Neither path establishes every possible runtime binding or caller outside the project.
Read the [rename contract](../skills/php-structured-edit/references/operations.md#convenience-operations),
review residual references and warnings, and test the behavior the request changes.

Parser validation checks grammar. Host lint additionally checks interpreter constraints
such as duplicate declarations. A selected newer target version can be parseable while
host lint is skipped; only the target runtime can establish its executability. Neither
check resolves missing classes, wrong return values, external callers, or business rules.

Multi-file preparation reduces partial edits caused by validation failures. During commit,
individual files become visible one at a time. Rollback restores transaction-managed paths
when writing or formatting fails. Arbitrary side effects of configured external commands
are outside that scope. Verification failures leave edits available for diagnosis.

Canonical printing may alter layout and has documented comment edge cases. Preserve
formatting by default, review diffs, and explicitly decide whether canonical formatting
fits the repository. Do not interpret minimal snippets as a guarantee of minimal output.

For efficiency, compare time and cost **until the task passes its independent oracle**.
Include failed attempts and setup. The [benchmark protocol](../benchmarks/README.md)
separates this question from raw CLI startup performance.
