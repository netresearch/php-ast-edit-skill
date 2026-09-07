# Prospective rename with actual final-byte behavior verification

This is a separate thirty-candidate experiment on a small extraction of public PHP
source. The earlier synthetic campaigns motivate the question; they are not controls
or additional repetitions. Freeze the complete design before any model calls.

## Workload and required outcome

Use the exact source extraction documented in [REAL_FIXTURE.md](REAL_FIXTURE.md):
six PHP files, the original license and source-only provenance from
`netresearch/t3x-nr-llm` commit `b505c936935b99baa3088ce62ad222d2ba61cee0`.
The task renames `SchemaPropertyClassifier::classify` to `controlType` in the
extraction, including its production and direct-test callers. This is one case with
three identifier edits, not a full TYPO3 installation or a representative corpus.
The extraction's excluded production caller is documented in its provenance.

Every arm receives the same explicit requirements: change only the necessary method
identifier bytes, preserve everything else, and actually execute the existing 17
PHPUnit tests successfully on the final file bytes using the provided checker.
Tests and assertions may not be weakened. The public source and tests are readable;
the expected rename inventory and hidden oracle are not candidate instructions.
The checker tests behavior only, so the unchanged baseline also passes its 17 tests.
It does not supply the answer or judge whether the requested rename was completed.

## Three treatments, ten paired repetitions

| Arm | Mutation route | Existing behavior checker |
| --- | --- | --- |
| `text-manual` | Ordinary text edits or a batched script | Candidate invokes `check-tests` after its final edit |
| `ast-manual` | Experimental semantic AST `rename_method --evidence` | Candidate invokes the same checker after its final edit |
| `ast-integrated` | Same experimental semantic AST command | Project verification automatically invokes the same checker |

Ten repetition blocks contain all three arms once: thirty fresh candidate processes.
Seed 20260909 shuffles the blocks; arm order rotates by block index. This gives each
arm ten observations but not perfect positional balance over ten three-arm blocks.
Retain the order and per-block comparisons, including failures.

All arms get identical compact system guidance and the same visible test command
apart from their isolated absolute paths. Guidance accepts a passed configured
invocation as satisfying the same test obligation; it does not demand further
inspection after a successful check. Any later edit invalidates prior test evidence.
Semantic report facts and tested behavior do not establish resolver completeness.
The AST arms explicitly require their assigned command for all PHP mutations;
ordinary tools remain available for source reads and checks. The text arm permits
batched scripts. Manual source repairs in an AST arm are therefore recorded as
treatment-adherence deviations rather than silently accepted as the assigned route.

Every workspace contains `.php-ast-edit.json`. Manual arms use the same empty
`verify` list; the integrated arm specifies a project-scoped invocation of its
`check-tests` wrapper. This necessary configuration difference is an explicit part
of the treatment. Each exact initial configuration hash is frozen and is the only
extra file the independent oracle permits. Configuration edits are prohibited.

Text versus AST compares a bundle of reference resolution, guarded writing and
evidence reporting. Manual versus integrated compares automatic triggering and
result reporting. Neither comparison isolates an AST-internal mechanism or the
effect of a particular output field. Existing engine code is used unchanged.

## Checker receipts and separate outcomes

`check-tests` invokes the same pinned fixture checker in every arm. It runs PHPUnit
12.5.31 with isolated external bootstrap/cache/JUnit files and writes a fresh UUID
receipt outside the workspace. The PHAR SHA-256 is
`194fcb6621866b542f1304e0da8dc7abcb15d6f9d1851893aec40896bcf5bb44`.
Each receipt retains exit status, executed test/assertion counts, output, JUnit
counters, measured duration, timing boundaries, PHAR identity and hashes of all
non-Git workspace files before and after checking. Successful CLI output is compact;
the receipt retains the full evidence. Failure output includes real diagnostics.

After the model process exits, the controller inventories the final workspace and
reads the candidate receipt directory **before** running either independent oracle.
A candidate's final-byte test obligation is met only if a recorded check has:

- `ok: true`, integer exit code zero and exactly 17 executed tests;
- no timeout, the pinned PHPUnit hash and unchanged-fixture status;
- before and after inventories that both equal the final workspace inventory.

Zero tests, failed tests, a check that mutates files, or a successful check followed
by another edit does not meet that obligation. Empty candidate receipts remain an
unverified result even if the controller's later test succeeds. Receipts are
observations from a trusted experimental checker, not an adversarial sandbox or a
cryptographic attestation against a malicious candidate.

