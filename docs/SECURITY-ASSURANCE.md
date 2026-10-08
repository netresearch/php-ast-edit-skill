<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<!-- SPDX-FileCopyrightText: Netresearch DTT GmbH -->

# Security assurance case — php-ast-edit-skill

This document states what a user can expect from this repository in terms of security, and argues why that expectation holds. Every claim names the file that implements it and, where one exists, the test that checks it. Reporting a vulnerability: see the organisation's [security policy](https://github.com/netresearch/.github/blob/main/SECURITY.md).

## What the repository ships

| Part | Files | Runs where |
| --- | --- | --- |
| PHP command-line editor `php-ast-edit` | `bin/php-ast-edit`, `src/` | On the user's machine, with the user's privileges, in the PHP project it edits |
| Skill instructions and wrapper | `skills/php-structured-edit/SKILL.md`, `references/*.md`, `scripts/php-ast-edit` | The agent reads the Markdown as instructions; the wrapper finds and runs the editor |
| Enforcement hook | `hooks/php-ast-only.py` | In the agent harness, before each tool call, when a user wires it up |
| Release artefacts | PHAR, archives, `runtime-dependencies.json`, `SHA256SUMS.txt` built by `scripts/build-release.sh` | Downloaded by users from GitHub releases |
| Tests and benchmark tooling | `tests/`, `benchmarks/`, `scripts/check.php` | In this repository's CI and on contributors' machines |

The editor has no network listener, stores no credentials and keeps no state outside the files it is asked to change, its temporary files and the configuration file `normalize` writes.

## Security requirements

1. The editor never executes the PHP source it reads or writes.
2. A write happens only when the source still matches the snapshot the request was prepared from; otherwise nothing is written.
3. A failure while writing or formatting leaves the files as they were before the transaction.
4. Commands the editor runs receive file paths and configuration values as separate arguments, never as shell text.
5. The one external program the editor runs from a configured path, Phpactor, runs only when it is the exact pinned release.
6. Release artefacts can be verified against the workflow run that built them.

## Actors and trust boundaries

- **Caller (user or agent).** Sends an edit request as JSON (`apply --input`, file or stdin) or as command-line options (`rename`, `inspect`, `format`, `normalize`, `doctor`). The request names the files to edit, create or delete. The editor acts with the caller's file-system permissions; it adds no privilege and removes none.
- **Edited PHP source.** Read from disk and parsed by `nikic/php-parser` (`src/Editor.php`, `src/ContextParser.php`). Snippets in a request are parsed the same way. Source is data to the editor.
- **Repository configuration `.php-ast-edit.json`.** Declares canonical printing, excluded paths, a `formatter` command, `verify` commands and the Phpactor PHAR (`src/RepositoryConfig.php`). The editor runs the declared commands, so this file is trusted like a project's Composer scripts or Makefile. It is read only from the edited file's own project: the search stops at the nearest directory holding `.git`, outside version control at the nearest holding `composer.json`, and a file owned by somebody else is refused.
- **Phpactor.** An optional resolver for project-wide method renames, located through `PHP_AST_EDIT_PHPACTOR` or the `phpactor` key (`src/PhpactorReferenceFinder.php`).
- **Agent harness.** Runs the hook (`hooks/php-ast-only.py`) if the user wires it up (`skills/php-structured-edit/references/enforcement.md`).
- **Contributors and CI.** Changes reach `main` through pull requests checked by the workflows in `.github/workflows/`. Every workflow sets `permissions: {}` at the top and grants each job only what it needs.

## Threats and countermeasures

