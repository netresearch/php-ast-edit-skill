<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;

/**
 * The repository's declaration that it is canonically formatted.
 *
 * Whether a file may be rewritten canonically cannot be measured from the file: the fixed
 * point belongs to the pair (printer, project formatter), and the formatter runs last. On a
 * correctly normalised TYPO3 extension, re-printing 48 of 63 files differed from disk — all
 * of it the formatter's own doing (blank lines, `declare` spacing, operator alignment). Any
 * threshold over that measurement would call a well-kept repository broken.
 *
 * So it is declared, not inferred. `php-ast-edit normalize` writes the marker; nothing else
 * does.
 */
final class RepositoryConfig
{
    public const FILE = '.php-ast-edit.json';

    public const MIN_WIDTH = 20;

    private function __construct(
        public readonly bool $canonical,
        public readonly int $width,
        public readonly ?string $path,
    ) {
    }

    /** Walk up from a file or directory until the marker turns up. */
    public static function discover(string $start): self
    {
        $directory = is_dir($start) ? $start : dirname($start);
        $directory = realpath($directory) ?: $directory;

        while (true) {
            $candidate = $directory.DIRECTORY_SEPARATOR.self::FILE;
            if (is_file($candidate)) {
                return self::fromFile($candidate);
            }
            $parent = dirname($directory);
            if ($parent === $directory) {
                return new self(false, CanonicalPrinter::DEFAULT_WIDTH, null);
            }
            $directory = $parent;
        }
    }

    public static function fromFile(string $path): self
    {
        $raw = file_get_contents($path);
        if ($raw === false) {
            throw new EditException('Cannot read '.$path);
        }
        try {
            $data = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
        } catch (\JsonException $failure) {
            throw new EditException(sprintf('%s is not valid JSON: %s', $path, $failure->getMessage()));
        }
        if (!is_array($data)) {
            throw new EditException($path.' must contain a JSON object.');
        }

        $width = $data['printWidth'] ?? CanonicalPrinter::DEFAULT_WIDTH;
        if (!is_int($width)) {
            throw new EditException($path.': printWidth must be an integer.');
        }
        self::assertWidth($width, $path.': ');

        return new self((bool) ($data['canonical'] ?? false), $width, $path);
    }

    /**
     * The repository root: where composer.json or .git lives.
     *
     * The marker describes a repository, so it must not land in whichever subdirectory
     * happened to be normalised — a marker under Classes/ would leave everything beside it
     * falling back to format-preserving printing.
     */
    public static function rootFor(string $start): string
    {
        $directory = is_dir($start) ? $start : dirname($start);
        $directory = realpath($directory) ?: $directory;
        $fallback = $directory;

        while (true) {
            foreach (['composer.json', '.git'] as $marker) {
                if (file_exists($directory.DIRECTORY_SEPARATOR.$marker)) {
                    return $directory;
                }
            }
            $parent = dirname($directory);
            if ($parent === $directory) {
                return $fallback;
            }
            $directory = $parent;
        }
    }

    /**
     * The one place that decides what a usable width is.
     *
     * Writing a width the read path would reject leaves a repository that declares itself
     * canonical and then fails every command until somebody edits the file by hand.
     */
    public static function assertWidth(int $width, string $prefix = ''): void
    {
        if ($width < self::MIN_WIDTH) {
            throw new EditException(sprintf(
                '%sprintWidth must be at least %d; %d cannot hold a useful line.',
                $prefix,
                self::MIN_WIDTH,
                $width,
            ));
        }
    }

    public static function write(string $directory, int $width): string
    {
        self::assertWidth($width);
        $path = rtrim($directory, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.self::FILE;
        $payload = json_encode(
            ['canonical' => true, 'printWidth' => $width],
            JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR,
        )."\n";
        if (file_put_contents($path, $payload) === false) {
            throw new EditException('Cannot write '.$path);
        }
        return $path;
    }
}
