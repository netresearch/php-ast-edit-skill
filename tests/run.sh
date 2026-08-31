#!/usr/bin/env bash
# Test entrypoint. Picked up by the tests.yml reusable (tests/**/*.sh) and runnable locally.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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

echo "::group::skills/php-structured-edit/scripts/php-ast-edit (wrapper resolves an executable)"
if [ -f vendor/autoload.php ]; then
  skills/php-structured-edit/scripts/php-ast-edit validate --file tests/fixtures/sample.php || fail=1
else
  echo "SKIP: vendor/autoload.php missing; wrapper needs the parser."
fi
echo "::endgroup::"

echo "::group::tests/cli.sh (CLI surface: inspect, apply, exit codes)"
bash tests/cli.sh || fail=1
echo "::endgroup::"

echo "::group::scripts/build-phar.php (PHAR builds and answers)"
if [ -f vendor/autoload.php ]; then
  php -d phar.readonly=0 scripts/build-phar.php
  php dist/php-ast-edit.phar validate --file tests/fixtures/sample.php || fail=1
  # `validate` never touches ContextParser or FileTransaction; `contexts` does, so this is
  # what proves the whole engine is inside the archive.
  php dist/php-ast-edit.phar contexts > /dev/null || fail=1
else
  echo "SKIP: vendor/autoload.php missing; PHAR build needs the parser."
fi
echo "::endgroup::"

if [ "$fail" -ne 0 ]; then
  echo "FAIL: at least one check failed." >&2
  exit 1
fi

echo "OK: all checks passed."
