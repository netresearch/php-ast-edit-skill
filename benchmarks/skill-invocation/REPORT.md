# What it costs to reach for the tool

Haiku 4.5, isolated configurations, a real TYPO3 extension that declares both a
`formatter` and a `verify` command. Method in [README.md](README.md).

As of 2026-09-10 the gate wins on a single rename (p = 0.0034). On a task with three
changes in one file it lost (p = 0.0012) to refused `apply` calls — 54 of 98 — and after
the engine took the edits those refusals were attempting, it is at parity: 14.5 to 17.0
turns against 13.0 without the skill, no longer measurably different in either direction.

Read the confound section first. Every number taken before 2026-09-09 was measured
against a subject whose own static analyser was broken by the measurement, and the
`checksPassed` figures from that period say nothing about the tool.

## The measurement broke its own subject

While every arm shared one `.Build` directory by symlink, an arm ran
`composer dump-autoload`. That rewrote the *subject's* autoloader to name that arm's
working directory as its root package, and the next run deleted that directory:

```
.Build/vendor/composer/autoload_files.php
$baseDir = dirname(dirname(dirname(dirname(dirname($vendorDir))))).'/bench/work/B1-free';
```

TYPO3's `autoload-include.php` and `alias-loader-include.php` are listed under that
`$baseDir`, so they became unloadable. PHPStan then lost reflection for the extension's
own classes and reported 66 errors of the shape

```
Method …\EnforcementLevel::severity() should return int but return statement is missing.
```

against a body that reads `return match ($this) { … };`. It reproduced with the PHPStan
extensions disabled, with `parallel.maximumNumberOfProcesses: 1`, and on a cold result
cache; it disappeared when the analyser ran from a different working directory, which
left the autoloader as the only variable. `composer install` in the subject took it from
66 to 0.

That is why 17 of 27 `apply` calls in the gated arms came back `checksPassed: false`,
and the failure rate was read as a property of the tool. `run.sh` now hardlinks the
packages into each arm and takes a real copy of `vendor/composer`, and refuses to run
against a subject whose root package no longer resolves to the repository.

## Task B could not be satisfied

> …add a private method `clearAttempts(string $key): void` … Make sure the project
> static analysis still passes.

This configuration reports `method.unused` for a private method nothing calls, so the
perfect answer still failed the check. Applying all three changes by hand leaves exactly
one error, and it is that one. Both arms therefore spent turns on a clause neither could
meet.

The successor asks for the same three changes and for the new method to be used in
`resetLockout()`, in place of the direct cache removal there. Hand-applied, that is
`[OK] No errors` and a passing oracle.

## The noise floor

Two runs of the same configuration, prompt and model, an hour apart: 4 of 8 invocations
at a 12.0-turn median, then 7 of 8 at 8.5. Nothing changed between them. Any single-digit
difference in a median over n=8 is inside that; the results below are reported with
p-values for that reason, and the ones near p = 0.05 should be read as suggestive.

## Task A — one rename

> Rename the private method `getQueryBuilder()` in
> `Classes/Service/CredentialRepository.php` to `queryBuilderFor()`, including every call
> to it in that file. Change nothing else. Make sure the project static analysis still
> passes.

One declaration, five calls. Every run counted below made the correct six replacements,
checked against the run's own working tree rather than its narrative.

Wording first. The arms differ only in the skill's `description`:

| description | n | invoked | turns | output | usd |
| --- | --- | --- | --- | --- | --- |
| as shipped | 8 | 1/8 | 12.5 | 3414 | 0.160 |
| intermediate | 8 | 4/8 | 13.0 | 3396 | 0.168 |
| task-shaped | 8 | **6/8** | 9.5 | 2582 | 0.147 |

Fisher p = 0.04 for 1/8 against 6/8. The shipped description names what the tool operates
on — "symbols, members, types, statements, expressions" — while the request says "rename
the method and its call sites". Wording that lists the *tasks* moved invocation to six of
eight. The turn difference between those arms is not separately significant at this n.

Wording is not enough, though, and the gate is what actually moves the numbers:

| | no gate | gate | gate + these messages |
| --- | --- | --- | --- |
| turns | 13.0 | 8.5 | **8.0** |
| output | 3030 | 2272 | **2033** |
| usd | 0.164 | 0.136 | **0.127** |

Exact Mann-Whitney p = 0.0034 against the ungated baseline, 8/8 invoked. Between the two
gated arms p = 0.55: the refusal messages did not move Task A on their own.

## Task B — three changes in one file

Against the repaired subject, and with the tool on PATH in every arm:

| task | arm | n | correct | turns | output | cache read | usd |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B, as written | no skill | 8 | 8/8 | 14.5 | 5414 | 679956 | 0.187 |
| B, as written | gate | 8 | 8/8 | 19.0 | 7996 | 959933 | 0.243 |
| C, satisfiable | no skill | 8 | 8/8 | 13.0 | 4230 | 599092 | 0.172 |
| C, satisfiable | gate | 8 | 8/8 | **22.0** | 6668 | 1143573 | **0.261** |

