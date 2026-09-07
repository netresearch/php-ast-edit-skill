# shellcheck shell=bash
# Executable documentation: no network and no project-wide formatting changes.
set -euo pipefail
QUICKSTART_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUICKSTART_BIN="${PHP_AST_EDIT_BIN:-$QUICKSTART_ROOT/bin/php-ast-edit}"
QUICKSTART_WORK="$(mktemp -d)"
trap 'rm -rf "$QUICKSTART_WORK"' EXIT
command -v jq >/dev/null
cd "$QUICKSTART_WORK"
jq -n '{report:"compact",files:[{path:"Clock.php",mode:"create",php:"<?php namespace App; final class Clock {}"}]}' \
  | "$QUICKSTART_BIN" apply > create.json
jq -e '.files[0].mode == "create" and .files[0].changed == true' create.json >/dev/null
jq -n --arg sha "$(php -r 'echo hash_file("sha256", "Clock.php");')" \
  '{report:"compact",files:[{path:"Clock.php",sha256:$sha,edits:[
    {target:{select:"class:Clock"},operation:"add_member",php:"public function now(): \\DateTimeImmutable { return new \\DateTimeImmutable(); }"},
    {target:{select:"class:Clock"},operation:"add_member",php:"public const TIMEZONE = '\''UTC'\'';"}
  ]}]}' | "$QUICKSTART_BIN" apply > apply.json
jq -e '.files[0].changed == true and .files[0].editsApplied == 2' apply.json >/dev/null
jq -e '.verify == [] and .files[0].checkIds == [] and .checksPassed == null
  and .files[0].validation.checks == "not_run" and (.files[0] | has("verify") | not)' apply.json >/dev/null
php -l Clock.php >/dev/null
# shellcheck disable=SC2016 # PHP variables are intentional literals for the shell.
php -r 'require $argv[1]; $clock = new App\Clock(); if (!$clock->now() instanceof DateTimeImmutable || App\Clock::TIMEZONE !== "UTC") { exit(1); }' Clock.php
jq -r '.files[0].diff' apply.json
printf '%s\n' 'OK: namespaced Clock created, two changes applied, runtime behavior verified.'
