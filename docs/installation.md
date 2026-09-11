# Install php-ast-edit and its agent skill

The editor and the instructions are separate components. The editor needs PHP 8.2+,
JSON/tokenizer extensions, and nikic/php-parser. A PHAR bundles the parser; a source or
Composer installation resolves it through Composer. Composer installations require 2.2+.

These instructions describe `main`. Historical v0.7.0 artifacts retain their documented
limitations; a release published after those repairs carries the bundled assets.

## Source checkout: the recommended development path

```bash
git clone https://github.com/netresearch/php-ast-edit-skill.git
cd php-ast-edit-skill
composer install --no-interaction
bin/php-ast-edit help
bash docs/quickstart.sh
```

`bin/php-ast-edit` is the package's own binary. A root checkout does not install its own
binary into `vendor/bin/`. `help` alone is not an engine test; the quickstart exercises
creation, selectors, batching, and runtime behavior.

## Composer dependency in an existing PHP project

Use an explicit VCS repository until availability of the desired version on Packagist
has been verified. This avoids depending on an unregistered package name:

```bash
composer config repositories.php-ast-edit vcs https://github.com/netresearch/php-ast-edit-skill.git
composer require --dev --no-plugins --no-scripts netresearch/php-ast-edit-skill:dev-main
vendor/bin/php-ast-edit doctor
```

The command above follows development `main`. For a reproducible production toolchain,
select a release containing the installation fixes and commit the consumer project's
`composer.lock`. Historical v0.7.0 has a Composer autoload defect; rebuilding its consumer
autoloader does not repair the entrypoint.

This engine-only install disables Composer plugins and project scripts for that command.
Register the skill separately using your agent's installer.

The Composer binary proxy supplies the consumer autoloader, including projects with
custom vendor and binary directories. Use the binary in the configured binary directory.
Composer installs the engine; whether an agent discovers the skill also depends on its
skill installer. The engine does not require granting an unrelated Composer plugin access.

## Release artifacts

Releases built with the current packaging pipeline contain:

- `php-ast-edit.phar`: standalone engine, still requiring a compatible PHP interpreter.
- Plugin and skill archives with a bundled PHAR next to their wrapper.
- `SHA256SUMS.txt` and `runtime-dependencies.json` for artifact and dependency inspection.

Choose assets from a specific [release](https://github.com/netresearch/php-ast-edit-skill/releases).
Confirm the listed assets exist; the historical v0.7.0 archives did **not** bundle an engine.
This documentation does not retroactively change those released archives.

Download the chosen PHAR and checksum file into the same directory, verify the applicable
checksum, then run it with `php php-ast-edit.phar help`. Extract a skill archive into your
agent's skill directory; its `scripts/php-ast-edit` wrapper resolves the bundled PHAR.
Check a real parse/edit in a disposable directory after installation.

To build these artifacts locally from a checkout:

```bash
bash scripts/build-release.sh "v$(jq -r .version plugin.json)"
```

Build output is in `dist/releases/`. The release builder installs runtime-only dependencies
in an isolated directory, leaving development dependencies in your working checkout.

Dependency versions are resolved at build time within the Composer constraints, using
the supported PHP floor. This library does not track a root `composer.lock`. Each release
records its resolved runtime dependencies and tests the exact packaged bytes before
signing them. Rebuilding the same source tag later can select newer compatible packages;
the pipeline does not promise byte-identical rebuilds. Use the verified release assets and
their dependency manifest when reproducing a deployed toolchain.

## Optional resolver for project-wide method renames

Project-wide `rename_method` uses a separate Phpactor PHAR. The engine PHAR and the
skill/plugin archives do not bundle it; local edits do not need it. The resolver is
pinned to **Phpactor 2026.07.22.0**, including its SHA-256 digest.

Use PHP 8.2+ with `mbstring`, `posix`, and `tokenizer`, in addition to the engine's
requirements. These are the [pinned resolver's declared requirements](https://github.com/phpactor/phpactor/blob/2026.07.22.0/composer.json).
Git must be available, and the target project must be a Git working tree: project
discovery includes tracked and non-ignored untracked files, respecting the editor's
exclusions. Composer's generated class tables help resolve ancestors in dependencies.
The POSIX requirement means this resolver installation targets Linux/macOS; use WSL
on Windows rather than a native Windows PHP interpreter.

From the target project's root, download and verify the resolver before using it:

```bash
mkdir -p .Build/bin &&
curl --fail --silent --show-error --location \
  --output .Build/bin/phpactor.phar \
  https://github.com/phpactor/phpactor/releases/download/2026.07.22.0/phpactor.phar &&
printf '%s  %s\n' \
  '8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d' \
  '.Build/bin/phpactor.phar' | sha256sum --check --strict &&
export PHP_AST_EDIT_PHPACTOR="$PWD/.Build/bin/phpactor.phar"
```

Stop if the download or checksum fails. On macOS, `shasum -a 256 --check` can replace
`sha256sum --check --strict`. The engine also verifies the pinned digest before starting
the resolver. For persistent configuration, merge `"phpactor": ".Build/bin/phpactor.phar"`
into `.php-ast-edit.json`; preserve any existing formatter, verification, and exclusion
settings. Relative configuration paths resolve beside that file; the environment
variable takes precedence. `doctor` reports the configured resolver and its digest
status. A ready digest does not establish that the PHP extensions are installed or
that every reference can be resolved.

## Install agent instructions

For an agent supported by the skills installer:

```bash
npx skills add https://github.com/netresearch/php-ast-edit-skill --skill php-structured-edit
```

A source-based skill install may omit the engine. Install the engine using a path above,
or use an archive that bundles it. Verify the installed wrapper before assigning a task.
The stable skill name is `php-structured-edit`; the repository is `php-ast-edit-skill`.

For Claude Code, adding a marketplace only registers it. Install the specific plugin from
that marketplace as a separate step, using the exact identifier shown by its current
listing. See the [Netresearch marketplace](https://github.com/netresearch/claude-code-marketplace)
for the current installation command. No unverified plugin identifier is assumed here.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `vendor/bin/php-ast-edit` missing in a clone | Run `bin/php-ast-edit` from the checkout |
| Parser missing after skill installation | Install the engine or choose an archive with its bundled PHAR |
| Consumer binary cannot autoload the parser | Upgrade from historical v0.7.0 to a version with Composer proxy support |
| `normalize --width` rejected | Declare `max_line_length` in `.editorconfig`, then run `normalize` |
| No canonical declaration | Use the supported format-preserving default; normalization is optional |
| Successful parse but failed project check | Read `validation` and `verify`; repair the retained edit and rerun the failed check |
| Newer PHP syntax than the host accepts | Run lint and tests on the target PHP runtime; parser compatibility is insufficient |

`bash tests/distribution.sh` tests source, consumer, custom-directory, PHAR, and extracted
archive execution. These smoke tests establish local installation behavior; registry
registration and publication still require the external release process.
