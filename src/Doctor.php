<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

/**
 * Reports whether a repository can hold the contract this tool depends on.
 *
 * The contract is: unambiguous formatting rules, the whole codebase already written to
 * them, and a gate that keeps it that way. Without it the tool still works, but every edit
 * either reflows the file it touches or falls back to format-preserving printing — which
 * preserves whatever shape is there, conformant or not.
 *
 * Nothing here is inferred from the code. Each answer names the artefact it read.
 */
final class Doctor
{
    /** Formatter configurations, in the order a PHP project usually carries them. */
    private const FORMATTER_FILES = [
        '.php-cs-fixer.php' => 'php-cs-fixer',
        '.php-cs-fixer.dist.php' => 'php-cs-fixer',
        'Build/.php-cs-fixer.php' => 'php-cs-fixer',
        'Build/.php-cs-fixer.dist.php' => 'php-cs-fixer',
        '.php_cs' => 'php-cs-fixer (legacy)',
        'pint.json' => 'laravel/pint',
        'ecs.php' => 'symplify/easy-coding-standard',
        'phpcs.xml' => 'PHP_CodeSniffer',
        'phpcs.xml.dist' => 'PHP_CodeSniffer',
    ];

    /**
     * Static analysers, and where each one keeps its configuration.
     *
     * A repository that has one of these has a check an agent will run anyway — as its own
     * call, after the edit, having decided by itself that it was needed. Declared as `verify`
     * it runs inside `apply` on the files that changed, and the result says whether it passed.
     */
    private const ANALYSER_FILES = [
        'phpstan.neon' => 'phpstan',
        'phpstan.neon.dist' => 'phpstan',
        'phpstan.dist.neon' => 'phpstan',
        'Build/phpstan.neon' => 'phpstan',
        'Build/phpstan.neon.dist' => 'phpstan',
        'psalm.xml' => 'psalm',
        'psalm.xml.dist' => 'psalm',
    ];

    /**
     * Rules that put back what canonical printing removes, with what each one recovers.
     *
     * The shares were measured on a 121-file TYPO3 extension whose formatting was clean
     * beforehand, by classifying every blank line the canonical print removed according to
     * the statement that followed it. They are an order of magnitude, not a promise — but
     * they are measured, and they let somebody decide which rules are worth adding.
     *
     * @var array<string, string>
     */
    private const RESTORING_RULES = [
        'class_attributes_separation' => 'blank lines between members (23% of what a canonical print removes)',
        'blank_line_before_statement' => 'blank lines before docblocks, return, throw and scope blocks (14%)',
        'blank_line_after_opening_tag' => 'the blank line after the open tag (part of the 7% around the file head)',
        'declare_parentheses' => 'the space the printer puts inside declare()',
    ];

    /**
     * What no rule restores.
     *
     * Until the printer kept them, a blank line an author put between two ordinary statements
     * was lost: measured at ~45% of the removed blank lines, the largest single share, and the
     * reason canonical formatting used to be a trade rather than an improvement. The printer
     * now carries the gap over from the line attributes the parser supplies, so nothing in
     * this class is unrecoverable any more. The field stays because callers read it.
     */
    private const UNRECOVERABLE_SHARE = 'none — the printer keeps the paragraph breaks between statements, which used to be ~45% of what a canonical print removed';

