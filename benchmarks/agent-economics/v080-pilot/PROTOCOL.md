# PHP AST Edit v0.8.0: Haiku workflow pilot

Prospective protocol, 2026-09-11. This is a new experiment. It neither replaces nor
reconstructs the unavailable historical `skill-invocation/powered` campaign.

## Question and design

Where does the released PHP AST Edit workflow reduce agent work compared with
competent ordinary contextual editing, while completing the same task correctly?

Four original, self-contained tasks cover a small edit, three changes in one file,
a method rename across an interface/class hierarchy and typed call sites, and a
rename surrounded by confusable variable/property/method/string occurrences.
The generated task manifest records the exact prompts, initial bytes, reference
edits and separate outcome oracles. No private or third-party source is needed.

Each task has two assigned arms and three repetitions: **24 candidate processes**.
Use only `claude-haiku-4-5-20251001`, without an effort flag or inherited effort
override, and record the installed Claude CLI version. No model fallback is set.
The existing efficiency harness randomizes blocks and balances arm starts using
seed `20260911`. Run candidates serially in fresh Git workspaces and processes.

| Arm | Editing instructions | Checks and input |
| --- | --- | --- |
| `contextual_patch` | Competent ordinary Edit/patch, normal reads and batching | Same source, project configuration, executable check and task prompt |
| `full_skill` | Complete released SKILL.md, named selectors and CLI on PATH | Same source, project configuration, executable check and task prompt |

Both arms can read normally and bundle operations. Both must preserve unrelated
code and make `php check.php` pass. Both receive the same project check declaration;
the AST engine can execute it within apply. This compares complete write workflows,
including integrated verification, rather than attributing every difference to
AST parsing alone. The full skill's extra context is included in measured tokens.

For the unmodified release harness these support files are explicitly included in
each external task's `files`, with `preserve_source: true`; they are not supplied by
the harness's separate check-arm injector. Every task uses the identical clause
``Make sure `php check.php` still passes.`` and prohibits background processes. Before
preparation, validate unique task IDs and file paths, safe relative paths and the
`changed` outcome. Exercise the release runner's exact-template and Git fixture
materialization path, then its grader, with the pinned resolver and task-specific
falsification checks. The older generic self-test does not support this raw fixture
path or initialize the Git index required for project-wide rename resolution.

Runtime, skill and original controller source are frozen at release commit
`092bf2fe362d8539105d11094be72703fee2bbf6`. Record the protocol/task commit separately,
and retain all frozen hashes, manifest, dependency identity, prompts and schedule.
Use the production-only `vendor` tree extracted from the verified released PHAR,
whose SHA-256 is
`a0e51d92b7a509cd79705a59b5c94f8d62802b41c0ae0beec65621470ec0385e`.
The harness executes the source CLI at the same release commit, with its passive
engine recorder; it does not execute the PHAR packaging layer during candidate runs.
Recorder overhead is part of observed AST-arm wall time and is not subtracted.
The optional Phpactor resolver is 2026.07.22.0, SHA-256
`8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d`.
Its identity is checked before and after the campaign; the engine also enforces
its pinned digest. Report preparation time separately from candidate wall time.

## Correctness before economics

The common candidate-facing check validates syntax and maintained behavior.
Independent hidden oracles require the requested changes, preserved decoys and
complete file scope. Their checksums protect the shared checker and configuration
against edits that could make the task appear complete. Before any model starts,
every original fixture must fail its task-completion oracle, a correct reference
solution must pass, and representative partial/collateral edits must fail.
Fixtures and oracles have no filesystem side effects. Review the final post-oracle
hashes, file scope and Git status as well: the legacy grader enumerates initial
scope before it executes candidate PHP, so its scope flag alone is insufficient.

For every attempted run retain its original trace, result, diff, initial/final
hashes, exit status, oracle output and assigned arm. Review final diffs and native
tool traces. A native success result, valid PHP or passing project check alone is
insufficient. Failed attempts remain in the ledger and consume their observed cost.

## Measurements and interpretation

Report by task and arm: completed/attempted, fresh input tokens, output tokens,
cache-read and cache-write tokens, total tokens including cache, visible model
rounds, native turns, tool calls, failed tool calls, candidate wall time, native
list-price estimate and changed lines. Cache state is unknown; a fresh process is
not evidence of a cold provider cache. List-price estimates are not invoices.

The native collector checks model identity, isolated initialization, deduplicated
response IDs and agreement between terminal and model-usage counters. Missing
usage remains unknown. Tool execution time is reported only when actual native
intervals cover all tools; partial observations stay separate. Do not derive it
by subtracting API duration from wall time.
When a documented native retry leaves missing visible response input, visible
rounds are a lower bound and `primary_model_rounds_exact` remains false. An
unexpected assistant model is an accounting failure, not an excluded cheap run.

