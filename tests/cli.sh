#!/usr/bin/env bash
# The skill tells agents to drive the CLI, not the Editor class: these are the argument
# shapes, output fields and exit codes SKILL.md promises. tests/run.php and tests/matrix.php
# both bypass all of it.
# PHP variables in single-quoted code and JSON must reach PHP without shell expansion.
# shellcheck disable=SC2016
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f vendor/autoload.php ]]; then
  echo "SKIP: vendor/autoload.php missing; the CLI needs the parser."
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

run_cli() { php "$ROOT/bin/php-ast-edit" "$@"; }
BIN=run_cli
fail=0

expect() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "ok   $label"
  else
    echo "FAIL $label: expected [$expected], got [$actual]" >&2
    fail=1
  fi
}

# The fixture itself goes through the tool: this repository does not write PHP as text, and
# it doubles as the CLI's only coverage of mode "create".
printf '{"files":[{"path":"%s","mode":"create","php":"<?php class Foo {}"}]}' "$WORK/a.php" \
  | $BIN apply > /dev/null
expect "apply mode create writes a new file" "1" "$(grep -c 'class Foo' "$WORK/a.php")"

expect "inspect --line/--column names the smallest node" "Identifier" \
  "$($BIN inspect --file "$WORK/a.php" --line 3 --column 7 | php -r 'echo json_decode(stream_get_contents(STDIN), true)["nodes"][0]["type"];')"

expect "inspect returns a structural ref" "stmts[0].name" \
  "$($BIN inspect --file "$WORK/a.php" --line 3 --column 7 | php -r 'echo json_decode(stream_get_contents(STDIN), true)["nodes"][0]["ref"];')"

# The canonical print is deterministic, so the byte offset of the class name is too.
OFFSET="$(php -r 'echo strpos(file_get_contents($argv[1]), "Foo");' "$WORK/a.php")"
expect "inspect --offset addresses the same node" "Identifier" \
  "$($BIN inspect --file "$WORK/a.php" --offset "$OFFSET" | php -r 'echo json_decode(stream_get_contents(STDIN), true)["nodes"][0]["type"];')"

expect "inspect --kind filters the ancestry" "1" \
  "$($BIN inspect --file "$WORK/a.php" --offset "$OFFSET" --kind Stmt_Class | php -r 'echo count(json_decode(stream_get_contents(STDIN), true)["nodes"]);')"

expect "contexts lists the file mode catalog" "edit create delete" \
  "$($BIN contexts | php -r 'echo implode(" ", json_decode(stream_get_contents(STDIN), true)["fileModes"]);')"

$BIN contexts --operation rename_variable > "$WORK/operation.json"
expect "targeted contexts returns only one operation contract" "true" \
  "$(jq 'keys == ["arguments", "operation"] and .operation == "rename_variable" and (.arguments | tostring | contains("from"))' "$WORK/operation.json")"
set +e
$BIN contexts --operation no_such_operation > /dev/null 2> "$WORK/unknown-operation.json"
operation_code=$?
set -e
expect "unknown operation exits 2" "2" "$operation_code"
expect "unknown operation is machine-readable" "false" "$(jq '.ok' "$WORK/unknown-operation.json")"

# apply from stdin, dry run: reports the change without touching the file
BEFORE="$(cat "$WORK/a.php")"
printf '{"files":[{"path":"%s","edits":[{"target":{"ref":"stmts[0]"},"operation":"add_member","php":"public int $n = 1;"}]}]}' "$WORK/a.php" \
  | $BIN apply --dry-run > "$WORK/dry.json"
expect "apply --dry-run reports the change" "1" \
  "$(php -r 'echo (int) json_decode(file_get_contents($argv[1]), true)["files"][0]["changed"];' "$WORK/dry.json")"
expect "apply --dry-run leaves the file alone" "$BEFORE" "$(cat "$WORK/a.php")"
expect "dry-run separates parse, lint and project checks" "true" \
  "$(jq '.files[0] | .parsed == true and .validation.parser == "passed" and .validation.lint.status == "passed" and .validation.checks == "not_run"' "$WORK/dry.json")"

# apply from a file: writes
printf '{"files":[{"path":"%s","edits":[{"target":{"ref":"stmts[0].name"},"operation":"set_name","value":"Bar"}]}]}' "$WORK/a.php" > "$WORK/edits.json"
$BIN apply --input "$WORK/edits.json" > /dev/null
expect "apply --input writes the change" "1" "$(grep -c 'class Bar' "$WORK/a.php")"

