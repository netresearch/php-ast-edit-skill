# Prepared rename invocations: matched Haiku experiment

A ready-to-run command removed four invocation errors, but did **not** meet the
prospective efficiency criterion. On the small task it used 11.6% fewer median
tokens and 20.8% less time. Across files it used 29.2% more tokens and 3.8% less
time. Median tool calls were unchanged on both tasks. All 24 final code states
were correct; 22 final completion claims passed independent review.

**Correction, September 12:** A second review of all 24 final responses found an
overlooked false YAML-value claim in run022. The final-claims count is 22/24,
previously reported as 23/24. Raw evidence, code correctness, economic measurements
and the failed adoption criterion are unchanged; the manual audit is corrected.

The result supports better command formulation in these attempts, not a general
efficiency gain. The prepared-invocation arm stays optional benchmark tooling;
this study makes no production skill instruction change or AST-versus-text claim.

## Design and provenance

The [prospective protocol](../../intent-command/EXACT-INVOCATION.md) was committed
and pushed before paid calls at
[`ff3484f`](https://github.com/netresearch/php-ast-edit-skill/commit/ff3484f928ea1557ff88c6fae314fcff9600d2f2).
It is separate from the completed
[instruction/delegation experiments](../2026-09-11-intent-instructions/REPORT.md).
No observations are pooled or replaced.

- 24 attempts: two tasks × two arms × six paired repetitions, seed `20260915`.
- Pinned `claude-haiku-4-5-20251001`, no effort flag or fallback; Claude Code 2.1.268.
- Same source CLI after PR #83, PHP 8.5.10, php-parser 5.8.0 and Phpactor 2026.07.22.0.
- Same Bash/Read/Edit/Write tool set, guards, resolver, reports, checks and independent oracles.
- Fresh private workspaces, serial execution and a 120-second per-attempt timeout.
- Starting arm balanced within each task: three paired repetitions start with each arm.
- USD 3 planning ceiling, reserving USD 0.75 only for the next attempt before replacing it with actual usage. Total native list-price estimate: **USD 0.8135955**, not an invoice.

Both arms receive identical delegated system instructions and operator-selected
method, declaration file, destination and project path metadata. Both may use
`--file`, which narrows declaration discovery while supported callers remain
project-wide. Only `exact_invocation` additionally receives the complete command,
generated deterministically with `shlex.join`.

This controls target knowledge while testing prepared command presentation.
**The cost of selecting that metadata is excluded.** This is not autonomous
discovery and has no ordinary text-editing control. Actual arguments are retained:
the successful control write uses `--file` in 6/12 runs, versus 12/12 treatment
runs. Treat that actual command choice as part of the observed invocation bundle.

Preparation verified all twelve pairs had identical starting hashes, system
instructions and shared prompt prefixes. The frozen manifest, controller, raw
inputs, argument vectors, runtime hashes and operator provenance are in the
evidence archive. Later executable-bit, import-order and Ruff formatting fixes in
the publication branch do not change the frozen controller used for these runs.

## Complete-session results

All values below are medians of **all six attempts per cell**. Tokens sum native
fresh input, cache creation, cache reads and output; thinking is already part of
output. These are processed tokens including cache reuse, not just fresh input.
Visible model rounds are distinct from native turn accounting. Component medians
need not sum to the median total. Every category is retained in [report.json](report.json).

| Task | Arm | Correct code | Tokens | Rounds | Calls | Wall seconds | Native cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Small rename | delegated_intent | 6/6 | 59,222.5 | 5 | 5 | 25.86 | 0.02498 |
| Small rename | exact_invocation | 6/6 | 52,376 | 4.5 | 5 | 20.49 | 0.02150 |
| Cross-file rename | delegated_intent | 6/6 | 116,942 | 8.5 | 10 | 37.20 | 0.04312 |
| Cross-file rename | exact_invocation | 6/6 | 151,086 | 11 | 10 | 35.79 | 0.04443 |

The predefined criterion requires at least 15% fewer median tokens, no higher
median wall time on **both** tasks, and all quality gates passing in both arms.
It fails: the small token reduction is below 15%, the cross-file token count
increases, and treatment runs022 and 023 fail the final-claims gate. Small-task cost falls
13.9%; cross-file cost rises 3.0%. Cost and total processed tokens are distinct.

Pairing also shows substantial variation. Below, each ratio is treatment/control;
values below 1 favor treatment. The headline percentages above compare cell
medians, not medians of these paired ratios. See [comparison.json](comparison.json)
for full precision and every paired metric.

| Task | Repetition | Control / treatment run | Token ratio | Wall-time ratio | Tool-call ratio |
| --- | ---: | --- | ---: | ---: | ---: |
| Small | 1 | run009 / run010 | 1.431 | 1.021 | 1.400 |
| Small | 2 | run019 / run020 | 0.993 | 0.665 | 0.625 |
| Small | 3 | run013 / run014 | 1.340 | 1.042 | 1.250 |
| Small | 4 | run018 / run017 | 1.228 | 0.849 | 1.000 |
| Small | 5 | run004 / run003 | 0.667 | 1.037 | 1.000 |
| Small | 6 | run012 / run011 | 0.458 | 0.510 | 0.556 |
| Cross-file | 1 | run001 / run002 | 1.221 | 0.876 | 1.000 |
| Cross-file | 2 | run005 / run006 | 1.819 | 1.253 | 1.200 |
| Cross-file | 3 | run008 / run007 | 0.999 | 0.836 | 1.000 |
| Cross-file | 4 | run021 / run022 | 1.412 | 0.889 | 0.909 |
| Cross-file | 5 | run024 / run023 | 1.022 | 1.048 | 1.000 |
| Cross-file | 6 | run016 / run015 | 1.329 | 0.913 | 0.846 |

Six pairs per task remain exploratory. Provider cache state is unknown. Full tool
execution intervals are unavailable, so no tool-versus-orchestration time split
is inferred. These two synthetic tasks do not establish savings in arbitrary PHP
repositories or fewer source-repair loops than text editing.

## What the traces establish

The [independent audit](audit.json) includes every run, actual argv, raw hashes,
line references and separate correctness, checks, write-route and final-claim gates.

| Observation across both tasks | Delegated control | Exact invocation |
| --- | ---: | ---: |
| Successful guarded AST mutations | 12 | 12 |
| Failed tool calls, all malformed rename invocations | 4 | 0 |
| PHP Read calls before first rename attempt | 4 | 2 |
| PHP Read calls before successful write, including recovery | 6 | 2 |
| Calls after successful write | 73 | 79 |
| Subsequent Read calls for changed files | 25 | 28 |
| Subsequent Read calls for unchanged files | 25 | 27 |
| Repeated already-passed project check calls | 11 | 12 |
| Runs repeating that check | 11 | 11 |
| All four quality gates passing | 12/12 | 10/12 |

- All twelve treatment runs adopt the provided argv exactly. Control runs001,
  016, 021 and 024 pass doubled namespace backslashes through single-quoted shell
  arguments and receive exit 2 before mutation. Recovery succeeds. This is an
  invocation-encoding problem, not an incorrect AST write. The shared JSON metadata
  contains escaped namespace separators; the treatment supplies shell quoting.
- Both arms usually invoke the command before PHP reads. Two control runs and one
  treatment run read PHP before their first attempt. This is distinct from the
  additional recovery reads after a refused command. No extra method-family rename
  is queued before the previous result.
- Removing invocation errors does not remove later orchestration. Cross-file
  treatment has more median model rounds despite identical median tool-call count;
  its increased cache-read token volume is consistent with processing context over
  more rounds. This observation does not prove a general causal effect from six pairs.
- Reads are not all redundant. The engine asks for review of a method-name literal
  in `check.php` and an unchanged YAML mention; task requirements also protect
  unrelated callers. In run002, warning review is followed by unchanged-caller and
  changed-file reads and two repetitions of `php check.php`. Repeated checks are
  counted only after the identical engine check passed, without another mutation.
- All 24 independent oracles, actual engine checks and write-route gates pass.
  Final code diffs are byte-identical within each task. Printer whitespace changes
  remain visible; protected files are byte-identical to the initial fixtures.
- Run023's final response invents `OtherConsumer::fetch()`. The actual caller is
  `OtherConsumer::run()`, invoking `Other::fetch()`. Its code is correct but its
  completion claim fails. Run007 makes the same mistake in intermediate prose and
  corrects it in the final response; that separate observation does not change the
  preregistered final-claims threshold.
- Run022's final response identifies the YAML label as `'fetch service'`; the
  protected `config/services.yaml` actually contains `label: fetch`. The file is
  unchanged and correct, but the quoted final value is false. This is the missed
  claim corrected in the September 12 audit, rather than a new code failure.

The concrete next candidate is bounded source context beside unresolved literal
and non-PHP mention locations in the existing rename report. The engine already
has those lines, while the present report often sends the model back to files.
Such context would support review without pretending to classify semantic meaning.
It adds output tokens and may be ignored, so its net benefit needs a separate
matched experiment; this study does not measure or ship that change.

## Reproduce and audit

The [protocol](../../intent-command/EXACT-INVOCATION.md) gives preparation and paid
execution commands. Rechecking the published evidence needs no model calls:

```bash
sha256sum -c SHA256SUMS
mkdir /tmp/exact-invocation-evidence-review
tar -xzf evidence.tar.gz -C /tmp/exact-invocation-evidence-review
# From the repository root:
python3 benchmarks/agent-economics/intent-command/summarize.py \
  /tmp/exact-invocation-evidence-review > /tmp/exact-invocation-recomputed.json
```

The archive contains 787 allowlisted files plus `export-sha256.json`, including
all 24 raw streams, initial/final fixtures, configured checks, independent oracle
results and exact frozen inputs. Runtime binaries and unrelated local sessions
are excluded; their identities remain recorded. Export hashes and relocated
report metrics were checked independently. [SHA256SUMS](SHA256SUMS) covers the
archive and published report, comparison, audit and this document.
