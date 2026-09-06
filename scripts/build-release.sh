# shellcheck shell=bash
# Build in isolation: a developer's vendor/ must never leak into release artifacts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-v$(jq -r '.version' "$ROOT/plugin.json")}"
OUTPUT="${2:-$ROOT/dist/releases}"
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  echo "Invalid release version: $VERSION" >&2
  exit 2
fi
PLUGIN="$(jq -er '.name | select(test("^[a-z0-9][a-z0-9-]*$"))' "$ROOT/plugin.json")"
for manifest in "$ROOT/plugin.json" "$ROOT/.claude-plugin/plugin.json"; do
  jq -e --arg version "${VERSION#v}" --arg name "$PLUGIN" '.version == $version and .name == $name' "$manifest" > /dev/null
done
if [[ -e "$OUTPUT" && -n "$(ls -A "$OUTPUT")" ]]; then
  echo "Output directory must be empty: $OUTPUT" >&2
  exit 2
fi
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/runtime/scripts" "$WORK/skill" "$WORK/plugin/skills/php-structured-edit"
cp -R "$ROOT/src" "$ROOT/bin" "$WORK/runtime/"
cp "$ROOT/composer.json" "$ROOT/LICENSE-MIT" "$ROOT/LICENSE-CC-BY-SA-4.0" "$WORK/runtime/"
cp "$ROOT/scripts/build-phar.php" "$WORK/runtime/scripts/"
# Resolve on the supported PHP floor even when building with a newer interpreter.
# Library policy leaves the root unlocked; record and test the resolved artifact below.
COMPOSER_ROOT_VERSION="${VERSION#v}" composer config --working-dir="$WORK/runtime" platform.php 8.2.0
# --no-plugins prevents the optional skill installer from changing the build host.
COMPOSER_ROOT_VERSION="${VERSION#v}" composer install --working-dir="$WORK/runtime" --no-dev --no-plugins --no-scripts --prefer-dist --no-interaction --no-progress --quiet
php -d phar.readonly=0 "$WORK/runtime/scripts/build-phar.php"
jq '{dev, packages: [.packages[] | {name, version, source, dist, license}]}' \
  "$WORK/runtime/vendor/composer/installed.json" > "$WORK/runtime-dependencies.json"
jq -e '.dev == false and ([.packages[].name] | index("friendsofphp/php-cs-fixer") == null)' "$WORK/runtime-dependencies.json" > /dev/null

# Only tracked regular files enter archives; no local credentials, symlinks or caches.
copy_tracked() {
  local prefix="$1" destination="$2" path relative
  while IFS= read -r -d '' path; do
    [[ -f "$ROOT/$path" && ! -L "$ROOT/$path" ]] || { echo "Not a regular source file: $path" >&2; exit 2; }
    relative="${path#"$prefix"/}"
    mkdir -p "$destination/$(dirname "$relative")"
    cp -p "$ROOT/$path" "$destination/$relative"
  done < <(git -C "$ROOT" ls-files -z -- "$prefix")
}
copy_tracked skills/php-structured-edit "$WORK/skill"
[[ -s "$WORK/skill/SKILL.md" && -f "$WORK/skill/scripts/php-ast-edit" ]]
cp "$WORK/runtime/dist/php-ast-edit.phar" "$WORK/skill/scripts/"
cp "$WORK/runtime-dependencies.json" "$WORK/skill/"
cp "$ROOT/LICENSE-MIT" "$ROOT/LICENSE-CC-BY-SA-4.0" "$WORK/skill/"
cp -R "$WORK/skill/." "$WORK/plugin/skills/php-structured-edit/"
copy_tracked .claude-plugin "$WORK/plugin/.claude-plugin"
copy_tracked hooks "$WORK/plugin/hooks"
cp "$ROOT/plugin.json" "$ROOT/LICENSE-MIT" "$ROOT/LICENSE-CC-BY-SA-4.0" "$WORK/plugin/"

mkdir -p "$OUTPUT"
OUTPUT="$(cd "$OUTPUT" && pwd)"
for kind in skill plugin; do
  (cd "$WORK/$kind" && zip -qr "$OUTPUT/$PLUGIN-$kind-$VERSION.zip" .)
  (cd "$WORK/$kind" && tar -czf "$OUTPUT/$PLUGIN-$kind-$VERSION.tar.gz" .)
done
cp "$WORK/runtime/dist/php-ast-edit.phar" "$WORK/runtime-dependencies.json" "$OUTPUT/"
(cd "$OUTPUT" && sha256sum ./*.zip ./*.tar.gz ./php-ast-edit.phar ./runtime-dependencies.json > SHA256SUMS.txt)
echo "Built executable skill/plugin archives, PHAR, dependency manifest and checksums in $OUTPUT"