expect "doctor reports a bare workspace as warn" "warn" \
  "$(cd "$WORK" && $BIN doctor | php -r 'echo json_decode(stream_get_contents(STDIN), true)["status"];')"

# The width is the project's declaration, so the workspace has to make it before normalize
# will declare anything — the same thing the tool asks of a real repository.
printf '{}\n' > "$WORK/composer.json"
# Refusing to normalise is a non-zero exit, which `set -e` would otherwise take as fatal.
set +e
$BIN normalize --path "$WORK" > "$WORK/nodecl.json"
nodecl_code=$?
set -e
expect "refusing to normalise exits non-zero" "1" "$nodecl_code"
# `?? ` reads an explicit null as absent, which is exactly the value under test.
expect "normalize refuses without a declared width" "null" \
  "$(php -r '$d = json_decode(file_get_contents($argv[1]), true); echo array_key_exists("declared", $d) && $d["declared"] === null ? "null" : "set";' "$WORK/nodecl.json")"

set +e
$BIN normalize --path "$WORK" --width 80 > /dev/null 2>&1
code=$?
set -e
expect "--width is refused, the project declares it" "2" "$code"

printf 'root = true\n\n[*]\nmax_line_length = 80\n' > "$WORK/.editorconfig"
$BIN normalize --path "$WORK" > "$WORK/norm.json"
expect "normalize declares the repository" "1" \
  "$(test -f "$WORK/.php-ast-edit.json" && echo 1 || echo 0)"
expect "the width comes from .editorconfig" "80" \
  "$(php -r 'echo json_decode(file_get_contents($argv[1]), true)["printWidth"];' "$WORK/norm.json")"
expect "format is idempotent afterwards" "0" \
  "$($BIN format --path "$WORK" | php -r 'echo count(json_decode(stream_get_contents(STDIN), true)["changed"]);')"
expect "an edit on a declared repository prints canonically" "canonical" \
  "$(printf '{"files":[{"path":"%s","edits":[{"target":{"ref":"stmts[0].name"},"operation":"set_name","value":"Baz"}]}]}' "$WORK/a.php" \
    | $BIN apply --dry-run | php -r 'echo json_decode(stream_get_contents(STDIN), true)["files"][0]["printer"];')"


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

if [[ "$fail" -ne 0 ]]; then
  echo "FAIL: CLI surface check failed." >&2
  exit 1
fi

# ---- The flag form: one call, no payload file ------------------------------------------
# Measured on controlled runs: every edit cost two calls, one writing a JSON payload to a
# temporary file and one applying it. A single edit against a named target should not need
# a file.
FLAGDIR="$WORK/flagform"
mkdir -p "$FLAGDIR"
printf '{"canonical":true,"printWidth":120}' > "$FLAGDIR/.php-ast-edit.json"
printf '[*.php]\nmax_line_length = 120\n' > "$FLAGDIR/.editorconfig"
printf '{"files":[{"path":"%s","mode":"create","php":"<?php class F { public function run(string $item): string { return $item; } }"}]}' \
  "$FLAGDIR/F.php" | $BIN apply > /dev/null
(cd "$FLAGDIR" && $BIN apply --file F.php --select 'method:F::run' --op rename_variable \
  --from item --to value > /dev/null)
expect "apply takes one edit from flags, without a payload file" "1" \
  "$(grep -c 'string \$value' "$FLAGDIR/F.php")"
expect "and says so when the target is missing" "1" \
  "$( (cd "$FLAGDIR" && $BIN apply --file F.php --op set_name --value x 2>&1 || true) | grep -c 'needs --select or --ref')"

# --kind is a constraint on a locator, not a locator: alone it would name every node of that
# kind in the file, so it must not satisfy the target check on its own.
expect "and --kind alone is not a target" "1" \
  "$( (cd "$FLAGDIR" && $BIN apply --file F.php --kind Stmt_ClassMethod --op set_name --value x 2>&1 || true) | grep -c 'needs --select or --ref')"
expect "while --kind still narrows a --select" "1" \
  "$( (cd "$FLAGDIR" && $BIN apply --file F.php --select 'method:F::run' --kind Stmt_ClassMethod \
       --op rename_variable --from value --to item > /dev/null 2>&1 && grep -c 'string \$item' "$FLAGDIR/F.php") )"


