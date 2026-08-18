## What changed

<!-- One paragraph. What does this change do? -->

## Why

<!-- The problem, issue link, or failure this addresses. -->

## Checklist

- [ ] `bash tests/run.sh` passes locally with `vendor/` installed (the round-trip and PHAR checks skip themselves without it).
- [ ] `.php` files were edited through `bin/php-ast-edit`, not `sed`, regex, or raw string replacement.
- [ ] Version changes went into the root `plugin.json` and `.claude-plugin/plugin.json` was regenerated, not hand-edited.
- [ ] New or changed operations are documented in `skills/php-structured-edit/references/operations.md`.
- [ ] `SKILL.md` stays under 500 words and every `references/*.md` remains reachable from it.
- [ ] Commits follow Conventional Commits and are signed.