| Threat | Countermeasure | Evidence |
| --- | --- | --- |
| Edited or snippet source gets executed (CWE-94) | Source and snippets are only parsed and printed. The lint step runs `PHP_BINARY -n -l` on a temporary copy, which compiles without executing and without loading `php.ini` | `src/PhpLint.php`; `src/` has no `eval`, `exec`, `system`, `shell_exec`, `passthru`, `popen` or `unserialize` |
| A file path or configured argument is interpreted by a shell (CWE-78) | Every external command is started with `proc_open` and an argument array: `verify` and `formatter` commands, `php -l`, Phpactor and `git ls-files`. `{files}` must be a whole argument and expands to one argument per file | `src/VerificationRunner.php`, `src/Editor.php`, `src/PhpLint.php`, `src/PhpactorReferenceFinder.php`, `src/ProjectIndex.php`, `src/RepositoryConfig.php`; `tests/verification.php` ("argv data was interpreted by a shell", "shell syntax executed") |
| A request built from an old read overwrites newer work (CWE-367) | An optional `sha256` per file is compared with `hash_equals` when the request is prepared; before the first write every changed file is hashed again, and a change since preparation aborts the whole transaction with `CONCURRENT_CHANGE` before anything is written | `src/Editor.php` (`assertSha`, `assertUnchangedOnDisk`); `tests/transactions.php`, `tests/matrix.php` (`STALE_SOURCE`) |
| A half-written file after a crash or a failed step | Every file is prepared and parsed before the first write. Each write goes to a temporary file in the target's own directory and is renamed over the target. A failure while writing or formatting restores the original bytes, mode and symlink of every file already written, in reverse order | `src/AtomicWriter.php`, `src/FileRestorer.php`, `src/Editor.php` (`commit`); `tests/transactions.php` ("rollback leaves target bytes", "rollback restores symlink identity") |
| A write replaces a symlink with a regular file (CWE-59) | The writer resolves the link chain (at most 40 links) and writes the target, so the link stays a link; the transaction also refuses when a link's target changed during preparation | `src/AtomicWriter.php`, `src/Editor.php`; `tests/transactions.php` |
| A substituted Phpactor PHAR runs (CWE-494) | The editor hashes the configured PHAR and refuses any file that is not the pinned release. Phpactor runs with its own XDG directories (mode 0700) and is stopped after 180 seconds | `src/PhpactorReferenceFinder.php`; `tests/project-rename.php` ("a PHAR that is not the pinned release is refused") |
| A method rename changes files outside the project | `rename` accepts only a non-symlink PHP file in the project for `--file`, and project-wide renames change only files that `git ls-files` lists for the project | `src/MethodRenameCommand.php`, `src/ProjectRename.php`, `src/ProjectIndex.php`; `tests/project-rename.php` |
| A configuration file outside the project, or one written by another user, supplies the commands the editor runs (CWE-426) | `discover()` looks for `.php-ast-edit.json` from the edited file up to the nearest directory holding `.git` and no further; outside version control up to the nearest holding `composer.json`, and outside both only in the file's own (or deepest existing) directory. A file whose owner is not the current user (with PHP's POSIX extension loaded) or not the owner of the directory the search starts in (without it) is refused | `src/RepositoryConfig.php`; `tests/formatting.php` ("a declaration above the project root is not read", "a package in a repository finds the declaration at the repository root", "a declaration owned by another user is refused") |
| Malformed or deeply nested JSON input | Requests and configuration are decoded with `JSON_THROW_ON_ERROR` and a depth limit (512 for requests, 32 for configuration); malformed `formatter`, `verify`, `exclude`, `printWidth` and `phpactor` values are refused | `src/Application.php`, `src/RepositoryConfig.php`; `tests/verification.php` |
| A release artefact is tampered with | The release workflow verifies that the tag is annotated and signed, builds with a production-only Composer install, tests the exact archives, signs `SHA256SUMS.txt` with Cosign, verifies the signature and attests build provenance before publishing | `.github/workflows/release.yml`, `scripts/build-release.sh`, `scripts/build-phar.php`, `tests/distribution.sh` |
| A development dependency ends up in a release | The build installs with `--no-dev`, `build-phar.php` refuses a development install, and `build-release.sh` fails if `runtime-dependencies.json` shows `dev: true` or `friendsofphp/php-cs-fixer` | `scripts/build-release.sh`, `scripts/build-phar.php`; `tests/distribution.php` checks the same for the built PHAR |
| A third-party action in CI is replaced | Third-party actions are pinned to a commit SHA. The repository's own jobs (Formatting, PHP Tests, Distribution, Release) start with Harden Runner and check out without persisted credentials | `.github/workflows/*.yml` |
| A behaviour change goes unnoticed | The runtime suite runs on PHP 8.2 to 8.5 on every push and pull request, and the distribution suite installs and runs the built artefacts | `.github/workflows/php-tests.yml`, `.github/workflows/distribution.yml`, `tests/run.sh` |

Which checks must pass before a pull request can merge is set in the branch protection of `main`, not in this repository.

## Secure design principles applied

- **Least privilege:** the editor needs no privilege beyond write access to the files it edits. Workflows grant permissions per job.
- **Fail-safe defaults:** ambiguous selectors, stale snapshots, unsupported rename cases and an unpinned Phpactor are refused rather than guessed. A failed write rolls back.
- **Complete mediation:** each file is hashed again before the first write, not only when the request is read.
- **Economy of mechanism:** one runtime library (`nikic/php-parser`); external commands only where the configuration or the rename resolver asks for them.
- **Open design:** operations, guards and limits are documented in `skills/php-structured-edit/references/operations.md` and `docs/limits-and-alternatives.md`.

## What a user cannot expect

- `apply` acts on the paths named in the request, with the caller's permissions. It does not confine them to a project directory: a request can create, edit or delete a file elsewhere if the caller may write there. Only `rename` restricts itself to project files.
- The editor runs the `formatter` and `verify` commands declared in `.php-ast-edit.json`, with no time limit. Use it only in repositories whose configuration you trust, as with Composer scripts.
- The transaction is not atomic for the operating system: concurrent readers can see some files written and others not, and side effects of configured commands are outside the rollback (README, "Guarantees and limits").
- Parsing and `php -l` show that the output is syntactically valid PHP, not that it behaves correctly. Run the project's tests.
- The enforcement hook is a linter-like aid with documented bypasses, not a security boundary (`skills/php-structured-edit/references/enforcement.md`).
- This repository's CI scans the git history for secrets (Betterleaks), checks the workflow files with zizmor, reviews dependency changes on pull requests, runs Composer Audit and an Opengrep static analysis (`.github/workflows/security.yml`). CodeQL default setup and SonarCloud automatic analysis, configured outside the repository, add static analysis on pull requests. Such scans report known patterns; they do not show that the code is free of vulnerabilities. The organisation's rule for static analysis is [Static analysis (SAST)](https://github.com/netresearch/.github/blob/main/SECURITY.md#static-analysis-sast); its policy on handling findings is linked from the README.
- Security fixes follow the supported-versions rules of the organisation's security policy; older releases may not receive them.
