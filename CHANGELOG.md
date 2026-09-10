# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `set_name` on a method declaration that the project calls by name is refused with the call count and the `rename_method` edit that renames the declaration and its callers, ready to copy; `"declarationOnly": true` (`--declaration-only`) keeps the declaration-only change. A gated run renamed a public method with 29 callers that way, the project's analysis failed on every caller, and the run renamed them by hand in 51 tool calls.
- An apply whose project-wide rename left string literals reading the old name says so first, in `open`, in every report mode. A gated run received 67 listed mock literals, saw the analysis pass and stopped, and 174 unit tests failed: static analysis does not read strings.
- A `match` that finds nothing while its replacement already stands in the scope is a reported no-op — `replaced: 0`, `alreadyPresent` — rather than a refusal. Four of eight gated runs asked `rename_method` to rename the call sites and then asked for the same rename by `match` in the same transaction.
- `add_member` with a member as its target puts the new member directly after that one. Measured, a caller selected the method it wanted the new one beside and was refused for not naming the class. A `position` beside a member target is refused rather than ignored.

### Added

- **`rename_method` renames across the project.** A public or protected method of a class that can be extended, or any method of a class with a parent, an interface or a trait, was refused — 180 of 274 methods in the measured TYPO3 extension. Named by selector, such a method is now renamed at every declaration and call site through the hierarchy: the hierarchy from the project's sources and Composer's class tables, the call sites from Phpactor 2026.07.22.0, pinned by digest and set up through `"phpactor"` in `.php-ast-edit.json` (`doctor` reports it). In that extension 221 of the 235 non-magic methods can now be renamed; the other 14 implement a vendor or PHP contract and are refused, as are calls Phpactor cannot attribute, a missing ancestor and a taken name. Mentions outside PHP — YAML, TypoScript, Fluid property reads such as `{credential.uid}` for `getUid()` — are listed under `renames.notRenamed`, not changed.
- `rename_method` across the project lists the PHP string literals that read the old name under `renames.literals` — a PHPUnit `->method('getConfiguration')`, a callable — grouped by file and declaration, with the `select` that one `replace_expression` with `match` takes to set all of an entry, and each literal's ref for `set_string` where only some mean the method. Renaming a service getter in the measured extension left 67 such mocks in nine test files unlisted, and 174 of its 682 unit tests failed; with the list, one follow-up `apply` of nine edits brings the suite back to green. They are listed, not changed: which class a string names is not known.
- `apply` says when its project checks make a rerun redundant: `alreadyRun` names every `scope: "project"` command that passed on the files as written, in every report mode. On a three-change task the gated arm ran the project's own analysis by hand after such applies anyway — 303 seconds of tool time across eight sessions against 171 without the skill.
- **`replace_expression` and `replace_statement` take a `match`.** With it, the target is a scope — `method:RateLimiter::resetLockout` — and every expression or statement inside it that is the same code as `match` is replaced, each with its own copy of `php`; the effect reports `replaced`. The comparison is structural, so spacing and quoting do not matter. Across sixteen gated agent sessions on a three-change task, "inside this method, replace X with Y" was tried five ways and refused each time; the engine took it only through `inspect` and a line and column, and 54 of 98 `apply` calls were refused. `--match` carries it in the flag form.
- `set_docblock` and `update_docblock` are taken as `set_doc_comment`. And an edit that lacks exactly one required argument while carrying exactly one field its operation does not take is read that way: `rename_method` with `new_name`, `set_doc_comment` with `docComment` or `php`. The engine refused these while quoting the field back in the refusal. Two unknown fields, or a missing argument with nothing to fill it, are still refused.
- The flag form reads a lone unknown flag the same way: `--op update_docblock --text …` is `set_doc_comment` with `--value`. `contexts --operation` answers for a synonym as `apply` does.
- A selector qualified with the file's own namespace — `method:Vendor\\Service\\RateLimiter::reset` — resolves like the short name. A different namespace still matches nothing.
- A class member written where a statement goes is refused with the operation that takes it: `add_member` on the class, or `parseAs: member`.
- `apply --input /dev/stdin` reads standard input like `--input -`. A heredoc caller spells it that way, and a sandbox may have no such path while standard input is readable.

### Fixed

- **`replace_statement` no longer accepts a declaration.** A method, property or class is a `Stmt` to the parser, so the class check let the operation swap one for a statement; the file then failed only at the reparse gate with a syntax error on a line the caller never wrote. It is refused before mutation, and the refusal shows the `match` form.

## [0.8.0] - 2026-09-10

### Changed

Two behaviours of `apply --file` changed. A caller that scripted against the old ones will notice.

