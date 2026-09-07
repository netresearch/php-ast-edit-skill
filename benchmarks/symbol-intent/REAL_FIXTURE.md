# Extracted public PHP fixture

This benchmark exports six original PHP files from the public
[`netresearch/t3x-nr-llm` commit b505c936935b99baa3088ce62ad222d2ba61cee0](https://github.com/netresearch/t3x-nr-llm/commit/b505c936935b99baa3088ce62ad222d2ba61cee0).
The export includes the upstream `LICENSE`, original copyright/SPDX headers,
and deterministic `PROVENANCE.json` with source hashes. Upstream declares
`GPL-2.0-or-later`. PHP source is extracted into disposable directories. Published
benchmark evidence may include those licensed snapshots; they are not engine
runtime dependencies.

The task renames `SchemaPropertyClassifier::classify()` to `controlType()`.
The extracted scope has one declaration, one production caller in
`SchemaInputCoercer`, and one direct test caller. The second upstream production
caller, `WaitingRunViewFactory`, depends on TYPO3 and is explicitly excluded.
This is an extracted public-source benchmark, not a full TYPO3 application
refactor or a run of the upstream Docker/PHP/TYPO3 test matrix.

The source closure is:

```text
Classes/Service/Tool/SchemaPropertyClassifier.php
Classes/Service/Tool/SchemaInputCoercer.php
Classes/Service/Schema/JsonSchemaValidator.php
Classes/Service/Schema/StrictSchemaSubset.php
Tests/Unit/Service/Tool/SchemaPropertyClassifierTest.php
Tests/Unit/Service/Tool/SchemaInputCoercerTest.php
```

`SchemaInputCoercerTest` constructs `JsonSchemaValidator`, whose default
constructor constructs `StrictSchemaSubset`. The tests use their original
assertions and inputs: ten classifier data cases and seven coercer tests.
Only the direct test's target method identifier changes after the rename.
There is no same-name runtime control in this extraction: the other upstream
`classify()` classes need additional exception-family or TYPO3 dependencies.
The independent oracle still requires all unaffected source, assertions, inputs,
license and provenance bytes to remain unchanged.

## Export and behavior check

Obtain the public Git repository separately and pass its path to the exporter.
The source checkout is only read; its current branch, working-tree contents and
untracked files do not affect export. `git show COMMIT:PATH` reads exact pinned
objects, including tests marked `export-ignore` in upstream archives. Every
object's SHA-256 is checked before the first output byte is written.

```bash
python3 benchmarks/symbol-intent/real_fixture.py export /tmp/classifier-fixture \
  --source-repo /path/to/t3x-nr-llm
python3 benchmarks/symbol-intent/real_fixture.py check /tmp/classifier-fixture \
  --phpunit /path/to/phpunit-12.5.31.phar \
  --receipt-dir /tmp/classifier-check-receipts
```

The checker pins PHPUnit **12.5.31**, SHA-256
`194fcb6621866b542f1304e0da8dc7abcb15d6f9d1851893aec40896bcf5bb44`,
as published in the [official PHAR index](https://phar.phpunit.de/).
It verifies the PHAR before executing it and never downloads dependencies.
The PHP source requires PHP 8.2 or newer; this PHPUnit release requires PHP 8.3
or newer and its normal PHP extensions. Use `--php` to choose an interpreter.

The bootstrap autoloads only the exported `Netresearch\NrLlm` classes. It does
not load the original repository's Composer autoloader. PHPUnit runs with no
project configuration, result caching disabled, and its bootstrap, cache and
JUnit report outside the fixture. Tests require no network, database, TYPO3
instance or model access. They run in both baseline and correctly renamed states.

Candidate-facing stdout is one JSON object containing `ok`, `tests`, `assertions`,
`returncode`, `duration_ms`, and an optional `receipt` path. Success requires exit
zero, all 17 tests executed, and identical fixture manifests before and after
the check. A failed run has exit status one and includes up to 4,000 characters
of actual PHPUnit diagnostics so the candidate can inspect a failed caller.
Unreadable or malformed JUnit metadata, including missing required counters or
an absent leaf suite, produces null (unknown) counts. It does
not establish that zero tests or failures occurred and cannot satisfy the check.
This command does not consult the
hidden expected edit inventory and cannot certify rename completeness by itself.

## Controller API and independent grading

`real_fixture.py` uses Python's standard library only:

- `export(root, source_repo)` returns source provenance.
- `task(root)` returns the intent selector, target name and expected edit metadata.
- `snapshot(root)` returns relative file paths mapped to SHA-256, excluding only
  the root `.git` metadata and refusing symlinks.
- `expected_inventory(renamed=True)` returns the pinned final inventory;
  `renamed=False` selects original bytes.
- `oracle(root, renamed=True, allowed_extras=None)` compares exact bytes. Extras
  are an independently frozen relative-path-to-hash mapping, for example the
  controller's `.php-ast-edit.json`. Extras cannot override any source/provenance
  entry. Do not expose oracle results or expected edits to the candidate.
- `check(root, phpunit, receipt_dir=None, php="php", timeout=60)` returns the full
  local observation, including stdout/stderr and manifests.
- `command(root, phpunit, receipt_dir=None, php="php")` returns an argv list for
  the concise candidate-facing checker CLI.

Keyword options must be passed by name. A receipt directory must be outside the
fixture. Each check creates a unique UUID-named JSON file using exclusive create
mode; previous receipts are never overwritten. Receipts include `before`, `after`,
`ok`, `tests`, `assertions`, `returncode`, `duration_ms`, start/end timestamps,
`fixture_unchanged`, `timed_out`, pinned PHPUnit identity, argv, stdout/stderr and
JUnit counts. These are trusted local observations, not a hostile-agent-proof
attestation or a claim that files cannot be changed after creation.

To determine whether the candidate tested the exact final bytes, the controller
must require a successful receipt with `returncode == 0`, `tests == 17`, and
`before == after == final_manifest`. A test of an earlier state, or a check during
which files changed, does not qualify. Independently run the hidden oracle on
the final state. Keeping the two judgments separate catches weakened assertions
even when PHPUnit still passes.

## Verification

Offline tests cover missing callers, untouched byte scope, frozen extras,
symlink refusal, PHAR pinning and source mutation during a successful test run.
Public-source integration is opt-in:

```bash
cd benchmarks/symbol-intent
NR_LLM_SOURCE_REPO=/path/to/t3x-nr-llm \
PHP_AST_TEST_PHPUNIT=/path/to/phpunit-12.5.31.phar \
python3 -m unittest test_real_fixture.py -v
```

Integration exports disposable source, runs the original suite before and after
the exact rename, proves an omitted production caller fails PHPUnit, and proves
a weakened assertion can pass PHPUnit while failing the hidden inventory oracle.
Neither the implementation nor these tests invoke a model.
