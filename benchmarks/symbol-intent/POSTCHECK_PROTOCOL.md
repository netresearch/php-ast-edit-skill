# Prospective post-rename evidence and guidance ablation

This is a new experiment. The completed 27-run symbol-intent pilot motivates the
question; none of those candidates enters the new treatment comparisons. The
question is whether precise result evidence, scoped verification guidance, or their
combination reduces avoidable work while preserving correctness and honest limits.

## Frozen design

The two factors are crossed in four arms:

| Result | Guidance | Treatment |
| --- | --- | --- |
| Legacy compact result | Current wording | Control |
| `--evidence` result | Current wording | Result evidence alone |
| Legacy compact result | Scoped verification wording | Guidance alone |
| `--evidence` result | Scoped verification wording | Combined |

Use 10 and 50 PHP files with three repetitions for each cell: 24 candidates.
Fixtures and the task are the existing synthetic Provider/Other method rename.
All four treatments occur once in each size/repetition block. Seed 20260908 shuffles
the six blocks; arm order rotates by block index. This is not perfect positional
balance across four arms and six blocks. Retain the recorded order for inspection.

The evidence flag is baked into the assigned command wrapper. For each wording
setting, both result treatments receive otherwise identical prompts apart from
their isolated workspace paths. Scoped guidance is added to the common system
wording and is meaningful with either result: rely only on facts actually reported;
skip repeated byte-level inspection only if exact replacement evidence passed;
independently address reference completeness and relevant behavior. Failed, skipped
and not-run checks remain distinct from success. The prompt generator takes no
expected-output or oracle input. It does not supply hidden runtime assertions.

The evidence treatment reports the request, planned/applied totals, and whether
actual output matches only the validated Identifier replacements. Repeated warnings
are grouped. This bundles evidence and compact presentation as one treatment; it
does not isolate the separate effect of warning deduplication. Exact byte agreement
does not validate resolver bindings or reference completeness. `completeness` stays
`unknown` in every arm. No universal instruction to stop checking is tested.

## Preparation, execution and immutable evidence

Prepare only from a clean committed source tree with installed runtime dependencies
and the pinned Phpactor PHAR. Preparation performs no model calls. It archives the
source commit, copies dependencies, creates all 24 fresh Git workspaces and isolated
resolver state directories, and freezes source/dependency hashes, PHAR hash, fixture
hashes, hidden expected outputs, wrappers, full prompts, schedule and exact CLI
version in `config.json`, whose hash is also stored before execution.

```bash
python3 benchmarks/symbol-intent/postcheck_pilot.py prepare \
  --output /tmp/php-postcheck-pilot --phpactor /absolute/path/phpactor.phar
python3 /tmp/php-postcheck-pilot/source/benchmarks/symbol-intent/postcheck_pilot.py run \
  --output /tmp/php-postcheck-pilot --execute-models
python3 /tmp/php-postcheck-pilot/source/benchmarks/symbol-intent/postcheck_pilot.py summarize \
  --output /tmp/php-postcheck-pilot
```

Execution must use the frozen controller copy. It imports the existing pilot runner,
capture, grader and native accounting unchanged. The runner verifies the frozen
source/dependencies and each candidate's inputs before and after model execution.
All attempts remain, including stopped candidates. There is no replacement or
automatic resume path. Any future protocol amendment must preserve originals and
be recorded separately before additional model execution.

Use `claude-haiku-4-5-20251001`, no effort flag, the same Bash/Read/Edit/Write tool set,
safe mode, empty settings and MCP, disabled slash commands, and no persisted
sessions. Native initialization must confirm the requested model and isolation.
This isolates context, not the OS. Candidate prompts forbid reading controller,
evaluator, state or answer files. Essential result evidence must therefore appear
inline; an inaccessible full-report path does not substitute for it.

The new campaign has its own USD 4 native-list-price planning allowance, USD 0.50
per-call CLI budget and 120-second deadline. Reserve the full call budget before
starting each candidate. Stop on timeout, unknown accounting, model/isolation
mismatch, source/input drift or observed budget overrun. These are planning controls,
not a guarantee of provider billing. Retain all raw traces, stderr, argv, process
measurements, diffs, final hashes and oracle results. Do not infer missing spend.

## Outcomes and limits

The inherited hidden grader runs after each candidate. It checks file scope, PHP
structure and runtime dispatch; exact bytes are a separate layout metric. Candidate
checks remain included in wall time and token/tool accounting, while grader work
remains excluded. The oracle does not judge whether the candidate's final prose
overstates completeness; that requires separate trace and final-answer review.

`postcheck-summary.json` contains each cell's individual values and medians for
whole-call tokens, visible model rounds, calls, wall time, native list-price cost and subsequent tool
calls. It also reports paired evidence-minus-legacy deltas at each fixed wording
and scoped-minus-current deltas at each fixed result treatment, within the same
size/repetition block. Missing values remain missing, failures remain in the
attempt count, and unknown accounting is never imputed. `postcheck-runs.json`
retains individual treatment metadata, measurements and oracle outcomes.

The automatic follow-up measure counts distinct tool calls after the first
parseable successful result from a Bash invocation of the assigned rename command.
It cannot separate checks batched inside that invocation. Redirected or mixed
output may make the boundary unobservable; then the measure is null, not zero.
These calls may perform necessary semantic or behavior checks. Review the traces
before calling any of them redundant, and inspect final claims for unsupported
completeness assertions. Native failed-tool counts do not capture false-positive
text checks that exit successfully.

Interpret only these new within-size treatment comparisons. Do not use the old 27
runs as a contemporaneous control or present three repetitions as a reliable
general effect. Provider cache warmth is unobserved; retain native cache counters
and recorded order. Better counts alone are insufficient if correctness,
instruction adherence, independent semantic checking or claim accuracy deteriorates.
