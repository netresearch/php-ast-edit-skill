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
            $findings[] = 'No formatter declared in ' . RepositoryConfig::FILE . '. The fixed point belongs to the printer and the project formatter together, so an edit that stops after printing leaves a file in neither shape: on a canonical TYPO3 extension, adding one 9-line method reported 34 changed lines rather than 10. Declare the command and `apply` runs it on the files it wrote: "formatter": ["php", ".Build/bin/php-cs-fixer", "fix", "--config=Build/.php-cs-fixer.php", "--path-mode=intersection", "{files}"]. Name the paths mode: php-cs-fixer defaults to override, which ignores the config Finder as soon as paths are given, so this project\'s own exclusions would stop applying.';
        }

        return [
            'root' => $root,
            'status' => $findings === [] ? 'ready' : 'warn',
            'declaredWidth' => $declaredWidth['width'],
            'widthSource' => $declaredWidth['source'],
            'missingRules' => $missingRules,
            'unrecoverable' => self::UNRECOVERABLE_SHARE,
            'formatters' => $formatters,
            'canonical' => $config->canonical,
            'printWidth' => $config->width,
            'declaredIn' => $config->path,
            'formatterInCi' => $inCi,
            'declaredFormatter' => $config->formatter,
            'editorconfig' => $editorconfig,
            'findings' => $findings,
        ];
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
}
