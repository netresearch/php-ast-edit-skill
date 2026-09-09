# Formatting: preserve existing layout or opt into canonical output

## Start with existing files

`apply` uses format-preserving printing when no canonical repository declaration exists.
This is a supported default: it preserves original tokens for unchanged syntax and prints
new or changed nodes. A subtree that cannot be mapped back to its original tokens may be
reprinted, so review the returned `diff` and `changedLines`. Small intended changes do
not guarantee small diffs. `NOT_CANONICAL` describes the selected printer; it does not
require normalization or an additional read when supplied evidence already establishes
the relevant byte changes. Evidence unavailable or showing unexpected changes still
requires inspection.

Select a printer explicitly per file with `"printer": "format-preserving"` or
`"printer": "canonical"`. The report states which was used. A format-preserving edit does
not automatically run the canonical formatter pipeline. Use the project's normal checks
for the touched files when they have not already run.

## Optional canonical formatting

Canonical printing selects one representation of syntax. It may change manual line breaks
and blank lines across a file. Treat adopting it as a separate project decision, with its
own diff review. It is not required to use the editor.

For a canonical workflow the project declares its width in `.editorconfig`, for example:

```ini
root = true

[*.php]
max_line_length = 100
```

The initial setup from a clean checkout is:

```bash
php-ast-edit doctor
php-ast-edit normalize
# Run this project's formatter using its documented fix command, then review the diff.
```

`normalize` reads `.editorconfig`; it does not accept `--width`. It prints the selected
tree and updates `.php-ast-edit.json`. Review and commit the formatting conversion
separately from feature changes. Re-normalization preserves existing `formatter`, `verify`,
and exclusion settings.

Configure optional commands in `.php-ast-edit.json` as argument arrays, not shell strings:

```json
{
  "canonical": true,
  "printWidth": 100,
  "formatter": ["vendor/bin/php-cs-fixer", "fix", "--path-mode=intersection", "{files}"],
  "verify": [{"scope": "project", "command": ["php", "vendor/bin/phpstan", "analyse", "--no-progress"]}]
}
```

Use commands compatible with your project. Both keys take an argv list, so any tool that
accepts file paths fits without changes here — `mago format {files}` and `mago analyze`
are valid values, as are Pint, ECS and PHP_CodeSniffer. Speed is a real
difference between them: measured on one file of a 121-file TYPO3 extension, `mago format`
took 0.01s against 0.40s for `php-cs-fixer fix`, and `mago analyze` 0.08s against 1.5-2.0s
for a warm `phpstan analyse`. That is not a reason to switch. Run against the same file,
mago's formatter disagreed with php-cs-fixer's output on 70 lines, and `mago analyze`
reported 69 findings on a file the project's own PHPStan level passes — the tools enforce
different things, and the declared formatter has to be the one the repository is already
written to, or every edit reformats what the last one wrote. Declare mago where the project
uses mago.

The formatter requires exactly one whole `{files}` argument, expanded to changed file
paths. Project-scoped verification commands
have no `{files}` placeholder and run once per affected configuration directory, including
after deletions. Configure PHPStan's stable analysis paths in `phpstan.neon`; a changing
CLI file list replaces those paths and can invalidate its result cache. See the
[verification contract](operations.md#verification-configuration) for changed-file checks
and legacy command arrays.

A canonical `apply` runs the declared formatter on changed files, then configured checks.
Verification also runs for eligible format-preserving edits. Excluded paths skip the
canonical formatter and do not trigger verification. Read the actual results instead of
running the same checks again unchanged. `"report": "compact"` returns each verification
result once in top-level `verify`, linked by file `checkIds`.

The stable formatting state is the composition of the canonical printer and the project
formatter. To check it in CI, start from a **clean committed checkout**, run both tools,
and then use `git diff --exit-code`. That final command detects formatting drift relative
to the committed baseline. It is inappropriate immediately after an intended source edit,
whose diff is supposed to be nonempty. In a working tree, review the diff and use available
formatter check modes or compare before/after hashes of a second formatting pass.

## Limits

Canonical printing can discard author paragraphing. It can also lose comments attached to
certain `else { if (...) ... }` layouts; the corpus suite currently documents two known
php-parser cases. Format preservation reduces exposure in unchanged subtrees but is not
a blanket comment-preservation guarantee.

The canonical printer wraps supported comma-separated lists according to the configured
budget. It does not wrap every method chain, string concatenation, or long literal. Width
is therefore a formatting target, not a guarantee that every output line fits.

Printer upgrades can change output. Review normalization and formatter changes together
in a dependency update. Do not silently reformat a whole project during an unrelated edit.
