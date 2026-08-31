# AGENTS.md — php-ast-edit-skill

PHP CLI plus Agent Skill for AST-native PHP source mutations.

## Repo Structure

```text
.
├── skills/php-structured-edit/
│   ├── SKILL.md                       # Agent runtime instructions
│   ├── agents/openai.yaml             # OpenAI-style agent descriptor
│   ├── evals/evals.json               # Trigger evals
│   ├── references/operations.md       # Edit schema, parseAs contexts, operation catalog
│   ├── references/enforcement.md      # PreToolUse gate wiring
│   └── scripts/php-ast-edit           # Wrapper: repo bin, vendor/bin, PHAR, or PATH
├── src/
│   ├── Application.php                # CLI dispatch (inspect, apply, validate, contexts, help)
│   ├── Editor.php                      # Transaction engine, primitives and convenience ops
│   ├── FileTransaction.php             # One file's state through the transaction phases
│   ├── NodeLocator.php                 # Position → AST ancestry; ref → node
│   ├── NodeLocation.php                # Container mutation: replace, delete, insert_into
│   ├── ContextParser.php               # Snippet → AST via synthetic host contexts
│   ├── SnippetParser.php               # Deprecated facade over ContextParser
│   └── Exception/EditException.php     # Typed failure
├── bin/php-ast-edit                    # CLI entrypoint
├── hooks/php-ast-only.py               # PreToolUse gate: no text mutation of .php
├── scripts/
│   ├── check.php                       # php -l over every shipped PHP file
│   └── build-phar.php                  # Build dist/php-ast-edit.phar
├── tests/
│   ├── run.sh                          # Test entrypoint (syntax gate, round-trip, matrix, CLI)
│   ├── run.php                         # Inspect/apply integration test
│   ├── matrix.php                      # Table-driven grammar and failure-mode matrix
│   ├── cli.sh                          # CLI surface: arguments, output fields, exit codes
│   ├── catalog.php                     # Dispatcher, `contexts` output and docs must agree
│   └── fixtures/sample.php             # Fixture for the round-trip
├── plugin.json                         # Portable Agent Plugins 1.0.0 manifest (source of truth)
├── .claude-plugin/plugin.json          # Generated Claude Code manifest
├── composer.json                       # PHP distribution
├── .github/workflows/                  # Reusable-workflow callers + php-tests.yml
└── README.md
```

## Commands

- `composer install` — install `nikic/php-parser`; required for every parsing command
- `bash tests/run.sh` — syntax gate plus inspect/apply round-trip
- `php scripts/check.php` — `php -l` over `src/` and the named entrypoints in `bin/`, `scripts/` and `tests/`
- `php -d phar.readonly=0 scripts/build-phar.php` — build `dist/php-ast-edit.phar`
- `vendor/bin/php-ast-edit inspect --file <path> --line <n> --column <n>` — AST ancestry at a position
- `vendor/bin/php-ast-edit apply --input edits.json` — apply an edit transaction
- `vendor/bin/php-ast-edit validate --file <path>` — parse check
- `vendor/bin/php-ast-edit contexts` — parseAs contexts, operations and file modes
- `php tests/matrix.php` — grammar and operation coverage matrix on its own
- `bash tests/cli.sh` — CLI arguments, output fields and exit codes
- `php tests/catalog.php` — operation and context catalog parity across code, CLI and docs

## Rules

1. **Any creation, modification, replacement, deletion or movement of PHP syntax goes through `bin/php-ast-edit`** — never `sed`, regex, raw string replacement, `apply_patch`, or writing a `.php` file directly. Never fall back to text mutation when an AST operation looks unsupported: the primitives (`replace_node`, `delete_node`, `insert_into`, `replace_child`, `delete_child`, `move_node`) plus the `parseAs` contexts reach every construct, and `mode: create` / `mode: delete` cover the file lifecycle. This repository's own source is subject to the rule it ships. `hooks/php-ast-only.py` enforces it before the write for harnesses that support `PreToolUse`.
2. **`plugin.json` at the repo root is the source of truth.** After changing it, regenerate the Claude manifest — never hand-edit `.claude-plugin/plugin.json`.
3. **`composer.json` `name` must equal the GitHub repository name** (`netresearch/php-ast-edit-skill`); the skill validator fails otherwise.
4. **No `composer.lock`** — this is a library plus skill package, not an application.
5. **Version lives in `plugin.json`** and is mirrored into `.claude-plugin/plugin.json`; both must agree before a tag.
6. **Bump the version only in a PR, tag only after that PR merges.**
7. **Every `references/*.md` stays reachable from `SKILL.md`** — orphaned reference files fail the audit.
8. **`SKILL.md` body stays under 500 lines** (warning past 300) — the limit `skill-repo-skill`'s `validate-skill.sh` actually enforces; detail belongs in `references/`.

## CI

| Workflow | Source |
| --- | --- |
| `validate.yml`, `release.yml`, `pr-quality.yml`, `harness-verify.yml`, `eval-validate.yml`, `tests.yml` | `netresearch/skill-repo-skill` reusables |
| `auto-merge-deps.yml` | `netresearch/.github` reusable |
| `php-tests.yml` | repo-local — the reusable runs one PHP version; this carries the 8.2/8.3/8.4/8.5 matrix |

The repository's default `GITHUB_TOKEN` is read-only, so every caller job declares its own `permissions:` block matching what the reusable requires. A caller without one fails at startup with no logs.

## References

- [SKILL.md](skills/php-structured-edit/SKILL.md) — agent runtime instructions and workflow
- [operations.md](skills/php-structured-edit/references/operations.md) — edit schema, targets, guards, parseAs contexts, operation catalog
- [enforcement.md](skills/php-structured-edit/references/enforcement.md) — wiring the PreToolUse gate
- [README.md](README.md) — installation, usage, transaction safety
- [CHANGELOG.md](CHANGELOG.md) — released versions
