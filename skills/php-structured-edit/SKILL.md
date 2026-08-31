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

`ready` means edits print canonically and cost only the lines they touch. `warn` names what
is missing. Do not paper over it: **say what is missing and what it costs**, and offer the
one-time setup — `normalize`, then the project's formatter, committed on its own. Until
then `apply` falls back to format-preserving printing and returns a `NOT_CANONICAL`
warning; pass that warning on rather than dropping it.

A repository with no formatting rules at all is the case to raise loudest: there is nothing
for the printer to agree with, so every edit is a style decision nobody made.
`references/formatting-contract.md` has the measured detail and the setup commands.

## Workflow

1. Locate the code with the normal search tools.
2. `php-ast-edit inspect` at a byte offset or line/column inside the target syntax.
3. Take the narrowest useful node from the returned ancestry. Each entry carries a
   `ref` (`stmts[1].stmts[0].params[0]`) and its `slots` — the sub node names you can
   insert into or replace.
4. Send every edit for one transaction in a single `apply`. Include the `sha256` from
   `inspect`. Refs and coordinates are resolved against that snapshot.
5. Write compact, syntactically valid snippets. Spend no tokens on formatting; the
   printer canonicalizes the output.
6. Run the project's formatter and normal validation after the transaction. That is not a
   courtesy: the fixed point belongs to the printer and the formatter together, so the file
   is only back on it once the formatter has run.

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