    public function examine(string $root): array
    {
        $root = rtrim(realpath($root) ?: $root, DIRECTORY_SEPARATOR);
        $formatters = [];

        foreach (self::FORMATTER_FILES as $relative => $name) {
            if (is_file($root . DIRECTORY_SEPARATOR . $relative)) {
                $formatters[] = ['tool' => $name, 'config' => $relative];
            }
        }
        $config = RepositoryConfig::discover($root);
        $declaredWidth = RepositoryConfig::widthFor($root);
        $missingRules = $this->missingRestoringRules($root, $formatters);
        $inCi = $this->formatterRunsInCi($root);
        $editorconfig = is_file($root . DIRECTORY_SEPARATOR . '.editorconfig');
        $findings = [];

        if ($formatters === []) {
            $findings[] = 'No formatter configuration found. Without one there are no unambiguous ' . 'rules for this tool to print towards, and every agent edit is a style decision. ' . 'Set up php-cs-fixer, Pint or ECS first.';
        }

        if (!$config->canonical) {
            $findings[] = sprintf(
                'No %s. The repository has not been normalised, so edits fall back to ' . 'format-preserving printing. Run `php-ast-edit normalize`, then the project ' . 'formatter, and commit that on its own.',
                RepositoryConfig::FILE,
            );
        }

        if ($declaredWidth['width'] === null) {
            $findings[] = 'No max_line_length in .editorconfig. Line width is a project rule and ' . 'this tool does not bring one: declare it under [*] or [*.php]. Without it a ' . 'repository cannot be normalised, because the printer would be breaking lines ' . 'by a number nobody chose.';
        }

        if ($missingRules !== []) {
            $findings[] = 'The formatter does not carry the rules that put back what canonical ' . 'printing removes, so normalising would lose layout the rules could have ' . 'restored: ' . implode('; ', $missingRules) . '.';
        }

        if (!$inCi) {
            $findings[] = 'No workflow appears to run the formatter. Canonical formatting decays ' . 'the first time somebody edits by hand: the formatter accepts both the collapsed ' . 'and the expanded shape, so nothing reports the drift and the next AST edit ' . 'reflows it. Gate it: `php-ast-edit format && <project formatter> && ' . 'git diff --exit-code`.';
        }

        if ($config->canonical && $config->formatter === null) {
            $suggestion = $this->suggestedFormatter($root, $formatters);
            $advice = $suggestion === null ? '.' : ': "formatter": ' . json_encode($suggestion, JSON_UNESCAPED_SLASHES) . '.';

            if ($suggestion !== null && in_array('--path-mode=intersection', $suggestion, true)) {
                // Only php-cs-fixer has a paths mode, and only there is the flag load-bearing.
                $advice .= ' The paths mode is not decoration: php-cs-fixer defaults to override, which ignores the configuration Finder as soon as paths are named, so this project\'s own exclusions would stop applying.';
            }
            $findings[] = 'No formatter declared in ' . RepositoryConfig::FILE . '. The fixed point belongs to the printer and the project formatter together, so an edit that stops after printing leaves a file in neither shape: on a canonical TYPO3 extension, adding one 9-line method reported 34 changed lines rather than 10. Declare the command and `apply` runs it on the files it wrote' . $advice;
        }
        $suggestedVerify = $this->suggestedVerify($root);

        if ($config->verify === null && $suggestedVerify !== null) {
            // What this saves is measured in calls, not seconds. An agent that cannot see
            // whether the repository's own checks passed runs them itself, after the fact and
            // on its own judgement: one recorded thirteen-turn edit spent four turns on
            // PHPStan and two on the coding standard, all of it after the write.
            $findings[] = 'No verify commands declared in ' . RepositoryConfig::FILE . '. This repository carries a static analyser, so an agent editing it will run one — as a separate call, after the write, deciding for itself that it was needed. Declared, it runs inside `apply` on the files that changed and the result carries checksPassed: "verify": [' . json_encode($suggestedVerify, JSON_UNESCAPED_SLASHES) . '].';
        }

        // Beside the findings for the same reason as the resolver below: a repository whose
        // chains run past its own `max_line_length` is still ready for canonical editing.
        // Naming the overrun is the point — nothing here can remove it, and a finding would
        // report a repository as not ready for something no run of this tool will fix.
        $overWidth = $declaredWidth['width'] === null ? null : $this->overWidth($root, $config, $declaredWidth['width']);

        // Reported beside the findings rather than among them: `status` answers whether the
        // repository is ready for canonical editing, and a missing resolver does not change
        // that. It changes which renames the engine can decide.
        $phar = PhpactorReferenceFinder::locate($config);
        $resolver = match (true) {
            $phar === null => 'missing',
            is_file($phar) && hash_file('sha256', $phar) === PhpactorReferenceFinder::SHA256 => 'ready',
            default => 'wrong_release',
        };

        return [
            'root' => $root,
            'status' => $findings === [] ? 'ready' : 'warn',
            'resolver' => [
                'phpactor' => $phar,
                'status' => $resolver,
                'advice' => $this->resolverAdvice($resolver, $phar),
            ],
            'declaredWidth' => $declaredWidth['width'],
            'widthSource' => $declaredWidth['source'],
            'overWidth' => $overWidth === null ? null : [
                ...$overWidth,
                'advice' => $overWidth['total'] === 0 ? null : sprintf(
                    '%d lines exceed the declared width of %d, %d of them carrying a method chain. ' . 'The printer breaks comma-separated lists and method chains at that width, so what ' . 'is left is what it cannot reach: what stands before an expression on its own line, ' . 'string concatenation, and a name already longer than the budget. Longest line: %d. ' . 'Normalising will not remove these.',
                    $overWidth['total'],
                    $declaredWidth['width'],
                    $overWidth['chains'],
                    $overWidth['longest'],
                ),
            ],
            'missingRules' => $missingRules,
            'unrecoverable' => self::UNRECOVERABLE_SHARE,
            'formatters' => $formatters,
            'canonical' => $config->canonical,
            'printWidth' => $config->width,
            'declaredIn' => $config->path,
            'formatterInCi' => $inCi,
            'declaredFormatter' => $config->formatter,
            'declaredVerify' => $config->verify,
            'editorconfig' => $editorconfig,
            'findings' => $findings,
        ];
    }

