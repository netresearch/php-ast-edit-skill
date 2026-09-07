# Prospective continuation guidance trial

`real-php-guidance-v1` is a new twenty-candidate profile of `real_pilot.py`.
Freeze its source, dependencies, inputs, schedule and this protocol before any
model invocation. The completed thirty-run `real-php-verification-v1` campaign
remains immutable. Its observations motivate this question; they are neither
controls nor additional repetitions in this trial. The controller's original
profile remains the default.

## Question and fixed workload

Does the guidance output bundle reduce unnecessary continuation after a correct,
verified rename while preserving correct edits, tests and accurate final claims?
The primary descriptive comparison is later tool calls, supported by duplicate
final-byte checks and a manual audit of every attempted trace. A lower call count
is beneficial only when task correctness, verification and treatment adherence
remain intact. Do not select a winner from time or tokens alone.

Use the unchanged public extraction in [REAL_FIXTURE.md](REAL_FIXTURE.md): six PHP
files, GPL license and provenance from `netresearch/t3x-nr-llm` commit
`b505c936935b99baa3088ce62ad222d2ba61cee0`. Rename
`SchemaPropertyClassifier::classify` to `controlType` in the extracted workspace.
The hidden oracle expects exactly three method-name identifiers in three files:
the declaration, its extracted production call and its direct test call. It
requires every other byte, including assertions and test inputs, to remain intact.
The only additional allowed file is the frozen initial project configuration.
Candidates receive the task and readable public source, not the expected edit
inventory or oracle implementation. The documented excluded production caller
and absent unrelated same-name runtime control remain limitations of this fixture.
This is one small extracted case, not the full TYPO3 extension runner or a corpus.

The original 17 PHPUnit tests must run on final bytes using the existing checker;
the original suite reports 20 assertions. The baseline also passes, so behavior
tests alone cannot establish that the rename occurred. Retain the existing
exact-byte oracle and all candidate-receipt and independent-behavior conditions
from [REAL_PROTOCOL.md](REAL_PROTOCOL.md) without strengthening their meaning.
In particular, candidate credit requires successful exit, 17 executed tests, the
pinned PHPUnit PHAR and before/after manifests both equal to the final inventory.
The controller snapshots candidate receipts before its own hidden checker runs.
An independent later pass cannot substitute for candidate verification.

## Two arms, ten prospective pairs

| Arm | Frozen rename wrapper | Checker and prompt |
| --- | --- | --- |
| `compact` | `rename_method --evidence` | Existing `ast-integrated` prompt and project checker |
| `guidance` | `rename_method --evidence --guidance` | Identical `ast-integrated` prompt and project checker |

Both arms use the same frozen engine, including the same neutral `NOT_CANONICAL`
warning, resolver, mutation route, configuration and original tests. Prompts and
checker wrappers differ only in isolated absolute paths. Every PHP mutation must
use the assigned rename command; ordinary tools remain available for reads and
checks. The treatment wrapper alone adds `--guidance`. The treatment is the whole
result-presentation bundle, including continuation guidance and AST-derived
syntactic role counts. It does not isolate the effect of a single sentence or
field. Method-call and callable-reference site counts do not count runtime
executions or distinct calling methods. A callable-reference expression is not
necessarily an invocation. Reference completeness remains unknown.
Skill files are not loaded in these isolated candidate processes. This comparison
therefore measures neither the skill-document changes nor the shared warning
change; both arms receive the same engine and explicit candidate instructions.

Use model `claude-haiku-4-5-20251001` in twenty fresh, isolated candidate processes.
Seed `20260910` shuffles ten repetition blocks. Each contains both arms once;
alternating arm order gives each arm five first and five second positions.
Retain this order, all ten within-block comparisons, failures and incomplete
attempts. No reruns, replacement candidates, adaptive prompt changes or borrowing
old campaign observations. Missing values remain unknown; all twenty intended
rows and ten intended pairs remain visible even if execution stops early.

## Freeze and execution limits

Preparation uses the existing controller rather than a copied trial runner:

```sh
python3 benchmarks/symbol-intent/real_pilot.py prepare \
  --experiment real-php-guidance-v1 \
  --output /tmp/php-real-guidance-campaign \
  --source-repo /home/cybot/projects/t3x-nr-llm/main \
  --phpactor /tmp/phpactor-symbol-intent-tools-20260907/phpactor.phar \
  --phpunit /tmp/phpunit-12.5.31.phar
```

Preparation requires committed, clean source and makes no model calls. Before
execution, review the recorded source commit and complete source/dependency
manifest, fixture commit, PHAR hashes, exact model, CLI path/version, PHP/Python
identity, twenty frozen task/prompt/config/wrapper inputs and schedule. Config
and input digests are rechecked during execution. The PHPUnit identity remains
12.5.31 with SHA-256
`194fcb6621866b542f1304e0da8dc7abcb15d6f9d1851893aec40896bcf5bb44`.

