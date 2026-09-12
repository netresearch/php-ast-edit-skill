# Prospective unchanged-file context experiment

This new campaign follows PR #85's completed source-excerpt experiment. It neither
extends nor pools earlier attempts. That experiment reduced the ratio of cross-file
cell medians, but only three of six paired comparisons saved tokens. Its small task
regressed. One of the small task's three excerpts repeats the old source line of a
file already shown in the diff. This campaign tests a filtered excerpt variant
against original reports without added context. It does not isolate the filtering
effect against full excerpts: that would require a contemporaneous third arm.

## Intervention

The two arms retain the same selected intent, complete rename command, instructions,
fixtures, AST engine, verification, native tools and independent oracles:

| Arm | Candidate-visible engine output |
| --- | --- |
| `unchanged_locations` | Original report bytes |
| `unchanged_excerpts` | Original report bytes plus bounded unchanged-file context |

Both arms compute exactly the same additional context. Only treatment displays it.
The original warnings, unresolved locations, diffs, checks, counts and exit behavior
remain intact. No wording in the task or system prompt changes between arms.

The benchmark-only proxy captures the same bounded pre-command fixture snapshot as
PR #85. It derives requested lines from the original rename warnings, then excludes
files explicitly marked `changed: true` in the original per-file engine results,
except dry-run entries: a planned change does not make the source file changed.
Thus "unchanged" means not changed by this command according to that report; it
does not mean a warning is unrelated or safe to ignore. Selection performs no
additional source reads. Independent review must compare this classification with
actual before/after file hashes for every measured command.

New-mode file paths are checked lexically within the known fixture root. Absolute
and relative warning aliases are canonicalized and deduplicated. Malformed or
ambiguous file results stop the experiment when warning locations require filtering.
Legitimate outputs with no requested locations, and failed engine calls, remain
unchanged. Existing experimental arms preserve their original behavior.

The additional context keeps the pre-command, raw-untrusted-source label and prior
bounds: 20 entries, 240 UTF-8 bytes per line and 8,192 serialized bytes including
metadata. It adds `scope: "unchanged-files"` and `excludedChanged`; omitted locations
remain separately counted. Entries + omissions + changed-file exclusions account
for every distinct requested location. Changed-file warnings remain in the original
report even when no excerpt is included. Context is not semantic classification or
a current write coordinate. Multiline expressions may still require a read.

The same contained, nonsymlink, git-listed initial fixture allowlist bounds capture
to 200 files, 1 MiB per file and 4 MiB total. Both arms pay capture/filter cost;
treatment also pays for the additional visible output. This small-fixture prototype
does not establish production-scale capture performance.

## Freeze, budget and decisions

Two unchanged tasks (`method-and-literal`, `cross-file-rename-clarified`) × two arms ×
six paired repetitions = **24 new attempts**. Seed `20260917`; for each task three
pairs begin with each arm, so both arms run six times. Pin
`claude-haiku-4-5-20251001`, no effort/fallback override, Claude Code
2.1.268 via its versioned executable and the same PHP/Phpactor runtime identities as
the preceding campaign. Fresh workspaces, serial calls, 120 seconds per attempt,
USD 3 campaign ceiling and USD 0.75 reservation for only the next imminent run.
Actual native cost replaces that reservation. Provider cache state is unknown.

Freeze signed source, protocol, controller, helper and unchanged task generator
before paid calls. Independent design/code review, helper/proxy boundary tests,
actual adapter propagation and both task oracles must pass first. Record all runtime
and source identities and verify each pair's fixture, prompt and instruction hashes.
Run no competing local tests during candidate wall-time measurement.

Retain every attempted run. Do not rerun, replace, refine or add paid candidates in
this campaign. Stop after preserving the attempt and accounting on missing cost,
model drift, timeout, isolation/intervention error or budget violation. Unpaid
preflight checks are separate from candidate measurements.

The prospective primary criterion uses **paired ratios**, rather than comparing
cell medians: on each task, median treatment/control total-token ratio must be at
most 0.85, median wall-time ratio at most 1.0, and at least four of six pairs must
save tokens. All 24 attempts must pass independent final-code, protected-file,
candidate-check, AST-route and supported-final-claim gates. Report cell medians too,
but do not substitute them for this criterion. Instruction adherence stays separate.
Gate comparisons use exact rational ratios of integer token counts and serialized
decimal wall times; floating-point presentation does not move the thresholds.

Six pairs per task remain exploratory even if the criterion passes. Keep the
feature isolated from the production CLI and loaded skill; a larger, separately
registered confirmation and production implementation review would be needed.
If it fails, publish the failure and reproducible prototype without promotion.

## Reporting and execution

Report every attempt's native fresh input, cache creation, cache reads, output and
their total; thinking is a subset of output. Publish paired ratios, cell medians,
rounds, tool calls/failures, wall time and native cost. Audit delivered context,
changed-file exclusion, reads of warned files, repeated already-passed checks and
final claims. Distinguish useful unresolved review from redundant reads. Tool
execution time remains unknown without complete interval coverage.

This is an AST-report comparison, not AST versus text editing. Operator-selected
targets and exact commands exclude the cost of autonomous target selection. Previous
campaigns are motivation only, not contemporaneous controls or pooled observations.

Generate the unchanged manifest with `exact_tasks.py`. Prepare the efficiency runner
with `--arms unchanged_locations,unchanged_excerpts --models haiku --seed 20260917
--repetitions 6 --balance-by-task --campaign-budget-usd 3`, the frozen source and
pinned runtime-only vendor directory. Execute the frozen controller, retain original
and presented stdout plus native streams, then summarize and export with the
existing intent-command and pilot tools. Run the frozen `unchanged_compare.py` on
the summary for the registered paired criterion; manual quality review remains a
separate gate. Publish only allowlisted synthetic inputs
and run evidence; exclude private sessions, credentials, dependencies and binaries.