Per-run turns, no skill then gate:

```
B   10 12 13 14 15 15 17 19   |   12 14 16 19 19 20 27 28
C   12 12 12 13 13 14 17 18   |   13 18 19 22 22 23 24 26
```

**The gate loses here.** Exact one-sided Mann-Whitney p = 0.031 on B and p = 0.0012 on C:
on the satisfiable task it costs nine more turns and half as much again in dollars. The
outcomes are equal — all sixteen C trees pass the oracle, report `[OK] No errors` from
the project's own PHPStan, and touch no file but the one named — so the difference is
cost alone. There is no "invoked" column for the gated arm: a gate that refuses `Edit`
makes the tool the only way through, and counting skill loads under it measures nothing.

The pre-repair figure for the ungated arm on B was 17.0 turns at $0.217. Two and a half
turns of that arm's cost were the broken analyser, not the task.

### Where the gated arm's turns go

Across its sixteen B and C transcripts: 98 `apply` calls, **54 of them refused**, and
every run opened with one `Edit` the gate denied. Turns follow refusals — Pearson
r = 0.74 over the sixteen runs, roughly one and a half turns per refused `apply` on top
of a base of fifteen. The one run with no refusal took 12 turns, under the ungated
median. The floor is real; the tool's contract is what keeps the arm off it.

The refusals are one intent tried five ways. For the change the task names inside
`resetLockout()` — replace `$this->rateLimitCache->remove($key)` with
`$this->clearAttempts($key)` — runs sent `match`/`replace` fields, `replace_statement`
on the method's selector, `replace_node`, `replace_child` with a guessed property path,
and `insert_before`. The engine takes that edit only through `inspect` and a line and
column, and that loop is the cost. The largest single class, eight `INVALID_RESULT`s,
is an engine defect rather than a caller mistake: `ClassMethod` extends `Stmt`, so
`replace_statement` accepts a method as its target, swaps it for a statement, and the
file only fails at the reparse gate.

An earlier gated arm's figures are void for a different reason: `cfg-hook3` pointed at a
worktree removed after its pull request merged, so the hook script was missing and
Claude Code denied every operation. All sixteen runs changed nothing and burned 17 to 40
turns saying so — with `subtype` `success` and `is_error` `false` in every result.
`run.sh` now refuses an arm whose hook scripts are not there.

### Closing it, one refusal class at a time

Each round below is the same gated arm on task C, n = 8, against a frozen commit, and
each commit answers the refusals the round before it left. Every tree in every round
passes the oracle, reports `[OK] No errors` and touches only the named file.

| gate against | turns | usd | wall s | apply calls | refused |
| --- | --- | --- | --- | --- | --- |
| `main` before #62 | 22.0 | 0.261 | 101.1 | 54 | 29 |
| `9088a31` — `match` inside a named scope | 16.5 | 0.218 | 112.7 | 36 | 17 |
| `defa62f` — lone unknown field, qualified selectors | **14.5** | **0.198** | 91.7 | 35 | 11 |
| `aa045f2` — idempotent `match`, member beside a member | 17.0 | 0.206 | 104.4 | 42 | 16 |
| no skill | 13.0 | 0.172 | 66.5 | — | — |

At `defa62f` the gate is significantly cheaper than before #62 — turns p = 0.013,
dollars p = 0.0052 — and no longer measurably worse than no skill (turns p = 0.31,
dollars p = 0.080). Wall time follows turns: across eight runs the API accounts for 557
seconds against 400 without the skill, tools for 258 against 174. A cold project-wide
PHPStan takes ten seconds and a warm one half a second, and the ungated arm pays the
same cold run when it checks its own work.

The fourth round did what it was built for and moved nothing else. The two classes it
answers — a `match` asked for after `rename_method` had already done it, `add_member`
aimed at a method — do not recur in its transcripts, and the arm is no different from
the third round (turns p = 0.68, dollars p = 0.67, two-sided). What is left is a long
tail: sixteen refusals of ten different shapes across eight runs, among them two
operations that do not exist (`add_sibling_after`, `change_docblock`), `insert_into`
without `property`, and a flag the CLI never had. Removing one shape per round does not
move a median over eight runs whose own spread is several turns wide. The gate is at
parity with no skill on this task, not ahead of it.

## What the invoking runs still spend

From the transcripts of the Task A runs that did invoke it:

- Each spent a turn locating the executable — `which php-ast-edit || find . -name
  php-ast-edit`. `SKILL.md` opens by asking the reader to "resolve the executable once"
  and lists four places to look, while the skill ships `scripts/php-ast-edit`, a wrapper
  that resolves all four itself.
- Three wrote a JSON payload through a heredoc, although step 3 of the same file says a
  single edit against a named target needs no payload file.

Both are `SKILL.md` body problems, not description problems, and neither is measured
here.
