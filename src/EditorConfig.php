<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

/**
 * Reads the line width a project declares for itself.
 *
 * The printer has to choose line breaks — it cannot emit code without choosing — but the
 * number it chooses by is the project's, not this package's. `.editorconfig` is where a
 * project states it in a way no single formatter owns, and where an editor already honours
 * it. Where a project declares nothing, canonical printing is not available to it; the tool
 * says so rather than inventing a width.
 *
 * A documented subset of the format, not an implementation of the spec:
 *
 * - sections `[*]` and any section whose pattern mentions `php` literally
 * - `max_line_length`, as an integer; `off` counts as no declaration
 * - the nearest `.editorconfig` wins, and `root = true` stops the walk upwards
 * - no brace expansion, no character classes, no `!` negation
 *
 * Anything outside that is reported as undeclared rather than guessed at, which is the
 * failure direction that cannot silently reformat somebody's repository.
 */
final class EditorConfig
{
    private function __construct(
        public readonly ?int $maxLineLength,
        public readonly ?string $path,
        public readonly ?string $section,
    ) {}

    public static function discover(string $start): self
    {
        $directory = is_dir($start) ? $start : dirname($start);
        $directory = realpath($directory) ?: $directory;

        while (true) {
            $candidate = $directory . DIRECTORY_SEPARATOR . '.editorconfig';

            if (is_file($candidate)) {
                $found = self::read($candidate);

                if ($found->maxLineLength !== null) {
                    return $found;
                }

                if (self::isRoot($candidate)) {
                    return new self(null, $candidate, null);
                }
            }
            $parent = dirname($directory);

            if ($parent === $directory) {
                return new self(null, null, null);
            }
            $directory = $parent;
        }
    }

    public static function read(string $path): self
    {
        $contents = file_get_contents($path);

        if ($contents === false) {
            return new self(null, $path, null);
        }
        $section = null;
        $best = null;
        $bestSection = null;

        foreach (preg_split('/\R/', $contents) ?: [] as $line) {
            $line = trim($line);

            if ($line === '' || str_starts_with($line, '#') || str_starts_with($line, ';')) {
                continue;
            }

            if (str_starts_with($line, '[') && str_ends_with($line, ']')) {
                $section = substr($line, 1, -1);

                continue;
            }

            if (!str_contains($line, '=') || !self::applies($section)) {
                continue;
            }
            [$key, $value] = array_map(trim(...), explode('=', $line, 2));

            if (strtolower($key) !== 'max_line_length') {
                continue;
            }

            if (!ctype_digit($value)) {
                // `off` and anything unparseable mean the project declared no limit here.
                continue;
            }

            // A php-specific section outranks the catch-all, whatever their order.
            if ($best === null || self::isPhpSpecific($section)) {
                $best = (int) $value;
                $bestSection = $section;
            }
        }

        return new self($best, $path, $bestSection);
    }

    private static function applies(?string $section): bool
    {
        return $section === '*' || self::isPhpSpecific($section);
    }

    private static function isPhpSpecific(?string $section): bool
    {
        return $section !== null && $section !== '*' && str_contains($section, 'php');
    }

    private static function isRoot(string $path): bool
    {
        $contents = file_get_contents($path);

        if ($contents === false) {
            return false;
        }

        foreach (preg_split('/\R/', $contents) ?: [] as $line) {
            $line = trim($line);

            if (str_starts_with($line, '[')) {
                return false;
                // `root` is only meaningful before the first section.
            }

            if (preg_match('/^root\s*=\s*true$/i', $line) === 1) {
                return true;
            }
        }

        return false;
    }
}
