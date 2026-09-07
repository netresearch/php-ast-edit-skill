# Independent native-trace audit: runs 024–027

Campaign: `/tmp/php-real-verification-pilot-20260907`.
Read-only audit of the existing `native.jsonl` and `measurement.json` files.
No model, mutation, checker, oracle, export, or summarizer was invoked.
Line references below are physical one-based JSONL lines in each named run.
Tool IDs are unique native `tool_use` IDs, not response/message counts.

## Findings

| Run | Arm | Native tools / error flags | Behavior checks | Readbacks after passed behavior check | PHP mutation route |
|---|---|---:|---:|---:|---|
| 024 | text-manual | 13 / 1 | 1 | 0 | Three successful Edit calls, one per target site |
| 025 | ast-integrated | 1 / 0 | 1, integrated | 0 | One provided rename-tool invocation, three edits |
| 026 | text-manual | 13 / 2 | 1 | 1 grep | Three successful Edit calls, one per target site |
| 027 | ast-manual | 6 / 0 | 1 | 3 full-file Reads | One provided rename-tool invocation, three edits |

- All four measurements report exact-scope correctness, hidden behavior success,
  candidate final-byte verification and overall success. Native results show the
  three intended edit sites and a passed supplied checker. This audit did not
  independently rerun the hidden oracle or PHPUnit.
- No PHP repair, edit retry, fallback text mutation in an AST arm, or duplicate
  behavior-check invocation occurs in these four traces.
- The three native error flags correspond to actual usage errors: one malformed
  grep command in 024, and a directory Read plus a malformed grep in 026. Both
  grep failures are `ugrep: invalid option` with exit **2**, caused by a leading
  `->` pattern without `-e`/`--`. None is a legitimate no-match exit 1.
- Run 024 also performs one changed-name grep after successful Edit results but
  **before** its behavior check (line 53). Keep this separate from the explicit
  post-test readbacks in 026 and 027.
- Final 17-test/20-assertion counts are correct wherever given. Reported
  93.643 / 94.692 / 94.782 ms values reproduce the checker JSON exactly; these are
  checker wall durations, not end-to-end candidate durations or isolated PHPUnit
  execution timings. No final mislabels them as whole-candidate timing.
- AST finals 025 and 027 do not repeat the tool's `completeness: unknown` caveat.
  They use unqualified task-completion language, but neither explicitly claims a
  universal resolver completeness guarantee or support for the full TYPO3 repo.
  The completed task is in the extracted workspace and the hidden outcome agrees.
  Record this as omitted limitation language, not demonstrated incorrect code.

## Run 024: every tool call

| Call line → result line | Tool ID | Action and observed result |
|---|---|---|
| 7 → 8 | `toolu_01LZyGvTDxoZYnh7wqvjDZbv` | Bash `find ... -name "*.php" \| head -20`; lists the fixture files, success |
| 12 → 13 | `toolu_01TyDwBdwAYhp1VLF8q9ix9d` | Read classifier declaration source, success |
| 14 → 15 | `toolu_0181mLZ7QQtGdtTKuugndEsH` | Bash grep pattern starts with `->classify`; actual exit 2, invalid option, `is_error:true` |
| 19 → 20 | `toolu_01QdRVm2u5SPVoLgPrDJU618` | Corrected `grep -r "classify"` with filters; finds production caller, success |
| 24 → 25 | `toolu_01LtLPJjspKXnXqQURUJuo2o` | Read coercer source, success |
| 26 → 27 | `toolu_01VEoWmMPnxzcmmG7V8CfEVD` | Read direct classifier test, success |
| 32 → 33 | `toolu_01LgN8cwPi3MiPz4m3Co5tS6` | Read coercer tests, success |
| 37 → 38 | `toolu_01QBnzwvDwaL6h9vrbHA3utq` | Bash full `classify` search, success |
| 43 → 44 | `toolu_01JGDJSsK1oG6qdrjR3CHXda` | Edit classifier declaration `classify` → `controlType`, success |
| 45 → 46 | `toolu_01EdjNfm5u7PxbxicPA21y3K` | Edit coercer method call, success |
| 47 → 48 | `toolu_01TKgC878TfPbYpH5imVpd4V` | Edit direct test method call, success |
| 53 → 54 | `toolu_018t9LhpENewxj7eeVYo52wP` | Bash grep `controlType\|classify` over the three changed files; mutation readback before checker |
| 60 → 61 | `toolu_01HshuAH9KUi2478QA7XScek` | Supplied `check-tests`; ok, exit 0, 17 tests, 20 assertions, 93.643 ms |

Final text is native line **65**. It correctly identifies declaration line 41,
production call line 61 and test call line 28, with three changed files/sites.
It reports exactly 17 tests, 20 assertions, return code 0 and 93.643 ms.
Its scope is expressly “all its callers within the workspace.” The assertion
that all other bytes were preserved is consistent with the three exact Edit
requests and the independent measurement's oracle; the behavior checker alone
does not establish that stronger byte claim. No commands follow the passed
checker, only the final response.

## Run 025: every tool call

| Call line → result line | Tool ID | Action and observed result |
|---|---|---|
| 8 → 11 | `toolu_01WNtD11f85ahEqC5Cope1oV` | Provided `rename-tool --file Classes/Service/Tool/SchemaPropertyClassifier.php --select method:SchemaPropertyClassifier::classify --to controlType`; one successful AST mutation transaction and integrated checker |

