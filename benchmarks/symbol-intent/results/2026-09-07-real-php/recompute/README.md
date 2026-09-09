# Recomputing the published figures

The report next door states medians, per-category token totals and a set of
percentage changes. This directory recomputes the derived numbers from the
transcribed measurements, so a reader can check the arithmetic without rerunning
anything.

It contains **no new agent runs, no rerun of the PHP suite and no independent
audit of the raw traces.** Its input is a transcription of the published tables,
and `tests/recompute.sh` asserts that transcription against `REPORT.md` itself
before computing anything — a recomputation of numbers nobody checked against
the source would only launder them.

- `reported_metrics.json` — medians and per-category token totals, transcribed
- `recompute.jq` — validates each arm's category sum against its stated total, then derives the comparisons

```sh
jq -f recompute.jq reported_metrics.json
```

## What the arithmetic says

Comparing the **medians** of AST/integrated against text/manual gives −90.2%
combined tokens. Comparing the **summed** tokens of all ten attempts per arm
gives −83.2%. Both are correct and they answer different questions; they must not
be swapped.

Of the 1,115,139 fewer counted tokens, 92.6% are cache-read, 5.9% cache creation
and 1.5% output. Fresh input rises slightly. The output total on its own falls by
54.8%.

Cache-read tokens are not equivalent to freshly computed ones, in processing or
in price. The decomposition shows where the counted difference sits. It does not
by itself establish that any single measure caused it: the arms differ in
resolution, write path, result shape and check integration at once.

Thirty attempts at one six-file task are thirty attempts at one task, not a
sample of long coding sessions.
