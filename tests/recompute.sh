#!/usr/bin/env bash
# Published numbers are claims. This asserts the transcription against the report it
# came from, then checks the report's own category sums and the derived comparisons.
# A recomputation that never reads the source only launders the figures it restates.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/benchmarks/symbol-intent/results/2026-09-07-real-php"
DIR="$RUN/recompute"

if ! command -v jq > /dev/null 2>&1; then
  echo "SKIP: jq is not installed; the recomputation needs it."
  exit 0
fi

fail=0
# 12196 -> 12,196, independently of the locale.
grouped() { printf '%s' "$1" | sed -E ':a;s/([0-9])([0-9]{3})($|,)/\1,\2\3/;ta'; }
expect() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "ok   $label"
  else
    echo "FAIL $label: expected [$expected], got [$actual]" >&2
    fail=1
  fi
}

# 1. The transcription must still be what the report says. A number edited in the report
#    and not here would leave this file recomputing a figure the project no longer claims.
rows="$(jq -r '
  {"text_manual":"Text/manual","ast_manual":"AST/manual","ast_integrated":"AST/integrated"} as $label
  | .token_totals
  | to_entries[]
  | [$label[.key], (.value | .fresh, .cache_create, .cache_read, .output, .total)]
  | @tsv' "$DIR/reported_metrics.json")"

if [[ -z "$rows" ]]; then
  echo "FAIL transcription: no arms read from reported_metrics.json" >&2
  exit 1
fi
checked=0
while IFS=$'\t' read -r arm fresh cc cr out total; do
  row="$(grep -F "| $arm |" "$RUN/REPORT.md" | head -1)"
  if [[ -z "$row" ]]; then
    echo "FAIL transcription: REPORT.md has no row for $arm" >&2
    fail=1
    continue
  fi
  arm_ok=1
  for value in "$fresh" "$cc" "$cr" "$out" "$total"; do
    # The report groups thousands. printf "%'d" only does that in a locale that
    # groups, and the C locale CI runs under does not — so the separator is placed
    # here rather than asked for.
    printed="$(grouped "$value")"
    if [[ "$row" != *"$printed"* ]]; then
      echo "FAIL transcription: $arm does not carry $printed in REPORT.md" >&2
      fail=1
      arm_ok=0
    fi
  done
  checked=$((checked + 1))
  if [[ "$arm_ok" -eq 1 ]]; then
    echo "ok   transcription matches REPORT.md for $arm"
  fi
done <<< "$rows"

# Three arms, or the loop skipped one and every assertion below is about a subset.
expect "all three arms were transcription-checked" "3" "$checked"

OUT="$(cd "$DIR" && jq -f recompute.jq reported_metrics.json)"

# 2. Every arm's four categories must add up to the total the report prints beside them.
expect "each arm's categories sum to its stated total" "true" \
  "$(printf '%s' "$OUT" | jq -c '[.sum_validation[].valid] | all')"

# 3. The two headline reductions answer different questions and must stay distinguishable.
expect "median comparison is -90.2%" "-90.2" \
  "$(printf '%s' "$OUT" | jq -r '.integrated_vs_text_percent_change_of_medians.tokens | .*10 | round / 10')"
expect "total comparison is -83.2%" "-83.2" \
  "$(printf '%s' "$OUT" | jq -r '.integrated_vs_text_percent_change_of_token_totals | .*10 | round / 10')"

# 4. Where the counted reduction sits. Cache-read dominating is the finding; output
#    falling by more than half is real and is nonetheless a small part of the total.
expect "cache-read is 92.6% of the reduction" "92.6" \
  "$(printf '%s' "$OUT" | jq -r '.token_reduction_decomposition[] | select(.category=="cache_read") | .fraction_of_total_reduction_percent | .*10 | round / 10')"
expect "output is 1.5% of it" "1.5" \
  "$(printf '%s' "$OUT" | jq -r '.token_reduction_decomposition[] | select(.category=="output") | .fraction_of_total_reduction_percent | .*10 | round / 10')"
expect "while the output total itself falls 54.8%" "-54.8" \
  "$(printf '%s' "$OUT" | jq -r '.output_token_reduction_percent | -. | .*10 | round / 10')"
expect "fresh input did not fall" "true" \
  "$(printf '%s' "$OUT" | jq -c '[.token_reduction_decomposition[] | select(.category=="fresh") | .saved] | .[0] <= 0')"

if [[ "$fail" -ne 0 ]]; then
  echo "FAIL: the published figures do not recompute." >&2
  exit 1
fi

echo "OK: the published figures recompute from the report's own tables."
