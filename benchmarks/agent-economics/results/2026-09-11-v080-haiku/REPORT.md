# Released skill economics: gains on one task, overhead on others

Thirty-six fresh Claude Haiku sessions tested the released v0.8.0 workflow and an
instruction follow-up. **There is no general token-saving result.** The small edit
improved; batching three local changes and the clarified cross-file rename cost
more through the full skill. Adding explicit declaration-first guidance did not
fix that overhead. All runs, including failed tasks, remain in the evidence.

The model was `claude-haiku-4-5-20251001`, with no effort flag or fallback. Each cell
has three attempts. Values below are medians of **all attempted runs**, with ordinary
contextual editing on the left and the skill on the right. Tokens include fresh
input, cache creation, cache reads and output; cost is the native list-price estimate,
not an invoice. Cache state is unknown.

## The released skill: original 24 sessions

| Task | Oracle pass | Tokens | Model rounds | Tool calls | Wall seconds | USD |
| --- | --- | --- | --- | --- | --- | --- |
| Small greeting edit | 3/3 → 3/3 | 53,258 → 36,681 | 5 → 3 | 6 → 4 | 15.51 → 12.74 | .01757 → .01516 |
| Three local renames in one file | 3/3 → 3/3 | 66,744 → 92,539 | 6 → 7 | 7 → 6 | 20.58 → 26.28 | .02412 → .03217 |
| Rename beside confusable occurrences | 3/3 → 2/3 | 55,889 → 51,492 | 5 → 4 | 7 → 6 | 20.13 → 19.30 | .02205 → .02646 |
| Cross-file rename, ambiguous YAML fixture | 2/3 → 0/3 | 99,628 → 209,275 | 8 → 13 | 23 → 28 | 38.97 → 59.70 | .04457 → .06719 |

The small edit used **31.1% fewer tokens and 17.9% less wall time**, with all six
outcomes correct. Three changes in one file used **38.6% more tokens and 27.7% more
time**, despite fewer tool calls. The confusable-name task's apparent token benefit
comes with a failed completion: original run013 left `edit.json` in the workspace
after the correct PHP edit. It is retained as a failure, not excluded from medians.

The original cross-file oracle has an interpretation defect. YAML contained an
actual service call to `fetch`, but the hidden checker required that file to remain
unchanged. Runs006, 011, 012 and 017 updated it to `load`, a defensible interpretation
of the requested rename. Run006 additionally modified the checker through ordinary
PHP `Edit` calls, violating the supplied skill. Keep the frozen failed scores, but
do not use those scores alone as evidence of incorrect AST reference resolution.

Per-run values, token components, successful-only medians and ordered tool-call
queues are in [original.json](original.json). The [prospective protocol](../../v080-pilot/PROTOCOL.md)
was committed before execution; the [clarification](../../v080-pilot/CLARIFICATION.md)
records the discovered fixture ambiguity and the separately scheduled follow-up.

## The clarified cross-file task: six new sessions

The PHP source and requested transformation stayed identical. YAML became an
unrelated `label: fetch` value, and both prompts explicitly protected all support
files. Both arms passed all three attempts.

| Metric | Contextual editing | Released full skill |
| --- | ---: | ---: |
| Tokens | 131,640 | 175,335 |
| Model rounds | 10 | 11 |
| Tool calls | 21 | 23 |
| Wall seconds | 41.92 | 47.19 |
| USD | .04769 | .05592 |
| Oracle pass | 3/3 | 3/3 |

The released skill used **33.2% more tokens and 12.6% more time**. This unambiguous
task therefore does not establish a multi-file saving either. See
[clarified.json](clarified.json); its six runs are not pooled with the original cell.

## Declaration-first instructions: six further sessions

The [instruction intervention](../../v080-pilot/INTENT-FOLLOWUP.md) combined a stdin
example, direct use of a supplied executable, and explicit guidance to confirm the
declaration and submit one rename for the hierarchy. It used the same clarified
fixture and unchanged PHP engine, with a new frozen skill and schedule.

| Metric | Contextual editing | Revised full skill |
| --- | ---: | ---: |
| Tokens | 118,810 | 195,741 |
| Model rounds | 9 | 12 |
| Tool calls | 22 | 25 |
| Wall seconds | 36.40 | 50.70 |
| USD | .04577 | .06605 |
| Oracle pass | 3/3 | 3/3 |

