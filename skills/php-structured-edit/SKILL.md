---
name: php-structured-edit
description: "Use when creating, modifying, replacing, deleting or moving PHP syntax — new files included. Discovery stays as it is; PHP is written exclusively through php-ast-edit, never with regex, sed, raw string replacement, apply_patch, or by writing a .php file directly. Covers files, classes, interfaces, traits, enums, methods, properties, constants, parameters, types, modifiers, attributes, statements, expressions, arrays, match arms, docblocks and call arguments."
---

# PHP Structured Edit

Discovery stays whatever it already is. This skill controls **how PHP is written**.

## The rule

Any creation, modification, replacement, deletion or movement of PHP syntax MUST go
through `php-ast-edit`. PHP text may be *authored* as compact syntax, but it is parsed,
mutated as an AST, and written back exclusively from that AST.

Never fall back to text mutation when an AST operation looks unsupported. Every PHP
construct is reachable: a snippet is parsed inside a synthetic host context
(`parseAs`), and the primitives address any node or container.

## Before the first edit: is the repository set up?

An AST write reprints the file from the tree, so the repository has to be written the way
this printer writes — otherwise a one-line change reflows the file. Run `doctor` once:

```bash
scripts/php-ast-edit doctor
```

`ready` means an edit prints canonically, runs the project's formatter itself and costs only the lines it touches. A repository that declares no `formatter` is reported `warn`: the fixed point belongs to the printer and the formatter together, so a write that stops after printing leaves a file in neither shape. `warn` names what
is missing. Do not paper over it: **say what is missing and what it costs**, and offer the
one-time setup — `normalize`, then the project's formatter, committed on its own. Until
then `apply` falls back to format-preserving printing and returns a `NOT_CANONICAL`
warning; pass that warning on rather than dropping it.

A repository with no formatting rules at all is the case to raise loudest: there is nothing
for the printer to agree with, so every edit is a style decision nobody made.
`references/formatting-contract.md` has the measured detail and the setup commands.

## Workflow

1. Locate the code with the normal search tools.
2. Name the target by what it is, and skip the lookup: `"target": {"select":
   "method:Foo::bar"}` — also `class:`, `interface:`, `trait:`, `enum:`, `function:`,
   `property:Foo::$bar`, `const:Foo::BAR`. The owner may be left out where the file holds
   one class; an ambiguous selector is refused with the paths it matched, never resolved
   to the first hit.
3. Where no name fits — an expression, one statement inside a body — `php-ast-edit
   inspect` at a byte offset or line/column, and take the narrowest useful node from the
   returned ancestry. Each entry carries a `ref` (`stmts[1].stmts[0].params[0]`) and its
   `slots`, the sub node names you can insert into or replace.
4. Send every edit for one transaction in a single `apply`. Where an `inspect` was needed,
   pass its `sha256`: refs and coordinates are resolved against that snapshot, and the
   write is refused if the file moved underneath.
5. Renaming a variable is one edit, not one per occurrence: `rename_variable` on the
   method, function or closure it lives in, with `from` and `to`. It moves `Expr_Variable`
   and `Param` nodes only, so a property, a method name and a string literal that share the
   word are untouched by construction.
6. Write compact, syntactically valid snippets. Spend no tokens on formatting; the
   printer canonicalizes the output.
7. Where the repository declares a `formatter` in `.php-ast-edit.json`, `apply` runs it on
   the files it wrote and the write is finished — the report says `"formatter": "ran"` and
   `changedLines` describes the file that survives. Adding one 9-line method to a canonical
   TYPO3 extension goes from 34 changed lines to 10 that way.

   Where it does not, close the transaction yourself, with the whole chain:

   ```bash
   scripts/php-ast-edit format && <the project's formatter> && git diff --exit-code
   ```

   The fixed point belongs to the printer and the formatter together, so the file is only
   back on it once both have run; `git diff --exit-code` is what proves it, since neither
   tool reports drift on its own. Then the project's normal validation.

For foreign code stored inside a PHP string, target the `Scalar_String` node and use
`set_string` unless a dedicated nested-language editor exists.

## Choosing an operation

- Inserting into an **empty or slot-based container** (a class with no members, an empty
  body, an empty parameter list): `insert_into` with `property` and `position`. It needs
  no existing sibling.
- Swapping **any** node — `Param`, `Arg`, `AttributeGroup`, `ArrayItem`, `MatchArm`, a
  type: `replace_node`.
- **New file**: a file entry with `"mode": "create"` and full construction syntax in
  `php`. **Removing a file**: `"mode": "delete"` under the sha guard.
- The named shorthands (`set_name`, `add_member`, `add_parameter`, `set_return_type`, …)
  are ergonomics over the primitives; reach for a primitive as soon as one does not fit.

## Commands

```bash
scripts/php-ast-edit inspect --file src/Foo.php --line 42 --column 18
scripts/php-ast-edit apply --input edits.json
scripts/php-ast-edit validate --file src/Foo.php
scripts/php-ast-edit contexts
scripts/php-ast-edit doctor
scripts/php-ast-edit normalize --width 80
scripts/php-ast-edit format
```

Coordinates are byte-based: `offset` is zero-based; `line` and `column` are one-based.

Read `references/operations.md` for the edit schema, the `parseAs` contexts and the full
operation catalog. Read `references/formatting-contract.md` for what the repository must
provide, why no PHP formatter decides line breaking, and how the fallback behaves. Read
`references/enforcement.md` to block text edits on `.php` at the tool layer rather than by
instruction alone.