# An import has no node to name, so the flag form must not demand one — and asking twice must
# not write it twice, which is the whole reason the operation exists.
(cd "$FLAGDIR" && $BIN apply --file F.php --op add_use --value 'Vendor\Other\Thing' > /dev/null)
(cd "$FLAGDIR" && $BIN apply --file F.php --op add_use --value 'Vendor\Other\Thing' > /dev/null)
expect "a file-level import needs no target, and lands once" "1" \
  "$(grep -c 'use Vendor.Other.Thing;' "$FLAGDIR/F.php")"
expect "and naming a target for it is refused" "1" \
  "$( (cd "$FLAGDIR" && $BIN apply --file F.php --op add_use --value 'Vendor\X\Y' --select 'class:F' 2>&1 || true) | grep -c 'takes no target')"

# ---- The flag form carries the same contract as the JSON form ---------------------------
# The two forms are one command written two ways, so they must answer alike. They did not:
# the flag form returned 0 over failed project checks, and silently dropped --sha256 and
# --report, which the option parser accepts under any spelling. Each case below gets its own
# file: chained renames let an assertion pass because an earlier step left the wrong state.
CONTRACTDIR="$WORK/contract"
mkdir -p "$CONTRACTDIR"
# The one method every case edits, and what its body looks like before any rename —
# the pattern the "nothing was written" assertions grep for.
CONTRACT_TARGET='method:C::run'
CONTRACT_UNTOUCHED='string \$a'
# A project check that always fails. Failed checks keep the edit and exit 1 — help says so.
php -r '$c = ["canonical" => false, "verify" => [["scope" => "project", "command" => [PHP_BINARY, "-r", "exit(1);"]]]];
  file_put_contents($argv[1] . "/.php-ast-edit.json", json_encode($c));' "$CONTRACTDIR"

# The declared check fails by design, so creating a fixture exits 1 as well. The helper's
# job is the file, not the check: assert the file, and let the exit code belong to the cases.
contract_file() {
  local name="$1"
  local path="$CONTRACTDIR/$name.php"
  printf '{"files":[{"path":"%s","mode":"create","php":"<?php class C { public function run(string $a): string { return $a; } }"}]}' \
    "$path" | $BIN apply > /dev/null 2>&1 || true
  if [[ ! -f "$path" ]]; then
    echo "FAIL contract fixture $name was not created" >&2
    fail=1
  fi
}

contract_file exit_json
contract_file exit_flag
printf '{"files":[{"path":"%s","edits":[{"target":{"select":"%s"},"operation":"rename_variable","from":"a","to":"b"}]}]}' \
  "$CONTRACTDIR/exit_json.php" "$CONTRACT_TARGET" > "$CONTRACTDIR/doc.json"
set +e
$BIN apply --input "$CONTRACTDIR/doc.json" > "$CONTRACTDIR/json.out" 2>&1
json_code=$?
$BIN apply --file "$CONTRACTDIR/exit_flag.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  > "$CONTRACTDIR/flag.out" 2>&1
flag_code=$?
set -e
expect "a failed project check exits 1 through the JSON form" "1" "$json_code"
expect "and exits 1 through the flag form too" "1" "$flag_code"
expect "both forms report the same checksPassed" "false false" \
  "$(php -r '$o = []; foreach (array_slice($argv, 1) as $f) { $o[] = json_decode(file_get_contents($f), true)["checksPassed"] ? "true" : "false"; } echo implode(" ", $o);' \
    "$CONTRACTDIR/json.out" "$CONTRACTDIR/flag.out")"
expect "and both kept the edit" "1 1" \
  "$(grep -c 'string \$b' "$CONTRACTDIR/exit_json.php" | tr '\n' ' ' | tr -d '\n"'; grep -c 'string \$b' "$CONTRACTDIR/exit_flag.php")"

# --sha256 is a guard. Accepting the flag and not checking it is worse than not having it:
# the caller believes it edited the file it read.
contract_file stale
set +e
$BIN apply --file "$CONTRACTDIR/stale.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  --sha256 0000000000000000000000000000000000000000000000000000000000000000 > "$CONTRACTDIR/stale.out" 2>&1
stale_code=$?
set -e
expect "a stale --sha256 refuses the flag form" "2" "$stale_code"
expect "and names the guard that refused it" "1" "$(grep -c 'STALE_SOURCE' "$CONTRACTDIR/stale.out")"
expect "and the file is untouched" "1" "$(grep -c "$CONTRACT_UNTOUCHED" "$CONTRACTDIR/stale.php")"