The independent exact-byte oracle verifies the requested rename and preservation
of all other fixture bytes, allowing only the frozen initial configuration file.
The controller separately reruns the existing behavior checker without a receipt
directory; this later run cannot create candidate verification credit. Original
assertions must survive the exact-byte oracle even when weakened tests would pass.

Report these outcomes separately:

- exact rename/file-scope correctness;
- independent hidden behavior result on unchanged final bytes;
- candidate-performed successful verification of those final bytes;
- normal CLI/native completion, separate from oracle correctness;
- overall success, requiring all of those conditions.

A terminal model error, refusal leaving the requested edit undone, unexpected CLI
exit or timeout cannot be disguised by a passing post-run oracle. Candidate repairs
and repeated checks remain in the measurements rather than being replaced by a
clean rerun.

## Freeze, execution and accounting

Preparation requires clean committed controller source, installed runtime vendor
dependencies, the pinned Phpactor PHAR and pinned PHPUnit PHAR, and a local clone
containing the exact public Git objects. The exporter reads fixed `git show` blobs;
it does not rely on an upstream archive that may exclude tests. Preparation makes
no model calls and creates all thirty workspaces before execution.

Freeze controller/engine source and vendor hashes, both PHARs and their digests,
source provenance, all prompts/wrappers, initial non-Git manifests, task metadata,
schedule, model, CLI version and PHP/Python interpreter identities in a hash-bound
configuration. Source Git metadata
does not enter candidate inventories. A candidate may not read controller, receipt,
state or answer files; the named wrappers are the authorized external entry points.

```bash
python3 benchmarks/symbol-intent/real_pilot.py prepare \
  --output /tmp/php-real-verification-pilot \
  --source-repo /absolute/path/public-nr-llm-clone \
  --phpactor /absolute/path/phpactor.phar \
  --phpunit /absolute/path/phpunit-12.5.31.phar
python3 /tmp/php-real-verification-pilot/source/benchmarks/symbol-intent/real_pilot.py run \
  --output /tmp/php-real-verification-pilot --execute-models
python3 /tmp/php-real-verification-pilot/source/benchmarks/symbol-intent/real_pilot.py summarize \
  --output /tmp/php-real-verification-pilot
```

The independent design/code review and a dry preparation precede model execution.
Run only the frozen controller copy. It validates source, vendor, PHARs, prompts,
wrappers, exact CLI version and PHP/Python runtime identities before and after each
candidate. A started campaign
cannot silently resume or rerun a candidate. A future amendment must retain the
original artifacts and document its scope before more model execution.

Use `claude-haiku-4-5-20251001`, no effort flag, Bash/Read/Edit/Write, safe mode,
empty settings and MCP, disabled slash commands and no persisted sessions. Native
initialization must confirm model and isolation. These are context controls, not an
OS sandbox. Reuse the existing capture/environment/native-accounting helpers; the
dedicated controller never patches the older graders or changes older campaigns.

The campaign allowance is USD 8 at native list prices, with a USD 0.50 per-run CLI
budget and a 120-second process deadline. Reserve a full run budget before each
start. Stop on capture, accounting, integrity, evaluation or timeout errors, an
unexpected CLI process exit, or an observed cap overrun. Preserve every started
attempt and its raw evidence. These are planning controls, not guaranteed provider
billing limits or subscription charges.

Retain all native JSONL, stderr, argv, process measurements, receipts, initial/final
hashes, diffs and independent oracle outputs. Report whole-call token vectors
(fresh/cache-read/cache-created input and output), whole-call list-price cost,
visible primary-model rounds, calls and candidate wall time. Native turn counts
remain a separate field. Do not double-count thinking tokens.

`real-summary.json` contains three cell distributions and within-repetition paired
deltas for AST/manual minus text/manual and AST/integrated minus AST/manual.
`real-runs.json` retains individual outcomes and raw measurement references. Missing
accounting stays unknown; failed candidates are retained in denominators. Paired
effects contain observed pairs only: an attempted but incomplete arm remains in
the ledger and produces null deltas, while an unattempted arm cannot form a pair.
The frozen schedule retains every planned ID, including unattempted candidates.
Behavior check counts and summed checker-measured duration come from candidate receipts.
Controller-only checking is excluded from candidate wall time and receipt totals.
Checker duration is not total tool-execution duration; no API-time subtraction is
used to invent orchestration time. Preserve unexposed native timing as null.

Ten repetitions estimate variability for this one extraction. They do not establish
general performance on other refactorings, complete applications, inheritance,
dynamic calls, framework configuration, other models or a broad production corpus.
Judge efficiency alongside actual final-byte verification, preserved code and final
response accuracy. Inspect native traces for adherence and unsupported claims before
publishing an interpretation of the numeric differences.
