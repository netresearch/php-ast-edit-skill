# Read-only native audit, runs016–030

The frozen campaign and candidates are unchanged. This review distinguishes correct
source/test outcomes from tool adherence and final-response claims.

## run016 — AST integrated

One Bash mutation call (`toolu_011an4cim5GQHiezAryX7oDL`), no follow-up reads or
manual check. One successful candidate receipt matches final bytes. Final correctly
distinguishes one declaration and two caller references, 17 tests, PHP 8.5 and exact
byte scope. No factual or route finding in the observed trace.

## run017 — text manual

Three successful individual Edit calls; no PHP repair loop. Three leading-dash
grep option errors (native lines16,19,66) and two additional native error flags
for expected no-match exit1 checks (69,74). These are different categories; five
native error flags do not mean five broken edits. One successful behavior check
at53 followed by six source-search calls. Final78 reports the correct three
changes, 17 tests/20 assertions and 95.874ms test duration. Route respected.

## run018 — AST manual

Read(directory) EISDIR at9, then ordinary discovery and one AST write. Three
changed-file Reads after exact-byte success, one subsequent behavior check. Eight
calls, one native error, one successful final-byte receipt. Final45 counts/tests
are accurate; 'all existing functionality is preserved' is broad assurance beyond
the named test coverage. No PHP repair or forbidden mutation.

## run019 — text manual

Three individual successful Edit calls, no PHP repair. Two leading-dash grep
errors: line16 is masked by `| head`, line76 is marked native error. The final
grep pipeline returns no matches without a native error flag. One behavior check,
then five search calls. Final84 correctly describes the changed identifiers and
17 tests/20 assertions. Native failure count is1, while two actual option errors
were visible. No route violation.

## run020 — AST manual

Two calls: AST write then provided checker. No failures or additional readbacks.
Final22 correctly distinguishes declaration/callers and reports 17 tests with
20 assertions, parser/lint and exact-byte evidence. One final-byte receipt.

## run021 — AST integrated

One AST call, no separate check or readback. Accurate final15 describes byte
preservation and the 17-test check. No failed call or mutation-route issue.

## run022 — AST manual

Seven calls: initial source/discovery, rename, one checker, then three full
changed-file Reads. No errors or duplicate behavior check. Final41 gives accurate
three positions, 17 tests/20 assertions and95.257ms. Post-pass reads reconfirm
already reported byte evidence; no PHP repair.

## run023 — AST integrated

One AST call already executes the configured checker, then three Reads and a
second manual checker (`toolu_01NZF3SbUipogDd9iJ7CCiXZ`, line30). Both receipts
match final bytes. Final36 attributes resolution of 'all references' to the AST
command despite its explicit completeness-unknown result. Counts/test assertions
are accurate; no PHP repair or forbidden mutation.

## runs024–027

Separately reviewed read-only in php-real-audit-24-27.md.

## run028 — text manual

Read all six PHP files, then three successful individual Edit calls (52,54,56).
No PHP repair. Invalid leading-dash grep at16; repeated invalid grep at70 is
masked by `|| echo` claiming no old calls. Later valid searches inspect both old
text and new method. One behavior check; final84 counts, positions and rounded
94.5ms duration agree with actual evidence. Byte/scope oracle passes.

## run029 — AST manual

Two calls: AST then checker. No errors/readbacks/duplicate tests. Final22 correctly
counts17tests/20assertions, but says the tool 'resolved all references' despite
reported unknown completeness. The actual fixture's three edits are correct.

## run030 — AST integrated

Seven calls: initial Read/discovery, AST, three post-write Reads, second manual
checker (`toolu_01TzTdmQFqwfHhiMU59MQ4Ms`, line36). The AST call already ran the
same checker; both receipts certify identical final bytes. Final42 says final
test execution 'confirms all functionality is working correctly', broader than
the supplied17-test coverage. Concrete positions/counts are correct. No PHP repair.
