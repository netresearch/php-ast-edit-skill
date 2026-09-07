# Haiku pilot: delegate cross-file rename intent

For this synthetic 50-file rename, a symbol-aware intent API reduced median total
tokens by **65.5%**, tool calls by **40.9%**, visible main-loop rounds by **56.5%**
and wall time by **45.8%** versus a competent batched-text baseline. Existing Phpactor
CLI refactoring was still cheaper and faster at this size. The evidence supports
delegating reference discovery and individual edits; it does not establish that an
AST writer alone causes the saving.

There are only **three repetitions per arm and size**, using one generated task
family and one model. Results vary substantially, including within the same arm.
These are pilot observations, not general ROI estimates or a production rename claim.

## Results

Each row is the median of three attempted candidates, including scope failures.
Tokens include fresh input, cache reads, cache writes and output from native
whole-call `modelUsage`. Thinking detail is not added to output a second time.
Rounds count visible unique main-loop response IDs; tool calls can run in parallel
within a round. All values are available individually in [runs.json](runs.json).

| PHP files | Route | Total tokens | Tool calls | Rounds | Wall seconds | Native list USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2 | Batched text | 33,443 | 7 | 6 | 20.01 | 0.02786 |
| 2 | Intent + AST | 28,784 | 7 | 5 | 19.07 | 0.02336 |
| 2 | Phpactor CLI | 27,457 | 6 | 5 | 16.46 | 0.02193 |
| 10 | Batched text | 57,444 | 22 | 8 | 36.57 | 0.04495 |
| 10 | Intent + AST | 54,562 | 9 | 8 | 25.63 | 0.03117 |
| 10 | Phpactor CLI | 72,479 | 10 | 9 | 30.05 | 0.03727 |
| 50 | Batched text | 299,061 | 22 | 23 | 75.17 | 0.11571 |
| 50 | Intent + AST | 103,123 | 13 | 10 | 40.77 | 0.05621 |
| 50 | Phpactor CLI | 78,261 | 13 | 11 | 33.51 | 0.03928 |

| Files | Intent token reduction | Tool-call reduction | Round reduction | Wall-time reduction |
| --- | ---: | ---: | ---: | ---: |
| 2 | 13.9% | 0.0% | 16.7% | 4.7% |
| 10 | 5.0% | 59.1% | 0.0% | 29.9% |
| 50 | 65.5% | 40.9% | 56.5% | 45.8% |

At ten files, far fewer tool calls do not produce fewer model rounds: the text agent
often reads several files in parallel. Tool-call counts alone would overstate the
token benefit. At fifty files, encoding and checking a text-edit script costs many
more rounds and repeated context tokens. This is where delegation helps most here.

The 50-file intent runs span 38,139–118,254 tokens, 6–18 calls and 20.77–44.29 seconds.
The Phpactor runs span 28,247–146,852 tokens and 16.56–33.86 seconds. Do not read the
median ordering as proof that either semantic route always wins.

## Correctness and actual repair loops

All **27 final sets of PHP files exactly match the expected source**, including
unrelated `Other::fetch` declarations/calls and comments. The structural oracle
also passes in all 27. The complete file-scope-and-runtime oracle passes in 25:
`run007` (Phpactor) leaves `rename-output.log`, and `run026` (text) leaves
`rename_script.sh`. Their PHP edits are correct; the controller skips runtime
execution when file scope fails. These two scope failures are retained, not treated
as incorrect PHP renames or removed from the metrics.

Two text runs visibly need edit repair despite **zero native failed tool calls**:

- `run010`: a global replacement renames both `Provider::fetch` and unrelated
  `Other::fetch`. The agent detects this on rereading and uses Edit to restore the
  unrelated declaration.
- `run019`: the first shell replacement loses the `$` on receiver variables. The
  agent rereads, reverts the affected files and switches to a Perl script before
  reaching the correct result.

These traces support the observed repair-loop mechanism, not a population failure
rate. Every write process can exit zero while the source is wrong. Counting only
`is_error` tool results misses that problem. There are no observed edit-repair loops
in the nine intent candidates or nine Phpactor candidates, but their agents still
make failed reads and invalid grep calls during discovery or post-edit checking.

The intent API also does not automatically stop redundant verification. In `run009`,
one successful rename is followed by many source reads and grep attempts. In `run020`,
a text check falsely treats the intentionally preserved unrelated `fetch` method as
a rename failure. Better evidence from the tool and precise agent stop conditions
remain useful; silently claiming resolver completeness would be the wrong fix.

