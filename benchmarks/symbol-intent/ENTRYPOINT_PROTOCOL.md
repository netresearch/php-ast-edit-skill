# Prospective intent-entrypoint trial

## Question and scope

Does a short capability contract, visible before the first edit, reduce model-led
preparation for an explicitly named semantic rename without losing correct edits,
required final-byte tests or honest scope reporting? This tests the prototype's
instruction contract, not a new AST operation or the installed skill.

Consulted lessons before acting: the separate completed guidance trial found no
median continuation gain and recorded 14 control versus 28 treatment calls before
the differing output. That variation cannot be caused by unseen result guidance.
The current prompt already supplies the exact target file, selector, new name and
command. An additional source or AST view would add information and possibly a
call to a task that already has those inputs. Earlier focused-source experiments
had mixed outcomes; their byte-size comparisons are not token measurements.
Anthropic's [tool-design guidance](https://www.anthropic.com/engineering/writing-tools-for-agents)
recommends evaluating clear tool descriptions and checking held-out tasks against
overfitting. It supplies a design rationale, not evidence that this change saves.

Use the unchanged public six-file extraction from [REAL_FIXTURE.md](REAL_FIXTURE.md),
upstream `netresearch/t3x-nr-llm` commit
`b505c936935b99baa3088ce62ad222d2ba61cee0`. The requested change remains
`SchemaPropertyClassifier::classify` to `controlType`, preserving all other bytes.
The hidden oracle requires three identifier edits in three files. Both arms must
execute all 17 original PHPUnit tests on final bytes; the suite has 20 assertions.
Retain the exact-byte oracle, independent behavior outcome and separate candidate
receipt requirements of [REAL_PROTOCOL.md](REAL_PROTOCOL.md). Passing baseline tests
does not prove the requested rename occurred. The excluded TYPO3 UI caller and
absent independent same-name runtime control remain fixture limitations.

## Frozen comparison

Experiment `real-php-entrypoint-v1`: twenty fresh Haiku processes, ten prospective
pairs, seed `20260911`, alternating arm order within shuffled repetition blocks.

| Arm | Instruction | Rename result and verification |
| --- | --- | --- |
| `compact` | Existing AST/integrated system and task prompts | `--evidence`, integrated checker |
| `intent-first` | Identical prompts plus the paragraph below at the end of the task prompt | Identical `--evidence`, integrated checker |

The complete treatment paragraph is:

> For an explicitly named rename, the command accepts the intended symbol change,
> not precomputed call sites or replacement text. You may invoke it directly without
> reading source solely to locate edit coordinates. Use reads when needed to resolve
> task ambiguity or assess unsupported references. Reference completeness remains
> unknown; the verification requirements above still apply.

Both arms use the same engine, resolver, configuration, fixture, command arguments,
compact output and required tests. No `--guidance`, added source facts, AST outline,
expected edit inventory, receipt contents or new tools are supplied to treatment.
Skill files are not loaded. Read access is available equally; the contract permits
direct invocation, it does not prohibit useful inspection or waive scope assessment.
This contract belongs to the experimental project-aware resolver route, not the
installed CLI's conservative same-file `rename_method` operation.

Reuse the existing frozen controller and safeguards. Prepare from committed clean
source, record full source/dependency/input manifests and pinned PHARs, and validate
these around every candidate. Run only the archived controller with
`run --execute-models`. Use model `claude-haiku-4-5-20251001`, record exact CLI/runtime
identities, and retain the same isolated Bash/Read/Edit/Write tool access and native
stream capture. Native list-price planning cap: USD 5 total, USD 0.50 per candidate,
120 seconds per candidate; forecast below USD 1. Reserve the next candidate allowance
before starting. Keep all twenty planned rows and ten pairs if a stop occurs. No
resume, reruns, replacement candidates, adaptive prompting or pooled earlier controls.

```bash
python3 benchmarks/symbol-intent/real_pilot.py prepare \
  --experiment real-php-entrypoint-v1 --output /tmp/php-entrypoint-campaign \
  --source-repo /home/cybot/projects/t3x-nr-llm/main \
  --phpactor /tmp/phpactor-symbol-intent-tools-20260907/phpactor.phar \
  --phpunit /tmp/phpunit-12.5.31.phar
python3 /tmp/php-entrypoint-campaign/source/benchmarks/symbol-intent/real_pilot.py run \
  --output /tmp/php-entrypoint-campaign --execute-models
```

## Observations and decision fixed before execution

