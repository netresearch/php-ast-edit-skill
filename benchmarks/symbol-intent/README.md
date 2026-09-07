# Experimental symbol intent

One request can express `rename method:Provider::fetch to load`, including its
resolved PHP references in other files. The LLM selects the symbol and new name;
the tool finds coordinates, validates name slots and submits one guarded AST
transaction. This is a benchmark prototype, not a shipped engine operation.

The AST alone does not resolve project symbols. This prototype composes the pinned
[Phpactor 2026.07.22.0](https://github.com/phpactor/phpactor/releases/tag/2026.07.22.0)
language server with `php-ast-edit`. Each invocation builds a fresh index. It rejects
resolver error notifications, unexpected indexing scope and unsupported edits.

## Run

Requires Linux, Python 3.10+, PHP 8.2+, installed engine dependencies and a downloaded
Phpactor PHAR. The PHAR SHA-256 must be
`8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d`.
The digest is checked at runtime; the binary is not vendored.

```bash
python3 benchmarks/symbol-intent/symbol_intent.py rename_method \
  --root /absolute/workspace --state /absolute/external-state \
  --phpactor /absolute/phpactor.phar \
  --file Provider.php --select 'method:Provider::fetch' --to load
```

`plan` takes the same arguments and performs analysis only. Use its content-hashed
ID with `show_plan --state ... --plan ID` or `apply_plan --state ... --plan ID`.
`rename_method` performs planning and apply under one local lock, without a model
round trip between them. Full plans, resolver messages and engine reports remain
in the external state directory. The concise result aggregates passed validations
and preserves warnings, failed checks, skipped lint and affected file paths.

Plans bind the complete workspace file inventory and tool/dependency bytes. Added,
removed or changed files invalidate a plan. Name edits carry AST references, node
expectations and source hashes. Consumed plans cannot be replayed. As with ordinary
engine apply, exit 1 means edits were retained but verification failed; exit 2 means
planning or application was rejected. Consult retained reports after interruption.

## Deliberate limits

- Trusted, self-contained workspaces only: no symlinks, custom Phpactor config,
  Composer autoload integration, external stubs or vendor dependencies. Maximum
  2,000 files, 64 MB total and less than 1 MB per PHP file. State lives outside root.
- Static method-name identifiers only: declarations, method/nullsafe/static calls.
  No dynamic name expressions, magic methods, resource operations, file moves,
  PHPDoc edits, strings, YAML, Fluid, TypoScript or framework-specific references.
- Local declaration collisions are rejected. Inheritance and ambiguous receiver
  coverage are not established. Phpactor can omit unresolved references, so every
  result explicitly says `completeness: unknown`, including successful results.
- File hashes detect drift, not malicious concurrent filesystem changes. The state
  directory is trusted local storage, not a sandbox or authenticated approval store.
- This is an experiment with no new production dependency or public API promise.
  A project-wide production rename needs stronger scope/typing guarantees and
  relevant behavior checks before it can claim completeness.

## Validate without model calls

```bash
python3 benchmarks/symbol-intent/test_symbol_intent.py
PHP_AST_TEST_PHPACTOR=/absolute/phpactor.phar \
  python3 benchmarks/symbol-intent/test_symbol_intent.py
```

The integration suite renames across 2, 10 and 50 files, checks exact source and
runtime dispatch, preserves unrelated methods with the same name, and tests stale
plans, plan tampering, replay, Unicode coordinates and retained verification failure.
These are functional tests, not evidence of LLM token savings.

The prospective [economics protocol](PROTOCOL.md) compares this API with batched
text changes and an existing Phpactor CLI route. It distinguishes the benefit of
delegating symbol work from any additional benefit of the AST write transaction.

From a clean committed checkout, prepare without model calls, then execute the
already authorized pilot explicitly using its frozen controller:

```bash
python3 benchmarks/symbol-intent/pilot.py prepare \
  --output /tmp/php-symbol-pilot --phpactor /absolute/phpactor.phar
python3 /tmp/php-symbol-pilot/source/benchmarks/symbol-intent/pilot.py run \
  --output /tmp/php-symbol-pilot --execute-models
python3 /tmp/php-symbol-pilot/source/benchmarks/symbol-intent/pilot.py summarize \
  --output /tmp/php-symbol-pilot
```

Preparation freezes source, dependencies, task bytes, prompts and schedule. The
controller is single-use; interruptions retain evidence and require offline review.
The normal test suite runs without Phpactor and explicitly skips LSP integration.
Set `PHP_AST_TEST_PHPACTOR` for both prototype and existing-CLI control integration.
