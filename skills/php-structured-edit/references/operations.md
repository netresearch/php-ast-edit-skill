# php-ast-edit operations

## Contents

- [Selectors](#selectors) — named declarations without a coordinate lookup
- [Inspect](#inspect) — node ancestry, structural refs, slots
- [Apply document](#apply-document) — schema, file modes, transaction semantics
- [Verification configuration](#verification-configuration) — project or changed-file checks
- [parseAs contexts](#parseas-contexts) — how a snippet becomes any AST node
- [Primitives](#primitives) — the complete mutation algebra
- [Convenience operations](#convenience-operations) — the ergonomic layer above it
- [Result fields](#result-fields) — full, compact and agent reports, checks and warnings
- [Snippet style](#snippet-style)

## Selectors

Prefer `target.select` when the target is a named declaration:

```json
{"target":{"select":"method:Checkout::submit"},"operation":"set_return_type","php":"string|false"}
```

Supported prefixes: `class:`, `interface:`, `trait:`, `enum:`, `function:`,
`method:Owner::name`, `property:Owner::$name`, and `const:Owner::NAME`.
The owner may be omitted when unambiguous. Selectors use declaration short names. For duplicate names across namespaces, use an inspected ref with its snapshot hash.
Ambiguous selectors fail and report candidates; they never select the first match.
Batch independent edits and files in a single document. Use `sha256` when relying on a
previously read source snapshot, including with selectors.

## Inspect

```bash
php-ast-edit inspect --file src/Foo.php --line 20 --column 24
```

Returns the file SHA-256 and every AST node covering the position, smallest first. Each entry carries:

| Field | Meaning |
| --- | --- |
| `type` | node type, usable as `target.kind` (`Identifier`, `Scalar_String`, `Expr_MethodCall`, `Stmt_Return`, …) |
| `ref` | structural path inside this snapshot, e.g. `stmts[1].stmts[0].params[0]` |
| `slots` | the node's sub node names — what `insert_into`, `replace_child` and `delete_child` can address |
| `property`, `index` | where the node sits inside its parent |
| `start`, `end`, `startLine`, `endLine` | byte and line coordinates |

A `ref` is only valid together with the `sha256` it was produced from. Refs survive nothing: re-inspect after every transaction.

## Apply document

```json
{
  "dryRun": false,
  "report": "compact",
  "files": [
    {
      "path": "src/Foo.php",
      "mode": "edit",
      "sha256": "hash-from-inspect",
      "phpVersion": "8.4",
      "edits": [
        {
          "target": {"ref": "stmts[0].stmts[0].name"},
          "expect": {"name": "oldFind"},
          "operation": "set_name",
          "value": "find"
        }
      ]
    }
  ]
}
```

`target` accepts `select`, `ref`, `offset` (zero-based byte offset), or `line` + `column` (one-based byte coordinates). `kind` is optional but recommended. `expect.name`, `expect.value` and `expect.type` are optional safety guards.

Optional top-level `report` accepts `"full"`, `"compact"` or `"agent"`. It defaults to `"full"`
for existing consumers. Compact mode places each verification result once at the top
level and gives files references to it; it does not change the edit, checks, exit status,
or other result fields. See [result fields](#result-fields).

### File modes

| `mode` | Requires | Notes |
| --- | --- | --- |
| `edit` (default) | `edits` | `sha256` guards the snapshot |
| `create` | `php` | Full construction syntax. The `<?php` open tag is **required**: prepending it silently would shift every byte offset the same document's `edits` use. Only the resulting AST is written. Fails when the file exists unless `"expectAbsent": false`; `edits` may then address the fresh AST. |
| `delete` | — | `sha256` guards the removal |

### Transaction semantics

Every file is read, guarded, resolved, mutated, printed and re-parsed **before the first byte is written**. A failure in any phase leaves the working tree untouched; a failure during the write phase rolls the already written files back. Before each operation the tool verifies its target is still attached, so an edit invalidated by an earlier edit fails instead of silently mutating a detached node.

Parser validation rejects output the configured parser cannot parse. Host lint also runs
before writes when the selected target version is compatible with the running interpreter;
otherwise the report explicitly marks lint skipped. Neither check establishes semantic
correctness. Read the validation report and run relevant project tests.

Writes are atomic per file, not across the entire file set as observed by other processes.
Rollback covers transaction-managed paths, not arbitrary external-command side effects.
Configured verification failures leave the edit in place and return a failing CLI status.

Immediately before the first write, every file is compared against the snapshot it was resolved from. A file that changed, appeared or disappeared while the transaction was being prepared fails with `CONCURRENT_CHANGE` and nothing is written — otherwise the output, built from a version that no longer exists, would silently discard whoever else wrote.

## Verification configuration

Declare optional `verify` commands in `.php-ast-edit.json`. They run after writing and
formatting, independently of report mode or whether canonical printing is enabled:

```json
{
  "verify": [
    {"scope": "project", "command": ["php", "vendor/bin/phpstan", "analyse", "--no-progress"]},
    {"scope": "changed_files", "command": ["./check-changed-files", "{files}"]}
  ]
}
```

`doctor` proposes this declaration where the repository carries a static analyser and has not made one: the point is not tidiness but calls. An agent that cannot see whether the project's own checks passed runs them itself, afterwards, on its own judgement — in one recorded thirteen-turn edit, four turns went on PHPStan and two on the coding standard, all after the write had already succeeded. Nothing is proposed where there is no analyser to run.

Each object contains exactly `scope` and `command`. Commands are non-empty argument
arrays of non-empty strings without NUL bytes, executed directly without shell expansion.
The working directory is the directory containing the applicable `.php-ast-edit.json`.
Choose commands available in that project.

| Declaration | Files that trigger it | Arguments |
| --- | --- | --- |
| `scope: "project"` | Changed, non-excluded files, including deletions | The declared command is unchanged; `{files}` is forbidden, including inside another argument |
| `scope: "changed_files"` | Changed, non-excluded edits and creates; intentional deletions are omitted | Exactly one whole `{files}` argument expands to the eligible absolute file paths |
| Legacy argument array | Same as `changed_files` | For example `["./check-changed-files", "{files}"]`; existing declarations remain supported |

Each declared entry runs once per affected configuration directory. Repeated identical
entries remain separate executions. Configuration and exclusions are captured before
writing. Unchanged or excluded files do not trigger checks; a delete-only transaction
can run project checks but has no changed-file check inputs. Dry runs execute neither.
Unexpectedly missing inputs stay in the planned command so the checker can report them;
they are not silently removed from the verification scope.
`project` controls invocation scope; the command itself determines what it verifies.

For PHPStan, keep analysed paths stable in its configuration and use a project-scoped
command. Passing a changing `{files}` list can invalidate its result cache and replaces
the configured analysis paths. A cold whole-project analysis can still cost more than
a partial check. See [PHPStan result caching](https://phpstan.org/user-guide/result-cache)
and [analysed paths](https://phpstan.org/config-reference#analysed-files).

## parseAs contexts

A snippet is parsed inside a synthetic host construct, so the grammar always comes from `nikic/php-parser`. `php-ast-edit contexts` prints the live list.

| `parseAs` | Synthetic host | Produces |
| --- | --- | --- |
| `expr` | `<snippet>;` | `Expr` |
| `stmt` | `<snippet>` | exactly one `Stmt` |
| `stmts` | `<snippet>` | one or more `Stmt`, inserted together |
| `member` | `class X { <snippet> }` | `Stmt_ClassMethod`, `Stmt_Property`, `Stmt_ClassConst`, `Stmt_TraitUse` |
| `enum_case` | `enum X { <snippet> }` | `Stmt_EnumCase` |
| `param` | `function f(<snippet>) {}` | `Param` |
| `arg` | `f(<snippet>);` | `Arg` |
| `type` | `function f(): <snippet> {}` | `Identifier`, `Name`, `NullableType`, `UnionType`, `IntersectionType` |
| `array_item` | `[<snippet>];` | `ArrayItem` |
| `match_arm` | `match (…) { <snippet> };` | `MatchArm` |
| `attribute` | `<snippet> class X {}` | `AttributeGroup` |
| `closure_use` | `function () use (<snippet>) {};` | `ClosureUse` |
| `catch` | `try {} <snippet>` | `Stmt_Catch` |
| `switch_case` | `switch (…) { <snippet> }` | `Stmt_Case` |
| `const` | `const <snippet>;` | `Const` |
| `use` | `use <snippet>;` | `UseItem` |
| `property_item` | `class X { public $<snippet>; }` | `PropertyItem` |
| `static_var` | `function f() { static $<snippet>; }` | `StaticVar` |
| `file` | the snippet itself | full statement list; the `<?php` open tag is required |

`parseAs` is inferred from the target node and the addressed property, so it rarely needs to be given. The inference is node-aware where a sub node name is shared: `stmts` is a member list on a class-like node and a statement list everywhere else, `uses` is a closure binding on a `Closure` and an imported name on a `use` statement, `vars` is a static variable on `static` and an expression on `unset`. Where a node still admits more than one shape — an enum body takes cases, methods and constants — the candidates are tried in order and the parser decides. Pass `parseAs` explicitly for anything the tool cannot name; the error message lists the known contexts.

An edit that lacks exactly one required argument and carries exactly one field its operation does not take is read as that argument — `new_name` beside `rename_method` is `to`. With two unknown fields, or a missing argument and none beside it, the edit is refused and the refusal shows the shape. `set_docblock` and `update_docblock` are `set_doc_comment`.

## Primitives

| Operation | Fields | Effect |
| --- | --- | --- |
| `replace_node` | `php`, optional `parseAs` | Replace the target node, whatever its class |
| `delete_node` | — | Splice the node out of its list, or null its slot |
| `insert_into` | `property`, `php`, optional `parseAs`, optional `position` | Insert into a child list of the target. **No sibling anchor needed** — this is what writes into empty classes, bodies, parameter lists and arrays. A property that holds a single node rather than a list is refused by name; use `replace_child` there |
| `replace_child` | `property`, optional `index`, `php`, optional `parseAs` | Replace a slot, or one list element |
| `delete_child` | `property`, optional `index` | Remove a slot or one list element |
| `move_node` | `into: {ref, property, position}` | Relocate an existing node inside the same file |

`position` is `"start"`, `"end"` (default) or a zero-based integer.

## Convenience operations

Shorthands over the primitives. They are ergonomics, not the coverage boundary.

- `set_name` — set an identifier/name/variable or a node's static `name` property. Requires `value`.
  On a method declaration that the project calls by name it would rename the declaration
  and none of the calls, so it is refused with the call count and the `rename_method` edit
  to use instead; `declarationOnly: true` (`--declaration-only` in the flag form) keeps
  the declaration-only change. A method nothing calls is renamed as asked.
- `set_string` — set a `Scalar_String` value. Requires `value`.
- `replace_expression` / `replace_statement` — replace one `Expr` / one `Stmt`. Requires `php`. With `match`, the target is a scope instead — a method, function or class named by its selector — and every expression or statement inside it that is the same code as `match` is replaced, each with its own copy of `php`; the effect reports `replaced`. The comparison is structural: spacing and quoting in `match` do not matter, names, arguments and operators do. A match that finds nothing is refused — unless the replacement already stands in the scope, as it does after a `rename_method` earlier in the same transaction: then the edit is a no-op reported as `replaced: 0` with `alreadyPresent`, and so is `replace_statement` on a declaration without `match` — a method or class is a `Stmt` to the parser, and swapping one for a statement never parses. `replace_node` replaces a declaration whole.
- `insert_before` / `insert_after` — insert around a node that already sits in a list. Requires `php`.
- `delete` — alias of `delete_node`.
- `replace_argument` / `add_argument` / `remove_argument` — zero-based call arguments. Require `index`; the first two require `php`.
- `add_member` — append a class/interface/trait/enum member. Requires `php`. With a member as the target instead of the class, the new member goes directly after that one; `position` then has nothing to say and is refused.
- `add_parameter` — append a parameter. Requires `php`.
- `add_attribute` — append an attribute group. Requires `php`.
- `set_return_type` / `set_type` — set the `returnType` / `type` slot. Require type `php`.
- `set_visibility` — `public`, `protected` or `private` in `value`.
- `add_implements` / `set_extends` — class hierarchy. Require `php`.
- `add_use` — add a class import to the file. Requires `value` (the fully qualified name), takes an optional `alias`. This is the one operation with no `target`: an import belongs to the file, not to a node, and `use` inside a class body means a trait — that is `add_member` with `php: "use SomeTrait;"`. Adding an import the file already has is a no-op rather than a duplicate, group uses included, and the effect reports `alreadyPresent` with the local name the class is available under, so nothing has to grep for it afterwards. Importing a class that is present under a different alias, or a name that is already bound to another class, is refused with the conflicting import named. The import goes after the last existing one; ordering is left to the project formatter — and so is removal: a declared formatter carrying `no_unused_imports` deletes an import nothing references yet, so the file comes back with `changed: false` while the effect still reports `alreadyPresent: false`. The effect describes the edit, `changed` describes the file. Add the import in the same transaction as the code that uses it.
- `set_doc_comment` — set the docblock. `value` is plain text or a complete `/** … */` block; an existing docblock is replaced, not duplicated.
- `remove_doc_comment` — drop the docblock. Line and block comments on the same node are left alone.
- `rename_method` — rename the selected method declaration and structurally attributable calls
  in the same file. Takes `to`; use `expect.name` for an optional declaration-name guard. Calls to `parent::` cannot be
  treated as calls to the child declaration. Inheritance, other receivers, and external
  callers require further analysis; read effect counts and warnings. The convenience operation accepts a private method or a method in a final class, with
  no extends/implements/trait composition; magic methods and unsafe late-static dispatch
  are refused. Calls in the declaring class's property hooks are included.

  Any other method — public or protected in a class that can be extended, or in a class
  with a parent, an interface or a trait — is renamed across the project when the edit
  names it by selector (`method:Class::name`). The hierarchy comes from the project's
  sources and Composer's class tables (the autoloader is never run); the call sites come
  from Phpactor 2026.07.22.0, pinned by digest and located through `"phpactor"` in
  `.php-ast-edit.json` or `PHP_AST_EDIT_PHPACTOR`. `doctor` reports it under `resolver`.
  Every declaration and call site becomes a guarded `set_name` in one transaction, and the
  result carries `renames`: `method`, `declarations`, `references`, `files`, `hierarchy`,
  and `notRenamed` — mentions of the old name outside PHP, plus Fluid property reads
  (`{item.label}` for `getLabel()`), which are listed and not changed. PHP string literals
  that read the old name — a PHPUnit `->method('old')`, a callable `[$x, 'old']` — are
  listed under `literals`, one entry per file and declaration with its `select`, `lines`
  and `refs` in the same order, and `literalsCount`; they are not changed, because which
  class a string names is not known. A `replace_expression` on an entry (`target.select`
  as listed, `match: "'old'"`, `php: "'new'"`) sets every literal of that entry — right
  when all of them mean the method. Where some do not (a data provider's name, a backed
  enum value), or where an entry has no `select` (a literal outside any declaration, or a
  selector the file uses twice), `set_string` on the refs that do. `literalsUnread` names
  PHP files the scan could not read or skipped above 1 MB. Refused before
  anything is written: a declaration of the method outside the project (a vendor base
  class, a PHP interface such as `JsonSerializable`), an ancestor found nowhere, a trait
  declaring the method, the new name taken anywhere in the hierarchy, and any call whose
  receiver type Phpactor could not determine.

  With `"mocks": true` (`--mocks`), the project-wide rename also sets the literals a PHPUnit
  mock lists the method by: the first argument of `->method()`, the entries of
  `->onlyMethods()`, `->addMethods()` and `->setMethods()`, the method list of
  `createPartialMock()` and the keys of `createConfiguredMock()`. It counts them as
  `mocksSet`. Which class a mock stands for is not resolved, so a mock of another class
  with a method of the same name is set too; everything else — data provider names,
  callables, enum values — stays listed under `literals`. A rename one file decides
  (a private method, a final class without a hierarchy) has no mocks to set.
- `rename_variable` — rename a variable in a selected method, function, closure, or arrow
  function. Takes `from` and `to`, with or without `$`. Renames matching variable/parameter
  nodes and associated explicit captures; unrelated property and string names stay intact.
  Nested scopes and destination bindings are analyzed before mutation. Recognized binding
  collisions are rejected instead of capturing or merging names. `$this` is refused as
  either endpoint. Function imports are resolved before checking symbol-table access.
  Affected scopes containing `call_user_func()` or `call_user_func_array()` are refused
  conservatively; callback target analysis is not performed. Property hooks are not
  supported as direct scope targets. Parameter renames do not update named arguments
  at callers. Dynamic variable behavior is not fully resolvable statically.

## Result fields

For each file, inspect:

| Field | Meaning |
| --- | --- |
| `changed`, `changedLines`, `diff` | Measured final output, including a configured formatter |
| `effects` | Operation effects and residual references; residual names may belong to another scope |
| `warnings` | All accumulated warnings, omitted when empty; do not read only the first |

A `warnings` entry starts with a code. Two are emitted by the engine itself:

| Code | Meaning |
| --- | --- |
| `INCOMPLETE_RENAME` | A rename left occurrences of the old name in the file. They may belong to another scope; the engine does not decide that for you |
| `PHP_LINT_SKIPPED` | The target PHP is newer than the running interpreter, so nothing checked the syntax the file will actually meet. Validate on the target runtime |

The rest come from the printer and the repository configuration. In `agent` reports the
same two conditions appear in `open` instead, as `REMAINING_IN_FILE` and
`SYNTAX_UNCHECKED_ON_TARGET`.
| `warning` | Legacy joined warning string for older consumers |
| `parsed` | Output accepted by the selected PHP parser |
| `valid` | Deprecated alias of `parsed`; **not** semantic validation |
| `validation.parser` | Parser status |
| `validation.lint` | Host lint status, runtime, and a reason when skipped |
| `validation.checks` | `passed`, `failed`, or `not_run` for verification associated with this file |
| `formatter` | Formatter execution, where present |
| `verify` | Full mode: associated check results with `command`, `ok`, and failure `output`, omitted when no checks ran |
| `checkIds` | Compact mode: IDs of associated top-level verification results; `[]` when none ran |

With `"report": "compact"`, top-level `verify` is an array of actual check executions:

| Field | Meaning |
| --- | --- |
| `id` | Execution identifier, unique within this Apply response |
| `cwd` | Absolute working directory of the check |
| `scope` | `project` or `changed_files` |
| `command` | Display string of the expanded command; not a shell-escaped replay instruction |
| `ok` | Whether that check returned exit status zero |
| `output` | Failure output excerpt, at most 4,000 bytes; omitted on success |

Compact files omit `verify`; their `checkIds` refer to the shared entries. Two identical
commands still have different IDs when executed twice. A project-check failure is a
shared result, not evidence that every linked file caused the diagnostic. If no checks
ran, top-level `verify` and every file's `checkIds` are empty arrays.

With `"report": "full"` (the default), results keep the existing per-file `verify`
layout without `checkIds` or top-level `verify`. Full describes that layout; it does not
remove existing diff or diagnostic limits. Both modes retain effects, warnings, parser
and lint information, and the same check statuses.

Every mode carries `alreadyRun` when every check passed and at least one had
`scope: "project"`: a sentence naming those project commands. They ran after the
formatter, on the files as written, so rerunning them while no file, dependency or check
tool has changed repeats the result; `proofExcludes` lists what the engine cannot see
change. A `changed_files` check is never named there; it did not see the project.

### `"report": "agent"`

The decision-shaped projection: what the write is known to have done, and what it left
open. It answers what the next step needs, not what happened — so it drops the fields a
caller can recover for itself, and it never states a claim it cannot support.

| Field | Meaning |
| --- | --- |
| `reportVersion` | Schema version of this mode. A bump means a field was removed or changed meaning; an added field does not bump it. `full` and `compact` carry no version |
| `outcome` | `applied`, `applied_checks_failed`, or `dry_run` |
| `checks` | `passed`, `failed`, or `none_declared` — a repository that declares no checks did not pass them |
| `checksPassed` | The nullable boolean the exit code is derived from, kept so one command has one verdict. Read `checks` instead |
| `checksPassedCount` | How many declared checks passed. Their output is not carried |
| `checksFailed` | Failing executions only, each with `id`, `scope`, `command` and `output` |
| `verifications` | **Every** execution, passing ones included: `id`, `scope`, `cwd`, `command`, `ok`. No `output` — a passing check's is routine noise, a failing one's is in `checksFailed` |
| `alreadyRun` | Present when every check passed and one was project-scoped: those commands, which need no rerun while no file, dependency or check tool has changed |
| `proofExcludes` | Inputs this response does **not** account for |

Per file: `path`, `mode`, `changed`, `editsApplied`, `beforeSha256`, `afterSha256`,
`changedLines`, `effects`, `warnings` (list only), `checkIds`, plus

| Field | Meaning |
| --- | --- |
| `syntax` | `passed`, `skipped` (target PHP newer than the running interpreter), or `not_run` (deletion) |
| `checks` | The same tri-state, for the checks associated with this file |
| `open` | What this write did **not** establish; `[]` means the tool found nothing to flag |

#### Deciding whether a check may be skipped

`verifications` plus the per-file `checkIds` and `afterSha256` are the whole proof this
tool can give: which command ran, in which directory, over which files, at exactly which
bytes, with which verdict. A caller that recorded that can ask whether the same command
over the same bytes needs running again.

`proofExcludes` names what it leaves out — `dependencies`, `checkToolVersions`, `runtime`,
`environment`. The engine sees none of those, and a reuse key built only from what is above
will reuse a stale pass after a dependency bump or a tool upgrade. It is stated rather than
left to be discovered, because a verification cache that silently answers `passed` is worse
than no cache. Building that key is the caller's, not this tool's: it is the side that knows
what its environment consists of.

`open` entries are derived from real state, never boilerplate: `NOT_WRITTEN` on a dry run,
`REMAINING_IN_FILE` and `UNRESOLVED_RECEIVERS` from rename effects, `CALLERS_OUTSIDE_FILE`
whenever `rename_method` ran, `SYNTAX_UNCHECKED_ON_TARGET` when host lint was skipped, and
`NO_CHECKS_DECLARED` when the repository declares none. One thing this list never says,
because it is true of every response and would be noise on all of them: whether the task
you were given is met does not follow from any of these fields.

Absent by design: `diff`, `code`, `validation`, `verify`, and the legacy `warning` and
`valid` duplicates. The diff is recoverable without re-running anything — `git diff --
<path>` against the working tree, with `beforeSha256` naming the snapshot the edit started
from. A file outside version control has no such record; that is the one case where this
mode loses information `full` would have carried, and a reason to ask for `full` there.

The top-level `checksPassed` is `true`, `false`, or `null` when no checks ran. A failing
verification makes `apply` exit nonzero; examine the retained edit before repairing it.
`--dry-run` does not run commands that need the files written. Never report those checks
as passed merely because preparation succeeded.
Deletion has no output source to parse or lint, so those validation statuses are `not_run`.
Its `validation.checks` can still report a configured project check that ran after deletion.

## Limits

A snippet is PHP *inside* the PHP context. An open tag in a string literal is fine (`'<?xml version="1.0"?>'` is an ordinary expression); a snippet that actually leaves the PHP context — a stray closing tag followed by literal output — is rejected, because the resulting `Stmt_InlineHTML` is almost never what the caller meant. Write such output as an explicit `echo`.

## Snippet style

Prefer one-line snippets:

```json
{"operation":"insert_before","php":"if ($customer === null) { throw new CustomerNotFound($id); }"}
```

```json
{"operation":"insert_into","property":"stmts","php":"public function bar(): void {}"}
```

Formatting is intentionally not part of the edit payload.