contract_file fresh
FRESH_SHA="$(php -r 'echo hash_file("sha256", $argv[1]);' "$CONTRACTDIR/fresh.php")"
set +e
$BIN apply --file "$CONTRACTDIR/fresh.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  --sha256 "$FRESH_SHA" > /dev/null 2>&1
fresh_code=$?
set -e
expect "a matching --sha256 lets the edit through" "1" "$fresh_code"
expect "and the edit landed" "1" "$(grep -c 'string \$b' "$CONTRACTDIR/fresh.php")"

# --report chooses the response shape: compact moves verify results to one top-level field.
contract_file compact
$BIN apply --file "$CONTRACTDIR/compact.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  --report compact > "$CONTRACTDIR/compact.out" 2>&1 || true
expect "--report compact reaches the document" "1" \
  "$(php -r 'echo (int) array_key_exists("verify", json_decode(file_get_contents($argv[1]), true));' "$CONTRACTDIR/compact.out")"
contract_file fullreport
$BIN apply --file "$CONTRACTDIR/fullreport.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  > "$CONTRACTDIR/full.out" 2>&1 || true
expect "and the default stays full" "0" \
  "$(php -r 'echo (int) array_key_exists("verify", json_decode(file_get_contents($argv[1]), true));' "$CONTRACTDIR/full.out")"
contract_file loudreport
set +e
$BIN apply --file "$CONTRACTDIR/loudreport.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  --report loud > "$CONTRACTDIR/loud.out" 2>&1
report_code=$?
set -e
expect "an unknown --report value is refused" "2" "$report_code"
expect "and says which two values it takes" "1" "$(grep -c 'compact' "$CONTRACTDIR/loud.out")"
expect "and wrote nothing" "1" "$(grep -c "$CONTRACT_UNTOUCHED" "$CONTRACTDIR/loudreport.php")"

# The parser takes any --spelling. A flag the chosen form cannot carry has to say so, or it
# reads as applied: --mode create through flags did nothing and reported success.
contract_file unsupported
contract_file mixed
# Its own document against its own file: pointed at an already-renamed fixture this would
# exit 2 over the missing binding and look like the refusal it is supposed to be testing.
printf '{"files":[{"path":"%s","edits":[{"target":{"select":"%s"},"operation":"rename_variable","from":"a","to":"b"}]}]}' \
  "$CONTRACTDIR/mixed.php" "$CONTRACT_TARGET" > "$CONTRACTDIR/mixed.json"
set +e
$BIN apply --file "$CONTRACTDIR/unsupported.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  --mode create > "$CONTRACTDIR/unsupported.out" 2>&1
unsupported_code=$?
$BIN apply --input "$CONTRACTDIR/mixed.json" --select "$CONTRACT_TARGET" > "$CONTRACTDIR/mixed.out" 2>&1
mixed_code=$?
set -e
expect "a flag the flag form cannot carry is refused" "2" "$unsupported_code"
expect "and the message names it" "1" "$(grep -c -- '--mode' "$CONTRACTDIR/unsupported.out")"
# Three kinds of wrong flag need three answers. One message for all of them sends the
# author of a typo to write it into a document, where it does not belong either.
expect "a real setting with no flag is sent to the document" "1" \
  "$(grep -c 'per-file setting with no flag' "$CONTRACTDIR/unsupported.out")"
contract_file typo
set +e
$BIN apply --file "$CONTRACTDIR/typo.php" --select "$CONTRACT_TARGET" --op rename_variable --from a --to b \
  --moed create > "$CONTRACTDIR/typo.out" 2>&1
typo_code=$?
set -e
expect "a typo is refused as a typo" "2" "$typo_code"
expect "and is not called a per-file setting" "0" \
  "$(grep -c 'per-file setting' "$CONTRACTDIR/typo.out")"
expect "and says there is no such flag" "1" "$(grep -c 'is not a flag apply takes' "$CONTRACTDIR/typo.out")"
expect "two of them agree in number" "1" \
  "$( (cd "$CONTRACTDIR" && $BIN apply --file typo.php --select "$CONTRACT_TARGET" --op rename_variable \
       --from a --to b --mode create --printer canonical 2>&1 || true) | grep -c 'are per-file settings')"
