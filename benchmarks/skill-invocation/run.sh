#!/usr/bin/env bash
# One arm of one measurement: a fresh checkout, an isolated Claude Code configuration,
# one `claude -p`.
#
# What this measures is not whether the tool is faster. It is whether the model reaches
# for it at all. A skill that is listed and never invoked costs its listing and returns
# nothing, and no amount of work on the CLI changes that — so the arms differ in exactly
# one thing, the skill directory the configuration carries. Prompt, base commit, model,
# repository and PATH are identical, the engine on PATH in every arm including `free`:
# an arm that cannot reach the binary would be measuring two changes at once.
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
#        arm: free (no skill) | any cfg-<arm> you prepared
set -euo pipefail
BENCH="${BENCH:?set BENCH to the working root}"
REPO="${REPO:?set REPO to the repository under test}"
BASE="${BASE:?set BASE to the pinned commit}"
TOOL="${TOOL:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Both arguments end up inside paths this script deletes with `rm -rf`, and BENCH holds
# credentials. Neither is ever a path, so neither is allowed to look like one.
for value in "${1:?task id}" "${2:?arm}"; do
  [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]] || {
    echo "refusing to use '$value' in a path" >&2
    exit 2
  }
done
# Say so if the subject is already poisoned, rather than measuring against it: a
# root package that does not resolve to the repository means an earlier run wrote
# through, and every check the arms run is answering about a tree that is not there.
for autoload in "$REPO/.Build/vendor/composer/installed.php" "$REPO/vendor/composer/installed.php"; do
  [[ -f "$autoload" ]] || continue
  # The declared path is printed, not the resolved one: the case that matters is a
  # root package pointing at a directory an earlier run deleted, where realpath gives
  # nothing back and a message built on it would name the problem as an empty string.
  declared=$(php -r '$d=require $argv[1]; echo $d["root"]["install_path"] ?? "";' "$autoload")
  root=$(php -r 'echo realpath($argv[1]) ?: "";' "$declared")
  [[ "$root" == "$(cd "$REPO" && pwd -P)" ]] || {
    echo "$REPO has an autoloader whose root package is '$declared'." >&2
    echo "An arm wrote through to the subject. Run 'composer install' there before measuring." >&2
    exit 2
  }
done

task="$1"; arm="$2"; prompt="${3:?prompt}"; model="${4:-claude-haiku-4-5-20251001}"
work="$BENCH/work/$task-$arm"
mkdir -p "$BENCH/out" "$BENCH/work"
rm -rf "$work"
git -C "$REPO" worktree remove --force "$work" 2>/dev/null || true
git -C "$REPO" worktree add --detach "$work" "$BASE" >/dev/null
# The subject's dependencies, so the project's own checks can run inside the arm.
#
# Not a symlink to the shared directory. An arm is a full Claude Code session with a
# real repository in front of it, and one of them ran `composer dump-autoload` — which,
# through a shared symlink, rewrote the SUBJECT's autoloader to point its root package
# at that arm's working directory. The next run deleted that directory, so TYPO3's
# autoload-include.php became unloadable, and the project's own PHPStan then reported
# 66 errors of the shape "return statement is missing" against `return match (...)`.
# Every `apply` in every later arm came back checksPassed:false for that reason, which
# is the measurement's own doing rather than anything the model did.
#
# So: hardlink the packages (half a second, no extra disk) and take a real copy of
# `vendor/composer`, which is the part composer rewrites. The arm may then install,
# dump, or wreck its dependencies without the subject or its siblings noticing. The
# analyser's cache under .Build/var stays per-arm for the same reason.
copy_deps() {
  local from="$1" to="$2"
  mkdir -p "$(dirname "$to")"
  cp -al "$from" "$to"
  if [[ -d "$to/composer" ]]; then
    rm -rf "$to/composer"
    cp -a "$from/composer" "$to/composer"
  fi
}
if [[ -d "$REPO/.Build/vendor" ]]; then
  copy_deps "$REPO/.Build/vendor" "$work/.Build/vendor"

  # An explicit conditional rather than `[[ -d … ]] && cp`. Under `set -e` the short
  # form is safe here — the failing command is the test, not the one after the final
  # `&&`, so it is exempt — but it reads like the trap it is not, and a subject with
  # no bin directory is a case worth naming rather than arguing about.
  if [[ -d "$REPO/.Build/bin" ]]; then
    cp -a "$REPO/.Build/bin" "$work/.Build/bin"
  fi
elif [[ -d "$REPO/vendor" ]]; then
  copy_deps "$REPO/vendor" "$work/vendor"
fi

cfg="$BENCH/cfg-$arm"
[[ -d "$cfg" ]] || { echo "no configuration $cfg — see prepare.sh" >&2; exit 2; }
export PATH="$TOOL/bin:$PATH"

# `claude -p` waits on stdin for three seconds before giving up; closing it keeps the
# measured wall time from carrying that wait.
status=0
( cd "$work" && CLAUDE_CONFIG_DIR="$cfg" timeout 900 claude -p "$prompt" \
    --output-format json --dangerously-skip-permissions \
    --model "$model" < /dev/null ) > "$BENCH/out/$task-$arm.json" 2>"$BENCH/out/$task-$arm.err" || status=$?

# The exit status is written, not swallowed. A timeout or an expired token produces an
# empty or error result that summarize.py then drops, and an arm whose failures are
# invisible reports a smaller denominator and a flattering invocation rate off it.
echo "$status" > "$BENCH/out/$task-$arm.status"
exit 0
