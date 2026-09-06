#!/usr/bin/env bash
# Exercise installed parsing and mutation, not just the dependency-free help command.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

smoke() {
  local label="$1" fixture="$WORK/$1.php"
  shift
  jq -n --arg path "$fixture" '{files:[{path:$path,mode:"create",php:"<?php echo 41;"}]}' \
    | "$@" apply > "$WORK/result.json"
  "$@" inspect --file "$fixture" --line 3 --column 6 > "$WORK/inspect.json"
  jq -e '.nodes[0].type == "Scalar_Int"' "$WORK/inspect.json" > /dev/null
  jq --arg path "$fixture" '{files:[{path:$path,sha256:.sha256,edits:[{
    target:{ref:.nodes[0].ref},operation:"replace_node",parseAs:"expr",php:"42"
  }]}]}' "$WORK/inspect.json" | "$@" apply > "$WORK/result.json"
  jq -e '.files[0].changed == true' "$WORK/result.json" > /dev/null
  php -l "$fixture" > /dev/null
  [[ "$(php "$fixture")" == 42 ]]
  echo "OK: $label installs, inspects and applies a guarded edit"
}

# Stage exactly the shipped source, with no accidentally inherited root vendor tree.
mkdir -p "$WORK/source"
cp -R "$ROOT/bin" "$ROOT/src" "$ROOT/skills" "$WORK/source/"
cp "$ROOT/composer.json" "$ROOT/LICENSE-MIT" "$ROOT/LICENSE-CC-BY-SA-4.0" "$WORK/source/"
mkdir -p "$WORK/consumer"
jq -n --arg source "$WORK/source" '{
  name:"php-ast-edit/distribution-test",
  repositories:[{type:"path",url:$source,options:{symlink:false,versions:{"netresearch/php-ast-edit-skill":"1.0.0"}}}],
  require:{"netresearch/php-ast-edit-skill":"1.0.0"},
  config:{"allow-plugins":false}
}' > "$WORK/consumer/composer.json"
composer install --working-dir="$WORK/consumer" --no-dev --no-plugins --no-scripts --no-interaction --no-progress --quiet
[[ ! -f "$WORK/consumer/vendor/netresearch/php-ast-edit-skill/vendor/autoload.php" ]]
smoke composer php "$WORK/consumer/vendor/bin/php-ast-edit"
smoke composer-wrapper bash "$WORK/consumer/vendor/netresearch/php-ast-edit-skill/skills/php-structured-edit/scripts/php-ast-edit"

# Composer supports relocating both directories; avoid hard-coding vendor ancestry.
mkdir -p "$WORK/custom"
jq '.config += {"vendor-dir":"dependencies","bin-dir":"tools"}' "$WORK/consumer/composer.json" > "$WORK/custom/composer.json"
composer install --working-dir="$WORK/custom" --no-dev --no-plugins --no-scripts --no-interaction --no-progress --quiet
smoke composer-custom php "$WORK/custom/tools/php-ast-edit"
smoke composer-custom-wrapper bash "$WORK/custom/dependencies/netresearch/php-ast-edit-skill/skills/php-structured-edit/scripts/php-ast-edit"

# A VCS repository is the supported route before this package is on Packagist.
# Commit the candidate source locally so this tests the candidate, not a public tag.
cp -R "$WORK/source" "$WORK/vcs-source"
git -C "$WORK/vcs-source" init --quiet --initial-branch=main
git -C "$WORK/vcs-source" add .
git -C "$WORK/vcs-source" -c commit.gpgsign=false -c core.hooksPath=/dev/null \
  -c user.name=DistributionTest -c user.email=distribution@example.invalid commit --quiet -m fixture
mkdir -p "$WORK/vcs-consumer"
jq -n --arg source "$WORK/vcs-source" '{
  name:"php-ast-edit/vcs-test",
  repositories:[{type:"vcs",url:$source}],
  require:{"netresearch/php-ast-edit-skill":"dev-main"},
  config:{"allow-plugins":false}
}' > "$WORK/vcs-consumer/composer.json"
composer install --working-dir="$WORK/vcs-consumer" --no-dev --no-plugins --no-scripts --no-interaction --no-progress --quiet
smoke composer-vcs php "$WORK/vcs-consumer/vendor/bin/php-ast-edit"

composer install --working-dir="$WORK/source" --no-dev --no-plugins --no-scripts --no-interaction --no-progress --quiet
smoke clone php "$WORK/source/bin/php-ast-edit"
smoke clone-wrapper bash "$WORK/source/skills/php-structured-edit/scripts/php-ast-edit"

# A standalone wrapper on PATH must fail promptly if its engine is absent.
mkdir -p "$WORK/no-engine/deep/scripts"
cp "$ROOT/skills/php-structured-edit/scripts/php-ast-edit" "$WORK/no-engine/deep/scripts/"
chmod +x "$WORK/no-engine/deep/scripts/php-ast-edit"
set +e
(cd "$WORK/no-engine" && PATH="$WORK/no-engine/deep/scripts:$PATH" \
  timeout 5 bash "$WORK/no-engine/deep/scripts/php-ast-edit" contexts) > "$WORK/no-engine.out" 2>&1
status=$?
set -e
[[ "$status" == 127 ]]
echo "OK: standalone wrapper does not recurse into itself on PATH"

if [[ "${1:-}" == --install-only ]]; then
  exit 0
fi

if [[ "${1:-}" == --artifacts && -n "${2:-}" ]]; then
  RELEASES="$(cd "$2" && pwd)"
else
  VERSION="v$(jq -r '.version' "$ROOT/plugin.json")"
  RELEASES="$WORK/releases"
  bash "$ROOT/scripts/build-release.sh" "$VERSION" "$RELEASES"
fi
(cd "$RELEASES" && sha256sum --check SHA256SUMS.txt)
jq -e '.dev == false and ([.packages[].name] | index("friendsofphp/php-cs-fixer") == null)' "$RELEASES/runtime-dependencies.json" > /dev/null
smoke phar php "$RELEASES/php-ast-edit.phar"
php "$ROOT/tests/distribution.php" "$RELEASES/php-ast-edit.phar"

for archive in "$RELEASES/"*.zip "$RELEASES/"*.tar.gz; do
  name="$(basename "$archive")"
  destination="$WORK/extracted-$name"
  mkdir -p "$destination"
  if [[ "$archive" == *.zip ]]; then
    unzip -q "$archive" -d "$destination"
  else
    tar -xzf "$archive" -C "$destination"
  fi
  if [[ "$name" == *-plugin-* ]]; then
    wrapper="$destination/skills/php-structured-edit/scripts/php-ast-edit"
  else
    wrapper="$destination/scripts/php-ast-edit"
  fi
  # An unrelated working directory has neither a checkout nor project vendor/bin.
  (cd "$WORK" && smoke "$name" bash "$wrapper")
done
