# Prospective clarification of the cross-file fixture

Recorded on 2026-09-11 after original run006 and before any clarified candidate.
The original protocol/task commit is `0c3a43bf5619a8a336316642d7e2c8b74b8809e0`.
Its 24-run schedule and all observed attempts remain unchanged.

The original YAML fixture contained a real `calls: fetch` reference to the renamed
service. The hidden oracle nevertheless required that support file to stay intact.
The prompt asked for the PHP rename and preserved labels without explicitly freezing
the support files. In run006 the AST candidate updated that YAML call and subsequently
changed the checker. These actions fail the frozen oracle, but the YAML change has a
defensible interpretation. That score alone cannot establish a semantic defect in
the AST operation. The checker edits and tool-instruction adherence remain separate
review observations. Do not relabel or remove the original oracle result.

An independent review recommended a narrower, explicit fixture. The new task ID is
`cross-file-rename-clarified`. Its PHP source, requested PHP transformation, project
checks, runtime, complete skill, model and arms match the original task. The YAML
becomes unrelated metadata with a `fetch` label, and the prompt explicitly requires
the checker, tool configuration, Composer metadata and YAML bytes to remain intact.
The hidden guard hashes these new support bytes. This tests the originally intended
PHP transformation with an unambiguous unrelated non-PHP occurrence.

Run this as a separate campaign: three repetitions in each of the same two arms,
six planned candidates, pinned Haiku, no effort flag, serial fresh processes and
seed `20260912`. Commit the generator and this amendment before preparation. Record
their commit and manifest hash alongside the frozen release/runtime provenance.
All original stop conditions still apply. The follow-up planning cap is USD 2 and
may start only after the original campaign ends with known total usage below USD 6;
the combined planning allowance therefore stays below USD 8. No model upgrade or
automatic rerun is authorized by this amendment.

Report both campaigns separately, including original failures and the reason for
the follow-up. Do not pool the clarified runs with the original cross-file cell or
use the new result to overwrite an old score. This amendment responds to evaluator
ambiguity discovered in the traces; it is not a preregistered confirmatory finding.

Generate the new one-task manifest with `clarified_tasks.py --output PATH` and use
the original preparation command with `--tasks cross-file-rename-clarified`, the
new manifest, `--seed 20260912`, and `--campaign-budget-usd 2`.
