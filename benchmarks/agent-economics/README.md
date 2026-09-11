# Complete-agent economics

The [instruction and discovery experiments](results/2026-09-11-intent-instructions/REPORT.md)
test whether a short command contract and explicit delegation of method-family
discovery reduce the overhead observed with the direct rename command. The report
separates final-code correctness, instruction adherence and unsupported completion
claims, and retains the initial campaign and its single refinement independently.

The [36-run v0.8.0 Haiku pilot](results/2026-09-11-v080-haiku/REPORT.md) compares
ordinary contextual edits with the released full skill and a separate instruction
follow-up. The small edit saved 31.1% of tokens; three changes in one file and the
clarified cross-file rename used more. Additional declaration-first prose also lost
and was withdrawn. Every attempt, the ambiguous original fixture, and the separately
scheduled correction remain in the report; no general saving is claimed.

The [compact-workflow follow-up](results/2026-09-06-efficiency/REPORT.md) compares
contextual editing, the unchanged full skill and one experimental compact adapter with two read modes
with Sonnet and Haiku. It includes public TYPO3 code, mandatory read-bound revisions,
and a separate directed method-read comparison. Savings are task-dependent: the
report retains failed attempts, unknown usage, and correct outputs obtained through
text-edit bypasses. The [runner and protocol](efficiency/PROTOCOL.md) are explicit
benchmark tooling; no model calls occur during preparation or ordinary tests.

The [2026-09-06 native pilot](results/2026-09-06-native-pilot/REPORT.md) contains
twelve Claude Code runs: two small tasks, two variants and three paired repetitions.
The complete skill used **75.70% more input-plus-output tokens** than competent
contextual editing, with all twelve final outputs passing their runtime oracles.
This is a bounded negative observation, not a general efficiency percentage.

The [evidence and reproduction instructions](results/2026-09-06-native-pilot/README.md)
include sanitized native usage, all failures, prompts, fixtures, diffs and oracle
outcomes. Provider cache state is unknown; actual cache counters are retained.
Native USD values are list-price estimates, not proof of subscription charges.
Two independent AI reviews accepted the outputs; human acceptance remains pending.
All six skill-assigned runs omitted the instructed snapshot hashes. The separate
[adherence audit](results/2026-09-06-native-pilot/adherence.json) records this failure;
the variant identifies supplied instructions, not perfect compliance.

These records deliberately do not pretend to satisfy the older import schema's
cold/warm classification and human-acceptance requirements. See the
[general comparison protocol](../README.md#fair-agent-comparison) before extending
the task corpus or making broader claims.
