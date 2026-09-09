# AGENTS.md — php-ast-edit-skill

PHP CLI plus Agent Skill for AST-native PHP source mutations.

## Repo Structure

```text
.
├── skills/php-structured-edit/
│   ├── SKILL.md                       # Agent runtime instructions
│   ├── agents/openai.yaml             # OpenAI-style agent descriptor
│   ├── evals/evals.json               # Outcome evals; eval_queries.json tests routing
│   ├── references/operations.md       # Edit schema, parseAs contexts, operation catalog
│   ├── references/enforcement.md      # PreToolUse gate wiring
│   └── scripts/php-ast-edit           # Wrapper: repo bin, vendor/bin, PHAR, or PATH
├── src/
│   ├── Application.php                # CLI dispatch (inspect, apply, validate, contexts, help)
│   ├── Editor.php                      # Transaction engine, primitives and convenience ops
│   ├── CanonicalPrinter.php            # Width-aware canonical printing
│   ├── RepositoryConfig.php            # Canonical, formatter and verification settings
│   ├── EditorConfig.php                # max_line_length — the project's own declaration
│   ├── Formatter.php                   # format / normalize over a tree
│   ├── AtomicWriter.php                # temp file + rename, symlink-aware
│   ├── Doctor.php                      # Is the repository set up for the contract?
│   ├── FileTransaction.php             # One file's state through the transaction phases
│   ├── FileRestorer.php                # Restore bytes, modes and symlink identity on failure
│   ├── EditReport.php                  # Per-file effects, warnings and validation status
│   ├── PhpLint.php                     # Host-runtime compile check without executing source
│   ├── RenameVariable.php              # Lexical scope and collision preflight
│   ├── RenameMethod.php                # Conservative method dispatch and collision checks
│   ├── NodeLocator.php                 # Position → AST ancestry; ref → node
│   ├── NodeLocation.php                # Container mutation: replace, delete, insert_into
│   ├── ContextParser.php               # Snippet → AST via synthetic host contexts
│   ├── SnippetParser.php               # Deprecated facade over ContextParser
│   └── Exception/EditException.php     # Typed failure
├── bin/php-ast-edit                    # CLI entrypoint
├── hooks/php-ast-only.py               # PreToolUse gate: no text mutation of .php
├── scripts/
│   ├── check.php                       # php -l over every shipped PHP file
│   ├── build-phar.php                  # Package a runtime-only Composer installation
│   └── build-release.sh                # Isolated production build and executable archives
├── tests/
│   ├── run.sh                          # Test entrypoint (syntax gate, round-trip, matrix, CLI)
│   ├── run.php                         # Inspect/apply integration test
│   ├── matrix.php                      # Table-driven grammar and failure-mode matrix
│   ├── renames.php                     # Binding collisions and dispatch boundaries
│   ├── transactions.php                # Configuration, guards, rollback, validation reports
│   ├── distribution.sh                 # Clean consumer installs and extracted archives
│   ├── distribution.php                # PHAR contents and runtime dependency assertions
│   ├── cli.sh                          # CLI surface: arguments, output fields, exit codes
│   ├── catalog.php                     # Dispatcher, `contexts` output and docs must agree
│   ├── formatting.php                  # Printer width, printer choice, fallback, doctor
│   ├── php-floor.php                   # Dereferenced `new` needs parentheses below PHP 8.4
│   ├── corpus.php                      # Round trip over php-parser's own source
│   ├── hook.py                         # Enforcement gate behaviour table
│   └── fixtures/sample.php             # Fixture for the round-trip
├── plugin.json                         # Portable Agent Plugins 1.0.0 manifest (source of truth)
├── .claude-plugin/plugin.json          # Generated Claude Code manifest
├── composer.json                       # PHP distribution
├── benchmarks/                        # Reproducible CLI samples and agent outcome oracles
├── docs/                              # Executable quickstart, installation, FAQ and limits
├── .github/workflows/                  # Shared skill gates and local engine/distribution gates
└── README.md
```

## Commands

- `composer install` — install `nikic/php-parser`; required for every parsing command
- `bash tests/run.sh` — full runtime suite, executable docs, task oracles, clean install and artifact checks
- `bash tests/run.sh --runtime-only` — omit the separately matrix-tested distribution suite
- `composer cgl` — canonical print plus the project's formatting rules; run before committing PHP
- `php scripts/check.php` — `php -l` over `src/` and the named entrypoints in `bin/`, `scripts/` and `tests/`
- `bash scripts/build-release.sh` — build `dist/releases/` with isolated production dependencies; output directory must be empty
- `bin/php-ast-edit inspect --file <path> --line <n> --column <n>` — AST ancestry at a position
- `bin/php-ast-edit apply --input edits.json` — guarded transaction; exit 1 retains edits when project checks fail
- `bin/php-ast-edit validate --file <path>` — parse and host PHP lint; check explicit skip status for newer target syntax
- `bin/php-ast-edit contexts --operation rename_variable` — the contract for one operation
- `bin/php-ast-edit doctor` — canonical-mode setup diagnostics; ordinary edits support format preservation
- `bin/php-ast-edit normalize` — optional canonical print plus declaration; width comes from `.editorconfig`
- `bin/php-ast-edit format` — canonical print only
- `bash docs/quickstart.sh` — the documented first edit, checked at runtime
- `python3 benchmarks/agent_benchmark.py self-test` — task oracles and imported evidence validation; no model calls
- `php tests/matrix.php` — grammar and operation coverage matrix on its own
- `bash tests/cli.sh` — CLI arguments, output fields and exit codes
- `php tests/catalog.php` — operation and context catalog parity across code, CLI and docs
- `php tests/corpus.php` — print-and-reparse fidelity over 270 real files
- `php tests/formatting.php` — printer width, printer choice, the fallback, doctor
- `php tests/php-floor.php` — the one version-dependent construct that has broken CI twice (`new X()->y()` below PHP 8.4); it is not a general compatibility check, for which the floor interpreter has to run
- `python3 tests/hook.py` — what the enforcement gate denies and allows

