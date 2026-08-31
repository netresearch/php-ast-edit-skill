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

    public function examine(string $root): array
    {
        $root = rtrim(realpath($root) ?: $root, DIRECTORY_SEPARATOR);

        $formatters = [];
        foreach (self::FORMATTER_FILES as $relative => $name) {
            if (is_file($root.DIRECTORY_SEPARATOR.$relative)) {
                $formatters[] = ['tool' => $name, 'config' => $relative];
            }
        }

        $config = RepositoryConfig::discover($root);
        $inCi = $this->formatterRunsInCi($root);
        $editorconfig = is_file($root.DIRECTORY_SEPARATOR.'.editorconfig');

        $findings = [];
        if ($formatters === []) {
            $findings[] = 'No formatter configuration found. Without one there are no unambiguous '
                .'rules for this tool to print towards, and every agent edit is a style decision. '
                .'Set up php-cs-fixer, Pint or ECS first.';
        }
        if (!$config->canonical) {
            $findings[] = sprintf(
                'No %s. The repository has not been normalised, so edits fall back to '
                .'format-preserving printing. Run `php-ast-edit normalize`, then the project '
                .'formatter, and commit that on its own.',
                RepositoryConfig::FILE,
            );
        }
        if (!$inCi) {
            $findings[] = 'No workflow appears to run the formatter. Canonical formatting decays '
                .'the first time somebody edits by hand: the formatter accepts both the collapsed '
                .'and the expanded shape, so nothing reports the drift and the next AST edit '
                .'reflows it. Gate it: `php-ast-edit format && <project formatter> && '
                .'git diff --exit-code`.';
        }

        return [
            'root' => $root,
            'status' => $findings === [] ? 'ready' : 'warn',
            'formatters' => $formatters,
            'canonical' => $config->canonical,
            'printWidth' => $config->width,
            'declaredIn' => $config->path,
            'formatterInCi' => $inCi,
            'editorconfig' => $editorconfig,
            'findings' => $findings,
        ];
    }

    private function formatterRunsInCi(string $root): bool
    {
        $needles = ['php-cs-fixer', 'pint', 'ecs check', 'ecs.php', 'phpcbf', 'ci:cgl', 'php-ast-edit format'];
        foreach (['.github/workflows', '.gitlab-ci.yml', '.gitlab', 'ci'] as $relative) {
            $path = $root.DIRECTORY_SEPARATOR.$relative;
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
        foreach (glob($path.'/*') ?: [] as $entry) {
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