## What this says about “what” versus “where/how”

The model supplies a file, a method selector and a new name. Phpactor resolves the
symbol references. Deterministic code translates their ranges into validated AST
name slots, and the engine applies a guarded transaction. The model does not encode
every offset, quoted replacement or individual call-site mutation.

The direct Phpactor control also delegates this work, using `index:build` followed
by `references:member --replace`. Its strong results prevent attributing the entire
gain to AST mutation. The AST composition adds source/plan guards, a transaction
and integrated reporting; those guarantees have a tool-execution cost.

No arm exposes a full AST dump to the model. This pilot supports a compact intention
interface backed by structural and symbol analysis. It does not test whether raw
AST JSON is a better reading representation than PHP source.

## Provenance, accounting and limits

- Protocol: [prospective design and accounting amendment](../../PROTOCOL.md).
- Original frozen source: [`016fe0b`](https://github.com/netresearch/php-ast-edit-skill/commit/016fe0bbe05e26039a34f2c96f1ac932407f16d3).
  The unchanged original runtime and prompts are used by every candidate.
- Amended controller: [`2f13c04`](https://github.com/netresearch/php-ast-edit-skill/commit/2f13c0443f002c7677007762cc20b3c09b084f63).
  Later prototype review fixes are not silently substituted into measured runs.
- Claude Code 2.1.263, `claude-haiku-4-5-20251001`, no effort flag; PHP 8.5.10
  on Linux/WSL, Linux temporary workspaces. Dependency and executable manifests
  are retained. Fresh resolver indexes; provider prompt-cache warmth is unknown.
- Phpactor 2026.07.22.0 PHAR SHA-256:
  `8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d`.
- **27/27 have validated native aggregate usage**, totaling **2,156,929 tokens**
  and **USD 1.1434738 native list-price estimate**. This is not a provider invoice.
  No timeouts, replacement candidates or missing-cost imputations.
- `run001` originally stopped the controller on a scope mismatch between terminal
  `usage` and `modelUsage`. Its original measurement and raw trace remain intact;
  a separate hash-bound recovery applies the SDK-documented main-loop/whole-call
  distinction. The visible input totals match the main loop; whole-call work is
  included without inventing auxiliary response counts or their cause.
- Per-tool execution intervals are not exposed in these traces. Every
  `tool_execution_ms` remains null; API duration is not subtracted from wall time
  to invent orchestration time. Cold indexing and agent-initiated checks count in
  candidate wall time; the external oracle runs afterward.
- All arms can batch shell edits/reads. Native init verifies the same tools and
  no loaded skills/plugins/MCP. This is context isolation, not an OS sandbox.
- Temporary-file scope deviations: text runs 008/010/015/019/024 write helper
  scripts outside the workspace; Phpactor run025 writes an external log. These
  violate the common workspace-only instruction. They remain in assigned-arm
  aggregates; no AST/semantic-route bypass was observed in the intent arm.
- Operator review inspected traces, mutations and final source outcomes; the PR
  also received external code review. Human acceptance and an independent
  replication of these economics measurements have not been performed.

The fixtures are intentionally bounded: self-contained typed receivers, no Composer
dependencies, inheritance coverage, dynamic calls or TYPO3 configuration references.
Successful results still say `completeness: unknown`. Real extension workloads and
additional models/repetitions are needed before recommending a general default.

## Recompute from public evidence

[evidence.tar.gz](evidence.tar.gz) contains all 27 native traces, full prompts,
initial/final source, diffs, original/recovered measurements, plans, resolver traces,
frozen controllers and configuration. It contains generated public fixtures only;
no home sessions, credentials, vendor tree or PHAR binary. File hashes are in
[evidence-manifest.json](evidence-manifest.json); artifact hashes are in
[SHA256SUMS](SHA256SUMS).

```bash
mkdir /tmp/php-symbol-evidence
tar -xzf evidence.tar.gz -C /tmp/php-symbol-evidence
python3 /tmp/php-symbol-evidence/controller-amendment-source/benchmarks/symbol-intent/pilot.py \
  summarize --output /tmp/php-symbol-evidence
```

This reaggregation makes no model calls and requires no PHP/vendor installation.
Compare its output with [summary.json](summary.json). Re-execution of candidates
instead requires the documented runtime setup, provenance checks and model budget.
