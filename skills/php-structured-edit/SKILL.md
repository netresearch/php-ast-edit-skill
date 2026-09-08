---
name: php-structured-edit
description: "Use when creating, changing, deleting, or moving PHP syntax with the php-ast-edit CLI: symbols, members, types, statements, expressions, and PHP string literals. Use ordinary search for discovery. Not for read-only PHP questions or edits to non-PHP files."
---

# PHP Structured Edit

Use `php-ast-edit` for PHP writes while this skill is active. The tool parses snippets,
changes the AST, and prints the result. After rejection, correct the cause; do not
fall back to text mutation.

## First use

Resolve the executable once: repository `bin/php-ast-edit`, project `vendor/bin/php-ast-edit`,
installed command, or this skill's `scripts/php-ast-edit` wrapper. Use `help` if needed;
install missing engine dependencies before retrying.

Auto mode uses format-preserving printing unless applicable configuration enables
canonical printing. Explicit printer choices override auto mode. Normalization is
optional; `doctor` diagnoses canonical setup. Read the formatting reference when
configuring formatting.

## Workflow

1. Find the relevant code with normal search or an LSP.
2. Prefer named targets: `{"select":"method:Checkout::submit"}`. Other selectors:
   `class:`, `interface:`, `trait:`, `enum:`, `function:`, `property:Foo::$items`,
   `const:Foo::LIMIT`. Ambiguous names are refused. Use `inspect` for unnamed targets;
   retain its `ref` and `sha256`.
3. One edit against a named target is one call, with no payload file:
   `apply --file F.php --select method:Foo::bar --op rename_variable --from a --to b`.
   Batch related edits across files in one `apply`. Include `sha256` when relying on a
   read snapshot. After `STALE_SOURCE`, reread and reassess; never drop the guard.
   Use `"report":"compact"` to receive each verification result once.
4. Supply compact valid snippets. Import or qualify external types in namespaced PHP,
   e.g. `\\DateTimeImmutable` in JSON. The printer handles indentation.
5. Review returned `effects`, `diff`, all `warnings`, and `validation`. `parsed` and legacy
   `valid` mean parser success. Follow `checkIds` to top-level `verify` in compact reports.
   Failed checks need repair; skipped or unrun checks remain outstanding where required.
6. A passed configured command satisfies that same check on unchanged inputs. Repeat it
   after relevant changes, or run additional checks required by the task. Use supplied
   exact-byte evidence for its stated scope instead of rereading solely to reconfirm it.
   Neither passing tests nor byte preservation proves reference completeness. Report
   changed symbols and checks actually run; distinguish declarations from call sites.
   An intended edit leaves a Git diff. Avoid repository-wide `format` for a local edit.

Minimal transaction:

```json
{"report":"compact","files":[{"path":"src/Registry.php","edits":[{"target":{"select":"class:Registry"},"operation":"add_member","php":"public function register(string $name): void {}"}]}]}
```

```bash
php-ast-edit apply --input edits.json
```

`"report":"full"` (the default) retains per-file verification. Report mode changes
presentation only; `checksPassed: null` means no checks ran.

## Choose the narrow operation

- Empty list: `insert_into` with `property` and `position`; class members: `add_member`.
- Replace any node: `replace_node`; change a slot: `replace_child`.
- New file: `mode: create`, full PHP including `<?php`, default `expectAbsent` guard.
  Delete: `mode: delete` with the snapshot hash.
- Local rename: `rename_variable` on the enclosing function-like scope with `from`/`to`.
  Binding collisions are rejected; dynamic variables remain limited.
- Method rename: `rename_method` with `to`; assess unresolved receivers and inheritance
  limits. Cross-file resolution requires project-aware tools. Use `set_name` for an
  intentionally declaration-only change.
- SQL/HTML/JSON inside a PHP literal: `set_string` on its `Scalar_String` node.

Use `contexts --operation <name>` before guessing unfamiliar arguments.
Parser and host lint passes do not prove application behavior.

## References, when needed

- [Operations](references/operations.md): full schema, selectors, guards, `parseAs`, reports.
- [Formatting](references/formatting-contract.md): preserving layout, optional normalization.
- [Enforcement](references/enforcement.md): optional hook and its limits.
