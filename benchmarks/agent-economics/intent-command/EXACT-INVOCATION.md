# Prospective exact invocation experiment

This separate experiment follows the completed 18-attempt instruction ablation
and 12-attempt delegation refinement. It neither extends their exhausted protocol
nor pools their observations. Both arms use the same current AST engine revision
after PR #83. Its positional project-path alias is available in both arms; the
prepared invocation uses the existing explicit `--path` option.

## Question and matched information

Does supplying a ready-to-run rename command reduce the model's command
construction, discovery and repair work compared with the same generic delegated
instructions and the same selected target information?

| Arm | Shared information | Additional information |
| --- | --- | --- |
| `delegated_intent` | Existing delegated system instructions and common contract; selected method, declaration file, destination name and project path | None |
| `exact_invocation` | Identical system instructions, common contract and selected metadata | Deterministically shell-quoted complete rename invocation |

The new `exact_tasks.py` wraps the existing two-task manifest without changing its
prompts, files, protected checks, edit references or independent oracles. It adds
only these operator-selected targets, made visible to **both** arms:

| Task | Method | Declaration file | Destination | Project path |
| --- | --- | --- | --- | --- |
| `method-and-literal` | `Product::findByUid` | `Product.php` | `resolveByUid` | `.` |
| `cross-file-rename-clarified` | `Pilot\CrossFile\Contract::fetch` | `src/Contract.php` | `load` | `.` |

Both arms may use the supplied declaration file with `--file`. This narrows
declaration discovery, while the engine still resolves supported project callers.
Only the treatment gets the complete `php-ast-edit rename --method … --to …
--path . --file …` string generated with Python `shlex.join`. Record the metadata,
rendered prompt and system instruction hashes, and the actual candidate argv.
The controller never executes the generated string itself through a shell.

This is a test of command presentation with preselected intent. It does **not**
measure autonomous target selection, include its cost, establish AST savings
against text editing, or isolate an intrinsic engine benefit. It also does not
change the stopping/check repetition instructions or tool/report implementation.

## Freeze, schedule and budget

Two tasks × two arms × six repetitions = **24 attempts**. Use pinned
`claude-haiku-4-5-20251001`, no effort override or fallback, seed `20260915`, and
120 seconds per attempt. Run serially. Balance starting arm within each task/model
block: each arm starts three of the six paired repetitions. These schedule options
are opt-in; the runner's original arms and default three-repetition order remain
unchanged. Freeze protocol, manifest generator, instructions and controller in a
signed source commit before preparation or paid calls.

The campaign planning ceiling is **USD 3**, with the existing USD 0.75 reservation
only for the next imminent attempt, replaced by its actual native cost afterward.
Use the existing frozen runtime, empty skills/plugins/MCP settings, fresh private
workspaces, serial lock and native usage accounting. Record Claude CLI and PHP
versions, source/runtime/controller/task hashes and the pinned Phpactor digest.
Provider-side cache state remains unknown. Do not run competing tests during
candidate wall-time measurement.

Before execution, offline tests must verify both exact commands pass the independent
oracles, initial fixtures fail, protected-file mutations fail, shell quoting is safe,
both arms get identical target knowledge, and defaults remain unchanged. Independent
design review is required before paid calls. Record the review in operator provenance.

Retain **every attempted candidate**, including failure, refusal and timeout. Never
rerun or replace an attempted candidate. Stop for missing accounting, unexpected
model, timeout, isolation mismatch or budget violation. There is **no refinement**
or additional-attempt allowance under this protocol.

## Outcomes and interpretation

The primary criterion is at least **15% lower median total tokens** with **no higher
median wall time on both tasks**, and all quality gates passing in both arms.
Quality requires the independent final oracle, actual successful candidate checks,
the intended AST write route, and supported completion claims. Instruction adherence
is a separate observation, not a substitute for code correctness. A safe refusal
does not complete the task. Mixed task effects do not constitute an overall win.

Publish all native token categories (fresh input, cache creation, cache read, output),
their total, native cost, visible model rounds, tool calls/failures and candidate wall
time. Thinking is part of output where reported. Show paired per-repetition ratios
as well as cell medians, all-attempt denominators and quality failures. Six pairs
per task remain exploratory; do not turn these into a universal savings percentage.
Tool execution time stays unknown without complete interval coverage.

Audit pre-write PHP reads, exact-command adoption and actual arguments, invocation
errors, queued family renames, post-write reads and repeated checks, report evidence
and completion claims. Do not attribute a mechanism to a command the model did not
use. Publish only these synthetic fixtures and allowlisted candidate evidence.

## Commands

```bash
python3 benchmarks/agent-economics/intent-command/exact_tasks.py --output /tmp/exact-invocation-tasks.json
PHP_AST_PILOT_ARTIFACT="$PWD/bin/php-ast-edit" PHP_AST_PILOT_PHPACTOR=<PINNED_PHPACTOR> \
  python3 -m unittest discover -s benchmarks/agent-economics/intent-command -p 'test_*.py'
python3 benchmarks/agent-economics/efficiency/test_harness.py
python3 benchmarks/agent-economics/efficiency/runner.py prepare \
  --source "$PWD" --source-ref <FROZEN_COMMIT> --vendor <PINNED_VENDOR> \
  --manifest /tmp/exact-invocation-tasks.json \
  --tasks method-and-literal,cross-file-rename-clarified \
  --arms delegated_intent,exact_invocation --models haiku --seed 20260915 \
  --repetitions 6 --balance-by-task --campaign-budget-usd 3 \
  --output /tmp/php-ast-exact-invocation-campaign-20260911
PHP_AST_EDIT_PHPACTOR=/tmp/php-ast-exact-invocation-campaign-20260911/runtime/vendor/phpactor.phar \
python3 /tmp/php-ast-exact-invocation-campaign-20260911/controller/efficiency/runner.py \
  run --output /tmp/php-ast-exact-invocation-campaign-20260911 --execute-models
python3 benchmarks/agent-economics/intent-command/summarize.py \
  /tmp/php-ast-exact-invocation-campaign-20260911
```
