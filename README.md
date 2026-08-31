# php-ast-edit

Agent skill plus PHP CLI: **coding agents stop writing PHP directly.** They describe syntax, `php-ast-edit` turns it into an AST, mutates the AST, and only the AST may produce a `.php` file. Discovery stays textual; every write goes through `nikic/php-parser`.

## What this skill solves

An agent that writes PHP with regex, `sed`, string replacement or a unified-diff patch has no structural model of the file. A rename hits a same-named string literal, an inserted guard clause lands outside the block it was meant to protect, a replaced argument breaks the call it belonged to — and the damage surfaces at runtime, not at edit time.

- Maps a source position (byte offset, or line/column) to the AST node ancestry covering it, and hands back a structural `ref` for each node.
- Provides a small complete mutation algebra over that AST — `replace_node`, `delete_node`, `insert_into`, `replace_child`, `delete_child`, `move_node`, plus file creation and deletion — with typed shorthands (`set_name`, `add_member`, `set_return_type`, …) layered on top.
- Parses every snippet inside a synthetic host context, so the grammar comes from `nikic/php-parser` rather than being modelled a second time here. New PHP syntax arrives with the parser.
- Pretty-prints the whole file, reparses the result, and writes it atomically. A transaction spans files: everything is mutated, printed and reparsed before the first byte is written.

## Why this is a skill (model delta)

- **Value categories:** tool-boundary discipline, failure patterns that surface only after the edit ships.
- **Without the skill:** the model reaches for `sed`/regex/`apply_patch` on PHP because they are the tools always at hand, and silently corrupts a file whenever the textual match is broader than the syntactic target — most often a rename that also rewrites a string literal, or an insertion placed outside its intended block.
- **Eval evidence:** `skills/php-structured-edit/evals/evals.json` (trigger cases, including one negative case for non-PHP files).

## Use when

- Creating a new PHP file, class, interface, trait or enum.
- Adding a method, property, constant, enum case, parameter, attribute or trait use — including into an empty container.
- Renaming a method, function, class, property or variable.
- Changing types, return types, visibility, `extends` or `implements`.
- Replacing an expression or statement, inserting a guard clause, deleting a statement or a whole file.
- Changing call arguments, array items, match arms, closure `use` clauses or docblocks.
- Editing a string literal, including foreign code (SQL, HTML, JSON) stored inside a PHP string.
- Any point where the alternative would be `sed`, a regex substitution, raw string replacement, `apply_patch`, or writing a `.php` file directly.

Discovery is out of scope: keep using ripgrep, ast-grep, an LSP, symbol search or plain reasoning to find the location.

## Expected outputs

- An `inspect` JSON document: file SHA-256 plus the AST ancestry at the requested position, smallest node first.
- A mutated PHP file, canonically printed and reparsed before the write.
- A structured failure (`STALE_SOURCE`, expectation mismatch, detached target) when a guard rejects the transaction — the file is left untouched.

## Context requirements

- PHP 8.2+ with `ext-json` and `ext-tokenizer`.
- `nikic/php-parser` 5.8+ — via `composer install`, or bundled in the release PHAR.
- Write access to the target working tree. No external network access.

## Example prompts

```text
"Rename the method `findByUid` to `resolveByUid` in src/Domain/Repository/ProductRepository.php."

"Add a null guard at the top of `Checkout::submit()` that throws CartEmpty when the cart has no items."

"The third argument of that GeneralUtility::makeInstance call is wrong — replace it with $this->context."

"Change the SQL in the $query string literal in ReportService.php to select the new column, without touching the surrounding PHP."
```

## Classification

| Field | Value |
| --- | --- |
| `action_level` | `modifies_files` |
| `risk_level` | `medium` |

## Related skills

