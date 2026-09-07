---
name: php-structured-edit
description: "Use when creating, changing, deleting, or moving PHP syntax with the php-ast-edit CLI: symbols, members, types, statements, expressions, and PHP string literals. Use ordinary search for discovery. Not for read-only PHP questions or edits to non-PHP files."
---

# PHP Structured Edit

Use `php-ast-edit` for PHP writes while this skill is active. PHP snippets are construction
input: the tool parses them, changes the AST, and prints the result. Do not fall back to
text mutation after a rejected transaction; inspect the error and correct its cause.

## First use

Resolve the executable once: repository `bin/php-ast-edit`, project `vendor/bin/php-ast-edit`,
installed `php-ast-edit`, or this skill's `scripts/php-ast-edit` wrapper. Run `help` if needed.
A missing parser requires installing the engine, not repeated edit attempts.

Existing files use format-preserving printing by default. No normalization is needed to
start. `doctor` explains optional canonical configuration; it is not a prerequisite for
every edit. Read the formatting reference only when formatting setup is part of the task.

## Workflow

1. Find the relevant code with normal search or an LSP.
2. Prefer a named target: `{"select":"method:Checkout::submit"}`. Other selectors:
   `class:`, `interface:`, `trait:`, `enum:`, `function:`, `property:Foo::$items`,
   `const:Foo::LIMIT`. Ambiguous names are refused. Use `inspect` only where a name does
   not identify the target, such as an expression inside a body; keep its `ref` and `sha256`.
3. Put related edits, including multiple files, in one `apply` transaction. Include the
   file's `sha256` when relying on a snapshot you read. Refs and coordinates are tied to
   that snapshot. After `STALE_SOURCE`, reread and reassess; never drop the guard to force it.
   Set top-level `"report": "compact"` to receive each verification result once.
4. Supply compact valid snippets. In namespaced PHP, import external types or qualify them,
   for example `\\DateTimeImmutable` inside JSON. Do not spend tokens reproducing indentation.
5. Read `effects`, `diff`, **all** `warnings`, and `validation`. `parsed` means parser
   success; legacy `valid` has the same limited meaning. In compact reports, follow each
   file's `checkIds` to top-level `verify`. Check whether lint and the project's verification
   commands ran. A failed verification needs repair even when a file was written.
6. Run only relevant checks that remain unperformed. Review the intended diff; an edit is
   expected to change it. Do not use a clean Git diff as a post-edit success condition.
   Avoid repository-wide `format` for a local edit.

Minimal transaction:

```json
{"report":"compact","files":[{"path":"src/Registry.php","edits":[{"target":{"select":"class:Registry"},"operation":"add_member","php":"public function register(string $name): void {}"}]}]}
```

```bash
php-ast-edit apply --input edits.json
```

Omitting `report`, or setting it to `"full"`, keeps the legacy per-file `verify` layout.
Report mode changes presentation only; `checksPassed: null` means no checks ran.

## Choose the narrow operation

- Empty member/body/parameter list: `insert_into` with `property` and `position`, or a
  shorthand such as `add_member`. No sibling anchor is needed.
- Replace any node: `replace_node`; change a slot: `replace_child`.
- New file: `mode: create`, full PHP including `<?php`, and default `expectAbsent` guard.
  Delete: `mode: delete` with the snapshot hash.
- Local variable rename: `rename_variable` on the enclosing method/function/closure with
  `from` and `to`. Unsafe binding collisions are rejected. Dynamic variable behavior is
  not fully resolvable statically.
- Method rename: `rename_method` with `to`. Inspect unresolved receivers and inheritance
  limitations; this does not update every caller in a project. A declaration-only change
  may use `set_name` when that is the intended scope.
- SQL/HTML/JSON inside a PHP literal: `set_string` on its `Scalar_String` node.

Use `php-ast-edit contexts --operation rename_variable` for compact argument help before
guessing an unfamiliar operation.

Do not equate an AST, parser pass, or host lint pass with correct application behavior.
Use project-aware refactoring tools when the task requires cross-file symbol resolution.

## References, when needed

- [Operations](references/operations.md): full schema, selectors, guards, `parseAs`, reports.
- [Formatting](references/formatting-contract.md): preserving layout, optional normalization.
- [Enforcement](references/enforcement.md): optional hook and its limits.
