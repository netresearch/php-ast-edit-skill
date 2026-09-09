# What it costs to reach for the tool

Haiku 4.5, isolated configurations, a real TYPO3 extension that declares both a
`formatter` and a `verify` command. Method in [README.md](README.md).

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
| C, satisfiable | no skill | 8 | 8/8 | 13.0 | 4230 | 599092 | 0.172 |

Per-run turns: `10 12 13 14 15 15 17 19` and `12 12 12 13 13 14 17 18`.

The pre-repair figure for the same arm and the same task was 17.0 turns at $0.217. Two
and a half turns of the free arm's cost were the broken analyser, not the task.

The gated arm is being re-measured. Its earlier figures are void for a second reason:
`cfg-hook3` pointed at a worktree removed after the pull request it belonged to merged,
so the hook script was missing and Claude Code denied every operation. All sixteen runs
of that arm changed nothing at all and burned 17 to 40 turns saying so. A missing hook
script fails closed, and an arm can be entirely dead without anything in the result JSON
saying so — `subtype` was `success` and `is_error` was `false` in every one.

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
