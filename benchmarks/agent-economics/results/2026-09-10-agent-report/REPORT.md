# Does recommending `report: "agent"` make a session cheaper?

**No. On this task it makes a Sonnet session 71% more expensive and changes nothing for
Haiku.** The recommendation added to `SKILL.md` was measured against its own absence and
lost.

Measured 2026-09-10 against `main` at `b1b79e6`. Twelve sessions, list price USD 0.39.

## Design

One decision differs between the arms: which response shape `SKILL.md` recommends.

| Arm | `SKILL.md` says |
| --- | --- |
| `full_skill` (treatment) | use `report: "agent"` unless you need the diff |
| `full_skill_compact_report` (control) | use `report: "compact"` to receive each verification result once |

Both substitutions express that one choice — the sentence stating it and the example an
agent copies. Every other line of the skill is byte-identical; `runner.py` builds the
control from the live `SKILL.md` and refuses if the sentence it edits has moved.

Task `local-variable`: rename a local in one file. Two models, three repetitions per
cell, interleaved. All twelve oracles passed — no arm won by failing.

**This is the only place the measurement is possible.** `symbol_intent.py` and the
`php-ast-agent` adapter both pin `report: "compact"` and hand the model their own
projection, so the engine's shape never reaches it there. Only `engine_proxy.py` is
passive, and only in `full_skill` does the model write its own apply document.

## Result

Medians, n=3 per cell.

| Model | Arm | Rounds | Tool calls | Output | Total tokens | List USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| haiku | control | 4 | 3 | 1118 | 46,470 | 0.0157 |
| haiku | **agent** | 4 | 3 | 1077 | 46,296 | 0.0155 |
| sonnet | control | 3 | 2 | 360 | 32,218 | 0.0257 |
| sonnet | **agent** | 5 | 4 | 567 | 55,022 | 0.0484 |

Haiku: −0.4% tokens, identical rounds. No effect.

Sonnet: **+71% tokens, +67% rounds, +89% list price.**

## Why — the mechanism, from the traces

The agent report withholds the diff, and `SKILL.md` tells the model where to get it
instead. It went and got it.

| Model | Arm | Runs making a tool call *after* the apply |
| --- | --- | --- |
| sonnet | control | **0 of 3** |
| sonnet | agent | **3 of 3** — twice `git diff`, once a `Read` |
| haiku | control | 3 of 3 |
| haiku | agent | 3 of 3 |

`run010` (control, sonnet), two calls, three rounds:

```
Read  Cache.php
Bash  php-ast-edit apply --file Cache.php --select method:Cache::key --op rename_variable …
```

`run004` (agent, sonnet), four calls, five rounds:

```
Bash  find … -name "Cache.php"
Read  Cache.php
Bash  php-ast-edit apply … --report agent
Bash  git -C … diff -- Cache.php        ← the round the report was supposed to save
```

Removing the diff from the response did not remove the need for it. It relocated the need
into an extra tool call and an extra model round, which costs more than the bytes it
saved. Haiku re-reads the file after every write regardless of report mode, so for it the
mode is neither help nor harm.

## What this does and does not establish

**Establishes:** recommending `agent` as the default is worse than not recommending it, on
a single-file edit in a repository that declares no checks. The mechanism is visible in the
traces, and the separation is clean — 3 of 3 against 0 of 3.

**Does not establish** that the mode itself is bad. This task is its worst case: with no
`.php-ast-edit.json`, the response came back `checks: "none_declared"`, `verifications: []`
and `checksFailed: []`. Every field that distinguishes the mode was empty, so only its cost
was present. Whether it pays for itself where checks are declared and fail — where
`checksFailed` carries the output a caller would otherwise fetch, and `open` carries real
entries — is untested.

**Does not establish an effect size.** Three repetitions per cell shows a direction. The
Sonnet cells separate without overlap (rounds 5,6,5 against 4,3,3), which is why the
direction is reported at all; the percentages are not a number to plan against.

## Consequence

The blanket recommendation is withdrawn. `SKILL.md` no longer tells an agent to prefer
`agent` over the default; it names the case the mode is for — a declared check whose
verdict matters, or a response whose diff would be large — and leaves the default alone.

The next question worth measuring is the one this run could not: the same comparison on a
task with a declared check that fails, where the mode's own fields are non-empty.

## Files

- `config.json` — the frozen campaign configuration
- `runs.json` — every run's tokens, rounds, tool calls, price, wall time and oracle result
- `frozen-SKILL.md` — the treatment text as the campaign ran it, which the live skill no
  longer carries

The controller that ran this is commit `5f4fde5460c5fc73661069fac8bb7a6460fee42c` on this
branch — the commit that added the arm and the one after it removes it again. Its
`runner.py` hashes to `3208ff447e72de9df02655b21983c46d02d981e3482b173ccf048e8511713203`, which is what the campaign
directory recorded at prepare time. A verbatim copy is deliberately not committed here: it
would be a second copy of a file three directories away, and git already holds those exact
bytes.
