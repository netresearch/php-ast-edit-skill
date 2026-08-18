# php-ast-edit

Agent skill plus PHP CLI for **AST-native PHP source mutations**. Discovery stays textual; the edit itself goes through `nikic/php-parser`.

## What this skill solves

An agent that edits PHP with regex, `sed`, string replacement or a unified-diff patch has no structural model of the file. A rename hits a same-named string literal, an inserted guard clause lands outside the block it was meant to protect, a replaced argument breaks the call it belonged to — and the damage surfaces at runtime, not at edit time.

- Maps a source position (byte offset, or line/column) to the AST node ancestry covering it.
- Applies typed mutations (`set_name`, `replace_expression`, `insert_before`, `remove_argument`, …) guarded by an optional SHA-256 optimistic lock and expected node type/name/value.
- Pretty-prints the whole file, reparses the result, and writes it atomically — an edit that would produce invalid PHP fails rather than landing.

## Why this is a skill (model delta)

- **Value categories:** tool-boundary discipline, failure patterns that surface only after the edit ships.
- **Without the skill:** the model reaches for `sed`/regex/`apply_patch` on PHP because they are the tools always at hand, and silently corrupts a file whenever the textual match is broader than the syntactic target — most often a rename that also rewrites a string literal, or an insertion placed outside its intended block.
- **Eval evidence:** `skills/php-structured-edit/evals/evals.json` (11 trigger cases, including one negative case for non-PHP files).

## Use when

- Renaming a method, function, class, property or variable in PHP source.
- Replacing an expression or statement, inserting a guard clause, deleting a statement.
- Changing call arguments (replace, add, remove at a zero-based index).
- Editing a string literal, including foreign code (SQL, HTML, JSON) stored inside a PHP string.
- Any point where the alternative would be `sed`, a regex substitution, raw string replacement or `apply_patch` on a `.php` file.

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

`set_name` · `set_string` · `replace_expression` · `replace_statement` · `insert_before` · `insert_after` · `delete` · `replace_argument` · `add_argument` · `remove_argument`

The public API exposes stable agent-oriented operations rather than raw PHP-Parser AST JSON, and uses PHP source snippets only as a compact syntax for constructing replacement nodes. Full schema: [`skills/php-structured-edit/references/operations.md`](skills/php-structured-edit/references/operations.md).

### Transaction safety

- Optional SHA-256 optimistic-lock guard (`STALE_SOURCE` on mismatch).
- Optional expected node type, name and value guards.
- All targets resolve against the original source before mutation.
- Before each edit the target node must still be attached to the current AST; invalidated follow-up edits fail.
- Output is reparsed before write.
- Writes use a same-directory temporary file plus atomic rename.

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

`scripts/check.php` runs `php -l` over every shipped PHP file and needs no dependencies. `tests/run.php` exercises the full inspect/apply round-trip and skips itself when `vendor/` is absent; CI installs Composer dependencies so the round-trip actually executes.

## Security

Report vulnerabilities to <security@netresearch.de>. The tool writes only to paths named in the transaction document and performs no network access.

## Contributing

Contributions welcome — open an issue or a PR against `main`. Use [`.github/pull_request_template.md`](.github/pull_request_template.md); commits follow Conventional Commits.

## Repository extras

- Checkpoints: none (justified — the skill governs how a mutation is performed at authoring time. A file edited through the AST and the same file edited by a lucky regex are byte-identical afterwards, so no post-hoc repository state can grade adherence.)
- **CI exception:** `.github/workflows/php-tests.yml` is a repo-local workflow. The skill-repo reusable set covers shell and Python tests; this repository ships a PHP tool, and its test gate needs `composer install` plus a PHP matrix. All other CI delegates to `netresearch/skill-repo-skill` reusables.
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
├── src/                            # Editor, NodeLocator, SnippetParser, Application
├── scripts/                        # check.php (php -l gate), build-phar.php
├── tests/                          # run.sh, run.php, fixtures
├── .github/workflows/              # Reusable-workflow callers + php-tests.yml
└── skills/
    └── php-structured-edit/
        ├── SKILL.md                # Agent runtime instructions
        ├── agents/openai.yaml      # OpenAI-style agent descriptor
        ├── evals/evals.json        # Trigger evals
        ├── references/             # operations.md — edit schema
        └── scripts/php-ast-edit    # Wrapper resolving the binary or PHAR
```

## License

Split licensing:

- **Code** (`src/`, `bin/`, `scripts/`, workflows, configs): [MIT](LICENSE-MIT)
- **Content** (`skills/**/*.md`, `references/`, this README): [CC-BY-SA-4.0](LICENSE-CC-BY-SA-4.0)

Copyright Netresearch DTT GmbH.

## German summary

`php-ast-edit` ist die Mutations-Schicht für Coding-Agenten in PHP-Projekten. Gesucht wird weiterhin mit ripgrep, ast-grep oder LSP; geändert wird über den AST von `nikic/php-parser`. Jede Änderung ist typisiert, per SHA-256 und erwartetem Knoten abgesichert, und die Datei wird nach dem Schreiben neu geparst. Eine Umbenennung trifft damit nur den Bezeichner und nicht das gleichnamige String-Literal daneben.

---

Developed and maintained by [Netresearch DTT GmbH](https://www.netresearch.de/).

**Made with ❤️ for Open Source by [Netresearch](https://www.netresearch.de/)**