## Rules

1. **Any creation, modification, replacement, deletion or movement of PHP syntax goes through `bin/php-ast-edit`** — never `sed`, regex, raw string replacement, `apply_patch`, or writing a `.php` file directly. Never fall back to text mutation when an AST operation looks unsupported: the primitives (`replace_node`, `delete_node`, `insert_into`, `replace_child`, `delete_child`, `move_node`) plus the `parseAs` contexts reach every construct, and `mode: create` / `mode: delete` cover the file lifecycle. This repository's own source is subject to the rule it ships. `hooks/php-ast-only.py` enforces it before the write for harnesses that support `PreToolUse`.
   Automated tests and benchmarks may create, reset, or patch disposable fixtures in a temporary directory, including deliberately invalid PHP and contextual-patch baselines. This exception never permits text edits to tracked PHP implementation or test source. It makes parser failures and fair alternative-tool comparisons testable.
2. **`plugin.json` at the repo root is the source of truth.** After changing it, regenerate the Claude manifest — never hand-edit `.claude-plugin/plugin.json`.
3. **`composer.json` `name` must equal the GitHub repository name** (`netresearch/php-ast-edit-skill`); the skill validator fails otherwise.
4. **No `composer.lock`** — this is a library plus skill package, not an application.
4b. **This repository is on the canonical fixed point.** `.php-ast-edit.json` declares it, `.php-cs-fixer.php` carries the token-level rules, and `.github/workflows/formatting.yml` gates it. Before committing PHP: `composer cgl` — that is `php-ast-edit format` followed by `php-cs-fixer fix`. Neither half is a check on its own; the clean tree is. `tests/fixtures/` is excluded on purpose: a fixture exists to be code the printer has not seen.
5. **Version lives in `plugin.json`** and is mirrored into `.claude-plugin/plugin.json`; both must agree before a tag.
6. **Bump the version only in a PR, tag only after that PR merges.**
7. **Every `references/*.md` stays reachable from `SKILL.md`** — orphaned reference files fail the audit.
8. **`SKILL.md` body stays under 500 lines** (warning past 300) — the limit `skill-repo-skill`'s `validate-skill.sh` actually enforces; detail belongs in `references/`.

## CI

| Workflow | Source |
| --- | --- |
| `validate.yml`, `pr-quality.yml`, `harness-verify.yml`, `eval-validate.yml`, `tests.yml` | `netresearch/skill-repo-skill` reusables |
| `auto-merge-deps.yml` | `netresearch/.github` reusable |
| `formatting.yml` | repo-local — the two-step canonical gate |
| `php-tests.yml` | repo-local — the reusable runs one PHP version; this carries the 8.2/8.3/8.4/8.5 matrix |
| `distribution.yml` | repo-local — clean Composer installations and executable artifacts on PHP 8.2 and 8.5 |
| `release.yml` | repo-local — build and test executable artifacts before signing and publishing those exact bytes |

The local release workflow is an explicit engine-packaging exception to the generic skill-only reusable: the reusable has no pre-package runtime build hook. It retains annotated signed-tag verification, checksums, Cosign verification and provenance, and publishes only after the exact artifacts pass installation tests. Return to the reusable when it supports this build/test contract.

The repository's default `GITHUB_TOKEN` is read-only, so every caller job declares its own `permissions:` block matching what the reusable requires. A caller without one fails at startup with no logs.

## References

- [SKILL.md](skills/php-structured-edit/SKILL.md) — agent runtime instructions and workflow
- [operations.md](skills/php-structured-edit/references/operations.md) — edit schema, targets, guards, parseAs contexts, operation catalog
- [formatting-contract.md](skills/php-structured-edit/references/formatting-contract.md) — the precondition, the tools that can and cannot canonicalise, the fallback
- [enforcement.md](skills/php-structured-edit/references/enforcement.md) — wiring the PreToolUse gate
- [README.md](README.md) — installation, usage, transaction safety
- [installation.md](docs/installation.md) — source, Composer and executable release installations
- [benchmarks](benchmarks/README.md) — fair comparison protocol and evidence requirements
- [skill invocation](benchmarks/skill-invocation/README.md) — whether the model reaches for the skill at all
- [CHANGELOG.md](CHANGELOG.md) — released versions
