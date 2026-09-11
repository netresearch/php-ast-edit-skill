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
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
: "${BENCH:?set BENCH}" "${REPO:?set REPO}" "${TOOL:?set TOOL}" "${PHP_AST_EDIT_PHPACTOR:?set PHP_AST_EDIT_PHPACTOR}"
export BENCH REPO TOOL PHP_AST_EDIT_PHPACTOR

# This driver starts a new campaign once. It never resumes: the old run.sh removes
# its worktree and truncates its result, so retrying this loop would erase evidence.
case "${1:-}" in
  setup)
    [[ ! -e "$BENCH" && ! -L "$BENCH" ]] || {
      echo "setup requires a new BENCH path; existing evidence/configuration is preserved" >&2
      exit 2
    }
    ;;
  run)
    [[ -d "$BENCH" && ! -L "$BENCH" ]] || { echo "run requires the prepared BENCH directory" >&2; exit 2; }
    for prior in "$BENCH/out" "$BENCH/work"; do
      [[ ! -e "$prior" && ! -L "$prior" ]] || {
        echo "refusing to rerun or resume $BENCH; preserve the first attempt and use a new campaign" >&2
        exit 2
      }
    done
    ;;
  *) echo "usage: drive.sh setup|run" >&2; exit 2 ;;
esac
[[ "${N:-30}" == 30 ]] || { echo "the frozen protocol requires N=30" >&2; exit 2; }

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

if [[ "$1" == setup ]]; then
    mkdir -m 700 "$BENCH"
    "$TOOL/benchmarks/skill-invocation/prepare.sh" free >/dev/null
    cfg=$("$TOOL/benchmarks/skill-invocation/prepare.sh" gate "$TOOL/skills/php-structured-edit")
    python3 - "$cfg/settings.json" "$TOOL/hooks/php-ast-only.py" <<'PY'
import json
import shlex
import sys
from pathlib import Path

settings = {
    "includeCoAuthoredBy": False,
    "hooks": {
        "PreToolUse": [{
            "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
            "hooks": [{"type": "command", "command": shlex.join(["python3", sys.argv[2]])}],
        }],
    },
}
Path(sys.argv[1]).write_text(json.dumps(settings, indent=2) + "\n")
PY
    echo "$BENCH/cfg-free $cfg"
    exit 0
fi

RUN="$TOOL/benchmarks/skill-invocation/run.sh"
N=30
# Exclusive creation also arbitrates concurrent invocations. No marker is removed
# on failure; the first attempt, including an interrupted one, remains the evidence.
mkdir "$BENCH/out"
set -C
sha256sum "$HERE/PROTOCOL.md" "$HERE/drive.sh" "$HERE/analyze.py" \
  "$HERE/task-C.txt" "$HERE/task-D.txt" "$HERE/oracle-C.sh" "$HERE/oracle-D.sh" \
  > "$BENCH/out/harness.sha256"

for i in $(seq 1 "$N"); do
  n=$(printf '%02d' "$i")
  # Task order flips every round, and so does which arm goes first — per task, in
  # opposite phase — so neither an arm nor a task sits at a fixed point in the hour.
  if (( i % 2 )); then tasks=(C D); else tasks=(D C); fi

  for t in "${tasks[@]}"; do
    offset=0
    [[ "$t" == D ]] && offset=1
    phase=$(( i + offset ))
    if (( phase % 2 )); then arms=(free gate); else arms=(gate free); fi

    for arm in "${arms[@]}"; do
      id="$t$n"
      claude --version > "$BENCH/out/$id-$arm.version" 2>&1
      if "$RUN" "$id" "$arm" "$(cat "$HERE/task-$t.txt")"; then
        :
      else
        status=$?
        echo "driver failed before completing $id-$arm (exit $status); first attempt preserved" >&2
        exit "$status"
      fi
      work="$BENCH/work/$id-$arm"
      [[ -f "$BENCH/out/$id-$arm.status" && -d "$work" ]] || {
        echo "missing outcome or worktree for $id-$arm; campaign interrupted" >&2
        exit 2
      }
      # The oracle decides on the tree the run left; the diff is kept as the evidence,
      # and the tree goes, so a round of 120 runs does not hold 120 checkouts.
      oracle_status=0
      ( cd "$work" && sh "$HERE/oracle-$t.sh" ) \
        > "$BENCH/out/$id-$arm.oracle-output" 2>&1 || oracle_status=$?
      echo "$oracle_status" > "$BENCH/out/$id-$arm.oracle"
      # Compare final tracked bytes with the pinned subject, not merely the index:
      # a candidate can stage or commit an edit before finishing.
      git -C "$work" diff --binary "$BASE" > "$BENCH/out/$id-$arm.diff"
      git -C "$work" ls-files --others --exclude-standard -z > "$BENCH/out/$id-$arm.untracked"
      git -C "$REPO" worktree remove --force "$work" 2>/dev/null || true
    done
  done
done
touch "$BENCH/out/done"
