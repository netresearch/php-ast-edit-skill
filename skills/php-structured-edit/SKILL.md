---
name: php-structured-edit
description: "Use when changing PHP source: method or variable renames, declarations, statements, expressions, imports, literals and file creation/deletion. Provides guarded AST writes and project method discovery. Use ordinary search for reads; not for read-only questions or non-PHP edits."
---

# PHP Structured Edit

Use `php-ast-edit` for PHP writes. Use the supplied executable directly, or resolve
repository `bin/php-ast-edit`, `vendor/bin/php-ast-edit`, PATH or this skill's wrapper
once. Correct rejected requests rather than falling back to text writes.

## Method renames

```bash
php-ast-edit rename --method 'Checkout::submit' --to placeOrder
```

Name the declaring class and method. The command discovers the file, captures its
hash, resolves the hierarchy and callers, and submits one transaction with configured
checks. Do not enumerate callers or submit one rename per declaration. Use a fully
qualified class when ambiguous, `--path` for another project, or `--file` to narrow
declaration discovery. Non-private methods require Phpactor, including final classes;
missing or uncertain resolution is refused. `--dry-run` previews without writing.

In the default compact report, review `diff`, `renames`, `open`, `verify` and
`checksPassed`. The changed lines are included for review. PHP literals and
non-PHP mentions remain visible for task-specific decisions. `--mocks` also changes
listed PHPUnit method names regardless of mocked class; use it only when all listed
names mean this method. Use `--report agent` when no inline diff is needed.

## Other changes

Search normally; prefer a named selector. Use `inspect` only for unnamed nodes and
retain its `ref` and `sha256`. One variable rename needs no payload file:

```bash
php-ast-edit apply --file Checkout.php --select method:Checkout::submit --op rename_variable --from total --to amount
```

Use `replace_expression` or `replace_statement` with `match`/`php` within a named
method; `add_member` for members; `add_use` for imports. For unfamiliar operations,
read `contexts --operation NAME`. Qualify or import external types in PHP snippets.
Batch related edits in one `apply`:

```bash
php-ast-edit apply <<'JSON'
{"files":[{"path":"src/Registry.php","edits":[{"target":{"select":"class:Registry"},"operation":"add_member","php":"public function register(string $name): void {}"}]}]}
JSON
```

Include `sha256` when relying on a read snapshot. After `STALE_SOURCE`, reread and
reassess; never drop the guard. Auto printing preserves formatting unless the project
declares canonical mode; normalization is optional.

## Interpret the result

Use `"report":"agent"` when a declared check's verdict is sufficient; `apply` otherwise
defaults to `full`. `rename` defaults to `compact`. `full` and `compact` include small edit
diffs; choose the report before writing, since Git diff cannot recover transaction history.
Read effects, warnings and verification. `checks: "none_declared"` or
`checksPassed: null` means no configured check ran. Parser success alone is not
application correctness. Repair failed checks; run additional checks the task needs.
`alreadyRun` names checks already satisfied on unchanged inputs: do not repeat them
or reread solely to reconfirm supplied byte evidence. Tests and hashes do not establish
reference completeness. Review unresolved facts and report the observed outcome.

## References, when needed

- [Operations](references/operations.md): full schema, selectors, guards, `parseAs`, reports.
- [Formatting](references/formatting-contract.md): preserving layout, optional normalization.
- [Enforcement](references/enforcement.md): optional hook and its limits.
