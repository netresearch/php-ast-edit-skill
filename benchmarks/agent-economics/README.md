# Complete-agent economics

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

These records deliberately do not pretend to satisfy the older import schema's
cold/warm classification and human-acceptance requirements. See the
[general comparison protocol](../README.md#fair-agent-comparison) before extending
the task corpus or making broader claims.
