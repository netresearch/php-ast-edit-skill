# Instruction scope and delegated discovery: Haiku experiments

Neither shortening the complete skill nor explicitly delegating discovery met the
prospective efficiency criterion. The initial 18 runs improved cross-file token
use while worsening the small task. The 12-run refinement increased median tokens
and wall time on both tasks. All 30 final fixtures were correct; completion claims
are reviewed separately. The extra delegation instruction is not adopted into the
product skill. The experiment arms remain opt-in research controls.

## Design

The [prospective protocol](../../intent-command/INSTRUCTION-EXPERIMENT.md) freezes
two small existing method-renaming fixtures, the engine, independent oracles,
protected support files, the model and a bounded schedule. These are complete
agent sessions, including reads, mistakes, verification and final responses.

- Initial: 18 attempts, two tasks × three arms × three repetitions; seed `20260913`.
- Initial source: [`3ab4f83`](https://github.com/netresearch/php-ast-edit-skill/commit/3ab4f83f22d1831dd7ae8ddce7d255be0ba8441e).
- Refinement source: [`38a2ae9`](https://github.com/netresearch/php-ast-edit-skill/commit/38a2ae9a59f92a969c740c17e6975969d4f7c518); 12 attempts, two tasks × two arms × three repetitions; seed `20260914`.
- Model: `claude-haiku-4-5-20251001`, no effort flag, fallback or extra model.
- Claude Code 2.1.268; PHP 8.5.10; php-parser 5.8.0; Phpactor 2026.07.22.0.
- Same source CLI, production vendor and pinned resolver in every AST arm.
- Fresh workspaces/processes, serial execution, 120-second timeout, USD 0.75 per-run reservation.
- Native list-price cost: initial **USD 0.7160165**, refinement **USD 0.4743222**, combined **USD 1.1903387**. The refinement received the residual USD 2.2839835 of the shared USD 3 planning ceiling. These estimates are not invoices.

The initial comparison is `minimal_intent` versus contemporaneous `full_skill`,
with ordinary `contextual_patch` editing reported separately. The minimal arm has
70 whitespace-delimited instruction words; the full arm has 487 including its
wrapper. Counts exclude their common instructions and the CLI's native context.
The experimental arms are opt-in; released benchmark defaults remain unchanged.

The single refinement compares unchanged minimal instructions against explicit
delegation of initial source discovery and the complete method-family rename to
the command. Only that arm overrides the common model-read-before-write sentence.
It retains guards, resolution, diff review, warnings, configured checks and the
same independent oracle. This is a disclosed workflow bundle, not an isolated test
of one phrase. Both controllers and all actual per-run instructions are retained.

The older [direct-command study](../2026-09-11-intent-command/REPORT.md) is separate
historical context. None of its runs are pooled here. No candidate is replaced or
discarded; all attempted runs contribute to the metrics below.

## Initial: fewer instruction words are not enough

Values are per-cell medians of all three attempts. Correctness means independent
fixture oracles; the separate completion-claims gate is discussed below. Tokens
sum fresh input, cache creation, cache reads and output. Thinking is already part
of output; visible primary rounds differ from the provider's native turn count.

| Task | Arm | Correct | Tokens | Rounds | Calls | Wall seconds | Native cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| method-and-literal | contextual_patch | 3/3 | 87,840 | 8 | 10 | 16.90 | 0.02820 |
| method-and-literal | full_skill | 3/3 | 61,734 | 5 | 7 | 24.71 | 0.03074 |
| method-and-literal | minimal_intent | 3/3 | 82,944 | 7 | 10 | 27.18 | 0.03101 |
| cross-file-rename-clarified | contextual_patch | 3/3 | 112,555 | 9 | 20 | 32.52 | 0.03967 |
| cross-file-rename-clarified | full_skill | 3/3 | 204,758 | 13 | 26 | 45.36 | 0.05893 |
| cross-file-rename-clarified | minimal_intent | 3/3 | 154,635 | 11 | 24 | 43.65 | 0.05227 |

Minimal versus full uses **34.4% more tokens and 10.0% more time** on the small task,
but **24.5% fewer tokens and 3.8% less time** across files. It fails the prespecified
requirement of at least 15% fewer median tokens with no wall-time increase on both
tasks. Against ordinary editing, minimal still uses more cross-file tokens and
more wall time on both tasks.

The [independent trace audit](initial-audit.json) explains why a smaller write API
does not automatically shrink a session:

- All 12 AST candidates read source before invoking the command: 81 file reads.
  The common instruction required those reads, so this is not instruction
  non-adherence. The engine can instead discover the named declaration itself.
- After the successful AST mutation, 86 more calls occur: 30 reads of changed files,
  31 reads of unchanged files, 12 repeated checks and 13 Git queries. Some unchanged
  reads examine explicitly reported literal/YAML facts and are warranted review.
- Eleven of 12 AST runs repeat an already successful integrated check, without a
  subsequent write. The ordinary-edit arm needs its first manual check.
- Minimal run005 queues Contract, Base and Child renames before seeing the first
  response. Contract succeeds; Base/Child then fail because the family is already
  renamed. Minimal run013 supplies an unsupported positional `.` and then retries
  correctly. Both failures remain in the metrics.
- Fourteen other failed calls are native directory reads (`EISDIR`), spread across
  all arms. No ordinary text-edit call fails in these fixtures; this sample does
  not measure avoided text-edit repair loops.

All AST candidates use the intended writer and reach successful configured checks.
Run005's final claim of "ensuring type safety and consistency across the codebase"
fails the completion-claims gate: finite fixture checks do not establish that
general guarantee. Thus 18/18 fixture correctness is **not** an 18/18 complete
quality pass. The other 17 final claims passed manual review within this scope.

The AST cross-file mutation changes three declarations and two calls in four files,
with one successful write transaction per candidate. It also adjusts trailing
whitespace; the small fixture gains a final newline. The complete diffs retain
these changes. Protected check/configuration files remain byte-identical.

## Refinement: delegate discovery and family planning

All 12 scheduled attempts completed, with no timeout, unexpected model or missing
accounting. The primary comparison below uses only contemporaneous minimal and
delegated cells. The initial full-skill and contextual cells are not reused as
controls for this refinement.

| Task | Arm | Correct | Tokens | Rounds | Calls | Wall seconds | Native cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| method-and-literal | minimal_intent | 3/3 | 55,977 | 5 | 7 | 22.71 | 0.02299 |
| method-and-literal | delegated_intent | 3/3 | 69,407 | 6 | 6 | 24.11 | 0.02380 |
| cross-file-rename-clarified | minimal_intent | 3/3 | 141,019 | 10 | 23 | 43.44 | 0.05011 |
| cross-file-rename-clarified | delegated_intent | 3/3 | 182,360 | 12 | 23 | 52.96 | 0.06021 |

Delegated versus minimal, comparing cell medians:

| Task | Tokens | Rounds | Calls | Wall time | Native cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| method-and-literal | +24.0% | +20.0% | -14.3% | +6.2% | +3.5% |
| cross-file-rename-clarified | +29.3% | +20.0% | +0.0% | +21.9% | +20.2% |

Fewer calls on the small task still coincide with more tokens and time. A native
tool-call count is not an adequate proxy for session efficiency. The intended
delegation must occur in the observed workflow before it can explain savings.
The complete [refinement trace audit](refinement-audit.json) records its adherence
and quality gates independently of the numerical report.

Only one of six delegated candidates, refinement run005, invokes the rename before
reading PHP. The other five still read PHP first. Across six candidates per arm,
delegated uses 33 pre-command file reads versus minimal's 39, but 42 post-write
calls versus 32. Nine of 12 runs repeat already-passed checks, ten repetitions in
total. Neither arm queues separate family renames in this campaign, so their
absence cannot be credited uniquely to the new instruction.
Three rejected CLI calls use an unsupported positional project path; corrected
retries succeed. Three other failures are directory reads. These are retained
failures, with no corrupted PHP or text-write fallback observed.

All 12 pass fixture, candidate-verification and writer-route gates. Refinement
run002 fails the claims gate: it calls all remaining `findByUid` strings data with
no method reference, although `check.php:10` uses one in a `method_exists` negative
assertion. Preserving that assertion is correct; its explanation is not. This is
separate from initial run005's broad type-safety claim. Across both campaigns,
30/30 final fixtures pass but only 28/30 completions pass all reviewed quality gates.

Both experiments are complete. Their negative outcomes are retained; there are no
replacement runs or further adaptive rounds under this protocol. These results
do not justify adding the delegation prose to every user's loaded skill or claiming
that a shorter instruction inherently reduces token use.

## Why the earlier positive result is different

The [public-source verification study](../../../symbol-intent/results/2026-09-07-real-php/REPORT.md)
compared a composite AST/integrated workflow against text/manual editing. Its
[controller](../../../symbol-intent/real_pilot.py) supplied an exact task-specific
invocation and an explicit completion contract recognizing configured checks. It
used a different task and ten repetitions per arm. The present study tests generic
instructions in the current CLI harness with three repetitions per cell. Its
negative result does not invalidate that composite result, nor does the earlier
result prove a generic instruction-only benefit. Command preparation and deciding
when the task is complete remain distinct candidate mechanisms to test.

## Limits and evidence

Three repetitions per cell are exploratory, without significance or a universal
savings rate. Cache state is unknown; token categories have different prices.
Provider latency and model behavior vary. The tasks are small synthetic rename
fixtures, not a broad production workload. No complete tool-execution intervals
are exposed, so tool execution versus orchestration wall time remains unknown.
The JSON reports preserve that unknown value rather than estimating it.
The fixed refinement schedule places delegated first in all three small-task pairs
and minimal first in all three cross-file pairs; starts are balanced globally, not
within each task. Per-task order and cache effects are not separately identified.

- [Initial report](initial-report.json), [trace audit](initial-audit.json) and [exact evidence archive](initial-evidence.tar.gz).
- [Refinement report](refinement-report.json), [trace audit](refinement-audit.json) and [exact evidence archive](refinement-evidence.tar.gz).
- [Checksums](SHA256SUMS) cover the published reports, audits and archives.

Archives include the frozen controller, task manifest, loaded skill, schedule,
native arguments and traces, engine audit, initial/final files and hashes, diffs,
oracle output and runtime/operator provenance. `export-sha256.json` covers each
exported file. Vendor binaries are omitted; the full frozen checksum manifest and
pinned dependency identities remain. Runtime source is recoverable from the named
commit. Only this synthetic experiment's files are included.

To reproduce a report, extract an archive into a new directory and run:

```bash
mkdir /tmp/instruction-initial
tar -xzf initial-evidence.tar.gz -C /tmp/instruction-initial
python3 benchmarks/agent-economics/intent-command/summarize.py /tmp/instruction-initial
```

Evidence paths relocate to the extraction directory. The reporter validates
containment and preserves failed or unknown observations. Trace-audit quality
gates are separate from automated oracle correctness; the reporter's `successful`
count does not independently evaluate final prose claims.
All six initial and four refinement cells, per-run metrics and intent counts
recomputed unchanged after export relocation. The archives' 588 and 402 listed
file checksums respectively matched their source bytes. Use the same procedure
with `refinement-evidence.tar.gz` in a separate empty directory for the refinement.