Primary descriptive observation: distinct native tool-use IDs before the first
assigned rename invocation, `pre_calls`. The boundary is the first Bash tool-use
whose shell command begins with the exact assigned rename executable as a shell
word. Quoted executable paths work; merely echoing or reading a command path does
not count. Complex shell prefixes, pipelines and compound commands are not silently
interpreted: observation is unknown if an unsupported command mentions the assigned
executable. Read all traces to identify batching, retries and any unsupported forms.
Within-shell work is not split into separate calls. Native event order does not
establish wall-clock execution order of parallel tool calls. Calls in the same
assistant event as the first rename are counted separately as concurrent/peer
calls, not pre-calls. Repeated streamed tool blocks count once; conflicting IDs,
malformed structure, orphan results or unavailable native accounting yield unknown.
A first failed rename still establishes the invocation boundary; retries and their
preceding failures are reviewed separately. A missing invocation is unknown, not zero.

The recorded observation includes first-call ID/event, preceding and same-event
call IDs/tool names, and subsequent invocation IDs. These are deterministic trace
observations, not automatic judgments that initial reads were unnecessary.
Retain the existing successful-result later-call boundary and duplicate successful
final-byte receipt metric. Regenerate pre/post call observations from native traces;
rederive duplicate-final-check counts from archived candidate receipts and final
inventories in the offline evidence verifier.
Whole-call token categories, calls, visible model rounds, native list-price cost,
candidate wall time, checker duration and all correctness outcomes remain separate.
Unknown total tool duration remains null; do not subtract unrelated counters.

Publish complete distributions, known-value coverage and all ten paired deltas,
including failures and nulls. Keep `pre_calls` primary even with a zero-median floor.
For an instruction adoption recommendation on this task, require all twenty normal,
correct, candidate-verified completions, complete primary/token/time observations
for all twenty runs and all ten pairs, no route/verification regressions, no greater
number of explicit unsupported final claims, a difference of arm medians
`median(compact pre_calls) - median(intent-first pre_calls) >= 1`, fewer pre-calls
in at least six of ten pairs,
and no increase in total-token or candidate-wall-time medians. These are a conservative
engineering decision rule, not a statistical significance test. Otherwise retain the
current entrypoint and publish the negative/inconclusive result. Even a passing
result requires a separately frozen held-out task before claiming broad benefit.
Do not add the treatment to the installed skill based on this selected rename.

Apply the complete manual trace rubric from [GUIDANCE_PROTOCOL.md](GUIDANCE_PROTOCOL.md)
to every attempted call/result and final answer, with tool IDs and native physical
line references. Additionally classify every initial call as source context/scope
work, coordinate discovery, command repair, other task work or unclear. Do not label
all initial reads redundant. Check final claims against declaration/reference roles,
named executed tests and unknown resolver completeness. Audit candidate receipts
before/after against final inventories independently of hidden-check outcomes.

## Failure anticipation and execution contract

| Failure mode | Mitigation / acceptance |
| --- | --- |
| Task/role drift | Only the explicit paragraph differs; review exact prompt and wrapper bytes before execution. |
| Dropped verification | Unchanged 17-test obligation, exact oracle and final-byte candidate receipts gate adoption. |
| Step repetition | Existing start marker and immutable campaigns forbid reruns; no reward for repeated checks. |
| Lost history / conversation reset | This protocol, frozen source and configuration define the run independently of chat history. |
| Missing termination rule | Twenty planned attempts, budget/time stops and the prospective adoption rule are fixed. |
| Unclear authorization | User already authorized model experiments, public OSS evidence, reviewed fixes and green merges; no new approval gate. |
| Task derailment | No new MCP server, AST view, production API, release or unrelated repository change in this trial. |
| Withheld/ignored evidence | Publish all raw traces/pairs and independent review findings, including nulls and negatives. |
| Reasoning/action mismatch | Verify actual calls, changed bytes and receipts rather than accepting final prose or exit zero alone. |
| Premature completion / incomplete verification | D01–D04 below require concrete evidence; a correct diff alone does not finish the trial. |
| Incorrect verification | Independent plan/code/data review, observer negative controls and archived offline reproduction. |
| Temporal or provider noise | Balanced order and paired reporting; no causal claim from pre-output imbalance or uncontrolled caches. |
| Observer falsely treats printed command as execution | Exact executable-word recognition, ambiguous-shell unknowns and manual audit of all traces. |
| Fixture overfitting | Selected single-task scope explicit; earlier campaigns separate; held-out validation needed before promotion. |
| Public evidence omits attribution / exposes private data | Explicit export scope, frozen code/document licenses, hashes, independent archive review. |

D01: implement only this profile/contract and a fail-closed invocation observer;
meaningful tests must reject malformed, duplicate-conflicting, missing and unsupported
boundaries while preserving old profiles. D02: freeze and independently inspect all
inputs, then execute once within fixed limits. D03: verify and publish every outcome,
full trace audit, all paired observations and licensed offline evidence; apply the
predeclared decision rule without changing the measured source. D04: independent
review, fix valid findings, pass required CI, merge the reviewed commit and verify
remote/local main and archive checksums. No release/tag or memory update is included.