- **A failed project check now exits 1 through the flag form too.** It returned 0 while its own JSON body said `checksPassed: false`. `help` and the 0.7.0 notes had promised exit 1 since the checks landed; only the JSON form delivered it.
- **A flag the chosen form cannot carry is refused instead of dropped.** The option parser accepts `--anything value`, so `--sha256`, `--report`, `--mode` and typos were taken and silently ignored. `--sha256` and `--report` now reach the document; everything else is refused by name, and the refusal says which kind of wrong it is — a flag belonging to the other form, a per-file setting only the document can carry, or no such flag.

### Fixed

- The flag form of `apply` now answers exactly as the JSON form does. It returned exit 0 over failed project checks while reporting `checksPassed: false`, and silently dropped `--sha256` and `--report`, which the option parser accepts under any spelling — a supplied file guard never ran and the caller was told the edit was clean. Both flags now reach the document, both input forms share one execution and one verdict, and a flag the chosen form cannot carry is refused instead of dropped.
- Resolve imported symbol-table function aliases before variable renames, and conservatively refuse `call_user_func()` and `call_user_func_array()` in affected scopes to prevent behavior-changing renames.
- Reject variable renames that collide with local, parameter or captured bindings, or depend on unsafe dynamic scope. Refuse ambiguous inherited method renames, case-insensitive destination conflicts and unsupported late-static dispatch; preserve parent calls and nested lexical scopes.
- Load Composer consumer autoloaders, including custom vendor and binary directories. Prevent a standalone skill wrapper from invoking itself recursively.
- Preserve formatter, verification and custom JSON settings during normalization. Enforce supplied SHA guards on create-overwrite and restore file contents, permissions and symlink identity after failed transactions.
- Reject PHP compile errors before writing and after formatting when the host runtime can check the target. Report `parsed`, `validation.lint` and `validation.checks` separately; `valid` remains a deprecated parser-only compatibility alias.
- Preserve multiple warnings in `warnings`; retain the combined legacy `warning` field. Reset verification state between transactions. Failed project checks now return exit 1 while retaining the edit; transaction failures still return exit 2.
- Make the documented quickstart executable, correct source/Composer installation paths, and remove obsolete normalization flags and the misleading post-edit clean-tree gate.

### Measured

- **Recommending `report: "agent"` as the default was measured and withdrawn.** Twelve sessions against `b1b79e6`: Sonnet paid +71% tokens, +67% model rounds and +89% list price for the recommendation; Haiku was unaffected. The mechanism is in the traces — the mode withholds the diff, `SKILL.md` said where to fetch it, and Sonnet fetched it in 3 of 3 runs against 0 of 3 in the control. `SKILL.md` now names the case the mode is for rather than prescribing it. The mode itself is unchanged, and the run is its worst case: with no declared checks, every field that distinguishes it was empty. See [`benchmarks/agent-economics/results/2026-09-10-agent-report`](benchmarks/agent-economics/results/2026-09-10-agent-report/REPORT.md).
- The published figures of the 2026-09-07 comparison now recompute in the test suite from the report's own tables, including the distinction between the median comparison (−90.2%) and the comparison of summed tokens (−83.2%), and the decomposition showing 92.6% of the reduction is cache-read.

### Added

- `report: "agent"` names every verification execution in `verifications`, passing ones included — `id`, `scope`, `cwd`, `command`, `ok`, without output. With the per-file `checkIds` and `afterSha256` already in the response, that is the whole proof a caller needs to decide whether a check it already ran must run again: which command, where, over which files, at which bytes. `proofExcludes` names what the engine cannot see and therefore does not account for — `dependencies`, `checkToolVersions`, `runtime`, `environment` — because a reuse key missing those answers `passed` when it should not. No schema bump: added fields do not change what the existing ones mean.

- Optional `report: "agent"`. The decision-shaped projection: `outcome`, a `checks` tri-state where `none_declared` is not `passed`, the output of failing checks only, and a per-file `open` list naming what the write did **not** establish — remaining occurrences, unresolved receivers, callers `rename_method` cannot reach, syntax unconfirmed on a newer target, a repository that declares no checks. It carries no `diff`, no generated `code`, and neither of the legacy `warning`/`valid` duplicates; `git diff -- <path>` has the diff, from the snapshot `beforeSha256` names, and a file outside version control is the one case that loses information. Versioned by `reportVersion`, which `full` and `compact` deliberately do not carry.

- **One edit against a named target is one call.** `apply --file F.php --select method:Foo::bar --op rename_variable --from nonce --to nonceValue` — no payload file. Measured across controlled runs, every edit cost two calls, one writing JSON to a temporary file and one applying it; that was the last fixed overhead the tool imposed on the simple case. The operation's own arguments become flags, and `contexts` says which each takes. Several edits, or several files, still go through JSON on stdin, which is what that form is for.

