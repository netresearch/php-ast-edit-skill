#!/usr/bin/env bash
# Test entrypoint. Picked up by the tests.yml reusable (tests/**/*.sh) and runnable locally.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f vendor/autoload.php ]]; then
  echo "Missing dependencies: run composer install before tests/run.sh." >&2
  exit 2
fi
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --runtime-only ) ]]; then
  echo "Usage: bash tests/run.sh [--runtime-only]" >&2
  exit 2
fi

fail=0

echo "::group::scripts/check.php (php -l over shipped sources)"
php scripts/check.php || fail=1
echo "::endgroup::"

echo "::group::tests/run.php (inspect/apply round-trip)"
php tests/run.php || fail=1
echo "::endgroup::"

echo "::group::tests/matrix.php (grammar and operation coverage matrix)"
php tests/matrix.php || fail=1
echo "::endgroup::"

echo "::group::tests/guidance.php (what a refusal says next)"
php tests/guidance.php || fail=1
echo "::endgroup::"

echo "::group::tests/scoped-replace.php (replace by what the code says, inside a named scope)"
php tests/scoped-replace.php || fail=1
echo "::endgroup::"

echo "::group::tests/renames.php (binding collisions and method dispatch)"
php tests/renames.php || fail=1
echo "::endgroup::"

echo "::group::tests/transactions.php (guards, rollback and validation contract)"
php tests/transactions.php || fail=1
echo "::endgroup::"

echo "::group::tests/verification.php (project and changed-file verification)"
php tests/verification.php || fail=1
echo "::endgroup::"

echo "::group::tests/reports.py (shared verification reports and compatibility)"
python3 tests/reports.py || fail=1
echo "::endgroup::"

echo "::group::skills/php-structured-edit/scripts/php-ast-edit (wrapper resolves an executable)"
bash skills/php-structured-edit/scripts/php-ast-edit validate --file tests/fixtures/sample.php || fail=1
echo "::endgroup::"

echo '::group::tests/php-floor.php (new-expression dereference below PHP 8.4)'
php tests/php-floor.php || fail=1
echo "::endgroup::"

echo "::group::tests/formatting.php (canonical printing, fallback, doctor)"
php tests/formatting.php || fail=1
echo "::endgroup::"

echo "::group::tests/imports.php (add_use: idempotence, group uses, name collisions)"
php tests/imports.php || fail=1
echo "::endgroup::"

echo "::group::tests/catalog.php (dispatcher, contexts catalog and docs agree)"
php tests/catalog.php || fail=1
echo "::endgroup::"

echo "::group::tests/cli.sh (CLI surface: inspect, apply, exit codes)"
bash tests/cli.sh || fail=1
echo "::endgroup::"

echo "::group::tests/recompute.sh (published figures recompute from their own tables)"
bash tests/recompute.sh || fail=1
echo "::endgroup::"

echo "::group::tests/examples.py (documented apply examples run and match the recommendation)"
python3 tests/examples.py || fail=1
echo "::endgroup::"

echo "::group::tests/hook.py (enforcement gate behaviour table)"
python3 tests/hook.py || fail=1
echo "::endgroup::"

echo "::group::tests/corpus.php (real-world round trip through the AST)"
php -d memory_limit=1G tests/corpus.php || fail=1
echo "::endgroup::"

echo "::group::docs/quickstart.sh (documented first edit and runtime result)"
bash docs/quickstart.sh || fail=1
echo "::endgroup::"

echo "::group::benchmarks/agent_benchmark.py (task oracles and evidence validation)"
python3 benchmarks/agent_benchmark.py self-test || fail=1
echo "::endgroup::"

echo "::group::efficiency harness (private campaign directories and native timing)"
python3 benchmarks/agent-economics/efficiency/test_harness.py || fail=1
echo "::endgroup::"

echo "::group::efficiency adapter (real-engine revision guards and source views)"
python3 benchmarks/agent-economics/efficiency/adapter/test_adapter.py || fail=1
echo "::endgroup::"

echo "::group::skill invocation summary (which runs a task filter keeps and drops)"
python3 benchmarks/skill-invocation/test_summarize.py || fail=1
echo "::endgroup::"

echo "::group::skill invocation arms (dependency isolation and the poisoned-subject guard)"
python3 benchmarks/skill-invocation/test_run.py || fail=1
echo "::endgroup::"

echo "::group::symbol intent (offline guards and pilot oracles; LSP integration opt-in)"
python3 -m unittest discover -s benchmarks/symbol-intent -p 'test_*.py' || fail=1
echo "::endgroup::"

if [[ "${1:-}" != --runtime-only ]]; then
  echo "::group::tests/distribution.sh (clean install and executable artifacts)"
  bash tests/distribution.sh || fail=1
  echo "::endgroup::"
fi

if [ "$fail" -ne 0 ]; then
  echo "FAIL: at least one check failed." >&2
  exit 1
fi

echo "OK: all checks passed."
