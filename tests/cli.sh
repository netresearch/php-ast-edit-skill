#!/usr/bin/env bash
# The skill tells agents to drive the CLI, not the Editor class: these are the argument
# shapes, output fields and exit codes SKILL.md promises. tests/run.php and tests/matrix.php
# both bypass all of it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f vendor/autoload.php ]; then
  echo "SKIP: vendor/autoload.php missing; the CLI needs the parser."
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

BIN="php $ROOT/bin/php-ast-edit"
fail=0

expect() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "ok   $label"
  else
    echo "FAIL $label: expected [$expected], got [$actual]" >&2
    fail=1
  fi
}

printf '<?php\nclass Foo\n{\n}\n' > "$WORK/a.php"

expect "inspect --line/--column names the smallest node" "Identifier" \
  "$($BIN inspect --file "$WORK/a.php" --line 2 --column 7 | php -r 'echo json_decode(stream_get_contents(STDIN), true)["nodes"][0]["type"];')"

expect "inspect returns a structural ref" "stmts[0].name" \
  "$($BIN inspect --file "$WORK/a.php" --line 2 --column 7 | php -r 'echo json_decode(stream_get_contents(STDIN), true)["nodes"][0]["ref"];')"

expect "inspect --offset addresses the same node" "Identifier" \
  "$($BIN inspect --file "$WORK/a.php" --offset 12 | php -r 'echo json_decode(stream_get_contents(STDIN), true)["nodes"][0]["type"];')"

expect "inspect --kind filters the ancestry" "1" \
  "$($BIN inspect --file "$WORK/a.php" --offset 12 --kind Stmt_Class | php -r 'echo count(json_decode(stream_get_contents(STDIN), true)["nodes"]);')"

expect "contexts lists the file mode catalog" "edit create delete" \
  "$($BIN contexts | php -r 'echo implode(" ", json_decode(stream_get_contents(STDIN), true)["fileModes"]);')"

# apply from stdin, dry run: reports the change without touching the file
BEFORE="$(cat "$WORK/a.php")"
printf '{"files":[{"path":"%s","edits":[{"target":{"ref":"stmts[0]"},"operation":"add_member","php":"public int $n = 1;"}]}]}' "$WORK/a.php" \
  | $BIN apply --dry-run > "$WORK/dry.json"
expect "apply --dry-run reports the change" "1" \
  "$(php -r 'echo (int) json_decode(file_get_contents($argv[1]), true)["files"][0]["changed"];' "$WORK/dry.json")"
expect "apply --dry-run leaves the file alone" "$BEFORE" "$(cat "$WORK/a.php")"

# apply from a file: writes
printf '{"files":[{"path":"%s","edits":[{"target":{"ref":"stmts[0].name"},"operation":"set_name","value":"Bar"}]}]}' "$WORK/a.php" > "$WORK/edits.json"
$BIN apply --input "$WORK/edits.json" > /dev/null
expect "apply --input writes the change" "1" "$(grep -c 'class Bar' "$WORK/a.php")"

# failures are JSON on stderr with a non-zero exit
set +e
$BIN inspect --file "$WORK/missing.php" --line 1 --column 1 > /dev/null 2> "$WORK/err.json"
code=$?
set -e
expect "a missing file exits 2" "2" "$code"
expect "the failure is machine-readable" "0" \
  "$(php -r 'echo (int) (json_decode(file_get_contents($argv[1]), true)["ok"] ?? true);' "$WORK/err.json")"

set +e
$BIN bogus > /dev/null 2>&1
code=$?
set -e
expect "an unknown command exits 2" "2" "$code"

if [ "$fail" -ne 0 ]; then
  echo "FAIL: CLI surface check failed." >&2
  exit 1
fi

echo "OK: CLI surface behaves as documented."
