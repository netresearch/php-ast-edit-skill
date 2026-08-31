# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **This repository now holds the contract it ships.** `doctor` reported `warn` on it until now — no formatter configured, not normalised, no gate — which is a poor argument for a tool whose whole thesis is that repositories need those three things. It carries `.php-cs-fixer.php`, a `.php-ast-edit.json` declaring it canonical at width 100, `composer cgl`, and `formatting.yml` running the two-step gate. `doctor` reports `ready`.
- An `exclude` entry that names nothing — `""`, `"."`, `"./"` — resolved to the repository root and excluded every file, so the formatting gate would have passed without looking at anything. Refused on both the read and the write path.
- **`exclude` in `.php-ast-edit.json`**, set by `normalize --exclude`. Found by that dogfooding: `tests/fixtures/sample.php` is input data, not source. Normalising it would mean the suite only ever sees code the printer already agrees with — and the round-trip test would stop testing anything. `format` and `normalize` skip the listed paths; the tests assert an excluded file survives both an absolute and a relative scan, because comparing the scan's own path strings against resolved exclusions silently missed it the first time.

- **`CanonicalPrinter`** — canonical printing that a human can read. nikic's `Standard` printer puts every comma-separated list on one line however long, which on a real TYPO3 extension produced a 1745-character line where the authors' longest was 294. No PHP formatter fixes that afterwards: none of php-cs-fixer's 303 fixers has a concept of line width, and PHP_CodeSniffer's `Generic.Files.LineLength` only reports, so `phpcbf` cannot wrap. Line breaking is the printer's job or nobody's. Two hooks — `pMaybeMultiline` and `pParams` — break call arguments, array items, attribute arguments and parameter lists at a column budget; at 80 the same extension printed at max 318 characters against the authors' 294.
- **The formatting contract, declared rather than inferred.** `php-ast-edit normalize` prints a tree canonically and writes `.php-ast-edit.json`; `apply` reads it. Whether a file may be rewritten canonically cannot be measured from the file, because the fixed point belongs to the printer and the project's formatter together and the formatter runs last: on a correctly normalised extension, re-printing differed from disk in 48 of 63 files, all of it the formatter's own doing.
- **Format-preserving printing as an announced fallback.** Without the declaration `apply` prints format-preserving and returns a `NOT_CANONICAL` warning naming the setup. Per-file override with `"printer": "canonical" | "format-preserving"`. Every result reports the printer used and `changedLines` as measured after printing — `printFormatPreserving()` silently falls back to full printing for a subtree it cannot map, so the number is taken, not assumed.
- **`doctor`** reports whether a repository can hold the contract: formatter configuration, the canonical declaration, and whether any workflow runs the formatter. Each answer names the artefact it read.
- **`format`** prints canonically; `--dry-run` lists what would change. Deliberately no `--check`: on the intended state it would be red, because the formatter has been over the files since. The gate is the chain `php-ast-edit format && <project formatter> && git diff --exit-code`, documented as such.
- `references/formatting-contract.md` — the precondition, the one-time setup, the decay without a CI gate, and a measured table of which PHP tools can canonicalise line breaking (php-cs-fixer, Pint, ECS and PHP_CodeSniffer cannot; `@prettier/plugin-php` and this printer can).
- `tests/formatting.php` — 33 checks: width behaviour and idempotence at three budgets, printer selection from the declaration, the explicit override, and the format-preserving footprint for six operation classes rather than for renames alone.
- **AST mutation primitives.** `replace_node`, `delete_node`, `insert_into`, `replace_child`, `delete_child` and `move_node` form a complete CRUD algebra over the AST. `insert_into` addresses a container by node, property and position, so it needs no existing sibling — adding the first method to an empty class, the first statement to an empty function body or the first parameter to an empty signature is now expressible.
- **Contextual snippet parsing.** A snippet is parsed inside a synthetic host construct, so the grammar comes from `nikic/php-parser` instead of being modelled a second time here: `expr`, `stmt`, `member`, `enum_case`, `param`, `arg`, `type`, `array_item`, `match_arm`, `attribute`, `closure_use`, `catch`, `const`, `use`, `property_item`, `static_var`, `file`. `parseAs` is inferred where unambiguous.
- **Structural node references.** `inspect` returns a `ref` (`stmts[1].stmts[0].params[0]`) and the node's `slots` alongside the byte coordinates; `target` accepts `ref` as an alternative to `offset` or `line`/`column`. A ref is only valid together with the snapshot it came from.
- **File lifecycle.** A file entry carries `"mode": "edit"` (default), `"create"` (full construction syntax in `php`, guarded by `expectAbsent`, with `edits` applied to the freshly parsed AST) or `"delete"` (guarded by `sha256`).
- **Comment handling.** `set_doc_comment` and `remove_doc_comment` — the one area regular AST child nodes do not cover. An existing docblock is replaced, not duplicated.
- **Semantic convenience operations.** `add_member`, `add_parameter`, `add_attribute`, `set_return_type`, `set_type`, `set_visibility`, `add_implements`, `set_extends`.
- **`contexts` command** listing the live `parseAs` catalog, operation groups and file modes.
- **`hooks/php-ast-only.py`**, a `PreToolUse` gate that denies `Edit`/`Write`/`MultiEdit`/`NotebookEdit` on `.php` and `sed -i`-style shell mutation, so the AST-only rule is enforced before the write rather than by instruction alone. Wiring: `references/enforcement.md`.
- A snippet may now carry a PHP open tag inside a string literal (`'<?xml …'`). The check is structural — a snippet that actually leaves the PHP context is rejected — instead of a substring search for `<?`.
- **`tests/matrix.php`**, a table-driven grammar and failure-mode matrix (61 cases) covering file root, namespace, use, class, interface, trait, enum, members, params, types, modifiers, statements, expressions, arrays, match, attributes, anonymous classes and closures, comments, empty containers and the file lifecycle, plus stale SHA, wrong kind, detached target, invalid contextual snippet, duplicate path, `phpVersion` pinning and write-phase rollback.
- PHP 8.5 in the CI matrix.