expect "and it wrote nothing" "1" "$(grep -c "$CONTRACT_UNTOUCHED" "$CONTRACTDIR/unsupported.php")"
expect "a flag the JSON form cannot carry is refused" "2" "$mixed_code"
expect "and that message names it too" "1" "$(grep -c -- '--select' "$CONTRACTDIR/mixed.out")"
expect "and it left that file alone too" "1" "$(grep -c "$CONTRACT_UNTOUCHED" "$CONTRACTDIR/mixed.php")"

# ---- rename project-path forms ----------------------------------------------------------
# A bare project path is an alias for --path on rename only. Keep each fixture pristine so
# the parser contract, including refusal-before-write, is tested independently.
RENAMEDIR="$WORK/rename-paths"
mkdir -p "$RENAMEDIR"
rename_fixture() {
  local dir="$1"
  mkdir -p "$dir"
  printf '{"canonical":false}' > "$dir/.php-ast-edit.json"
  printf '{"files":[{"path":"%s/F.php","mode":"create","php":"<?php class F { private function run(): string { return \\\"run\\\"; } }"}]}' \
    "$dir" | $BIN apply > /dev/null
  (cd "$dir" && git init -q && git add F.php)
}
RENAME_METHOD='private function execute'

rename_fixture "$RENAMEDIR/after-flags"
$BIN rename --method F::run --to execute "$RENAMEDIR/after-flags" > /dev/null
expect "rename accepts an absolute positional path after its options" "1" \
  "$(grep -c "$RENAME_METHOD" "$RENAMEDIR/after-flags/F.php")"

rename_fixture "$RENAMEDIR/dot"
(cd "$RENAMEDIR/dot" && "$ROOT/bin/php-ast-edit" rename --method F::run --to execute . > /dev/null)
expect "rename accepts the recorded dot path form" "1" \
  "$(grep -c "$RENAME_METHOD" "$RENAMEDIR/dot/F.php")"

rename_fixture "$RENAMEDIR/before-flags"
$BIN rename "$RENAMEDIR/before-flags" --method F::run --to execute > /dev/null
expect "rename accepts a positional path before its options" "1" \
  "$(grep -c "$RENAME_METHOD" "$RENAMEDIR/before-flags/F.php")"

rename_fixture "$RENAMEDIR/flag"
$BIN rename --method F::run --to execute --path "$RENAMEDIR/flag" > /dev/null
expect "rename keeps the explicit --path form" "1" \
  "$(grep -c "$RENAME_METHOD" "$RENAMEDIR/flag/F.php")"

rename_fixture "$RENAMEDIR/dir with spaces"
$BIN rename "$RENAMEDIR/dir with spaces" --method F::run --to execute > /dev/null
expect "rename preserves spaces in a positional path" "1" \
  "$(grep -c "$RENAME_METHOD" "$RENAMEDIR/dir with spaces/F.php")"

rename_fixture "$RENAMEDIR/conflict-positional-first"
conflict_before="$(sha256sum "$RENAMEDIR/conflict-positional-first/F.php")"
set +e
$BIN rename "$RENAMEDIR/conflict-positional-first" --method F::run --to execute \
  --path "$RENAMEDIR/conflict-positional-first" > /dev/null 2> "$RENAMEDIR/conflict-a.err"
conflict_a_code=$?
set -e
expect "rename rejects positional plus --path in that order" "2" "$conflict_a_code"
expect "and writes nothing for the first conflict" "$conflict_before" \
  "$(sha256sum "$RENAMEDIR/conflict-positional-first/F.php")"
expect "the first conflict explains the ambiguous path" "1" \
  "$(grep -c 'not both' "$RENAMEDIR/conflict-a.err")"

rename_fixture "$RENAMEDIR/conflict-option-first"
conflict_before="$(sha256sum "$RENAMEDIR/conflict-option-first/F.php")"
set +e
$BIN rename --method F::run --to execute --path "$RENAMEDIR/conflict-option-first" \
  "$RENAMEDIR/conflict-option-first" > /dev/null 2> "$RENAMEDIR/conflict-b.err"
conflict_b_code=$?
set -e
expect "rename rejects positional plus --path in reverse order" "2" "$conflict_b_code"
expect "and writes nothing for the reverse conflict" "$conflict_before" \
  "$(sha256sum "$RENAMEDIR/conflict-option-first/F.php")"

