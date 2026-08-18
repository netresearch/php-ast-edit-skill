# php-ast-edit operations

## Inspect

```bash
php-ast-edit inspect --file src/Foo.php --line 20 --column 24
```

Returns the file SHA-256 and every AST node covering the position, smallest first. Select a `kind` using the returned `type` value such as `Identifier`, `Scalar_String`, `Expr_MethodCall`, or `Stmt_Return`.

## Apply document

```json
{
  "files": [
    {
      "path": "src/Foo.php",
      "sha256": "hash-from-inspect",
      "phpVersion": "8.4",
      "edits": [
        {
          "target": {"line": 20, "column": 24, "kind": "Identifier"},
          "expect": {"name": "oldFind"},
          "operation": "set_name",
          "value": "find"
        }
      ]
    }
  ]
}
```

`target` accepts either `offset` (zero-based byte offset) or `line` + `column` (one-based byte coordinates). `kind` is optional but recommended. `expect.name`, `expect.value`, and `expect.type` are optional safety guards.

All targets are resolved against the original source version guarded by `sha256`. Before each operation, the tool verifies that the resolved node is still attached; if an earlier edit replaced or removed it, the transaction fails instead of silently editing a detached node.

## Operations

- `set_name`: set an identifier/name/variable or a node's static `name` property. Requires `value`.
- `set_string`: set a `Scalar_String` value. Requires `value`.
- `replace_expression`: replace an `Expr` node. Requires compact PHP in `php`, without `<?php`.
- `replace_statement`: replace one `Stmt`. Requires one statement in `php`.
- `insert_before` / `insert_after`: insert one or more statements around a statement-list target. Requires `php`.
- `delete`: remove a node stored in an AST list.
- `replace_argument`: replace a zero-based call argument. Requires `index` and expression `php`.
- `add_argument`: insert a zero-based call argument. Requires `index` and expression `php`.
- `remove_argument`: remove a zero-based call argument. Requires `index`.

Prefer one-line snippets, for example:

```json
{"operation":"insert_before","php":"if ($customer === null) { throw new CustomerNotFound($id); }"}
```

Formatting is intentionally not part of the edit payload.
