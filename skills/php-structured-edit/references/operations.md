# php-ast-edit operations

## Contents

- [Inspect](#inspect) — node ancestry, structural refs, slots
- [Apply document](#apply-document) — schema, file modes, transaction semantics
- [parseAs contexts](#parseas-contexts) — how a snippet becomes any AST node
- [Primitives](#primitives) — the complete mutation algebra
- [Convenience operations](#convenience-operations) — the ergonomic layer above it
- [Snippet style](#snippet-style)

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

`target` accepts `ref`, `offset` (zero-based byte offset), or `line` + `column` (one-based byte coordinates). `kind` is optional but recommended. `expect.name`, `expect.value` and `expect.type` are optional safety guards.

### File modes

| `mode` | Requires | Notes |
| --- | --- | --- |
| `edit` (default) | `edits` | `sha256` guards the snapshot |
| `create` | `php` | Full construction syntax including `<?php`. It is parsed and only the resulting AST is written. Fails when the file exists unless `"expectAbsent": false`. `edits` may then address the fresh AST. |
| `delete` | — | `sha256` guards the removal |

### Transaction semantics

Every file is read, guarded, resolved, mutated, printed and re-parsed **before the first byte is written**. A failure in any phase leaves the working tree untouched; a failure during the write phase rolls the already written files back. Before each operation the tool verifies its target is still attached, so an edit invalidated by an earlier edit fails instead of silently mutating a detached node.

The re-parse before the write is the universal net: an operation that would produce invalid PHP — an emptied slot that must not be empty, a snippet that does not fit its position — fails the whole transaction.

## parseAs contexts

A snippet is parsed inside a synthetic host construct, so the grammar always comes from `nikic/php-parser`. `php-ast-edit contexts` prints the live list.

| `parseAs` | Synthetic host | Produces |
| --- | --- | --- |
| `expr` | `<snippet>;` | `Expr` |
| `stmt` / `stmts` | `<snippet>` | one or more `Stmt` |
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
| `const` | `const <snippet>;` | `Const` |
| `use` | `use <snippet>;` | `UseItem` |
| `property_item` | `class X { public $<snippet>; }` | `PropertyItem` |
| `static_var` | `function f() { static $<snippet>; }` | `StaticVar` |
| `file` | the snippet itself | full statement list, `<?php` required |

`parseAs` is inferred from the target node or the addressed property whenever it is unambiguous. Pass it explicitly otherwise; the error message names the known contexts.

## Primitives

| Operation | Fields | Effect |
| --- | --- | --- |
| `replace_node` | `php`, optional `parseAs` | Replace the target node, whatever its class |
| `delete_node` | — | Splice the node out of its list, or null its slot |
| `insert_into` | `property`, `php`, optional `parseAs`, optional `position` | Insert into a child list of the target. **No sibling anchor needed** — this is what writes into empty classes, bodies, parameter lists and arrays |
| `replace_child` | `property`, optional `index`, `php`, optional `parseAs` | Replace a slot, or one list element |
| `delete_child` | `property`, optional `index` | Remove a slot or one list element |
| `move_node` | `into: {ref, property, position}` | Relocate an existing node inside the same file |

`position` is `"start"`, `"end"` (default) or a zero-based integer.

## Convenience operations

Shorthands over the primitives. They are ergonomics, not the coverage boundary.

- `set_name` — set an identifier/name/variable or a node's static `name` property. Requires `value`.
- `set_string` — set a `Scalar_String` value. Requires `value`.
- `replace_expression` / `replace_statement` — replace one `Expr` / one `Stmt`. Requires `php`.
- `insert_before` / `insert_after` — insert around a node that already sits in a list. Requires `php`.
- `delete` — alias of `delete_node`.
- `replace_argument` / `add_argument` / `remove_argument` — zero-based call arguments. Require `index`; the first two require `php`.
- `add_member` — append a class/interface/trait/enum member. Requires `php`.
- `add_parameter` — append a parameter. Requires `php`.
- `add_attribute` — append an attribute group. Requires `php`.
- `set_return_type` / `set_type` — set the `returnType` / `type` slot. Require type `php`.
- `set_visibility` — `public`, `protected` or `private` in `value`.
- `add_implements` / `set_extends` — class hierarchy. Require `php`.
- `set_doc_comment` — set the docblock. `value` is plain text or a complete `/** … */` block; an existing docblock is replaced, not duplicated.
- `remove_doc_comment` — drop the docblock.

## Snippet style

Prefer one-line snippets:

```json
{"operation":"insert_before","php":"if ($customer === null) { throw new CustomerNotFound($id); }"}
```

```json
{"operation":"insert_into","property":"stmts","php":"public function bar(): void {}"}
```

Formatting is intentionally not part of the edit payload.
