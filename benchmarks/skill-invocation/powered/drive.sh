#!/usr/bin/env bash
# shellcheck disable=SC2016 # backticks in the sed patterns are Markdown, matched literally
# The powered round: two tasks, two arms, N runs of each, interleaved. See PROTOCOL.md.
#
#   drive.sh setup   build cfg-free and cfg-gate under $BENCH from the frozen tool
#   drive.sh run     the runs, sequentially, in the protocol's order
#
# BENCH  a fresh working root for this round only; nothing from earlier rounds in it
# REPO   the subject repository
# TOOL   a checkout of this repository at the protocol's tool commit, with its vendor
# PHP_AST_EDIT_PHPACTOR  the pinned phpactor.phar, exported to both arms alike
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
: "${BENCH:?set BENCH}" "${REPO:?set REPO}" "${TOOL:?set TOOL}" "${PHP_AST_EDIT_PHPACTOR:?set PHP_AST_EDIT_PHPACTOR}"
export BENCH REPO TOOL PHP_AST_EDIT_PHPACTOR

# The commits come from the protocol, not from the caller: a round run against anything
# other than what the protocol froze is a different measurement.
BASE=$(sed -n 's/^- Subject commit: `\([0-9a-f]\{40\}\)`.*/\1/p' "$HERE/PROTOCOL.md")
tool=$(sed -n 's/^- Tool commit: `\([0-9a-f]\{40\}\)`.*/\1/p' "$HERE/PROTOCOL.md")
export BASE
[[ -n "$BASE" && -n "$tool" ]] || { echo "PROTOCOL.md does not name both commits" >&2; exit 2; }
[[ "$(git -C "$TOOL" rev-parse HEAD)" == "$tool" ]] || { echo "TOOL is not at the tool commit $tool" >&2; exit 2; }
[[ -z "$(git -C "$TOOL" status --porcelain --untracked-files=no)" ]] || { echo "TOOL has local changes" >&2; exit 2; }
[[ "$(sha256sum "$PHP_AST_EDIT_PHPACTOR" | cut -d' ' -f1)" == 8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d ]] \
  || { echo "PHP_AST_EDIT_PHPACTOR is not the pinned release" >&2; exit 2; }

case "${1:-}" in
  setup)
    "$TOOL/benchmarks/skill-invocation/prepare.sh" free >/dev/null
    cfg=$("$TOOL/benchmarks/skill-invocation/prepare.sh" gate "$TOOL/skills/php-structured-edit")
    cat > "$cfg/settings.json" <<EOF
{
  "includeCoAuthoredBy": false,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [{"type": "command", "command": "python3 $TOOL/hooks/php-ast-only.py"}]
      }
    ]
  }
}
EOF
    echo "$BENCH/cfg-free $cfg"
    exit 0
    ;;
  run) ;;
  *) echo "usage: drive.sh setup|run" >&2; exit 2 ;;
esac

RUN="$TOOL/benchmarks/skill-invocation/run.sh"
N="${N:-30}"
mkdir -p "$BENCH/out"

for i in $(seq 1 "$N"); do
  n=$(printf '%02d' "$i")
  # Task order flips every round, and so does which arm goes first — per task, in
  # opposite phase — so neither an arm nor a task sits at a fixed point in the hour.
  if (( i % 2 )); then tasks=(C D); else tasks=(D C); fi

  for t in "${tasks[@]}"; do
    phase=$(( i + (t == D ? 1 : 0) ))
    if (( phase % 2 )); then arms=(free gate); else arms=(gate free); fi

    for arm in "${arms[@]}"; do
      id="$t$n"
      claude --version > "$BENCH/out/$id-$arm.version" 2>&1
      "$RUN" "$id" "$arm" "$(cat "$HERE/task-$t.txt")" || echo "run $id-$arm exited $?"
      work="$BENCH/work/$id-$arm"
      # The oracle decides on the tree the run left; the diff is kept as the evidence,
      # and the tree goes, so a round of 120 runs does not hold 120 checkouts.
      ( cd "$work" && sh "$HERE/oracle-$t.sh" ); echo "$?" > "$BENCH/out/$id-$arm.oracle"
      git -C "$work" diff > "$BENCH/out/$id-$arm.diff"
      git -C "$REPO" worktree remove --force "$work" 2>/dev/null || true
    done
  done
done
touch "$BENCH/out/done"
