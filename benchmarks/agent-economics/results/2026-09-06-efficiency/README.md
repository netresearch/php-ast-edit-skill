# Reproducing the compact-workflow results

Read [REPORT.md](REPORT.md) for the findings, [TABLES.md](TABLES.md) for every descriptive
cell and [summary.json](summary.json) for numeric observations, availability and paired
comparisons. The [experimental runner protocol](../../efficiency/PROTOCOL.md) defines the
candidate settings and the compact adapter's scope.

`evidence.tar.gz` contains sanitized derivatives of the 120 native candidate traces,
complete prompts and tool payloads, original/final PHP, diffs, oracles, source inventories,
frozen controller/adapter snapshots and the separately retained accounting amendments.
It includes all failed attempts, unknown usage and instruction deviations. The public
TYPO3 fixtures retain their source commits, copyright notices and GPL-2.0-or-later
licenses. Project tooling remains MIT; skill/documentation material remains CC-BY-SA-4.0.
Private historical Claude transcripts and indexes are not part of this artifact.

The bundle also contains independent AI reviews, task construction/provenance, the
byte-size representation study, operator planning amendments and the exporter/verifiers.
Human acceptance stays pending. A passing checksum or task oracle does not imply human
approval, semantic correctness outside that oracle, or OS sandbox isolation.

## Verify and reaggregate without model calls

Requirements: Python 3.10+, Bash, tar and SHA-256 utilities. Run these commands from this
results directory. No candidate PHP program, shell command from a trace or model call is
executed by the verification and aggregation commands.

```bash
sha256sum -c SHA256SUMS
benchmark_review_dir=$(mktemp -d /tmp/php-ast-evidence-review-XXXXXX)
tar -xzf evidence.tar.gz -C "$benchmark_review_dir"
python3 "$benchmark_review_dir/evidence/tools/verify_public.py" \
  "$benchmark_review_dir/evidence" --output "$benchmark_review_dir/verification.json"
```

To independently recalculate all numeric summaries and compare them with the published
files:

```bash
mkdir "$benchmark_review_dir/analysis"
for phase in phase1 phase2; do
  python3 "$benchmark_review_dir/evidence/tools/analyze.py" \
    "$benchmark_review_dir/evidence/$phase" \
    --output "$benchmark_review_dir/analysis/$phase-summary.json"
done
python3 "$benchmark_review_dir/evidence/tools/analyze.py" \
  "$benchmark_review_dir/evidence/phase3" --baseline compact_full \
  --output "$benchmark_review_dir/analysis/phase3-summary.json"
cp "$benchmark_review_dir/evidence/reviews/"phase*-review.json "$benchmark_review_dir/analysis/"
python3 "$benchmark_review_dir/evidence/tools/build_public_summary.py" \
  --analysis-root "$benchmark_review_dir/analysis" --output "$benchmark_review_dir/recomputed"
cmp summary.json "$benchmark_review_dir/recomputed/summary.json"
cmp TABLES.md "$benchmark_review_dir/recomputed/TABLES.md"
```

The portable verifier checks exported file hashes, original hash anchors, captured native
accounting and review identity/coverage. The retained private-to-public verification
records additionally document full payload equality under the permitted sanitization.
Original measurement hash fields continue to refer to originals; `export-manifest.json`
maps original and derivative hashes. The separate `ancillary-manifest.json` covers
reviews, tools and supporting evidence. Hashes establish consistency, not independent
cryptographic authorship.

Sanitization removes account-specific rate-limit records, native session IDs and init
socket metadata, and normalizes explicitly recorded paths. Model response IDs, tool IDs,
failures, synthetic retries and numeric usage remain. The line map translates original
native event indexes after omitted records. Token/byte metrics describe the original
experiment inputs, not the shorter normalized path strings.

## Run another candidate experiment

Fresh model runs are separate from the offline verification above and need an authenticated
Claude Code installation. Their results will not be deterministic, and cache state must
be recorded as unknown unless separately controlled.

Use the runner's `prepare`, `validate` and explicit `run --execute-models` steps described
in its [protocol](../../efficiency/PROTOCOL.md). For an original-task replication, select
source commit `25bb90a82dbf4425d2d5a712079c9a507a82c82f`. The directed experiment was
prepared from `fd4ce4018055828530c5f47bc8e25b723b4d8109` with
`--arms compact_full,compact_focused` and the preserved directed task manifest. Use a fresh
Linux output directory and retain its new evidence; never overwrite the archived runs.

The archive includes the exact task manifests at `phaseN/controller/benchmarks/tasks.json`
and dependency/runtime hash inventories. A new Composer resolution can differ from the
original dependency tree; compare actual bytes and versions before claiming an identical
runtime. Installation, preparation and human onboarding are not measured by the candidate
wall times in this report. Later tooling hardening on development main is separate from
the frozen source used for these observations.