    /**
     * The lines the repository cannot hold under the width it declared, and how many of
     * them are method chains.
     *
     * `doctor` answers whether a repository is ready for canonical editing, and this is the
     * one place where the honest answer is "it will still exceed its own declaration".
     * Reported rather than fixed: the printer breaks comma-separated lists and method
     * chains at the declared width, and what is left over is what it cannot reach — what
     * stands before an expression on its line, string concatenation, and a single name
     * already longer than the budget.
     *
     * A chain is two or more `->call(` links on the line. One link is an ordinary call whose
     * argument list is long, and the printer already breaks those, so counting it here would
     * blame the construct the printer handles.
     *
     * @return array{total: int, chains: int, longest: int}
     */
    private function overWidth(string $root, RepositoryConfig $config, int $width): array
    {
        $total = $chains = $longest = 0;

        if (!is_dir($root)) {
            return ['total' => 0, 'chains' => 0, 'longest' => 0];
        }
        $iterator = new \RecursiveIteratorIterator(
            new \RecursiveDirectoryIterator($root, \FilesystemIterator::SKIP_DOTS),
        );

        foreach ($iterator as $entry) {
            if (!$entry->isFile() || $entry->getExtension() !== 'php') {
                continue;
            }
            $path = $entry->getPathname();

            // Nobody's dependencies are ours to hold to this repository's width.
            if (preg_match('#(^|/)(vendor|node_modules|\.Build|\.git)/#', $path) === 1 || $config->excludes($path)) {
                continue;
            }
            $contents = @file_get_contents($path);

            if ($contents === false) {
                continue;
            }

            foreach (explode("\n", $contents) as $line) {
                $length = mb_strlen(rtrim($line, "\r"));

                if ($length <= $width) {
                    continue;
                }
                ++$total;
                $longest = max($longest, $length);

                if (preg_match_all('/->\w+\s*\(/', $line) >= 2) {
                    ++$chains;
                }
            }
        }

        return ['total' => $total, 'chains' => $chains, 'longest' => $longest];
    }

    private function resolverAdvice(string $status, ?string $phar): ?string
    {
        if ($status === 'ready') {
            return null;
        }
        $state = $status === 'missing' ? 'not set up here' : 'not the pinned release at ' . $phar;

        return sprintf(
            'rename_method on a public, protected or inherited method resolves its call sites across the project through Phpactor %s, which is %s. %s',
            PhpactorReferenceFinder::RELEASE,
            $state,
            PhpactorReferenceFinder::installHint(),
        );
    }

    /**
     * Which restoring rules the project's formatter configuration does not mention.
     *
     * Read as text, deliberately: a fixer configuration is PHP that may compose presets from a
     * vendor package, and this is a report, not a gate. A rule named anywhere in the file
     * counts as present; a false negative here costs a wrong hint, where executing somebody's
     * configuration to be sure would cost rather more.
     *
     * @param list<array{tool: string, config: string}> $formatters
     * @return list<string>
     */
    private function missingRestoringRules(string $root, array $formatters): array
    {
        if ($formatters === []) {
            return [];
        }
        $haystack = '';

        foreach ($formatters as $formatter) {
            $contents = @file_get_contents($root . DIRECTORY_SEPARATOR . $formatter['config']);

            if ($contents !== false) {
                $haystack .= $contents;
            }
        }

        // A shared rule set lives in the vendor package the config pulls in, so look there too.
        foreach (glob($root . '/{vendor,.Build/vendor}/*/*/config/php-cs-fixer/*.php', GLOB_BRACE) ?: [] as $shared) {
            $contents = @file_get_contents($shared);

            if ($contents !== false) {
                $haystack .= $contents;
            }
        }
        $missing = [];

        foreach (self::RESTORING_RULES as $rule => $what) {
            if (!str_contains($haystack, $rule)) {
                $missing[] = $rule . ' — ' . $what;
            }
        }

        return $missing;
    }

    private function formatterRunsInCi(string $root): bool
    {
        $needles = ['php-cs-fixer', 'pint', 'ecs check', 'ecs.php', 'phpcbf', 'ci:cgl', 'php-ast-edit format'];

        foreach (['.github/workflows', '.gitlab-ci.yml', '.gitlab', 'ci'] as $relative) {
            $path = $root . DIRECTORY_SEPARATOR . $relative;

            foreach ($this->readable($path) as $contents) {
                foreach ($needles as $needle) {
                    if (str_contains($contents, $needle)) {
                        return true;
                    }
                }
            }
        }

        return false;
    }