Run only the frozen controller with explicit `--execute-models`, after the
prospective design review. The native list-price planning cap is USD 5 total,
USD 0.50 per candidate and 120 seconds per candidate. The forecast is below USD 1
for all twenty, an estimate rather than a promised charge. The controller reserves
the next candidate's USD 0.50 allowance before starting it. Twenty maximum-cost
candidates would exceed the campaign cap, so unusually expensive runs can stop
the campaign before twenty attempts. Do not silently increase the cap or replace
missing runs. Existing capture, accounting, timeout, integrity and unexpected-exit
stops remain active. A started campaign cannot be resumed or replayed.

## Automatic observations and comparison

Reuse existing native accounting for total model tokens, tool calls, model
rounds, native list-price USD and candidate wall time. Preserve raw observations,
known-value counts, medians and paired treatment-minus-control differences.
Checker wall time is observed separately; it is not total AST-tool duration or
candidate duration. Do not sum unrelated or overlapping timing boundaries.
Retain later tool calls as the primary descriptive metric even if both medians
are zero; publish full distributions and paired observations without switching
the primary metric after seeing results.

The guidance profile additionally records:

- `postcheck`: the existing `postcheck_pilot.post_calls` observation. Its boundary
  is the first parseable successful `rename-tool` result. It counts distinct later
  native tool-use IDs and their tool names. Duplicate streamed blocks do not add
  calls. Work batched inside the same shell call is not separated. Missing success
  boundaries, malformed traces or unavailable native accounting give unknown,
  not zero. Summary regeneration recomputes this observation from the raw trace.
- `post_calls`: the corresponding count of later tool calls. It is an observable
  continuation measure, not an automatic label of redundant work.
- `duplicate_final_checks`: successful candidate receipts matching the final
  inventory beyond the first such receipt. Checks on earlier bytes or failed
  checks do not inflate this number. Malformed or incomplete receipt counts give
  unknown. This metric identifies repeated successful checks of final bytes, not
  every possible duplicate check on intermediate states.

The summary records all twenty `planned_rows`, attempted status, `unattempted_ids`
and known coverage for the two additional metrics. The ten prospective pairs
retain null deltas when either observation is unavailable. Unknown costs are not
described as zero cost: the existing sum is explicitly the known native cost.
Keep correctness, hidden behavior, candidate verification and normal completion
as separate outcomes. Report failures and unknown coverage alongside efficiency.

## Prospective manual audit of every trace

Audit all twenty planned rows, marking unattempted or missing traces explicitly.
For every attempted trace, read all tool calls/results and the final text. Retain
tool-use IDs and native line references for each finding. Use the following fixed
rubric in both arms; do not infer semantic errors from native error flags alone.

| Observation | Classification and evidence |
| --- | --- |
| PHP mutation or repair | Assigned AST command; ordinary text mutation (route deviation); or no mutation. Record retries and the preceding failure that required them. |
| Calls after successful rename | Necessary repair or changed-byte verification; scope investigation prompted by unresolved evidence; reconfirmation of an already passed check; other task work; or unclear. Every later call receives a class; one shell call can contain several activities. |
| Readback | Search/grep, diff, full-file read or other inspection. State whether it happened before rename, between write and verification, or after successful rename/check; cite any new uncertainty it resolved. Count call-level and within-shell activities separately. |
| Repeated behavior check | Same byte state already passed; changed bytes requiring a fresh check; retry after failed check; or unknown state. Cross-check receipts, tool chronology and any intervening mutations. |
| Command issue | Invalid invocation, missing path/directory read, actual tool failure, legitimate no-match exit, or unknown. A grep no-match exit 1 is distinct from invalid-option exit 2; native `is_error` alone is not proof of an invalid command. |
| Final completion claim | Supported task completion and tests; explicit unsupported complete-reference claim; explicit inaccurate count/timing claim; or ambiguous. Mere omission of a completeness caveat is not an explicit universal claim. |

For final claims, check declaration versus method-call versus callable-reference
counts, sites versus distinct callers, executed tests versus assertions, the
actual result of required checks, and planning/checker/candidate timing boundaries.
Do not infer test success from parser/lint success, or resolver completeness from
exact replacements, guidance, passed tests or the hidden oracle. Label an explicit
claim that all full-repository references were found unsupported for this extracted
fixture. Preserve direct short evidence for disputed claims and ambiguous labels.
Summarize manual classes separately from automatic later-call counts; do not turn
every post-call into a redundant-call count.

This small paired trial supports a descriptive result for this case. Duplicate
checks were uncommon in the preceding campaign, so twenty attempts may show a
floor effect. Report the observed distribution and failures without extrapolating
to other projects, agents, model versions or a general completeness guarantee.