This attempt also failed to improve economics: **64.8% more tokens and 39.3% more
time**. The model still read callers, submitted redundant hierarchy operations and
rechecked successful work. The extra method-rename paragraph was withdrawn. The
stdin example and direct executable use remain as small usability changes; this
bundled trial does not establish an isolated performance benefit for either.
[intent.json](intent.json) retains every attempt and its revised instructions.

## What the traces establish

- A single `rename_method` can perform the intended PHP hierarchy/caller change;
  the surrounding agent workflow can still spend many calls discovering, reading
  and reviewing those files. Delegating mutation does not automatically delegate
  the agent's planning and verification decisions.
- Original run017 and clarified run001 submitted overlapping hierarchy operations.
  The engine rejected the transaction, then a single hierarchy operation succeeded.
  An invalidated in-memory edit is not evidence of a partial disk write.
  Original run017 also wrote `/tmp/edits.json` outside its assigned workspace; that
  instruction violation remains visible in the native trace and engine input audit.
- Original run013 combined `--input` with an incompatible CLI report flag, corrected
  the invocation and completed the PHP edit, but left its payload file behind.
- Original run022 used `which`, created `edits.json`, applied it, reread the result,
  repeated the configured check, inspected status, deleted the payload, and fetched
  the diff. Its AST operation was only one part of a fourteen-round session.
- Directory `Read` failures (`EISDIR`) occurred in both arms. These are discovery
  mistakes, not broken text replacements. Native error flags, failed engine exits,
  support mutations, and repair links must remain distinct.
- Passive recorder `capture_error` messages on successful flag-form invocations
  mean that JSON input capture was unavailable. They are not engine failures.

This pilot does not demonstrate a general reduction in text-edit repair loops.
The fixtures are small, original examples, not a representative PHP workload corpus.
Three repetitions per cell support descriptive observations, not significance or
universal ROI claims. A useful next hypothesis is a smaller intent-oriented tool
interface that removes orchestration choices; simply adding more skill prose failed
here. Giving the model a full AST representation was not tested in this campaign.

## Provenance and reproduction

The original and clarified campaigns used release
`092bf2fe362d8539105d11094be72703fee2bbf6`; the instruction trial used
`a7a059f5dd091456c2606c342694f353b86603d6` with the same `src` and `bin` trees.
Runtime dependencies came from the verified v0.8.0 PHAR, with pinned Phpactor
2026.07.22.0. All three campaigns ran serially, retained their first attempts,
passed native model/isolation/accounting validation, and verified their frozen
inputs afterward. Tool execution duration was not exposed, so it remains unknown;
it was not estimated by subtracting API duration from wall time.

Native list-price totals: original **$0.7813199**, clarified **$0.3249242**,
instruction trial **$0.3278084**; **$1.4340525 for 36 attempts**. None timed out and
no model was upgraded. Preparation and offline tests are outside candidate wall time.
One non-executable development preparation was retained without model calls before
the instruction campaign was prepared from its explicit intended commit.

[evidence.tar.gz](evidence.tar.gz) contains an explicit allowlist: native transcripts,
prompts, manifests, frozen hashes, original/final task source, diffs, oracle outputs,
passive engine audits and controller source. Authentication stores, installed
dependencies and unrelated files are excluded. Native traces remain byte-identical;
export checksums cover the archived subset of the larger original frozen tree.

```bash
sha256sum -c SHA256SUMS
mkdir evidence
tar -xzf evidence.tar.gz -C evidence
python3 ../../v080-pilot/summarize.py evidence/original > original-recomputed.json
python3 ../../v080-pilot/summarize.py evidence/clarified > clarified-recomputed.json
python3 ../../v080-pilot/summarize.py evidence/intent > intent-recomputed.json
```

Compare each report's `cells` to the published JSON: evidence-location fields change
with extraction paths. The reports preserve all scheduled slots, unknowns, native
usage decomposition and successful-only denominators. Automated fixture falsification
tests and independent agent diff/trace reviews supplement the oracles; independent
human acceptance is not claimed. These campaigns do not reconstruct the unavailable
historical 120-run powered campaign.
