# Powered round — protocol

Fixed before the first run. Anything changed after that is reported as a deviation, with
its reason, beside the result.

## Question

Is the gated skill cheaper than no skill on a TYPO3 extension, measured in turns, dollars
and wall time? The earlier rounds ran n = 8 per arm, and REPORT.md documents a drift of
3.5 turns in the median between two identical rounds an hour apart. A difference of one
or two turns cannot be seen at that size; this round is sized to see it, and it
interleaves the arms so drift lands on both.

## What is fixed

- Subject: `netresearch/t3x-nr-passkeys-be`
- Subject commit: `31275da4f846f77aba0e750b716e68647edbb818` — the extension's own
  `.php-ast-edit.json` declares PHPStan with `scope: project` and the php-cs-fixer formatter
- Tool commit: `622ecfcae188787b3599e405bdf0186340a70cc8` — main after #64 (`alreadyRun`) and #66 (project-wide `rename_method`)
- Resolver: Phpactor 2026.07.22.0, sha256 `8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d`,
  exported as `PHP_AST_EDIT_PHPACTOR` to both arms
- Model: `claude-haiku-4-5-20251001`, via `claude -p --output-format json`; the CLI
  version is recorded before every run (`out/<id>.version`)
- Harness: `run.sh` at the tool commit — fresh detached worktree per run, dependencies
  hardlinked with a real copy of `vendor/composer`, isolated configuration directory

## Arms

- `free`: credentials and a minimal `settings.json`, no skill, no hook. The engine is on
  PATH, as in every earlier round.
- `gate`: the same plus `skills/php-structured-edit` and the PreToolUse hook
  `hooks/php-ast-only.py`, both from the tool commit.

## Tasks

- **C** (`task-C.txt`): three changes in `Classes/Service/RateLimiterService.php` —
  rename a private method and its calls, add a private method and use it in
  `resetLockout()`, set a docblock — with the project's static analysis passing.
  Oracle `oracle-C.sh`.
- **D** (`task-D.txt`): rename the public method
  `ExtensionConfigurationService::getConfiguration()` to `configuration()`, with its 29
  calls in 12 files, and nothing else. Oracle `oracle-D.sh`: the declaration renamed, no
  `->getConfiguration(` left, exactly 29 `->configuration(`, only those 12 files changed,
  no new files. Checked before this round against an untouched tree (fails) and a tree
  renamed by the engine (passes).

## Size and order

N = 30 runs per task and arm, 120 runs, sequential — parallel runs would disturb wall
time, which is one of the measures. Round `i` runs both tasks; the task order flips every
round, and within a task the arm that goes first flips every round, in opposite phase for
C and D (`drive.sh`). No interim analysis and no early stop.

## Measures and test

Per task, three measures from the result JSON: `num_turns`, `total_cost_usd`,
`duration_ms`. For each, the hypothesis is that `gate` is lower than `free`: one-sided
Mann-Whitney U (normal approximation with tie correction and continuity correction). The
six p-values (2 tasks × 3 measures) are held to Holm's procedure at a family-wise 0.05.
Reported beside each: both medians, the Hodges-Lehmann shift, and a bootstrap 95%
interval for the difference of medians (10,000 draws, seed 20260910). `analyze.py`
implements exactly this; `analyze.py --self-test` checks the approximation against exact
enumeration.

## Exclusions

A run is excluded, and counted by reason, when its exit status is not 0, its result is
unreadable or an error, or its oracle fails. Excluded runs are not replaced. If more than
10% of an arm's runs on a task are excluded, that task's comparison is reported as
inconclusive whatever its p-values say: a cheap arm that fails more often is not cheap.

## What would count as the answer

"Nachweislich günstiger" on a task means Holm rejects for that task on turns or dollars,
with wall time not significantly worse (two-sided 0.05, reported). Anything else is
reported as measured, including a result in the other direction.
