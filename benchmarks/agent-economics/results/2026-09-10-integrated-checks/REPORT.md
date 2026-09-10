# The model stops re-running a check the tool has already run

Twenty-four sessions against `2a7616a`, two tasks, two models, two arms that differ in
one file. Method in the [protocol](../../efficiency/PROTOCOL.md) under *The check arms*;
every figure below is recomputed from [runs.json](runs.json) by
[`check_arms.py`](../../efficiency/check_arms.py).

Both arms carry `check.php` and the same task clause, `Make sure \`php check.php\` still
passes.` Only `check_integrated` carries a `.php-ast-edit.json` declaring that command
with `scope: project`. No instruction text and no prompt clause names the declaration,
the report field or the engine's checking: what the treatment's model learns about the
check having run, it learns from the report.

| | `check_manual` | `check_integrated` |
| --- | --- | --- |
| ran the check itself after its last `apply` | **12 / 12** | **0 / 12** |
| its own check runs, all sessions | 14 | 0 |
| rounds, median | 5 | **4** |
| tokens, median | 60,443 | **45,499** |
| output tokens, median | 1,158 | **920** |
| wall seconds, median | 17.3 | **13.0** |
| list price, median | $0.0327 | **$0.0222** |
| oracle passed | 12 / 12 | 11 / 12 |

Fisher exact on the first row, two-sided: **p = 7.4 × 10⁻⁷**. Exact one-sided
Mann-Whitney on the rest: rounds p = 0.0022, wall p = 0.00076, tokens p = 0.014, output
tokens p = 0.039, dollars p = 0.050.

**Manipulation check first.** Twelve of twelve treatment sessions had at least one
`apply` whose report actually carried `alreadyRun`. None received the arm without the
treatment, so none is excluded.

## The separation holds in every cell

| model | task | arm | ran check | rounds | tokens |
| --- | --- | --- | --- | --- | --- |
| haiku | local-variable | manual | 3/3 | 4, 5, 5 | 47,541 · 60,235 · 60,652 |
| haiku | local-variable | integrated | 0/3 | 3, 3, 4 | 34,678 · 34,996 · 47,312 |
| haiku | multi-file-members | manual | 3/3 | 6, 6, 7 | 73,652 · 76,630 · 89,496 |
| haiku | multi-file-members | integrated | 0/3 | 4, 4, 5 | 48,973 · 49,481 · 61,642 |
| sonnet | local-variable | manual | 3/3 | 4, 4, 4 | 44,665 · 44,686 · 44,695 |
| sonnet | local-variable | integrated | 0/3 | 3, 3, 3 | 32,998 · 33,002 · 33,020 |
| sonnet | multi-file-members | manual | 3/3 | 5, 7, 7 | 58,108 · 82,848 · 83,233 |
| sonnet | multi-file-members | integrated | 0/3 | 4, 4, 7 | 45,498 · 45,500 · 82,863 |

Rounds do not overlap between the arms in six of the eight cells, and the two that do
overlap are the same cell's outlier: the seven-round treatment session spent a turn on
`which php-ast-edit || find …`, which the skill-invocation report already attributes to
`SKILL.md` asking the reader to resolve the executable while shipping a wrapper that
resolves it. That is not the treatment.

## What the sessions say they did

Every treatment session asserts the check passed, and none ran it:

> Both edits were applied as a single task using php-ast-edit, and the validation
> confirms that `php check.php` passes.

> Done! I've added `public const VERSION = 2` to both First and Second classes. […] and
> `php check.php` passes successfully.

The control sessions ran `php check.php` and then said the same thing. That is the whole
effect: one tool call and the round that carries it.

## What this does not show

**It is not the −59.9%.** The README attributes that share of the 2026-09-07 result to
integrating the checks, measured with a real static analyser through the experimental
wrapper. `check.php` parses the tree in-process and costs milliseconds, so the saving
here — a quarter of the tokens, a fifth of the rounds — is what the *round* is worth with
the check itself free. A project whose check takes ninety seconds saves the ninety
seconds too. This measures the mechanism, not the magnitude.

**Two tasks, two models, three repetitions each.** Both tasks are small and single- or
two-file. Nothing here says what happens when a check fails, which is the case where the
model has a reason to re-run.

**One oracle failure, and it is not the treatment.** `pilot-2/run002` left an `edits.json`
in the workspace, which the common prompt forbids; its source edits are correct and
`fixture_intact` holds. A control session wrote the same file and removed it again.

## Why the existing evidence did not already answer this

The [skill-invocation report](../../../skill-invocation/REPORT.md) records that a gated
arm ran the project's analysis by hand after the tool had checked its edits — 303 seconds
of tool time across eight sessions against 171 without the skill — and reads as evidence
that integration does not stop the repeat run. That subject declares its check with
`scope: changed_files`, and `alreadyRun()` reports project scope only, because a
changed-files check saw the edited files and not the project. Those eight sessions were
never told the project check had run.

## Reproducing this

[evidence.tar.gz](evidence.tar.gz) holds all four campaigns' schedules, configurations,
frozen digests and per-run evidence — argv, prompts, the native transcript, the engine
audit, the diff and the oracle. It summarizes itself wherever it is unpacked:

```bash
sha256sum -c SHA256SUMS
mkdir evidence && tar -C evidence -xzf evidence.tar.gz
python3 ../../efficiency/check_arms.py evidence/{pilot-2,b,c,d}
```

The `summary` that prints is the one in [runs.json](runs.json), and every figure above
was recomputed from it rather than copied from the prose.

## Provenance

All four campaigns froze the same tree: source commit `2a7616a`, `SKILL.md`
`a82928e7…`, engine `37c8882…` (full digests in [provenance.json](provenance.json)).
Haiku is the pinned `claude-haiku-4-5-20251001` with no effort flag, Sonnet
`claude-sonnet-4-6` at `--effort medium`. Twenty-four sessions, $0.79 of native list
price, no accounting errors, no timeouts.
