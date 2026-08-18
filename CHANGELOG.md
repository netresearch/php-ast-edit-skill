# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

### Added

- `php-ast-edit` CLI with `inspect`, `apply` and `validate` commands.
- Ten typed operations: `set_name`, `set_string`, `replace_expression`, `replace_statement`, `insert_before`, `insert_after`, `delete`, `replace_argument`, `add_argument`, `remove_argument`.
- Transaction guards: SHA-256 optimistic lock, expected node type/name/value, attachment check before each edit, reparse before write, atomic rename.
- `php-structured-edit` Agent Skill with the operation reference and a wrapper resolving the repository binary, `vendor/bin`, a local PHAR, or `PATH`.
- PHAR build via `scripts/build-phar.php`.

[Unreleased]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/netresearch/php-ast-edit-skill/releases/tag/v0.1.0
