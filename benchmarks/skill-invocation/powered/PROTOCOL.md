# Powered round — protocol

## Historical protocol frozen on 2026-09-10

The following is the original round-2 plan from branch `bench/powered-round` at
`b51b196`. Its statements about execution are historical operator reports, not a
newly verified result. The [2026-09-11 reconciliation](#reconciliation-2026-09-11)
records the available evidence and subsequent harness corrections.

Fixed before the first run. Anything changed after that is reported as a deviation, with
its reason, beside the result.

### Question

Is the gated skill cheaper than no skill on a TYPO3 extension, measured in turns, dollars
and wall time? The earlier rounds ran n = 8 per arm, and REPORT.md documents a drift of
3.5 turns in the median between two identical rounds an hour apart. A difference of one
or two turns cannot be seen at that size; this round is sized to see it, and it
interleaves the arms so drift lands on both.

### What is fixed

- Subject: `netresearch/t3x-nr-passkeys-be`
- Subject commit: `31275da4f846f77aba0e750b716e68647edbb818` — the extension's own
  `.php-ast-edit.json` declares PHPStan with `scope: project` and the php-cs-fixer formatter
- Tool commit: `faaea34e994e17cf2bd907727bc69a413bc130fe` — main after #64 (`alreadyRun`), #66 (project-wide `rename_method`) and #68 (string literals of a renamed method listed); round 1 ran on `622ecfc`, see Deviations
- Resolver: Phpactor 2026.07.22.0, sha256 `8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d`,
  exported as `PHP_AST_EDIT_PHPACTOR` to both arms
- Model: `claude-haiku-4-5-20251001`, via `claude -p --output-format json`; the CLI
  version is recorded before every run (`out/<id>.version`)
- Harness: `run.sh` at the tool commit — fresh detached worktree per run, dependencies
  hardlinked with a real copy of `vendor/composer`, isolated configuration directory

### Arms

- `free`: credentials and a minimal `settings.json`, no skill, no hook. The engine is on
  PATH, as in every earlier round.
- `gate`: the same plus `skills/php-structured-edit` and the PreToolUse hook
  `hooks/php-ast-only.py`, both from the tool commit.

### Tasks

- **C** (`task-C.txt`): three changes in `Classes/Service/RateLimiterService.php` —
  rename a private method and its calls, add a private method and use it in
  `resetLockout()`, set a docblock — with the project's static analysis passing.
  Oracle `oracle-C.sh`: the three changes by shape, and the project's unit suite passes.
- **D** (`task-D.txt`): rename the public method
  `ExtensionConfigurationService::getConfiguration()` to `configuration()`, with its 29
  calls in 12 files, and nothing else. Nine more test files name the method in PHPUnit
  mocks (`->method('getConfiguration')`, 67 literals). Oracle `oracle-D.sh`: the
  declaration renamed, no `->getConfiguration(` left, exactly 29 `->configuration(`, only
  PHP files under `Classes/` and `Tests/` changed, no new files, and the unit suite
  (`phpunit -c Build/phpunit.xml --testsuite unit`) passes. Validated as listed under
  Deviations.

### Size and order

N = 30 runs per task and arm, 120 runs, sequential — parallel runs would disturb wall
time, which is one of the measures. Round `i` runs both tasks; the task order flips every
round, and within a task the arm that goes first flips every round, in opposite phase for
C and D (`drive.sh`). No interim analysis and no early stop.

### Measures and test

Per task, three measures from the result JSON: `num_turns`, `total_cost_usd`,
`duration_ms`. For each, the hypothesis is that `gate` is lower than `free`: one-sided
Mann-Whitney U (normal approximation with tie correction and continuity correction). The
six p-values (2 tasks × 3 measures) are held to Holm's procedure at a family-wise 0.05.
Reported beside each: both medians, the Hodges-Lehmann shift, and a bootstrap 95%
interval for the difference of medians (10,000 draws, seed 20260910). `analyze.py`
implements exactly this; `analyze.py --self-test` checks the approximation against exact
enumeration.

### Exclusions

A run is excluded, and counted by reason, when its exit status is not 0, its result is
unreadable or an error, or its oracle fails. Excluded runs are not replaced. If more than
10% of an arm's runs on a task are excluded, that task's comparison is reported as
inconclusive whatever its p-values say: a cheap arm that fails more often is not cheap.

### What would count as the answer

"Nachweislich günstiger" on a task means Holm rejects for that task on turns or dollars,
with wall time not significantly worse (two-sided 0.05, reported). Anything else is
reported as measured, including a result in the other direction.

### Deviations

#### Round 1 stopped after 16 of 120 runs, 2026-09-10

The first round started at 12:32 against tool commit `622ecfc` and was stopped at 13:11
during run D05-gate. Its 16 complete runs (C01–C05 and D01–D04, both arms) and the
interrupted one are kept outside the repository as `powered-aborted-1`. No analysis uses
them.

**Why.** Oracle D was wrong. It allowed only the twelve files with calls, but nine test
files name the method as a string in PHPUnit mocks. A rename that leaves those strings
fails 174 of the project's 682 unit tests. The oracle therefore failed five runs that
renamed the mocks as well, and passed three that left them. Before the round it had been
checked against an engine-renamed tree, and that tree was itself incomplete: the tool
under test neither renamed the mock strings nor reported them. #68 fixes that gap. The
rename now lists such literals under `renames.literals`, with the selector that one
`replace_expression` takes to set them.

**Seen before the stop:** exit statuses, oracle outcomes and diffs, plus one turn count
(C01) that appeared in a progress line. No measure was compared between arms.

**Changed for round 2:**

- `oracle-D.sh` accepts changes to any PHP file under `Classes/` and `Tests/` and
  requires the unit suite to pass; its shape checks stay.
- `oracle-C.sh` requires the same unit suite, so both tasks share one definition of
  correct.
- The tool commit is main after #68.

Tasks, prompts, N, order and analysis are unchanged, and the prompts do not mention the
tests. A rename that breaks the project's own tests was wrong whether or not the prompt
named them.

**Revised oracles, validated before round 2** on the subject at `31275da`, one tree at a
time. The old D oracle's outcome is given beside each round-1 run; the C oracle had
passed all ten.

| Tree | Revised oracle | Old oracle |
| --- | --- | --- |
| untouched (D, C) | fails, fails | — |
| engine rename of the 29 calls only | fails | passed |
| engine rename plus the listed mock literals | passes | — |
| D01-free, D01-gate, D04-gate (mocks left) | fail | passed |
| D02-free, D02-gate, D03-free, D03-gate, D04-free | pass | failed |
| C01–C05, both arms | pass | passed |

## Reconciliation, 2026-09-11

The remote branch supplies a protocol and executable harness, **not a published
120-run result**. No raw powered-round outputs were found in the available local
project checkouts, WSL temporary directories, or GitHub artifacts. Its five commits
attribute the work to host `32116e` and
[this Claude session](https://claude.ai/code/session_01ChkDsp64UiozGQdWhsU4sp), while
the local recovery search ran on host `bigone`. Round 2's execution/completion status
therefore remains **unknown**. Missing artifacts do not mean that zero runs occurred.

The historical round-1 account is internally inconsistent: it says 16 completed
runs, while C01–C05 and D01–D04 in both arms describe 18. The original wording and
table above are retained; neither count is adopted as verified without the native
records. `powered-aborted-1` and any round-2 artifacts must remain separate, including
failed and interrupted attempts. See [recovery and export instructions](README.md).

Review of the original harness found six defects, corrected after the freeze:

- The analyzer discovered only existing `.status` files. Missing planned attempts
  disappeared from the denominator, and it could analyze an unfinished campaign.
  It now emits all 120 prospective slots, including unknown status, oracle and
  metric fields. A `done` marker, all 120 readable statuses, and no unplanned
  candidate artifacts are required before computing aggregate metrics or inference.
- The protocol's greater-than-10% exclusion rule was not implemented. A task with
  four or more excluded candidates in either 30-run arm now has the decision
  `inconclusive_exclusions`, regardless of its p-values. Exactly three is 10%.
  Valid counters from failed candidates remain in the ledger; success-conditioned
  comparisons use only accepted candidates, as the historical plan specified.
- The required two-sided wall-time test was absent. The report now includes the
  tie- and continuity-corrected normal test and refuses a lower-cost conclusion
  when the rank statistic favors slower gated runs and two-sided p < 0.05; equal
  medians do not conceal that direction. Holm always covers
  six hypotheses; an unavailable comparison cannot shrink that family.
- Repeating the driver could overwrite outputs and delete prior worktrees. Setup
  now requires a new campaign path, and run refuses an existing `out` or `work`.
  Exclusive output-directory creation prevents concurrent starts. A driver failure
  stops the campaign with its first attempt preserved; there is no implicit resume.
- The driver's plain `git diff` omitted staged changes before deleting the candidate
  worktree. It now captures the final tracked diff against the frozen subject commit,
  including staged or committed edits, plus the NUL-separated names of untracked,
  nonignored files. Untracked contents and ignored files remain outside that record;
  missing historical evidence is not reconstructed.
- Setup interpolated the executable path into both JSON and a shell command without
  escaping. It now encodes valid JSON and shell-quotes the hook path independently,
  so checkout paths containing spaces or quotes preserve the intended command.

These changes do not retroactively change the original tool commit, subject,
prompts, sample size, order or recorded outcomes. Synthetic offline unit fixtures
test the harness; they are not model runs or benchmark results. The original source
remains accessible at commit `b51b196`. Any future execution of the revised driver
needs its own recorded harness revision and a fresh campaign directory, and must
not be presented as completion of unavailable historical attempts.