- [`php-modernization`](https://github.com/netresearch/php-modernization-skill) — decides *what* to modernize (PHP 8.x features, PHPStan, Rector); this skill carries out the resulting hand edits.
- [`file-search`](https://github.com/netresearch/file-search-skill) — the discovery half: ripgrep, ast-grep and `fd` locate the target position this skill then edits.

## Installation

### Marketplace (recommended)

```bash
/plugin marketplace add netresearch/claude-code-marketplace
```

### npx ([skills.sh](https://skills.sh))

```bash
npx skills add https://github.com/netresearch/php-ast-edit-skill --skill php-structured-edit
```

### Composer (PHP projects)

```bash
composer require netresearch/php-ast-edit-skill
```

Requires [netresearch/composer-agent-skill-plugin](https://github.com/netresearch/composer-agent-skill-plugin). This path also installs the `php-ast-edit` binary to `vendor/bin/`.

### Download release

Download the [latest release](https://github.com/netresearch/php-ast-edit-skill/releases/latest) and extract it into your agent's skills directory.

### Git clone

```bash
git clone https://github.com/netresearch/php-ast-edit-skill.git
cd php-ast-edit-skill
composer install
vendor/bin/php-ast-edit help
```

## Usage

### Inspect a location

```bash
vendor/bin/php-ast-edit inspect --file src/Foo.php --line 42 --column 18
```

The result contains the file SHA-256 plus the AST ancestry covering that byte position. Pick the narrowest useful node type. Coordinates are byte-based: `offset` is zero-based, `line` and `column` are one-based.

### Apply a transaction

```json
{
  "files": [
    {
      "path": "src/Foo.php",
      "sha256": "...",
      "edits": [
        {
          "target": {"line": 42, "column": 18, "kind": "Identifier"},
          "expect": {"name": "oldMethod"},
          "operation": "set_name",
          "value": "newMethod"
        }
      ]
    }
  ]
}
```

```bash
vendor/bin/php-ast-edit apply --input edits.json
```

For inserted or replacement PHP snippets, formatting is irrelevant — the snippet is parsed into AST nodes and the complete file is printed canonically:

```json
{
  "operation": "insert_before",
  "php": "if ($customer === null) { throw new CustomerNotFound($id); }"
}
```

### Operations

**Primitives** — the complete CRUD algebra over the AST:

`replace_node` · `delete_node` · `insert_into` · `replace_child` · `delete_child` · `move_node`

`insert_into` addresses a container by node, property and position, so it needs no existing sibling as an anchor. That is what writes the first method into an empty class, the first statement into an empty body, the first parameter into an empty signature.

**Convenience** — ergonomic shorthands over the primitives, not the coverage boundary:

`set_name` · `set_string` · `replace_expression` · `replace_statement` · `insert_before` · `insert_after` · `delete` · `replace_argument` · `add_argument` · `remove_argument` · `add_member` · `add_parameter` · `add_attribute` · `set_return_type` · `set_type` · `set_visibility` · `add_implements` · `set_extends` · `set_doc_comment` · `remove_doc_comment`

**File lifecycle** — a file entry carries `"mode": "edit"` (default), `"create"` or `"delete"`. `create` takes full construction syntax in `php`, parses it, and writes only the resulting AST; `expectAbsent` guards against clobbering.

The public API exposes stable agent-oriented operations rather than raw PHP-Parser AST JSON, and uses PHP source snippets only as a compact syntax for constructing nodes. Run `php-ast-edit contexts` for the live catalog. Full schema: [`skills/php-structured-edit/references/operations.md`](skills/php-structured-edit/references/operations.md).

### Creating a file

```json
{
  "files": [
    {
      "path": "src/Clock.php",
      "mode": "create",
      "php": "<?php declare(strict_types=1); namespace App; final class Clock {}",
      "edits": [
        {
          "target": {"ref": "stmts[1].stmts[0]"},
          "operation": "add_member",
          "php": "public function now(): DateTimeImmutable { return new DateTimeImmutable(); }"
        }
      ]
    }
  ]
}
```

### Transaction safety

- Optional SHA-256 optimistic-lock guard (`STALE_SOURCE` on mismatch); `create` additionally guards with `expectAbsent`.
- Optional expected node type, name and value guards.
- All targets resolve against the original source before mutation. A structural `ref` is only valid together with the snapshot it came from.
- Before each edit the target node must still be attached to the current AST; invalidated follow-up edits fail.
- **The transaction spans every file in the document.** All files are read, guarded, resolved, mutated, printed and reparsed before the first byte is written — a failure in file three no longer leaves files one and two changed. A failure during the write phase rolls the already written files back.
- The reparse before the write is the universal net: any mutation that would produce invalid PHP fails the whole transaction.
- Writes use a same-directory temporary file plus atomic rename.

### Enforcement

The rule "never write PHP as text" is an instruction, and an instruction cannot be checked after the fact — the same file edited through the AST and edited by a lucky regex is byte-identical. `hooks/php-ast-only.py` is a `PreToolUse` gate that denies `Edit`/`Write`/`MultiEdit`/`NotebookEdit` on `.php` and `sed -i`-style shell mutation, before the write. See [`references/enforcement.md`](skills/php-structured-edit/references/enforcement.md).

### PHAR

```bash
composer install
php -d phar.readonly=0 scripts/build-phar.php
./dist/php-ast-edit.phar help
```

The PHAR is the portable executable for agent environments. MCP can be added as a thin adapter over the same `inspect`, `apply` and `validate` contract.

## Tests

```bash
bash tests/run.sh
```

`scripts/check.php` runs `php -l` over every shipped PHP file and needs no dependencies. `tests/run.php` exercises the inspect/apply round-trip. `tests/matrix.php` is the table-driven grammar and operation matrix: file root, namespace, use, class, interface, trait, enum, members, params, types, modifiers, statements, expressions, arrays, match, attributes, anonymous classes and closures, comments, empty containers, file lifecycle — plus the failure modes (stale SHA, wrong kind, detached target, invalid contextual snippet, duplicate path, `phpVersion` pinning, multi-file and write-phase rollback). Both skip themselves when `vendor/` is absent; CI installs Composer dependencies so they actually execute.

## Security

Report vulnerabilities to <security@netresearch.de>. The tool writes only to paths named in the transaction document and performs no network access.

## Contributing

Contributions welcome — open an issue or a PR against `main`. Use [`.github/pull_request_template.md`](.github/pull_request_template.md); commits follow Conventional Commits.

## Repository extras

- Checkpoints: none (justified — the skill governs how a mutation is performed at authoring time. A file edited through the AST and the same file edited by a lucky regex are byte-identical afterwards, so no post-hoc repository state can grade adherence.)
- **CI split:** the `netresearch/skill-repo-skill` reusables run the suite on one PHP version, including `composer install`. `.github/workflows/php-tests.yml` stays repo-local for the version matrix (8.2/8.3/8.4/8.5), which a shared reusable running a single version cannot provide. The matrix additionally pins `phpVersion` per case, so grammar support is exercised independently of the runner's own PHP version.
- **Proposed GitHub topics:** `agent-skill`, `php`, `ast`, `refactoring`, `code-editing`, `php-parser`.
- **Marketplace sync:** when the classification table, example prompts or related skills change here, update the entry in [`netresearch/claude-code-marketplace`](https://github.com/netresearch/claude-code-marketplace) in the same change.

## Repository layout

```text
php-ast-edit-skill/
├── AGENTS.md                       # Agent rules / harness index
├── plugin.json                     # Portable Agent Plugins 1.0.0 manifest
├── .claude-plugin/plugin.json      # Generated Claude Code manifest
├── composer.json                   # PHP distribution
├── bin/php-ast-edit                # CLI entrypoint
├── src/                            # Editor, NodeLocator, NodeLocation, ContextParser, …
├── hooks/php-ast-only.py           # PreToolUse gate: no text mutation of PHP
├── scripts/                        # check.php (php -l gate), build-phar.php
├── tests/                          # run.sh, run.php, matrix.php, fixtures
├── .github/workflows/              # Reusable-workflow callers + php-tests.yml
└── skills/
    └── php-structured-edit/
        ├── SKILL.md                # Agent runtime instructions
        ├── agents/openai.yaml      # OpenAI-style agent descriptor
        ├── evals/evals.json        # Trigger evals
        ├── references/             # operations.md, enforcement.md
        └── scripts/php-ast-edit    # Wrapper resolving the binary or PHAR
```

## License

Split licensing:

- **Code** (`src/`, `bin/`, `scripts/`, workflows, configs): [MIT](LICENSE-MIT)
- **Content** (`skills/**/*.md`, `references/`, this README): [CC-BY-SA-4.0](LICENSE-CC-BY-SA-4.0)

Copyright Netresearch DTT GmbH.

## German summary

`php-ast-edit` ist die Schreibschicht für Coding-Agenten in PHP-Projekten: Agenten schreiben PHP nicht mehr direkt, sie beschreiben Syntax. Die wird geparst, als AST verändert, und nur aus dem AST entsteht wieder eine `.php`-Datei — neue Dateien eingeschlossen. Gesucht wird weiterhin mit ripgrep, ast-grep oder LSP. Eine kleine vollständige Primitivebene (`replace_node`, `delete_node`, `insert_into`, `replace_child`, `move_node`) deckt jeden Knoten und jeden Container ab; die benannten Operationen sind die bequeme Oberfläche darüber. Jede Transaktion ist per SHA-256 und erwartetem Knoten abgesichert, umfasst alle beteiligten Dateien und wird vor dem Schreiben neu geparst. Eine Umbenennung trifft damit nur den Bezeichner und nicht das gleichnamige String-Literal daneben.

---

Developed and maintained by [Netresearch DTT GmbH](https://www.netresearch.de/).

**Made with ❤️ for Open Source by [Netresearch](https://www.netresearch.de/)**
