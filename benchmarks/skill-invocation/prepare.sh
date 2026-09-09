#!/usr/bin/env bash
# Build the isolated configuration directories the arms run in.
#
# Each holds credentials, a minimal settings.json and — for every arm but `free` — one
# skill directory. Nothing else: no CLAUDE.md, no other skills, no MCP servers. A
# measurement taken against a personal configuration measures that configuration.
#
#   prepare.sh free                       an arm with no skill at all
#   prepare.sh ast   /path/to/skill/dir   the skill as shipped
#   prepare.sh trial /path/to/skill/dir   a variant to compare against it
set -euo pipefail
BENCH="${BENCH:?set BENCH to the working root}"
arm="${1:?arm}"

# The arm ends up inside a path this script deletes with `rm -rf`, and BENCH holds
# credentials. An arm is a short name, never a path.
[[ "$arm" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]] || {
  echo "refusing to use '$arm' in a path" >&2
  exit 2
}
skill="${2:-}"
cfg="$BENCH/cfg-$arm"
rm -rf "$cfg"; mkdir -p "$cfg"
cp "${CLAUDE_CREDENTIALS:-$HOME/.claude/.credentials.json}" "$cfg/.credentials.json"
chmod 600 "$cfg/.credentials.json"
printf '{"includeCoAuthoredBy":false}\n' > "$cfg/settings.json"

if [[ -n "$skill" ]]; then
  mkdir -p "$cfg/skills"
  cp -r "$skill" "$cfg/skills/$(basename "$skill")"
fi
echo "$cfg"
