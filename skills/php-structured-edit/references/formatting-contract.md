# The formatting contract

## Contents

- [Why this exists](#why-this-exists) — what an AST write costs without it
- [The contract](#the-contract) — three conditions, and who satisfies each
- [Setting a repository up](#setting-a-repository-up) — normalize, format, gate
- [The fallback](#the-fallback) — format-preserving printing and its warning
- [What the tools can and cannot do](#what-the-tools-can-and-cannot-do) — measured

## Why this exists

An AST write reprints the file from the tree. If the file was not already written the way
this printer writes, everything it disagrees with changes with it. Measured on a TYPO3
extension of 63 files: **a one-identifier rename changed 105 lines**, of which 2 were the
rename. Running the project's own `php-cs-fixer` afterwards did not bring it back — after
formatting *both* sides, 3065 of 8351 lines still differed, in 55 of 63 files.

That is not a printer defect. It is what canonical printing means: one rendering per AST.
The cost falls entirely on repositories whose code sits somewhere else. On a repository
that sits on the fixed point, the same rename changes **2 lines**.

## The contract

| Condition | Who satisfies it |
| --- | --- |
| Unambiguous formatting rules exist | the repository (php-cs-fixer, Pint, ECS …) |
| Line breaking is decided by one rule, not by taste | **this tool** — no PHP formatter does it |
| The whole codebase already sits on the fixed point | `php-ast-edit normalize`, once |
| It keeps sitting there | a CI gate; nothing else notices drift |

The fixed point belongs to the *pair*: `projectFormatter(canonicalPrint(x))`. Neither half
is it alone. `canonicalPrint(f) != f` for most files of a correctly normalised repository,
because the formatter runs last and has the final word on blank lines, operator alignment
and the licence header. That is why the tool does not try to detect canonical formatting by
re-printing — it would call a well-kept repository broken. It is declared, in
`.php-ast-edit.json`, and `php-ast-edit normalize` is the only thing that writes it.

## Setting a repository up

```bash
php-ast-edit doctor                 # what is missing
php-ast-edit normalize --width 80   # print canonically, write .php-ast-edit.json
composer ci:cgl                     # or whatever the project's formatter is
git add -A && git commit -m "style: normalise to canonical formatting"
```

**Commit that on its own.** It touches most of the repository; folding it into a feature
change makes both unreviewable.

Then gate it. A `format --check` would be the obvious thing and is deliberately absent: on
the intended state it would be red, because the formatter has been over the files since.
The gate is the whole chain:

```bash
php-ast-edit format && composer ci:cgl && git diff --exit-code
```

Without that gate the invariant decays on the first hand edit. Measured: a developer writes
a call across four lines — the formatter accepts it, `--dry-run` is clean, nothing reports
anything — and the next AST edit anywhere in that file collapses it again. One added
constant changed 6 lines instead of 1.

`printWidth` lives in `.php-ast-edit.json` and nowhere else. Formatting at a width the
repository was not normalised with moves the fixed point and reflows everything, which is
the same failure with extra steps. The printer's own version matters too: a
`nikic/php-parser` upgrade can change its output, and the repository then needs
re-normalising — a `normalize` run in the dependency-update PR, not a surprise in the next
feature branch.

## The fallback

Where no `.php-ast-edit.json` declares the repository canonical, `apply` prints
format-preserving and says so:

```json
{"printer": "format-preserving", "changedLines": 2,
 "warning": "NOT_CANONICAL: no .php-ast-edit.json declaring this repository …"}
```

This keeps the diff small in a repository that is not set up, and it is never silent. It is
a fallback, not a mode to prefer: it preserves whatever shape is in the file, conformant or
not, so a repository can drift indefinitely without anything objecting. And
`printFormatPreserving()` falls back to full printing for any subtree it cannot map back to
the source — silently — which is why every result reports `changedLines` as **measured**
after printing rather than as intended.

Force either printer per file with `"printer": "canonical" | "format-preserving"`.

## What the tools can and cannot do

Every claim here was measured against `friendsofphp/php-cs-fixer` 3.95 and
`squizlabs/php_codesniffer`, not read off a changelog.

| Tool | Canonicalises line breaking? |
| --- | --- |
| php-cs-fixer | **No.** 0 of 303 fixers carry any concept of line width. `method_argument_space` only decides what to do with a list that *already* contains a newline. |
| Laravel Pint | No — it is a php-cs-fixer wrapper and inherits the above. |
| ECS | No — it composes php-cs-fixer and PHP_CodeSniffer rules. |
| PHP_CodeSniffer | **No.** `Generic.Files.LineLength` calls `addError`/`addWarning`; it has no `addFixableError`, so `phpcbf` cannot wrap a line. |
| `@prettier/plugin-php` | Yes — width-driven by design. A Node dependency, and its own house style. |
| **this tool's `CanonicalPrinter`** | Yes, for the lists that account for the problem. |

So a PHP repository that wants canonical *and* readable formatting has two options: adopt
Prettier, or let this printer own line breaking and keep the existing formatter for
everything else. The second is what this package implements.

The printer breaks call arguments, array items, attribute arguments and parameter lists at
a column budget. It does not break string concatenations or method chains — that needs the
kind of document IR Prettier builds. Measured against the same extension:

| | longest line | lines > 120 |
| --- | --- | --- |
| written by hand | 294 | 74 |
| Standard printer + formatter | 1745 | 207 |
| **canonical printer (80) + formatter** | **318** | **86** |

The remaining long lines are concatenations — which the authors had not broken either.
