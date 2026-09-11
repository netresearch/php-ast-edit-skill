# Direct method intent: two exploratory Haiku campaigns

The new `rename --method Class::old --to new` command works on both fixtures, but
these runs do **not** establish an overall agent-efficiency win. In the refinement,
median total tokens and visible rounds fell on both tasks; wall time and native
list-price cost rose, while tool calls were equal or higher. The prospective
criterion of at least 15% fewer tokens with no wall-time increase on both tasks
was not met in either campaign. There were no failed final task oracles.

## Design and provenance

Two separately frozen campaigns each contain two existing tasks × two arms ×
three repetitions = twelve candidates; 24 candidates in total. The arms are ordinary
contextual editing and the real loaded skill with the new engine command. This is
a bundled interface/skill intervention, not an isolated AST algorithm comparison.

- Initial source: [`63c2e26`](https://github.com/netresearch/php-ast-edit-skill/commit/63c2e26ac707a9f84f38a5268c15513162416c6a), seed `20260911`, rename default `agent`.
- Refinement source: [`72bffce`](https://github.com/netresearch/php-ast-edit-skill/commit/72bffce8d7036107ac61b990099a315c1367945d), seed `20260912`, rename default `compact` with inline diff.
- Model: `claude-haiku-4-5-20251001`; no effort flag, fallback model or extra model.
- Claude Code 2.1.268; PHP 8.5.10; php-parser 5.8.0; pinned Phpactor 2026.07.22.0.
- Engine: frozen source CLI plus production-only vendor dependencies, not a released PHAR.
- Byte-identical task manifest in both campaigns: `e2d043c0cd9d9661903c0ca2f9471888b65d6a19dabb5ef68d756bb6803cf526`.
- Serial, fresh candidate processes/workspaces; unchanged runner and 120-second deadline.
- Native list-price costs: initial **USD 0.4732538**, refinement **USD 0.4657675**, combined **USD 0.9390213**. These are API-reported estimates, not an invoice.

The [prospective protocol](../../intent-command/PROTOCOL.md) defines the criterion,
fixed budgets and single refinement. No candidate was replaced, discarded or rerun.
The earlier [36-run v0.8.0 study](../2026-09-11-v080-haiku/REPORT.md) is historical
context and is not pooled with these controls. Missing historical “120 powered” raw
runs are not reconstructed here. Remote v0.8.1 release metadata was integrated later;
it did not change either frozen runtime.

## Initial campaign: review diff omitted by default

All values below except correctness are per-cell medians of all three attempts.
Total tokens sum fresh input, cache creation, cache reads and output, without double
counting thinking tokens. Rounds are observed primary assistant rounds, not native
turns. Both complete decompositions are retained in the JSON reports.

| Task | Arm | Correct | Total tokens | Rounds | Tool calls | Wall seconds | Cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| method-and-literal | contextual_patch | 3/3 | 54,053 | 5 | 7 | 20.15 | 0.02063 |
| method-and-literal | full_skill | 3/3 | 48,235 | 4 | 6 | 22.56 | 0.02171 |
| cross-file-rename-clarified | contextual_patch | 3/3 | 135,759 | 10 | 23 | 40.10 | 0.04979 |
| cross-file-rename-clarified | full_skill | 3/3 | 201,583 | 13 | 26 | 47.16 | 0.05988 |

The direct command removed manual request construction, but every cross-file skill
run reread changed source after its successful rename. One also performed a dry run.
The default `agent` report omitted the diff. All three small-task skill runs chose
`--report compact`. These observations motivated testing the existing compact report
as the new command's default; they do not isolate a causal effect across tasks.

## Refinement: review diff included by default

The refinement changes the direct command default and matching skill guidance.
Existing explicit report modes, guards, resolution and checks remain. It also includes
review-driven behavior-preserving complexity refactors and validator corrections;
the source identities above disclose that bundle. No task prompt or fixture changed.

| Task | Arm | Correct | Total tokens | Rounds | Tool calls | Wall seconds | Cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| method-and-literal | contextual_patch | 3/3 | 53,464 | 5 | 6 | 18.66 | 0.02000 |
| method-and-literal | full_skill | 3/3 | 48,121 | 4 | 6 | 21.96 | 0.02137 |
| cross-file-rename-clarified | contextual_patch | 3/3 | 155,869 | 12 | 22 | 38.21 | 0.04854 |
| cross-file-rename-clarified | full_skill | 3/3 | 147,249 | 10 | 23 | 48.79 | 0.05392 |

Relative changes below compare each refinement cell only with its contemporaneous
contextual-edit control. Negative means less; medians are compared, not paired ratios.

| Task | Tokens | Rounds | Tool calls | Wall time | Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| method-and-literal | -10.0% | -20.0% | +0.0% | +17.6% | +6.9% |
| cross-file-rename-clarified | -5.5% | -16.7% | +4.5% | +27.7% | +11.1% |

The command remains a useful smaller input interface: a symbol and new name express
a guarded multi-file change, including hierarchy and call sites. It does not make
an agent stop reading or rechecking. Even after receiving the diff and a passing
configured check, candidates sometimes repeated checks or reviewed source again.
The CLI's transaction success and the full agent session's efficiency are separate
observations. No independent tool-execution duration covers every call, so the extra
wall time cannot be assigned entirely to Phpactor, AST parsing or model orchestration.

## Correctness and limits

All 24 independent final oracles passed, with preserved decoys, literals and protected
support/configuration bytes. PHP lint and executable fixture behavior are part of
the oracles; passing these finite fixtures does not establish general semantic
refactoring safety or resolver completeness. Every candidate reported the pinned
model, without a timeout or accounting error.

In the refinement, all seven direct command invocations across six skill runs
exited successfully, and each run reached a passing configured checker. One run
added a dry run; another explicitly selected `agent` output. All eight observed
failed tool results were attempts to read a directory as a file (`EISDIR`). There
were no failed text edits in this sample, so it cannot quantify avoided edit-repair
loops. Both arms reached the same final correctness rate.

There are only three repetitions per cell. Cache state is unknown and not balanced;
provider latency and native reasoning vary. Token count is not cost: cache categories
have different prices. These two compact method-rename fixtures do not represent
large production repositories or variable batches. No significance or universal
ROI claim follows from this sample. The single permitted refinement is complete;
there is no third adaptive campaign hidden behind the reported result.

## Evidence and reproduction

- [Initial machine-readable report](initial-report.json) and [raw evidence archive](initial-evidence.tar.gz).
- [Refinement machine-readable report](refinement-report.json) and [raw evidence archive](refinement-evidence.tar.gz).
- [Checksums](SHA256SUMS) cover both reports and archives.

Each archive contains the exact task manifest, frozen runner/controller, loaded
skill, schedule, native argv and raw JSONL, stderr, initial/final hashes, oracle,
engine audit, source diffs, final task files and operator/runtime provenance. Its
`export-sha256.json` hashes every exported evidence file. Runtime source is recoverable
from the frozen commit; vendor/Phpactor identities and hashes are recorded separately.
Only original benchmark fixtures are included, with no private session content.

Extract an archive into an empty directory and recompute its report from a checkout
containing the reporter:

```bash
tar -xzf initial-evidence.tar.gz -C /tmp/intent-initial
python3 benchmarks/agent-economics/intent-command/summarize.py /tmp/intent-initial
```

Create `/tmp/intent-initial` first. The reporter relocates evidence paths, validates
containment, retains unknown values and counts `rename` separately from `apply`.
A missing audit remains unknown; intact native traces can separately establish the
ordinary edit route. Recomputed cells and every per-run metric/intent count matched
the original reports after both exports were relocated. The source/runtime preflight,
fixture oracles, CLI regressions and report tests run without any model calls.
