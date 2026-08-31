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
- **`tests/matrix.php`**, a table-driven grammar and failure-mode matrix (54 cases) covering file root, namespace, use, class, interface, trait, enum, members, params, types, modifiers, statements, expressions, arrays, match, attributes, anonymous classes and closures, comments, empty containers and the file lifecycle, plus stale SHA, wrong kind, detached target, invalid contextual snippet, duplicate path, `phpVersion` pinning and write-phase rollback.
- PHP 8.5 in the CI matrix.

### Changed

- **The contract is now "write PHP through the AST", not "edit PHP through the AST".** Any creation, modification, replacement, deletion or movement of PHP syntax goes through `php-ast-edit`; text mutation is never the fallback when an operation looks unsupported.
- **`apply` is transactional across files.** Every file is read, guarded, resolved, mutated, printed and re-parsed before the first byte is written, and a failure during the write phase rolls the already written files back. Previously each file was written as soon as it succeeded, so a failure in file three could leave files one and two changed.
- The existing typed operations are now convenience shorthands over the primitives rather than the coverage boundary.
- `atomicWrite` refuses a directory it cannot write instead of letting `tempnam()` fall back to the system temp directory and turning the rename into a cross-device move.

### Fixed

- Two spellings of one path (`src/A.php` and `./src/A.php`) produced two transactions on the same file; both resolved against the same snapshot and the second write silently discarded the first one's edits. Paths are now compared by identity.
- `insert_into` on a property that holds a single node rather than a list (`returnType`, `default`, a class's `extends`) raised a `TypeError` from inside the printer. It is now refused by name, pointing at `replace_child`.
- `remove_doc_comment` deleted every comment attached to the node, line comments included.
- The parse context for a sub node name is resolved against the node: `stmts` is a member list on a class-like node and a statement list everywhere else, `uses` is a closure binding on a `Closure` and an imported name on a `use` statement, `vars` is a static variable on `static` and an expression on `unset`. Inserting a statement into a function body without an explicit `parseAs` previously failed with a syntax error from the class host.
- `inspect` truncated its source excerpt at a fixed byte count, which lands mid-character often enough to matter; the resulting broken UTF-8 sequence failed `json_encode` and took down the whole command. The excerpt is cut on a character boundary, and the CLI substitutes invalid sequences instead of failing, so a latin-1 source file stays inspectable.
- `tests/corpus.php` runs the print-and-reparse round trip over php-parser's own 270 source files and requires the AST to come back identical, plus 2160 `inspect` calls at positions spread through them that must raise nothing untyped. A hand-picked fixture cannot show fidelity: the constructs that lose something are the ones nobody thought to write down.
- `contexts` advertised a hand-written list next to a hand-written dispatcher, which could drift in either direction; `tests/catalog.php` now checks the operation and context names agree across the dispatcher, the CLI catalog and `operations.md`, and fails on drift from any side.
- `scripts/check.php` silently skipped a listed path that did not exist, so the syntax gate would quietly stop covering a file that was renamed. A missing path now fails the gate.
- `inspect --kind` was accepted and then ignored, so the ancestry came back unfiltered. It now filters, and `tests/cli.sh` covers the CLI surface the skill actually tells agents to drive — arguments, output fields and exit codes — which neither `run.php` nor `matrix.php` touched.
- A file that changed on disk while the transaction was being prepared was written over. Every file is now re-compared against its snapshot immediately before the first write and the transaction fails with `CONCURRENT_CHANGE`.

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