rename_fixture "$RENAMEDIR/multiple"
rename_fixture "$RENAMEDIR/other"
multiple_before="$(sha256sum "$RENAMEDIR/multiple/F.php")"
other_before="$(sha256sum "$RENAMEDIR/other/F.php")"
set +e
$BIN rename "$RENAMEDIR/multiple" "$RENAMEDIR/other" --method F::run --to execute \
  > /dev/null 2> "$RENAMEDIR/multiple.err"
multiple_code=$?
set -e
expect "rename rejects multiple positional paths" "2" "$multiple_code"
expect "and writes nothing for multiple paths" "$multiple_before" \
  "$(sha256sum "$RENAMEDIR/multiple/F.php")"
expect "and does not select the second path" "$other_before" \
  "$(sha256sum "$RENAMEDIR/other/F.php")"

rename_fixture "$RENAMEDIR/empty"
empty_before="$(sha256sum "$RENAMEDIR/empty/F.php")"
set +e
(cd "$RENAMEDIR/empty" && "$ROOT/bin/php-ast-edit" rename "" --method F::run --to execute \
  > /dev/null 2> "$RENAMEDIR/empty.err")
empty_code=$?
set -e
expect "rename rejects an empty positional path" "2" "$empty_code"
expect "and writes nothing for an empty path" "$empty_before" \
  "$(sha256sum "$RENAMEDIR/empty/F.php")"

rename_fixture "$RENAMEDIR/0"
(cd "$RENAMEDIR" && "$ROOT/bin/php-ast-edit" rename 0 --method F::run --to execute > /dev/null)
expect "rename preserves a relative positional path named zero" "1" \
  "$(grep -c "$RENAME_METHOD" "$RENAMEDIR/0/F.php")"

rename_fixture "$RENAMEDIR/dot-root"
dot_before="$(sha256sum "$RENAMEDIR/dot-root/F.php")"
mkdir -p "$RENAMEDIR/dot-root/src"
set +e
(cd "$RENAMEDIR/dot-root/src" && "$ROOT/bin/php-ast-edit" rename --method F::run --to execute . \
  > /dev/null 2> "$RENAMEDIR/dot-root/dot.err")
dot_code=$?
set -e
expect "rename rejects a dot path that is only a project subdirectory" "2" "$dot_code"
expect "and writes nothing for a non-root dot path" "$dot_before" \
  "$(sha256sum "$RENAMEDIR/dot-root/F.php")"

rename_fixture "$RENAMEDIR/equal-conflict"
equal_before="$(sha256sum "$RENAMEDIR/equal-conflict/F.php")"
set +e
$BIN rename "$RENAMEDIR/equal-conflict" --method F::run --to execute \
  --path="$RENAMEDIR/equal-conflict" > /dev/null 2> "$RENAMEDIR/equal-conflict.err"
equal_code=$?
set -e
expect "rename rejects positional plus --path=value" "2" "$equal_code"
expect "and writes nothing for --path=value conflict" "$equal_before" \
  "$(sha256sum "$RENAMEDIR/equal-conflict/F.php")"

rename_fixture "$RENAMEDIR/dry-run"
$BIN rename "$RENAMEDIR/dry-run" --method F::run --to execute --dry-run > /dev/null
expect "rename positional dry-run leaves the declaration unchanged" "1" \
  "$(grep -c 'private function run' "$RENAMEDIR/dry-run/F.php")"

set +e
$BIN rename "$RENAMEDIR/missing path" --method F::run --to execute \
  > /dev/null 2> "$RENAMEDIR/missing.err"
missing_code=$?
set -e
expect "rename reports an invalid positional path" "2" "$missing_code"
expect "the invalid path is not mistaken for an option" "0" \
  "$(grep -c 'Unexpected argument' "$RENAMEDIR/missing.err")"

set +e
$BIN validate "$RENAMEDIR/after-flags/F.php" > /dev/null 2> "$RENAMEDIR/other-command.err"
other_command_code=$?
set -e
expect "other commands still reject positional arguments" "2" "$other_command_code"
expect "other-command rejection remains parser-level" "1" \
  "$(grep -c 'Unexpected argument' "$RENAMEDIR/other-command.err")"

if [[ "$fail" -ne 0 ]]; then
  echo "FAIL: CLI surface check failed." >&2
  exit 1
fi

echo "OK: CLI surface behaves as documented."
