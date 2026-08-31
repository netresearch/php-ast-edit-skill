# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **AST mutation primitives.** `replace_node`, `delete_node`, `insert_into`, `replace_child`, `delete_child` and `move_node` form a complete CRUD algebra over the AST. `insert_into` addresses a container by node, property and position, so it needs no existing sibling — adding the first method to an empty class, the first statement to an empty function body or the first parameter to an empty signature is now expressible.
- **Contextual snippet parsing.** A snippet is parsed inside a synthetic host construct, so the grammar comes from `nikic/php-parser` instead of being modelled a second time here: `expr`, `stmt`, `member`, `enum_case`, `param`, `arg`, `type`, `array_item`, `match_arm`, `attribute`, `closure_use`, `catch`, `const`, `use`, `property_item`, `static_var`, `file`. `parseAs` is inferred where unambiguous.
- **Structural node references.** `inspect` returns a `ref` (`stmts[1].stmts[0].params[0]`) and the node's `slots` alongside the byte coordinates; `target` accepts `ref` as an alternative to `offset` or `line`/`column`. A ref is only valid together with the snapshot it came from.
- **File lifecycle.** A file entry carries `"mode": "edit"` (default), `"create"` (full construction syntax in `php`, guarded by `expectAbsent`, with `edits` applied to the freshly parsed AST) or `"delete"` (guarded by `sha256`).
- **Comment handling.** `set_doc_comment` and `remove_doc_comment` — the one area regular AST child nodes do not cover. An existing docblock is replaced, not duplicated.
- **Semantic convenience operations.** `add_member`, `add_parameter`, `add_attribute`, `set_return_type`, `set_type`, `set_visibility`, `add_implements`, `set_extends`.
- **`contexts` command** listing the live `parseAs` catalog, operation groups and file modes.
- **`hooks/php-ast-only.py`**, a `PreToolUse` gate that denies `Edit`/`Write`/`MultiEdit`/`NotebookEdit` on `.php` and `sed -i`-style shell mutation, so the AST-only rule is enforced before the write rather than by instruction alone. Wiring: `references/enforcement.md`.
- A snippet may now carry a PHP open tag inside a string literal (`'<?xml …'`). The check is structural — a snippet that actually leaves the PHP context is rejected — instead of a substring search for `<?`.
- **`tests/matrix.php`**, a table-driven grammar and failure-mode matrix (47 cases) covering file root, namespace, use, class, interface, trait, enum, members, params, types, modifiers, statements, expressions, arrays, match, attributes, anonymous classes and closures, comments, empty containers and the file lifecycle, plus stale SHA, wrong kind, detached target, invalid contextual snippet, duplicate path, `phpVersion` pinning and write-phase rollback.
- PHP 8.5 in the CI matrix.

### Changed

- **The contract is now "write PHP through the AST", not "edit PHP through the AST".** Any creation, modification, replacement, deletion or movement of PHP syntax goes through `php-ast-edit`; text mutation is never the fallback when an operation looks unsupported.
- **`apply` is transactional across files.** Every file is read, guarded, resolved, mutated, printed and re-parsed before the first byte is written, and a failure during the write phase rolls the already written files back. Previously each file was written as soon as it succeeded, so a failure in file three could leave files one and two changed.
- The existing typed operations are now convenience shorthands over the primitives rather than the coverage boundary.
- `atomicWrite` refuses a directory it cannot write instead of letting `tempnam()` fall back to the system temp directory and turning the rename into a cross-device move.

### Deprecated

- `SnippetParser` — retained as a facade over `ContextParser`.

## [0.1.0]

### Added

- `php-ast-edit` CLI with `inspect`, `apply` and `validate` commands.
- Ten typed operations: `set_name`, `set_string`, `replace_expression`, `replace_statement`, `insert_before`, `insert_after`, `delete`, `replace_argument`, `add_argument`, `remove_argument`.
- Transaction guards: SHA-256 optimistic lock, expected node type/name/value, attachment check before each edit, reparse before write, atomic rename.
- `php-structured-edit` Agent Skill with the operation reference and a wrapper resolving the repository binary, `vendor/bin`, a local PHAR, or `PATH`.
- PHAR build via `scripts/build-phar.php`.

[Unreleased]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/netresearch/php-ast-edit-skill/releases/tag/v0.1.0