### Changed

- `apply` mutates a clone of the parsed tree and keeps the pristine tree and its tokens, which format-preserving printing needs to map a node back to the source.
- `tests/corpus.php` round-trips through `CanonicalPrinter`, so the printer that `apply` uses is the one whose fidelity is proven.
- `printWidth` lives in `.php-ast-edit.json` only. `format --width` is refused: formatting at a width the repository was not normalised with moves the fixed point and reflows everything.
- **The contract is now "write PHP through the AST", not "edit PHP through the AST".** Any creation, modification, replacement, deletion or movement of PHP syntax goes through `php-ast-edit`; text mutation is never the fallback when an operation looks unsupported.
- **`apply` is transactional across files.** Every file is read, guarded, resolved, mutated, printed and re-parsed before the first byte is written, and a failure during the write phase rolls the already written files back. Previously each file was written as soon as it succeeded, so a failure in file three could leave files one and two changed.
- The existing typed operations are now convenience shorthands over the primitives rather than the coverage boundary.
- `atomicWrite` refuses a directory it cannot write instead of letting `tempnam()` fall back to the system temp directory and turning the rename into a cross-device move.

### Fixed

- **Writing through a symlink replaced the link with a regular file.** `rename()` over a symlink swaps the link itself, so the repository's link topology changed and the file everyone else reads stayed untouched — the edit went nowhere visible. Both writers had it, and the one in the transaction engine has been shipped since 0.1.0. `AtomicWriter` now resolves the link chain first and is the single implementation both use, so the temp-file, permission and cross-device rules live in one place.
- `normalize` declared a repository canonical even when it had only been pointed at a subdirectory, or when files had failed to format. Both now refuse the declaration and say which. A marker that speaks for code it never covered is worse than none.
- `printWidth` was validated on read but not on write, so `normalize --width 10` persisted a value every later command then rejected. One method decides the minimum for both paths.
- `Formatter` wrote with a plain `file_put_contents`; it now uses the same temporary-file-and-rename the transaction engine does, so a crash mid-write cannot truncate a source file.
- `tests/corpus.php` stripped every attribute before comparing, comments included — which made comment loss invisible in the test that exists to prove nothing is lost. Comments are now compared as a set, by content: attachment moves in 206 of 270 files while the text survives, and **two genuine losses** surfaced. An `else` block whose only statement is an `if` prints as `else if`, collapsing the block and the comment attached to that inner `if`. That is php-parser's own behaviour — reproduced with its `Standard` printer — so the two are listed by their text and any other loss fails the suite.
- Nine uses of `new Foo()->bar()` — PHP 8.4 syntax — in a package whose floor is 8.2. It was the second time in one session: the host here runs 8.5, so `php -l` cannot see it, and neither can parsing, because php-parser's grammar is not version-gated for that construct. `tests/php-floor.php` closes that one construct by reading the source position after the `new` — it is not a general floor check, which would need the floor interpreter: a parenthesised one is followed by `)`, the bare form by the dereference. Scoped deliberately to that construct rather than pretending to cover every version difference — for that, run the floor interpreter.
- A contextual snippet that escaped its synthetic host — `echo 1;` in the `attribute` context, `} echo 1; class Y {` in `member` — reached into a node the extractor never expected and produced an undefined-property warning followed by a `TypeError`. The host node is now checked before extraction.
- `create` prepended a missing `<?php` open tag, which shifted every byte offset the same document's `edits` used. The tag is required and its absence is named.
- Emptying a slot that cannot be null (`Param::$var`) raised a `TypeError` at the assignment. It is refused by name, pointing at `replace_child` / `replace_node`.
- A mutation that only fails when printed or re-parsed surfaced as a raw printer or parser exception; those become `INVALID_RESULT` naming the file.
- Path identity did not collapse `.` and `..` below a directory that does not exist yet, so two `create` entries for the same new file could both run. Paths are collapsed textually before the deepest existing ancestor is resolved.
- The enforcement gate let `rm src/Foo.php` through, although deletion is part of the same contract and `mode: delete` guards it with the file's hash. `rm`, `unlink` and `shred` of a PHP path are denied.
- The enforcement gate judged the whole command line at once: a `php-ast-edit` invocation anywhere in it exempted everything after a `;`, a path-qualified `/usr/bin/sed -i` was missed, `1> file.php` was missed, and `sed -n f.php | grep -i x` was denied as an in-place edit. The line is now split into its simple commands and each is judged on its own; `tests/hook.py` pins 39 command and tool shapes, the known dataflow blind spot included.
- `mb_check_encoding()` was used without `ext-mbstring` in the package requirements; the UTF-8 check now goes through PCRE, which needs no extra extension.
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
