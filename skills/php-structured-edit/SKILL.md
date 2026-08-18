---
name: php-structured-edit
description: "Use when modifying syntactic content in PHP source files. Keep discovery unchanged (file-search, ast-grep, ripgrep, symbol search, or reasoning), but perform mutations through php-ast-edit instead of regex, sed, raw string replacement, or apply_patch. Covers renames, string literals, expression/statement replacement or insertion, deletion, and call arguments."
---

# PHP Structured Edit

Use normal repository discovery to find the intended code. This skill controls **mutation only**.

## Workflow

1. Locate the relevant PHP code using the normal search tools.
2. Run `scripts/php-ast-edit inspect` at a byte offset or line/column inside the target syntax.
3. Choose the narrowest useful AST node from the returned ancestry.
4. Send all edits for one file in a single `apply` transaction when practical. Include the SHA-256 returned by `inspect`; later edits fail if an earlier edit detached their target node.
5. Use compact syntactically valid PHP snippets. Do not spend tokens formatting snippets; the printer canonicalizes output.
6. Run the project's formatter and normal validation after the AST transaction.

Do not use raw text replacement for syntactic PHP. For foreign code stored inside a PHP string, target the `Scalar_String` node and use `set_string` unless a dedicated nested-language editor is available.

## Commands

```bash
scripts/php-ast-edit inspect --file src/Foo.php --line 42 --column 18
scripts/php-ast-edit apply --input edits.json
scripts/php-ast-edit validate --file src/Foo.php
```

Coordinates are byte-based: `offset` is zero-based; `line` and `column` are one-based.

Read `references/operations.md` for the edit schema and supported operations.
