# Independent entrypoint evidence export review

**PASS — no actionable export finding.** Reviewed
`/tmp/php-entrypoint-export-20260907` against the original completed campaign at
`/tmp/php-entrypoint-pilot-20260907`. No model, PHPUnit checker, source mutation,
campaign runner or campaign write was executed.

The verifier embedded in the archive was read and executed independently. It
returned `ok: true`: 20 native ledgers, 20 known pre-call observations, 20 correct
exact-scope results, 20 candidate-verification outcomes and the complete regenerated
summary match. All 28 archived frozen source files match their recorded hashes.
The four outer `SHA256SUMS` entries independently pass.

Archive SHA-256:
`fb5d337f2b48f40181b85dbeaf2150f9b571178a67be63660f3348095eade416`.

Additional checks independent of the embedded verifier:

- The archive has exactly **617 unique regular files**, with safe relative paths,
  and every member matches its manifest hash. Its **615 campaign-derived members
  match the original campaign bytes exactly**; the other two members are the
  embedded exporter and verifier. Native transcripts, prompts, measurements,
  initial/final inventories, receipts and resolver evidence are preserved.
- The original campaign's full **2,063-file source/dependency inventory** still
  matches `config.json` exactly, ignoring only the controller's documented
  `__pycache__` exclusion. Its source commit remains
  `793d8d596855c83eb6aaaf414ad86c64476ea034`, and the frozen configuration checksum
  matches. Publication has not substituted the working source for the measured
  snapshot.
- All twenty public fixture copies retain the exact pinned GPL license and
  provenance for `netresearch/t3x-nr-llm` commit
  `b505c936935b99baa3088ce62ad222d2ba61cee0`, including the excluded-caller notice.
  The archive also includes the engine/tooling MIT notice, documentation
  CC-BY-SA-4.0 notice and source README explaining the licensing split.
- Archive paths contain no Git metadata, vendor trees, PHAR binaries, private
  home-session directories, SSH directories or bytecode caches. Targeted content
  checks found no common Anthropic/OpenAI/GitHub credential or private-key patterns.
  Raw operational metadata, including temporary paths and native session IDs,
  remains present intentionally; this is not a claim that the archive contains
  no local path strings. The inspected native initialization has empty skills,
  plugins and MCP-server lists and `apiKeySource: none`.
- All twenty planned rows and **all ten within-repetition pairs** are present;
  no unattempted IDs are reported. Independently recomputed token, pre-call and
  candidate-wall-time pair deltas agree. The compact run016 outlier remains in
  both the raw records and comparisons.
- Every run's combined token count equals fresh input + cache-created input +
  cache-read input + output. Thinking is already included in output and is not
  added twice. Arm totals are 171,892 compact versus 158,015 intent-first tokens;
  arm medians are **12,151 versus 12,426.5**. The lower treatment aggregate does
  not imply a lower median or satisfy the prospective adoption rule.
- Pre-call medians remain **0 versus 0**, with totals four versus one. Candidate
  wall-time medians independently match **16,553.585 versus 17,138.146 ms**.
  Checker durations are separate observed receipt measurements. Native total
  tool-execution time remains unknown; no fabricated orchestration duration was
  introduced into the exported summary.

The verifier checks stored independent PHPUnit outcomes against final manifests;
it does not rerun PHPUnit, whose pinned PHAR is intentionally excluded. This review
does not replace the separate manual audit of all native calls and final claims,
and it does not establish held-out task performance or resolver completeness.
