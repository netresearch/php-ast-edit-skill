# Source excerpts in rename reports: matched Haiku experiment

Short source excerpts beside unresolved rename warnings reduced median tokens by
**15.3%**, wall time by **16.0%** and tool calls by **10%** on the cross-file task.
On the small task, median tokens instead increased **20.8%** and time **4.3%**,
despite fewer median tool calls. All 24 final code states were correct; **19/24**
final completion claims passed independent review. Total native cost was
**USD 0.6902544**, a list-price estimate rather than an invoice.

The prospective adoption criterion fails. This is a workload-specific signal
from six pairs per task, not a general AST savings rate. The excerpt feature stays
an isolated benchmark prototype; the production CLI and loaded skill are unchanged.

## Design and provenance

The [prospective protocol](../../intent-command/REVIEW-CONTEXT.md) follows the
completed [exact-invocation experiment](../2026-09-11-exact-invocation/REPORT.md).
It does not extend or pool its observations. The final source was signed and
pushed before paid calls at
[`b93c57c`](https://github.com/netresearch/php-ast-edit-skill/commit/b93c57c22fdd31df0c5b56d6a8f6f4ce16b8e150).

- Two tasks × two arms × six paired repetitions: all **24 attempts** retained.
- Seed `20260916`; three repetitions per task start with each arm.
- Pinned `claude-haiku-4-5-20251001`, no effort override or fallback, Claude Code
  2.1.268 at an explicit versioned executable path.
- Same source CLI, PHP 8.5.10, php-parser 5.8.0 and Phpactor 2026.07.22.0.
- Same fixture bytes, selected intent, ready-to-run command, system instructions,
  Bash/Read/Edit/Write tools, guards, checks and independent oracles in both arms.
- Fresh private workspaces, serial execution, 120-second timeout, USD 3 campaign
  ceiling and USD 0.75 reservation for only the next imminent attempt.

Both arms receive operator-selected method, declaration file, destination and
project path plus the same complete rename command. **Target-selection cost is
excluded.** This compares two AST report presentations, not AST against text edits
or autonomous project discovery. All twelve prepared pairs were checked for
byte-identical initial hashes, prompts and system instructions.

The wrapper snapshots allowlisted fixture files before the command and derives
excerpts only from unresolved locations named by the original engine report.
Both arms compute the same context. `review_locations` returns original stdout
byte for byte; `review_excerpts` inserts only a `reviewContext` member without
reformatting existing bytes or changing warnings, counts, checks or exit behavior.
The actual candidate output and underlying engine output are retained separately.

Context is explicitly pre-command source evidence, not semantic classification
or current edit coordinates. The additional context member is capped at 20 entries, 240 UTF-8
bytes per line and 8,192 serialized bytes. Actual contexts have three entries /
982 bytes on the small task and two / 690 bytes across files; none is truncated
or omitted. Snapshotting is bounded and limited to the small synthetic fixtures;
it is not a production-scale implementation. Its overhead is paid in both arms.

Two unpaid preparations were replaced before execution: one caught the CLI's
auto-updated default symlink, and another preceded the adapter-autoload fix.
No candidate was attempted in either. Real adapter read/apply smoke tests verified
the corrected proxy topology before the final freeze. Full local runtime and
distribution checks, 56 efficiency tests and 13 task/oracle tests passed before
paid calls; no competing local tests ran during candidate timing.

## Complete-session results

Medians below include **all six attempts per cell**. Total tokens include native
fresh input, cache creation, cache reads and output; thinking is already included
in output. Visible model rounds differ from tool calls. Component medians need
not sum to the median total. Full categories and native failures are retained in
[report.json](report.json).

| Task | Arm | Correct code | Total tokens | Rounds | Calls | Wall seconds | Native cost USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Small rename | review_locations | 6/6 | 33,879.5 | 3 | 4 | 20.20 | 0.01861 |
| Small rename | review_excerpts | 6/6 | 40,928.5 | 3.5 | 3 | 21.06 | 0.01957 |
| Cross-file rename | review_locations | 6/6 | 87,059 | 6.5 | 10 | 36.01 | 0.03633 |
| Cross-file rename | review_excerpts | 6/6 | 73,698 | 5.5 | 9 | 30.25 | 0.03254 |

The predefined criterion requires at least 15% fewer median tokens, no higher
median wall time on **both tasks**, and all quality gates passing in both arms.
The cross-file cell meets the numeric threshold, but the small task regresses;
five final-claim failures also prevent passing the quality condition. Cross-file
native median cost falls 10.4%; small-task cost increases 5.2%.

The treatment's lower small-task median call count does not imply fewer total
processed tokens. Its individual sessions vary widely: three finish with one
engine call, while others keep reading and checking. Paired results below expose
that variation; the headline percentages compare cell medians, not medians of
paired ratios. Full precision is in [comparison.json](comparison.json).

| Task | Repetition | Control / treatment run | Token ratio | Wall-time ratio | Tool-call ratio |
| --- | ---: | --- | ---: | ---: | ---: |
| Cross-file | 1 | run019 / run020 | 1.046 | 0.847 | 1.000 |
| Cross-file | 2 | run009 / run010 | 1.033 | 0.854 | 1.100 |
| Cross-file | 3 | run014 / run013 | 0.988 | 0.875 | 0.600 |
| Cross-file | 4 | run005 / run006 | 0.452 | 0.672 | 0.429 |
| Cross-file | 5 | run024 / run023 | 1.626 | 1.011 | 0.800 |
| Cross-file | 6 | run004 / run003 | 0.394 | 0.567 | 0.909 |
| Small | 1 | run021 / run022 | 0.645 | 0.828 | 0.250 |
| Small | 2 | run016 / run015 | 0.487 | 0.892 | 0.200 |
| Small | 3 | run018 / run017 | 0.479 | 0.930 | 0.167 |
| Small | 4 | run007 / run008 | 1.760 | 1.195 | 1.250 |
| Small | 5 | run011 / run012 | 2.118 | 1.411 | 3.000 |
| Small | 6 | run002 / run001 | 2.318 | 1.831 | 1.500 |

Only three of the six cross-file pairs use fewer treatment tokens. Their median
paired token ratio is approximately 1.01, even though the ratio of cell medians
is 0.847. Five of six cross-file pairs finish faster. This disagreement between
descriptive summaries reinforces the need for replication; the headline token
reduction is not a consistent per-run improvement.

Six pairs per task are exploratory; no statistical significance or universal
savings rate is claimed. Provider cache state is unknown. Tool execution intervals
are incomplete, so tool time is not separated from orchestration. The two tasks
do not measure source-repair failures of ordinary text editing.

## Correctness and observed behavior

The [independent manual audit](audit.json) covers every attempt, raw evidence
references, actual commands, output delivery, source hashes, reads, checks and
completion claims. All 24 independent code oracles, actual project checks and AST
write-route gates pass. Final diffs are identical within each task, and protected
files remain byte-identical. Original report bytes and JSON values survive every
treatment insertion, and the excerpts are visible in the native tool results.

| Observation across both tasks | Locations | Excerpts |
| --- | ---: | ---: |
| Successful AST writes / exact prepared argv | 12 / 12 | 12 / 12 |
| Failed engine calls | 0 | 0 |
| PHP Read calls before the engine attempt | 2 | 2 |
| Calls after the successful write | 69 | 54 |
| Subsequent native Reads of changed files | 27 | 16 |
| Subsequent native Reads of unchanged files | 29 | 22 |
| Subsequent native Reads of files named by warnings | 18 | 14 |
| Subsequent additional Bash reads of warned files | 2 | 0 |
| Repeated already-passed project check calls | 11 | 9 |
| Runs repeating that check | 10 | 9 |
| All four quality gates passing | 10/12 | 9/12 |

Warning-read counts include two explicit Bash reads in control run024; counting
native Read alone would miss them. These counters establish observed work, not
that every such read is redundant. The identical engine project check had passed
before each counted repetition, with no intervening mutation.

Three small treatment runs (015, 017, 022) use only the engine call, without
subsequent reads or repeated checks. Runs015 and 017 also have supported final
claims; run022 makes the semantic overstatement described below. In cross-file
run006, the engine call is followed only by a check.php read and a repeated check.
Other treatment runs still read files whose lines the result already displayed.
These are observations, not proof that every warning can be resolved from one line.

The five false final claims are separate from correct code:

- Treatment run003 and control run009 call the YAML value `'fetch service'`;
  the unchanged configuration contains `label: fetch`.
- Control run005 and treatment run023 invent `OtherConsumer::fetch()`; the actual
  preserved caller is `OtherConsumer::run()`, invoking `Other::fetch()`.
- Treatment run022 calls all three preserved literals non-references. One is a
  reflective method-name argument in a negative `method_exists()` assertion.
  Preserving that check is correct, but its stated semantic classification is not.

Thus final claims pass in **10/12 control** and **9/12 treatment** runs. Intermediate
errors stay separate: run013 incorrectly attributes a pre-existing checker fallback
to the edit, then makes no such claim in its final response. The pre-command label
did not prevent this misreading. Run012 also has a failed directory Read before its
successful engine call. Neither is an incorrect AST mutation.

The same concrete YAML-value error was found in the previous experiment's run022.
A second review of all 24 older final responses corrects its final-claims count
from 23/24 to 22/24. That report and audit include a dated correction; original raw
evidence, economics and its failed adoption verdict are unchanged.

## Decision and next hypothesis

Bounded context can remove orchestration in these tasks, and the cross-file result
justifies investigating it further. It has not met the declared conditions for
default adoption. The benchmark helper and evidence are retained for reproduction;
no new public report flag or loaded-skill instruction is introduced.

A narrower next hypothesis is to include excerpts for unchanged files, avoiding
duplication of pre-edit source from a changed file already represented in the diff.
On the small fixture, one physical line contains the entire old Product class,
including the old method declaration alongside the deliberately preserved string.
Whether excluding that duplicate helps is **unmeasured**. Repeated checks and false
summary claims also remain separate targets; this campaign did not change their
instructions or trade correctness requirements for speed.

## Reproduce and audit

The [protocol](../../intent-command/REVIEW-CONTEXT.md) describes the paid campaign.
Rechecking published measurements requires no model calls:

```bash
sha256sum -c SHA256SUMS
mkdir /tmp/review-context-evidence-review
tar -xzf evidence.tar.gz -C /tmp/review-context-evidence-review
# From the repository root:
python3 benchmarks/agent-economics/intent-command/summarize.py \
  /tmp/review-context-evidence-review > /tmp/review-context-recomputed.json
```

The archive contains 788 allowlisted files plus `export-sha256.json`, including all
24 native streams, initial/final fixtures, checks, oracles, frozen controller and
context helper. Dependencies, binaries and private sessions are excluded; runtime
identities remain recorded. [SHA256SUMS](SHA256SUMS) covers the archive, report,
comparison, manual audit and this document.

After measurement, the publication branch strengthens future controllers to stop
on missing/wrong presentation identity or altered control stdout. The measured
controller remains the frozen `b93c57c` version; independent trace review verified
those invariants in all actual outputs. All 58 efficiency tests pass after this
hardening. This later guard is not represented as part of the measured treatment.
