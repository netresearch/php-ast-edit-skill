# Limits and alternatives for PHP refactoring

Choose the tool by the task and the evidence available in the project.

| Task | Useful approach | Limit to account for |
| --- | --- | --- |
| Small change with known textual context | Contextual patch plus project checks | Context can become stale; tests determine behavior |
| Typed member/argument/body change | php-ast-edit selector or inspected node | Some changed syntax is reprinted |
| Related local edits across files | One php-ast-edit transaction | Per-file atomic writes do not provide global reader isolation |
| Rename with project-wide symbol resolution | A PHP LSP/IDE with reference resolution | Reflection and dynamic dispatch may still evade static analysis |
| Repeatable framework/version migration | Rector rules and project tests | Rule applicability and target behavior need validation |
| Simple discovery or explanation | Search, LSP, or code reading | No edit engine is needed |

`set_name` changes a selected syntactic name; it is not a refactoring engine.
`rename_method` and `rename_variable` add scoped analysis and reject recognized unsafe
cases. They do not establish all possible runtime bindings. Review residual references
and warnings, and test the behavior the request changes.

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
