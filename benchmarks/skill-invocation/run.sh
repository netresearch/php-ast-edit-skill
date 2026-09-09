#!/usr/bin/env bash
# One arm of one measurement: a fresh checkout, an isolated Claude Code configuration,
# one `claude -p`.
#
# What this measures is not whether the tool is faster. It is whether the model reaches
# for it at all. A skill that is listed and never invoked costs its listing and returns
# nothing, and no amount of work on the CLI changes that — so the arms differ in exactly
# one thing, the skill directory the configuration carries. Prompt, base commit, model,
# repository and PATH are identical.
#
# The configuration directory matters as much as the skill: run this against your own
# ~/.claude and you measure your CLAUDE.md, your other skills and whatever standing
# instructions you keep there. Each arm therefore gets a directory holding nothing but
# credentials, a minimal settings.json, and the skill under test.
#
#   BENCH=/tmp/bench                 working root, holds cfg-*/ out/ work/
#   REPO=/path/to/a/php/repository   the subject; a real one, not a fixture
#   BASE=<commit>                    pinned, so every arm edits the same bytes
#   TOOL=/path/to/php-ast-edit-skill this repository, for bin/php-ast-edit
#
# Usage: run.sh <task-id> <arm> <prompt> [model]
#        arm: free (no skill) | ast (skill as shipped) | any cfg-<arm> you prepared
set -euo pipefail
BENCH="${BENCH:?set BENCH to the working root}"
REPO="${REPO:?set REPO to the repository under test}"
BASE="${BASE:?set BASE to the pinned commit}"
TOOL="${TOOL:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
task="$1"; arm="$2"; prompt="$3"; model="${4:-claude-haiku-4-5-20251001}"
work="$BENCH/work/$task-$arm"
mkdir -p "$BENCH/out" "$BENCH/work"
rm -rf "$work"
git -C "$REPO" worktree remove --force "$work" 2>/dev/null || true
git -C "$REPO" worktree add --detach "$work" "$BASE" >/dev/null
# The subject's vendor directory, so the project's own checks can run inside the arm.
[ -d "$REPO/.Build" ] && ln -sfn "$REPO/.Build" "$work/.Build"
[ -d "$REPO/vendor" ] && ln -sfn "$REPO/vendor" "$work/vendor"
cfg="$BENCH/cfg-$arm"
[ -d "$cfg" ] || { echo "no configuration $cfg — see prepare.sh" >&2; exit 2; }
[ "$arm" = free ] || export PATH="$TOOL/bin:$PATH"
# `claude -p` waits on stdin for three seconds before giving up; closing it keeps the
# measured wall time from carrying that wait.
( cd "$work" && CLAUDE_CONFIG_DIR="$cfg" timeout 900 claude -p "$prompt" \
    --output-format json --dangerously-skip-permissions \
    --model "$model" < /dev/null ) > "$BENCH/out/$task-$arm.json" 2>"$BENCH/out/$task-$arm.err" || true
