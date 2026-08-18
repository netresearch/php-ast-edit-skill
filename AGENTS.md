# AGENTS.md — php-ast-edit-skill

PHP CLI plus Agent Skill for AST-native PHP source mutations.

## Repo Structure

```text
.
├── skills/php-structured-edit/
│   ├── SKILL.md                       # Agent runtime instructions
│   ├── agents/openai.yaml             # OpenAI-style agent descriptor
│   ├── evals/evals.json               # Trigger evals
│   ├── references/operations.md       # Edit schema and operation catalog
│   └── scripts/php-ast-edit           # Wrapper: repo bin, vendor/bin, PHAR, or PATH
├── src/
│   ├── Application.php                # CLI dispatch (inspect, apply, validate, help)
│   ├── Editor.php                      # Transaction engine and operations
│   ├── NodeLocator.php                 # Position → AST node ancestry
│   ├── NodeLocation.php                # Byte offset / line-column resolution
│   ├── SnippetParser.php               # PHP snippet → AST nodes
│   └── Exception/EditException.php     # Typed failure
├── bin/php-ast-edit                    # CLI entrypoint
├── scripts/
│   ├── check.php                       # php -l over every shipped PHP file
│   └── build-phar.php                  # Build dist/php-ast-edit.phar
├── tests/
│   ├── run.sh                          # Test entrypoint (syntax gate + round-trip)
│   ├── run.php                         # Inspect/apply integration test
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
- `php scripts/check.php` — `php -l` over `src/`, `bin/`, `scripts/`, `tests/`
- `php -d phar.readonly=0 scripts/build-phar.php` — build `dist/php-ast-edit.phar`
- `vendor/bin/php-ast-edit inspect --file <path> --line <n> --column <n>` — AST ancestry at a position
- `vendor/bin/php-ast-edit apply --input edits.json` — apply an edit transaction
- `vendor/bin/php-ast-edit validate --file <path>` — parse check

## Rules

1. **Never edit `.php` files with `sed`, regex, or raw string replacement** — use `bin/php-ast-edit apply`. This repository's own source is subject to the rule it ships.
2. **`plugin.json` at the repo root is the source of truth.** After changing it, regenerate the Claude manifest — never hand-edit `.claude-plugin/plugin.json`.
3. **`composer.json` `name` must equal the GitHub repository name** (`netresearch/php-ast-edit-skill`); the skill validator fails otherwise.
4. **No `composer.lock`** — this is a library plus skill package, not an application.
5. **Version lives in `plugin.json`** and is mirrored into `.claude-plugin/plugin.json`; both must agree before a tag.
6. **Bump the version only in a PR, tag only after that PR merges.**
7. **Every `references/*.md` stays reachable from `SKILL.md`** — orphaned reference files fail the audit.
8. **`SKILL.md` body stays under 500 words**; detail belongs in `references/`.

## CI

| Workflow | Source |
| --- | --- |
| `validate.yml`, `release.yml`, `pr-quality.yml`, `harness-verify.yml`, `eval-validate.yml` | `netresearch/skill-repo-skill` reusables |
| `auto-merge-deps.yml` | `netresearch/.github` reusable |
| `php-tests.yml` | repo-local — the reusable set covers shell and Python tests, not PHP |

## References

- [SKILL.md](skills/php-structured-edit/SKILL.md) — agent runtime instructions and workflow
- [operations.md](skills/php-structured-edit/references/operations.md) — edit schema, targets, guards, operation catalog
- [README.md](README.md) — installation, usage, transaction safety
- [CHANGELOG.md](CHANGELOG.md) — released versions