Report repair behavior separately: native error-marked tool results, failed shell
or apply exits visible in successful Bash envelopes, and subsequent corrective
attempts linked by run and tool-call IDs. These are distinct measures. Rechecking
after a correct edit is verification overhead, not automatically a repair.
The offline extractor validates present native error flags as booleans; missing
flags mean unmarked, not a shell exit verdict. It emits an ordered per-call review
queue. The reviewer records a repair only when a later mutation addresses the
specific earlier failure, with both call IDs and a reason; ambiguous linkage is
unknown. Flag-form proxy JSON capture errors are instrumentation limitations when
the unchanged forwarded command succeeds, not candidate failures. The new summary
reads this campaign directly; the historical check-arm summarizer is not used.

Use descriptive medians and per-run values. Three repetitions per cell do not
support general savings claims or a winner selected from many p-values. Show all
attempts and successful-run metrics separately, with missing values and failures
visible. Report protocol deviations rather than removing inconvenient runs.

After the pilot, a task is a candidate for an independently scheduled follow-up if
both arms complete all three attempts and AST lowers the median total tokens by
at least 15% without a higher median wall time, or if traces identify a concrete,
repairable interface problem. Any changed treatment gets a new frozen identity;
earlier outcomes remain immutable. Follow-up conclusions are separate from the
exploratory choice of task or improvement.

## Limits, stopping and evidence

Use the existing 120-second deadline and USD 0.75 per-run native planning cap, with
a shared USD 8 campaign planning allowance. Reserve the next full run allowance
before starting. Unknown usage, unexpected models, isolation mismatch, timeouts
or cap violations stop further calls for offline review. No automatic rerun or
discarding of a failed attempt. These controls do not establish a billing guarantee.
The schedule may therefore stop before all 24 planned candidates. Retain and report
planned, attempted and completed counts. Audit traces for background commands and
out-of-workspace access, and inspect for surviving campaign processes before a
subsequent campaign; the unmodified controller only kills descendants on timeout.

Before execution, validate the frozen files and receive an independent review of
the protocol and fixture oracles. The user has authorized this inexpensive-model
experiment. No new release or model upgrade is part of this campaign.

Retain results under a new campaign directory, then publish reviewed, allowlisted
evidence and a reproducible report. Never archive authentication stores, home
configuration or unrelated sessions. Candidate-facing tests are original fixture
code; hidden answers stay outside the candidate workspace. The local harness is
not an adversarial operating-system sandbox.

## Reproducing the pilot

Check out the protocol/task commit recorded in `operator-provenance.json`, install
the released runtime dependencies, and supply the pinned Phpactor PHAR through
`PHP_AST_EDIT_PHPACTOR`. The fixture preflight also uses the released engine PHAR;
set `PHP_AST_PILOT_ARTIFACT` and `PHP_AST_PILOT_PHPACTOR` to override its defaults
(`/tmp/php-ast-release-download-20260911/php-ast-edit.phar` and
`/tmp/phpactor-release-20260911.phar`). If either PHAR is unavailable, the released
fixture test is intentionally skipped; that skip is reported by unittest and does
not claim that the fixture oracle ran. Run the offline fixture and reporter tests first:

```bash
python3 -m unittest discover -s benchmarks/agent-economics/v080-pilot -p 'test_*.py'
python3 benchmarks/agent-economics/v080-pilot/tasks.py --output /tmp/v080-tasks.json
```

Use the release's `efficiency/runner.py prepare` with `--source-ref` set to the
release commit above, `--manifest /tmp/v080-tasks.json`, `--models haiku`,
`--arms contextual_patch,full_skill`,
`--tasks simple-edit,same-file-batch,cross-file-rename,confusable-rename`,
`--seed 20260911`, and `--campaign-budget-usd 8`. Supply the production vendor tree
with `--vendor` and choose a fresh direct child of `/tmp` as `--output`.
Preparation is offline. Validate the frozen campaign before explicitly executing
`runner.py run --output CAMPAIGN --execute-models` under the same resolver setting.
The latter command invokes paid-model services under the operator's authentication.
Run `summarize.py CAMPAIGN` afterward; its JSON includes every scheduled slot and
the tool-call queue for the separate correctness and repair review.

## Failure modes considered before execution

| Failure mode | Control |
| --- | --- |
| Wrong model or inherited instructions | Exact native model and empty skill/plugin/MCP checks; no fallback |
| Different starting source or checks | Shared templates and checksum identity across arms |
| Skill help cost omitted | Complete unchanged skill and native input accounting |
| Candidate changes the checker | Hidden checksum and file-scope oracle |
| Partial rename passes behavior test | Separate declaration/caller/decoy outcome assertions |
| Unrelated strings or receivers change | Explicit preserved-value and unchanged-source assertions |
| Repeated run replaces a failure | Exclusive raw output creation and immutable attempt IDs |
| Native Bash envelope hides failed command | Review engine audit and command result beside native error flag |
| Missing counters become zero | Collector rejects incomplete accounting and stops |
| Cache advantage masquerades as universal saving | Separate cache counters and unknown-cache qualification |
| Timeout obscures cost | Retain unknown cost and halt for individual review |
| Concurrent load or state contaminates timing | Serial processes, fresh workspaces and campaign lock |
| Evaluation rules change after results | Commit/freeze protocol and task manifest before execution |
| Premature completion or overstated conclusions | Independent diff/oracle review, complete ledger, exploratory report |