- Optional `report: "compact"` Apply responses emit each verification run once with per-file `checkIds`; the default `full` response preserves the existing per-file contract. The experimental adapter requests compact reports automatically; frozen benchmark evidence is unchanged.
- Explicit `project` and `changed_files` verification scopes. Project commands use stable configured paths and run after deletions; legacy argument arrays keep changed-file behavior. Each configured entry remains a distinct execution, with configuration and exclusions captured before writes.
- Isolated runtime-only PHAR builds, engine-bundled skill/plugin archives, dependency manifests, signed checksums and provenance. Clean installation and extracted-artifact tests run on PHP 8.2 and 8.5 before release publication. Historical release assets remain unchanged.
- `contexts --operation NAME` for a compact single-operation contract, plus shorter selector-first skill instructions with optional canonical mode.
- Outcome and routing evaluations, executable task oracles, actual model-run evidence import, and a reproducible CLI benchmark comparing both batched AST edits and batched contextual patches with lint.
- The documented apply examples in `README.md` and `SKILL.md` now run in the test suite and are checked against the guidance around them; the skill had recommended one report mode twenty lines above an example using another.
- Installation, FAQ, limits and alternatives documentation, with explicit distinctions between parsing, lint, behavior, local timings and measured model usage.

### Measurement note

The historical figures below come from reported controlled runs comparing successive tool builds. The [v0.7.0 release](https://github.com/netresearch/php-ast-edit-skill/releases/tag/v0.7.0) describes twelve separate agent processes and per-run JSON accounting. Publicly inspectable paired raw runs and complete harness configuration have not been located in the inspected release assets, source tree or linked PRs. This does not establish that the authors failed to retain them. These observations are useful development evidence; they are not a reproduced comparison against a competent contextual-patch baseline or general savings claims. The new benchmark protocol records failures, model settings, native usage and independent outcomes before publishing such a comparison.

## [0.7.0] - 2026-09-06

### Added

- **`rename_method` moves a declaration and the calls to it in one edit.** `method:` finds a declaration; renaming it left every `$this->old()` behind, so the caller went hunting — measured, four `inspect` calls spent locating call sites before anything could be written. What counts as a call to *this* method is decided structurally rather than by name: `$this->`, `self::`, `static::` and `parent::` inside the declaring class. A call on any other receiver may belong to a different class that shares the name, so it is counted and left alone; `otherReceivers` in the report is the number that says whether anything is left to do. On `ChallengeService`, renaming `getNonceCacheKey` is now one call: declaration and both call sites, `otherReceivers: 0`.
- **An incomplete rename is warned about, not only counted.** The number was already in `effects`, and a model read `remainingInFile: 2` and stopped anyway; a count nested in a per-edit record is easy to walk past. The report now carries `INCOMPLETE_RENAME` beside the result. The tool cannot make a caller act on it, but it can stop the omission from being quiet.

- **A repository can declare the checks it wants run, and `apply` runs them.** `verify` is the same shape as `formatter`, a list of commands with `{files}`, executed after it on what will be committed. Measured on a controlled run: a model that had just made a correct four-line edit then spent twelve calls on `validate`, PHPStan four times, the coding-standards check twice and a `git diff` — a quality gate nobody asked for, assembled by reading `composer.json`. A failing check does not roll the write back; the code is written and it parses, and what failed is an opinion about it, so the output comes back and the caller decides. The report also carries `valid`, since the write already parsed what it produced.

- **The write reports what it did, so nothing has to be read back.** `effects` carries a per-edit outcome — for `rename_variable`, how many occurrences moved and how many of the old name the file still holds — and `diff` shows the change itself, up to 200 lines. Measured on a controlled run: after a successful rename the model spent a `grep`, two `Read`s and a `tail` establishing what had happened, and sent a second `apply` because nothing had told it a third scope still carried the name. All three questions are now answered by the write. In the runs since, the model still reads the file once at the end out of habit, so the saving is in what it no longer has to work out rather than in the call count.

### Added

- **The catalogue publishes what each operation takes, and a misfiled edit is told.** `contexts` listed operation names and nothing else, so a caller reading it had to guess the argument names — and guessed by analogy with whatever it had seen last. Measured on a controlled run: asked to rename a variable, a model sent `expect` and `value`, which is `set_name`'s shape, three times over. Each attempt met `Expected node name $nonce, got createChallengeToken` — true, and no help at all. Four of its six `apply` calls failed on the contract rather than on the code; it then abandoned selectors for hand-guessed refs and renamed one scope at a time, leaving two of eleven occurrences behind. `contexts` now carries `operationArguments`, the check runs before the target's `expect` so the message is about the edit rather than the node, and `tests/catalog.php` requires an entry for every dispatched operation. The message shows the edit rather than listing field names — naming them was not enough: told `rename_variable requires "from" and "to". This edit carries value.`, the same model put `from` and `to` *inside* `value` and met the error again. The same run repeated against each build: **15 turns and 9 of 11 occurrences renamed, then 13 turns and 11 of 11, then 6 turns with no failed `apply` at all** — the model reads `contexts` up front and writes the payload correctly the first time. Cost per run fell from $0.375 to $0.244.

### Fixed

- **`property:` finds promoted constructor properties.** It matched `Stmt_Property` only, which in a modern extension is the exception: measured on `netresearch/t3x-nr-passkeys-be`, **58 of its 65 properties are promoted** and 7 are declared in the class body. Naming a dependency therefore fell back to a `ref`, which has to be read out of an `inspect` first — the coordinate hunt the selector exists to remove, reappearing on the most common target in the codebase.

## [0.6.1] - 2026-09-05

### Fixed

- **`parseAs: "stmts"` accepts more than one statement.** It was mapped straight onto `stmt` and then met the single-statement check, so the context could not do the one thing its name promises — and `operations.md` had been documenting "one or more `Stmt`" for it all along. Found by hitting it: inserting a guard, an assignment and the `if` that reads it, took two edits, and the second shifted the index the first had just moved, so they landed in the wrong order and had to be repaired. `stmts` is now `stmt` with the arity relaxed, and the `stmt` error names it.

## [0.6.0] - 2026-09-05

### Added

- **`doctor` reports the declared formatter, and says so when there is none.** A repository normalised before 0.5.0 has every other part of the contract and still leaves an edit halfway: the fixed point belongs to the printer and the project formatter together, so `apply` without a declaration stops after printing. That case is now `warn` rather than `ready`, with the command to add and a note that `--path-mode=intersection` is not decoration — php-cs-fixer defaults to `override`, which ignores the config's own Finder as soon as paths are named, so the project's exclusions would stop applying exactly when a tool starts naming files. `declaredFormatter` carries the declaration in the report. The command it suggests is derived from what the repository actually carries — the formatter `doctor` detected, its configuration path, and composer's own `bin-dir`, which a TYPO3 extension commonly moves to `.Build/bin` — rather than named from one project's layout.
- This repository declares its own, and its `doctor` says `ready`. Adding a method to `src/Doctor.php` is one call: 6 changed lines, formatter run included.

- **A `switch` arm can be written through the tool.** `parseAs: "switch_case"` parses `case 1: …;` and `default: …;`. It was missing, and the gap was found by hitting it: `rename_variable` shipped in 0.5.0 as a guard ahead of the dispatcher rather than a `case` in it, because a `case` could not be written at all — the one thing this tool exists to make unnecessary. It is a `case` now, written through the new context, and the special-case detection `tests/catalog.php` had grown to recognise the workaround is gone with it.

## [0.5.0] - 2026-09-05

### Added

- **A target can be named by what it is.** `"target": {"select": "method:Foo::bar"}` — also `class:`, `interface:`, `trait:`, `enum:`, `function:`, `property:Foo::$bar` and `const:Foo::BAR`. A `ref` is exact and survives nothing: it has to be read out of an `inspect`, and finding the coordinate to inspect at costs its own round trips — measured against an agent working without the tool, locating a method by line and column took two to four calls before any edit was written. The owner may be left out where the file holds one class; an ambiguous selector is refused with the paths it matched, never resolved to the first hit.
- **`rename_variable` renames a variable throughout a scope in one edit.** It targets the method, function, closure or arrow function the variable lives in and moves `Expr_Variable` and `Param` nodes whose name matches exactly, so a property fetch, a method name and a string literal sharing the word are untouched by construction. Measured on `ChallengeService.php`, which holds 39 occurrences of "nonce" of which 11 are the variable: one `apply` with three selectors renamed all 11 and left `$this->nonceCache`, `getNonceCacheKey()`, `'nonce_'` and `'noncePrefix'` exactly as they were. Scope is respected rather than approximated: a nested named function, method or class body is not entered at all; a closure is entered only when it captures the name in `use`, and then the capture and the body move together; an arrow function captures by value on its own, so it is entered unless a parameter of its own shadows the name. `$this` is refused as either endpoint, and a `$$name` is left alone — its name is an expression, not a name.

- **`apply` finishes the file.** The fixed point belongs to the printer and the project's formatter together, so a write that stopped after printing left a shape nobody wants: adding one 9-line method to a canonical TYPO3 extension reported 34 changed lines, the remainder trailing commas and `declare` spacing that only the formatter restores — and the agent had to know that, and run a second command. A repository can now declare its formatter in `.php-ast-edit.json` and `apply` runs it on the files it wrote: `"formatter": ["php", ".Build/bin/php-cs-fixer", "fix", "--config=Build/.php-cs-fixer.php", "--path-mode=intersection", "{files}"]`. The same edit now reports 10 changed lines, and the diff is the 8 lines it added. The report carries `"formatter": "ran"` and `changedLines` describes the file that survives.
- The declaration is an argv list, never a command line: nothing goes through a shell, so a path with a space in it stays one argument and the declaration cannot chain a second command. `{files}` is a whole element and expands to the files the edit wrote — running the formatter over the tree would put unrelated files into the diff of whatever change happened to be made. A non-zero exit rolls the whole write back and reports what the formatter said.

### Fixed

- **`apply` honours the project's `exclude` list.** `format` and `normalize` read it when they collect files; an edit reaches a file by name and never collects, so an excluded file was printed canonically anyway. The exclusion is not a scanning convenience: a TYPO3 `ext_emconf.php` cannot carry the `declare(strict_types=1)` a formatter adds, because TER stops parsing it, so the project takes the file out of the reach of both tools. Setting `state` in that file reported 3 changed lines and dropped a blank line; it now reports 2 — the line the edit asked for — prints format-preserving, and says `EXCLUDED` with the reason.

## [0.4.0] - 2026-09-04

### Fixed

- **The printer keeps the paragraph breaks between statements.** A blank line an author put between two ordinary statements was the largest single share of what a canonical print removed — measured at ~45% — and no formatter rule puts it back: the break carries the author's paragraphing and nothing derives it, which `doctor` reported as unrecoverable. It is not, because the parser hands the printer the line each node starts and ends on. `pStmts()` now emits one blank line wherever the source had at least one, and drops the rest. Measured on `netresearch/t3x-nr-passkeys-be`: printing the whole tree and running the project's formatter left 17 removed blank lines across 10 files before this change and **nothing** after it, so a repository that declares itself canonical now actually sits on that fixed point and can gate it.
- **A node an edit brings in carries no source position, or the one it replaces.** A node parsed from a snippet starts at line 1, which the printer read as a large gap and answered with a blank line nobody typed: `replace_statement` on a one-line statement shipped a three-line diff, and `insert_before` at the head of a body left a blank line between the new statement and the one it precedes. A replacement inherits `startLine`/`endLine` from the node it replaces (`NodeLocation::replace()`, `replaceChild()`); an insertion has no predecessor and loses its position entirely (`insertBefore()`, `insertAfter()`, `insertInto()`), so it abuts its neighbours. Only the outermost node is affected — statements inside a snippet keep their lines relative to each other, so paragraphing written into the snippet survives.

### Changed

- `doctor` no longer reports a share that no rule reaches: with the paragraph breaks preserved there is none. The `unrecoverable` field stays, because callers read it, and says so.

## [0.3.0] - 2026-09-02

### Fixed

- **The printer measures the line, not only the list on it.** `pMaybeMultiline()` and `pParams()` are handed a comma-separated list and compare the budget against that alone, so a call or a signature came out on one long line whenever its list fitted the budget and the whole line did not — `return new JsonResponse(` and `private function verifyUsernameFirst(` were never counted. Measured on a 119-file extension re-printed at 120 columns: 203 of 477 over-long lines were calls, 35 were signatures. Every node that puts a list behind a prefix now prints, measures, and prints again with that list broken — 598 over-long lines before, 246 after.
- Attribute arguments had no width at all: nikic prints them with `pCommaSeparated()`, so `#[AsCommand(name: …, description: …)]` stayed on one line however far it ran.
- A declaration's rendering carries its body's line breaks, and attribute groups sit on their own lines in front of the signature. The measurement takes the line the list opens on rather than the first line of the rendering, which would be `#[Attr]`.
- The re-print is keyed on the depth of the node being printed. Keyed on a flag, the receiver of a chain consumed it and the short inner list broke while the long line stayed; keyed on the list itself, two empty argument lists compared equal — PHP compares arrays by value — and `$q->one()->two()` split an empty list across two lines.
- `pPropertyHook()` is the fifth printer that puts a parameter list behind a prefix and was not covered.

### Changed

- **Line width is the project's declaration, not this tool's.** It is read from `.editorconfig` — `max_line_length` under `[*]` or a section naming `php` — and `normalize --width` is gone. A repository that declares no width cannot be normalised: the printer would be breaking lines by a number nobody chose, which is exactly the decision that belongs to the project. `printWidth` in `.php-ast-edit.json` stays as the record of what the last normalisation ran at, so a repository declared canonical before this change keeps printing at that width and is told what to add.
- **`doctor` checks that the rules exist, not only that a formatter does.** Canonical printing removes blank lines, and part of that is restorable by rule. Measured on a 121-file TYPO3 extension whose formatting was clean beforehand: 22.9% of the removed blank lines preceded a member (`class_attributes_separation`), 7.0% the file head, 6.6% a docblock, 4.5% a `return` or `throw`, 2.7% a scope block (`blank_line_before_statement`) — **43.6% restorable, 56.4% not**, the remainder being the author's paragraphing before plain calls, assignments and comments, which no rule reconstructs. `doctor` names the rules a project is missing and what each recovers, and states the share that no rule reaches.
- Against intuition, scope blocks are 2.7% of it rather than the bulk; the large restorable share sits before declarations. And the majority is not restorable — the opposite of what a first, coarser classification of the same data suggested, which had dropped a ninth of the sample into an unlisted remainder.
- No php-cs-fixer rule breaks a method chain that is already on one line, and the printer does not either — that would be a rule this tool brought with it. `formatting-contract.md` records it as the reason a project may not be able to hold its declared width. Since then `netresearch/typo3-ci-workflows` v1.12.0 ships one as a custom fixer, registered but not enabled, so a project can adopt it as its own rule.
- This repository declares `max_line_length = 100` and carries the four restoring rules its own `doctor` asked for.

## [0.2.0] - 2026-08-31

### Added

- **This repository now holds the contract it ships.** `doctor` reported `warn` on it until now — no formatter configured, not normalised, no gate — which is a poor argument for a tool whose whole thesis is that repositories need those three things. It carries `.php-cs-fixer.php`, a `.php-ast-edit.json` declaring it canonical at width 100, `composer cgl`, and `formatting.yml` running the two-step gate. `doctor` reports `ready`.
- An `exclude` entry that names nothing — `""`, `"."`, `"./"` — resolved to the repository root and excluded every file, so the formatting gate would have passed without looking at anything. Refused on both the read and the write path.
- **`exclude` in `.php-ast-edit.json`**, set by `normalize --exclude`. Found by that dogfooding: `tests/fixtures/sample.php` is input data, not source. Normalising it would mean the suite only ever sees code the printer already agrees with — and the round-trip test would stop testing anything. `format` and `normalize` skip the listed paths; the tests assert an excluded file survives both an absolute and a relative scan, because comparing the scan's own path strings against resolved exclusions silently missed it the first time.

- **`CanonicalPrinter`** — canonical printing that a human can read. nikic's `Standard` printer puts every comma-separated list on one line however long, which on a real TYPO3 extension produced a 1745-character line where the authors' longest was 294. No PHP formatter fixes that afterwards: none of php-cs-fixer's 303 fixers has a concept of line width, and PHP_CodeSniffer's `Generic.Files.LineLength` only reports, so `phpcbf` cannot wrap. Line breaking is the printer's job or nobody's. Two hooks — `pMaybeMultiline` and `pParams` — break call arguments, array items, attribute arguments and parameter lists at a column budget; at 80 the same extension printed at max 318 characters against the authors' 294.
- **The formatting contract, declared rather than inferred.** `php-ast-edit normalize` prints a tree canonically and writes `.php-ast-edit.json`; `apply` reads it. Whether a file may be rewritten canonically cannot be measured from the file, because the fixed point belongs to the printer and the project's formatter together and the formatter runs last: on a correctly normalised extension, re-printing differed from disk in 48 of 63 files, all of it the formatter's own doing.
- **Format-preserving printing as an announced fallback.** Without the declaration `apply` prints format-preserving and returns a `NOT_CANONICAL` warning naming the setup. Per-file override with `"printer": "canonical" | "format-preserving"`. Every result reports the printer used and `changedLines` as measured after printing — `printFormatPreserving()` silently falls back to full printing for a subtree it cannot map, so the number is taken, not assumed.
- **`doctor`** reports whether a repository can hold the contract: formatter configuration, the canonical declaration, and whether any workflow runs the formatter. Each answer names the artefact it read.
- **`format`** prints canonically; `--dry-run` lists what would change. Deliberately no `--check`: on the intended state it would be red, because the formatter has been over the files since. The gate is the chain `php-ast-edit format && <project formatter> && git diff --exit-code`, documented as such.
- `references/formatting-contract.md` — the precondition, the one-time setup, the decay without a CI gate, and a measured table of which PHP tools can canonicalise line breaking (php-cs-fixer, Pint, ECS and PHP_CodeSniffer cannot; `@prettier/plugin-php` and this printer can).
- `tests/formatting.php` — 33 checks: width behaviour and idempotence at three budgets, printer selection from the declaration, the explicit override, and the format-preserving footprint for six operation classes rather than for renames alone.
- **AST mutation primitives.** `replace_node`, `delete_node`, `insert_into`, `replace_child`, `delete_child` and `move_node` form a complete CRUD algebra over the AST. `insert_into` addresses a container by node, property and position, so it needs no existing sibling — adding the first method to an empty class, the first statement to an empty function body or the first parameter to an empty signature is now expressible.
- **Contextual snippet parsing.** A snippet is parsed inside a synthetic host construct, so the grammar comes from `nikic/php-parser` instead of being modelled a second time here: `expr`, `stmt`, `member`, `enum_case`, `param`, `arg`, `type`, `array_item`, `match_arm`, `attribute`, `closure_use`, `catch`, `const`, `use`, `property_item`, `static_var`, `file`. `parseAs` is inferred where unambiguous.
- **Structural node references.** `inspect` returns a `ref` (`stmts[1].stmts[0].params[0]`) and the node's `slots` alongside the byte coordinates; `target` accepts `ref` as an alternative to `offset` or `line`/`column`. A ref is only valid together with the snapshot it came from.
- **File lifecycle.** A file entry carries `"mode": "edit"` (default), `"create"` (full construction syntax in `php`, guarded by `expectAbsent`, with `edits` applied to the freshly parsed AST) or `"delete"` (guarded by `sha256`).
- **Comment handling.** `set_doc_comment` and `remove_doc_comment` — the one area regular AST child nodes do not cover. An existing docblock is replaced, not duplicated.
- **Semantic convenience operations.** `add_member`, `add_parameter`, `add_attribute`, `set_return_type`, `set_type`, `set_visibility`, `add_implements`, `set_extends`.
- **`contexts` command** listing the live `parseAs` catalog, operation groups and file modes.
- **`hooks/php-ast-only.py`**, a `PreToolUse` gate that denies `Edit`/`Write`/`MultiEdit`/`NotebookEdit` on `.php` and `sed -i`-style shell mutation, so the AST-only rule is enforced before the write rather than by instruction alone. Wiring: `references/enforcement.md`.
- A snippet may now carry a PHP open tag inside a string literal (`'<?xml …'`). The check is structural — a snippet that actually leaves the PHP context is rejected — instead of a substring search for `<?`.
- **`tests/matrix.php`**, a table-driven grammar and failure-mode matrix (61 cases) covering file root, namespace, use, class, interface, trait, enum, members, params, types, modifiers, statements, expressions, arrays, match, attributes, anonymous classes and closures, comments, empty containers and the file lifecycle, plus stale SHA, wrong kind, detached target, invalid contextual snippet, duplicate path, `phpVersion` pinning and write-phase rollback.
- PHP 8.5 in the CI matrix.

### Changed

- `apply` mutates a clone of the parsed tree and keeps the pristine tree and its tokens, which format-preserving printing needs to map a node back to the source.
- `tests/corpus.php` round-trips through `CanonicalPrinter`, so the printer that `apply` uses is the one whose fidelity is proven.
- `printWidth` lives in `.php-ast-edit.json` only. `format --width` is refused: formatting at a width the repository was not normalised with moves the fixed point and reflows everything.
- **The contract is now "write PHP through the AST", not "edit PHP through the AST".** Any creation, modification, replacement, deletion or movement of PHP syntax goes through `php-ast-edit`; text mutation is never the fallback when an operation looks unsupported.
- **`apply` is transactional across files.** Every file is read, guarded, resolved, mutated, printed and re-parsed before the first byte is written, and a failure during the write phase rolls the already written files back. Previously each file was written as soon as it succeeded, so a failure in file three could leave files one and two changed.
- The existing typed operations are now convenience shorthands over the primitives rather than the coverage boundary.
- `atomicWrite` refuses a directory it cannot write instead of letting `tempnam()` fall back to the system temp directory and turning the rename into a cross-device move.

### Fixed

- **Writing through a symlink replaced the link with a regular file.** `rename()` over a symlink swaps the link itself, so the repository's link topology changed and the file everyone else reads stayed untouched — the edit went nowhere visible. Both writers had it, and the one in the transaction engine has been shipped since 0.1.0. `AtomicWriter` now resolves the link chain first and is the single implementation both use, so the temp-file, permission and cross-device rules live in one place.
- `normalize` declared a repository canonical even when it had only been pointed at a subdirectory, or when files had failed to format. Both now refuse the declaration and say which. A marker that speaks for code it never covered is worse than none.
- `printWidth` was validated on read but not on write, so `normalize --width 10` persisted a value every later command then rejected. One method decides the minimum for both paths.
- `Formatter` wrote with a plain `file_put_contents`; it now uses the same temporary-file-and-rename the transaction engine does, so a crash mid-write cannot truncate a source file.
- `tests/corpus.php` stripped every attribute before comparing, comments included — which made comment loss invisible in the test that exists to prove nothing is lost. Comments are now compared as a set, by content: attachment moves in 206 of 270 files while the text survives, and **two genuine losses** surfaced. An `else` block whose only statement is an `if` prints as `else if`, collapsing the block and the comment attached to that inner `if`. That is php-parser's own behaviour — reproduced with its `Standard` printer — so the two are listed by their text and any other loss fails the suite.
- Nine uses of `new Foo()->bar()` — PHP 8.4 syntax — in a package whose floor is 8.2. It was the second time in one session: the host here runs 8.5, so `php -l` cannot see it, and neither can parsing, because php-parser's grammar is not version-gated for that construct. `tests/php-floor.php` closes that one construct by reading the source position after the `new` — it is not a general floor check, which would need the floor interpreter: a parenthesised one is followed by `)`, the bare form by the dereference. Scoped deliberately to that construct rather than pretending to cover every version difference — for that, run the floor interpreter.
- A contextual snippet that escaped its synthetic host — `echo 1;` in the `attribute` context, `} echo 1; class Y {` in `member` — reached into a node the extractor never expected and produced an undefined-property warning followed by a `TypeError`. The host node is now checked before extraction.
- `create` prepended a missing `<?php` open tag, which shifted every byte offset the same document's `edits` used. The tag is required and its absence is named.
- Emptying a slot that cannot be null (`Param::$var`) raised a `TypeError` at the assignment. It is refused by name, pointing at `replace_child` / `replace_node`.
- A mutation that only fails when printed or re-parsed surfaced as a raw printer or parser exception; those become `INVALID_RESULT` naming the file.
- Path identity did not collapse `.` and `..` below a directory that does not exist yet, so two `create` entries for the same new file could both run. Paths are collapsed textually before the deepest existing ancestor is resolved.
- The enforcement gate let `rm src/Foo.php` through, although deletion is part of the same contract and `mode: delete` guards it with the file's hash. `rm`, `unlink` and `shred` of a PHP path are denied.
- The enforcement gate judged the whole command line at once: a `php-ast-edit` invocation anywhere in it exempted everything after a `;`, a path-qualified `/usr/bin/sed -i` was missed, `1> file.php` was missed, and `sed -n f.php | grep -i x` was denied as an in-place edit. The line is now split into its simple commands and each is judged on its own; `tests/hook.py` pins 39 command and tool shapes, the known dataflow blind spot included.
- `mb_check_encoding()` was used without `ext-mbstring` in the package requirements; the UTF-8 check now goes through PCRE, which needs no extra extension.
- Two spellings of one path (`src/A.php` and `./src/A.php`) produced two transactions on the same file; both resolved against the same snapshot and the second write silently discarded the first one's edits. Paths are now compared by identity.
- `insert_into` on a property that holds a single node rather than a list (`returnType`, `default`, a class's `extends`) raised a `TypeError` from inside the printer. It is now refused by name, pointing at `replace_child`.
- `remove_doc_comment` deleted every comment attached to the node, line comments included.
- The parse context for a sub node name is resolved against the node: `stmts` is a member list on a class-like node and a statement list everywhere else, `uses` is a closure binding on a `Closure` and an imported name on a `use` statement, `vars` is a static variable on `static` and an expression on `unset`. Inserting a statement into a function body without an explicit `parseAs` previously failed with a syntax error from the class host.
- `inspect` truncated its source excerpt at a fixed byte count, which lands mid-character often enough to matter; the resulting broken UTF-8 sequence failed `json_encode` and took down the whole command. The excerpt is cut on a character boundary, and the CLI substitutes invalid sequences instead of failing, so a latin-1 source file stays inspectable.
- `tests/corpus.php` runs the print-and-reparse round trip over php-parser's own 270 source files and requires the AST to come back identical, plus 2160 `inspect` calls at positions spread through them that must raise nothing untyped. A hand-picked fixture cannot show fidelity: the constructs that lose something are the ones nobody thought to write down.
- `contexts` advertised a hand-written list next to a hand-written dispatcher, which could drift in either direction; `tests/catalog.php` now checks the operation and context names agree across the dispatcher, the CLI catalog and `operations.md`, and fails on drift from any side.
- `scripts/check.php` silently skipped a listed path that did not exist, so the syntax gate would quietly stop covering a file that was renamed. A missing path now fails the gate.
- `inspect --kind` was accepted and then ignored, so the ancestry came back unfiltered. It now filters, and `tests/cli.sh` covers the CLI surface the skill actually tells agents to drive — arguments, output fields and exit codes — which neither `run.php` nor `matrix.php` touched.
- A file that changed on disk while the transaction was being prepared was written over. Every file is now re-compared against its snapshot immediately before the first write and the transaction fails with `CONCURRENT_CHANGE`.

### Deprecated

- `SnippetParser` — retained as a facade over `ContextParser`.

## [0.1.0]

### Added

- `php-ast-edit` CLI with `inspect`, `apply` and `validate` commands.
- Ten typed operations: `set_name`, `set_string`, `replace_expression`, `replace_statement`, `insert_before`, `insert_after`, `delete`, `replace_argument`, `add_argument`, `remove_argument`.
- Transaction guards: SHA-256 optimistic lock, expected node type/name/value, attachment check before each edit, reparse before write, atomic rename.
- `php-structured-edit` Agent Skill with the operation reference and a wrapper resolving the repository binary, `vendor/bin`, a local PHAR, or `PATH`.
- PHAR build via `scripts/build-phar.php`.

[Unreleased]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/netresearch/php-ast-edit-skill/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/netresearch/php-ast-edit-skill/releases/tag/v0.1.0