    /** @return list<string> */
    private function readable(string $path): array
    {
        if (is_file($path)) {
            $contents = file_get_contents($path);

            return $contents === false ? [] : [$contents];
        }

        if (!is_dir($path)) {
            return [];
        }
        $out = [];

        foreach (glob($path . '/*') ?: [] as $entry) {
            if (is_file($entry)) {
                $contents = file_get_contents($entry);

                if ($contents !== false) {
                    $out[] = $contents;
                }
            }
        }

        return $out;
    }

    /**
     * The formatter command this project would most likely declare.
     *
     * Derived, not canned: `doctor` already knows which formatter the repository carries and
     * where its configuration sits, and a suggestion that names some other project's paths is
     * advice a reader has to correct before it works. The binary directory comes from
     * composer's `bin-dir`, which a TYPO3 extension commonly moves to `.Build/bin`.
     *
     * @param  list<array{tool: string, config: string}> $formatters
     * @return list<string>|null
     */
    private function suggestedFormatter(string $root, array $formatters): ?array
    {
        if ($formatters === []) {
            return null;
        }
        $bin = $this->binDirectory($root);
        $tool = $formatters[0]['tool'];
        $config = $formatters[0]['config'];

        return match (true) {
            str_starts_with($tool, 'php-cs-fixer') => [
                'php',
                $bin . '/php-cs-fixer',
                'fix',
                '--config=' . $config,
                // php-cs-fixer defaults to `override`, which ignores the configuration's own
                // Finder as soon as paths are named — the project's exclusions would stop
                // applying at the moment a tool starts naming files.
                '--path-mode=intersection',
                RepositoryConfig::FILES_PLACEHOLDER,
            ],
            $tool === 'laravel/pint' => ['php', $bin . '/pint', RepositoryConfig::FILES_PLACEHOLDER],
            $tool === 'symplify/easy-coding-standard' => ['php', $bin . '/ecs', 'check', '--fix', RepositoryConfig::FILES_PLACEHOLDER],
            $tool === 'PHP_CodeSniffer' => ['php', $bin . '/phpcbf', '--standard=' . $config, RepositoryConfig::FILES_PLACEHOLDER],
            default => null,
        };
    }

    /**
     * The verification command this project would most likely declare.
     *
     * Only a static analyser is suggested. A formatter is already the `formatter` key, and a
     * test suite is not a per-edit check — running one on every `apply` would trade the calls
     * this saves for wall time nobody asked to spend. Where the project carries nothing to
     * run, nothing is suggested: a repository with no analyser is not missing a declaration.
     *
     * @return array{scope: string, command: list<string>}|null
     */
    private function suggestedVerify(string $root): ?array
    {
        foreach (self::ANALYSER_FILES as $relative => $tool) {
            if (!is_file($root . DIRECTORY_SEPARATOR . $relative)) {
                continue;
            }
            $bin = $this->binDirectory($root);

            // Project scope, not the changed files. Naming files on the command line replaces
            // the analysis paths the configuration declares — which the formatting contract
            // warns invalidates the result cache — and avoiding it costs nothing: measured warm
            // on a 121-file TYPO3 extension, the whole project took 1.9s against 1.5-2.0s for a
            // single file, because the cache does the work either way. What project scope buys
            // on top is the error the edit caused somewhere else, which a file-scoped run
            // cannot see and would report as a pass.
            //
            // PHPStan dies at PHP's default 128M on any tree of size and reports it as an
            // ordinary failure, so the limit belongs in the command rather than in a note
            // somebody reads after the first crash.
            $command = match ($tool) {
                'phpstan' => [
                    'php',
                    $bin . '/phpstan',
                    'analyse',
                    '--configuration=' . $relative,
                    '--no-progress',
                    '--memory-limit=1G',
                ],
                default => ['php', $bin . '/psalm', '--config=' . $relative],
            };

            return ['scope' => 'project', 'command' => $command];
        }

        return null;
    }

    /**
     * Where composer puts vendor binaries here.
     *
     * `vendor/bin` unless the project says otherwise; a TYPO3 extension commonly moves it to
     * `.Build/bin`, and a suggestion naming the wrong one is a command that does not run.
     */
    private function binDirectory(string $root): string
    {
        $path = $root . DIRECTORY_SEPARATOR . 'composer.json';

        if (!is_file($path)) {
            return 'vendor/bin';
        }
        $raw = file_get_contents($path);
        $data = $raw === false ? null : json_decode($raw, true);

        if (!is_array($data)) {
            return 'vendor/bin';
        }
        $configured = $data['config']['bin-dir'] ?? null;

        return is_string($configured) && $configured !== '' ? rtrim($configured, '/') : 'vendor/bin';
    }
}
