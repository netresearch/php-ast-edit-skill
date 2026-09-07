# Experimental symbol intent

One request can express `rename method:Provider::fetch to load`, including its
resolved PHP references in other files. The LLM selects the symbol and new name;
the tool finds coordinates, validates name slots and submits one guarded AST
transaction. This is a benchmark prototype, not a shipped engine operation.

The [completed 27-run Haiku pilot](results/2026-09-07-haiku/REPORT.md) shows the
strongest savings at 50 files, much smaller token gains at 2/10 files, and a strong
existing-Phpactor control. All raw observations and accounting amendments are public.

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

Pass `--evidence` to `rename_method` or `apply_plan` for a more compact, evidence-bearing
result. It echoes the request, shows planned/applied edit totals, and replaces repeated
`file_issues` with `issue_groups` containing identical validation/warnings and all their
paths. The default response remains unchanged.
Within evidence groups, lint's PHP version is named `php_version` to distinguish
the interpreter version from elapsed time; the engine report retains its own schema.

`exact_edit_match.status: passed` means the tool read the workspace again **after**
engine apply and configured verification, and every non-Git file matched the expected
SHA-256 inventory for exactly the resolved, AST-validated identifier replacements.
Thus all other bytes, including unrelated identifiers, comments and strings, stayed
unchanged. Expected bytes are computed only for verification; the engine is still the
only PHP writer. The hashed plan stores the expected inventory; a `.readback.json`
sidecar beside `full_report` stores the observed inventory.
If that sidecar cannot be saved, `READBACK_NOT_SAVED` preserves the engine outcome
and inline evidence while reporting that the durable readback artifact is unavailable.

This evidence does **not** verify the resolver's binding choices or completeness.
An omitted reference can coexist with a passing exact-edit check. Behavior checks
and `completeness: unknown` therefore remain separate. Formatters or verifier side
effects can make exact byte preservation `not_established` even when engine apply
succeeds; inspect the mismatched files. An unreadable or unsupported final workspace
also yields `not_established`. Failed or skipped checks remain visible and never
become passes because the bytes matched. The evidence describes the readback instant,
not protection against a malicious concurrent writer.

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
The separate [post-rename ablation](POSTCHECK_PROTOCOL.md) crosses result evidence
with scoped verification guidance to test their effects without changing that pilot.

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
controller never reruns an attempted candidate. The documented accounting-scope
amendment supports offline `recover`, followed by explicit `run --resume-reviewed`;
both retain the original trace and measurement and verify the recovery sidecar.
The normal test suite runs without Phpactor and explicitly skips LSP integration.
Set `PHP_AST_TEST_PHPACTOR` for both prototype and existing-CLI control integration.