The result reports 3 edits across exactly the expected 3 files, parser/lint
passed for all three, PHP lint version 8.5, `checksPassed:true`, project
verification `check-tests` ok, and exact byte-match over all 9 non-Git workspace
files. It also reports `completeness:"unknown"` and the unresolved-reference
warning. Native output does not separately print the integrated checker's
17/20 JSON, but the supplied checker's contract requires all 17 tests and the
recorded measurement confirms one passed final receipt (96.654 ms).

Final text is native line **16**. Its three-file count, parser/lint counts,
PHP 8.5 lint claim, exact-byte result and successful configured verification
are supported. “Test callers updated” is loose plural wording for one direct
test call site, not an explicit incorrect numerical count. The final says
“complete and verified” without retaining the completeness limitation; see
the distinction in the findings above. No extra readback, test repetition,
manual PHP edit, or repair follows the tool result.

## Run 026: every tool call

| Call line → result line | Tool ID | Action and observed result |
|---|---|---|
| 8 → 9 | `toolu_01AfWpt839rqoTSdvsNa2r8y` | Read workspace directory as a file; actual `EISDIR`, `is_error:true` |
| 11 → 12 | `toolu_01XNZcuH15ohCbCsm7Eer6eS` | Bash find classifier file, success |
| 14 → 15 | `toolu_01YXZTJJceKLpHyjg2tAbU8X` | Read classifier source, success |
| 19 → 20 | `toolu_01Tu74tRtAupJyGALohsGxAw` | Bash grep `"->classify("`; actual ugrep invalid option / exit 2, `is_error:true` |
| 22 → 23 | `toolu_01TPv9NmMSAm43QME9ZijJbd` | Corrected grep `"classify("`; all target matches returned |
| 27 → 28 | `toolu_01Vyfk7qkEcSDakjAFETuLQw` | Read coercer source, success |
| 30 → 31 | `toolu_01WaJtcMcpUnAK3mHwZgVqB3` | Read direct classifier test, success |
| 35 → 36 | `toolu_016STPmfxvxfoJtTB8hnhJiZ` | Filtered grep finds production caller, success |
| 41 → 42 | `toolu_01CLJkbYwBmmcnZyR1xJ8yfb` | Edit classifier declaration once, success |
| 46 → 47 | `toolu_01XnuEVRBa5LHZg7YXZvpip2` | Edit coercer call once, success |
| 51 → 52 | `toolu_01B9V66mwyiTr7G9xK7dw9br` | Edit direct test call once, success |
| 57 → 58 | `toolu_01De4C1kgg9GB4xEp8wY64fd` | Supplied checker; ok, exit 0, 17 tests, 20 assertions, 94.692 ms |
| 63 → 64 | `toolu_019bnQWQ2DyYLzvGwDqkpBuZ` | After passed checker, grep `controlType` in all three changed files; unnecessary readback, no mutation |

Final text is native line **68**. Three named edit sites and line numbers,
17 tests, 20 assertions, exit 0 and 94.692 ms are all correct. The final-byte
test obligation remains satisfied because the post-check command only reads.
The final preserved-byte claim is consistent with the exact edits and recorded
hidden oracle, while the checker itself only proves behavior and its own
pre/post inventory equality. No failed edit or code repair occurred.

## Run 027: every tool call

| Call line → result line | Tool ID | Action and observed result |
|---|---|---|
| 8 → 9 | `toolu_011GqqfW3z5ZAkUB9emZiGX5` | Bash find PHP fixture files, success |
| 13 → 16 | `toolu_014hYmPPfekH49dvzGrAXbfL` | Provided rename-tool; 3 edits / 3 files, parser/lint passed; configured checks correctly reported `not_run`, verify list empty |
| 22 → 23 | `toolu_01C7UAcgehw5DEw4xM1tLEDX` | Supplied manual checker; ok, exit 0, 17 tests, 20 assertions, 94.782 ms |
| 28 → 29 | `toolu_01UfWarFtEU8SpGc31RwZDUc` | Read complete classifier source after passed AST and behavior checks |
| 30 → 31 | `toolu_01MxkPLzUVQEXQLSh9rr8SP3` | Read complete coercer source after passed checks |
| 32 → 33 | `toolu_01AqBzbxByGjUA8cgZmt3UQ6` | Read complete direct classifier test after passed checks |

All PHP mutations use the provided AST route; the following three Read calls
are redundant confirmation of unchanged final bytes, not repairs or tests.
The AST result's `checksPassed:null`, `checks:not_run` and empty `verify` are
handled correctly by subsequently running the required manual checker once.

Final text is native line **38**. Counts of 3 edits / 3 files and 17 tests /
20 assertions, checker exit 0 and 94.782 ms match the trace. “Test Method” is a
heading, but its body correctly says the *call* changed; the test method's own
name was not renamed. The exact-byte guarantee is scoped to the tool's actual
reported name replacements. “All validation checks passed” can accurately
describe the final combined AST-plus-manual-check state, although the AST result
itself had configured checks not run. The completeness limitation is omitted
from the final, as in run 025; there is no explicit universal claim.
