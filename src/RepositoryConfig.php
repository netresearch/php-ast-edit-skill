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

    /**
     * @param list<string> $exclude repository-relative paths normalisation must not touch
     * @param ?int $width the width the last normalisation ran at — a record, not the source.
     *                    The source is the project's own `.editorconfig`; this exists so drift
     *                    between the two can be reported.
     */
    private function __construct(
        public readonly bool $canonical,
        public readonly int $width,
        public readonly ?string $path,
        public readonly array $exclude = [],
        /** @var list<string>|null */
        public readonly ?array $formatter = null,
    ) {}

    /** Walk up from a file or directory until the marker turns up. */
    public static function discover(string $start): self
    {
        $directory = is_dir($start) ? $start : dirname($start);
        $directory = realpath($directory) ?: $directory;

        while (true) {
            $candidate = $directory . DIRECTORY_SEPARATOR . self::FILE;

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
            throw new EditException('Cannot read ' . $path);
        }

        try {
            $data = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
        } catch (\JsonException $failure) {
            throw new EditException(sprintf('%s is not valid JSON: %s', $path, $failure->getMessage()));
        }

        if (!is_array($data)) {
            throw new EditException($path . ' must contain a JSON object.');
        }
        $width = $data['printWidth'] ?? CanonicalPrinter::DEFAULT_WIDTH;

        if (!is_int($width)) {
            throw new EditException($path . ': printWidth must be an integer.');
        }
        self::assertWidth($width, $path . ': ');
        $exclude = $data['exclude'] ?? [];

        if (!is_array($exclude)) {
            throw new EditException($path . ': exclude must be an array of paths.');
        }
        self::assertExclusions($exclude, $path . ': ');
        $formatter = $data['formatter'] ?? null;

        if ($formatter !== null) {
            if (!is_array($formatter)) {
                throw new EditException($path . ": formatter must be an array of command arguments.");
            }
            self::assertFormatter($formatter, $path . ": ");
            $formatter = array_values(array_map(strval(...), $formatter));
        }

        return new self(
            (bool) ($data['canonical'] ?? false),
            $width,
            $path,
            array_values(array_map(strval(...), $exclude)),
            $formatter,
        );
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
                if (file_exists($directory . DIRECTORY_SEPARATOR . $marker)) {
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
    /**
     * The width the printer must use for this repository, and where it came from.
     *
     * The project declares it in `.editorconfig`, which no single formatter owns. This
     * package does not carry a default: a repository that declares nothing does not get
     * canonical printing, it gets the fallback and a reason.
     *
     * @return array{width: ?int, source: ?string, recorded: ?int}
     */
    public static function widthFor(string $start): array
    {
        $declared = EditorConfig::discover($start);
        $recorded = self::discover($start)->width;

        // Validate here, where the value is read, rather than at write() — by then the
        // formatter has already rewritten the files at a width that was never usable.
        if ($declared->maxLineLength !== null) {
            self::assertWidth($declared->maxLineLength, ($declared->path ?? '.editorconfig') . ': ');
        }

        return [
            'width' => $declared->maxLineLength,
            'source' => $declared->maxLineLength === null ? null : $declared->path,
            'recorded' => $recorded,
        ];
    }

    public static function assertWidth(int $width, string $prefix = ''): void
    {
        if ($width < self::MIN_WIDTH) {
            throw new EditException(
                sprintf(
                    '%sprintWidth must be at least %d; %d cannot hold a useful line.',
                    $prefix,
                    self::MIN_WIDTH,
                    $width,
                ),
            );
        }
    }

    /** @param list<string> $exclude */
    /**
     * An exclusion must name something.
     *
     * An empty string resolves to the repository root, which excludes every file — and the
     * formatting gate would then pass without having looked at anything. A check that fires
     * for nobody is worse than no check.
     *
     * @param array<mixed> $exclude
     */
    public static function assertExclusions(array $exclude, string $prefix = ''): void
    {
        foreach ($exclude as $entry) {
            if (!is_string($entry) || trim($entry) === '' || trim($entry, './') === '') {
                throw new EditException(
                    sprintf(
                        '%sexclude entries must be non-empty repository-relative paths; %s excludes everything.',
                        $prefix,
                        var_export($entry, true),
                    ),
                );
            }
        }
    }

    public static function write(string $directory, int $width, array $exclude = []): string
    {
        self::assertWidth($width);
        self::assertExclusions($exclude);
        $path = rtrim($directory, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . self::FILE;
        $payload = json_encode(
            array_filter(
                ['canonical' => true, 'printWidth' => $width, 'exclude' => array_values($exclude)],
                static fn (mixed $value): bool => $value !== [],
            ),
            JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR,
        ) . "\n";

        if (file_put_contents($path, $payload) === false) {
            throw new EditException('Cannot write ' . $path);
        }

        return $path;
    }

    /**
     * Whether the project put this file out of the tool's reach.
     *
     * `format` and `normalize` read the list when they collect files; an edit reaches a file
     * by name and never collects, so it used to print an excluded file canonically anyway.
     * The exclusion exists because the pair of printer and formatter must not run there —
     * a TYPO3 `ext_emconf.php` cannot carry the `declare(strict_types=1)` the formatter adds,
     * and TER stops parsing it — so it has to hold for every entry point, not only the ones
     * that walk a directory.
     *
     * A file being created does not exist yet, so its own path cannot be resolved. Resolving
     * the deepest ancestor that does exist keeps the guarantee for `mode: create`: a new file
     * inside an excluded directory is excluded before it is ever written.
     */
    public function excludes(string $file): bool
    {
        if ($this->exclude === [] || $this->path === null) {
            return false;
        }
        $target = self::resolveThroughAncestors($file);

        if ($target === null) {
            return false;
        }
        $root = \dirname($this->path);

        foreach ($this->exclude as $entry) {
            $candidate = realpath($root . DIRECTORY_SEPARATOR . ltrim($entry, '/'));

            if ($candidate === false) {
                continue;
            }

            if ($target === $candidate || str_starts_with($target, $candidate . DIRECTORY_SEPARATOR)) {
                return true;
            }
        }

        return false;
    }

    /** The element of a declared formatter that stands for the files an edit wrote. */
    public const FILES_PLACEHOLDER = '{files}';

    /**
     * The formatter the project declares, as an argv list with one `{files}` placeholder.
     *
     * A list rather than a command line: nothing goes through a shell, so a path with a space
     * in it cannot become two arguments and nothing in the declaration can be made to run a
     * second command. The placeholder is a whole element, expanded to the files an edit wrote
     * — running the formatter over the entire tree would put unrelated files into the diff of
     * whatever change happened to be made.
     *
     * @param array<mixed> $formatter
     */
    public static function assertFormatter(array $formatter, string $prefix = ''): void
    {
        if ($formatter === []) {
            throw new EditException($prefix . 'formatter must not be empty.');
        }

        if (!array_is_list($formatter)) {
            throw new EditException(
                $prefix . 'formatter must be a list of arguments; a JSON object gives them names nothing reads.',
            );
        }
        $placeholders = 0;

        foreach ($formatter as $argument) {
            if (!is_string($argument) || $argument === '') {
                throw new EditException($prefix . 'formatter entries must be non-empty strings.');
            }

            if ($argument === self::FILES_PLACEHOLDER) {
                ++$placeholders;
            }
        }

        if ($placeholders !== 1) {
            throw new EditException(
                sprintf(
                    '%sformatter must carry the %s placeholder exactly once, so the files an edit wrote can be named.',
                    $prefix,
                    self::FILES_PLACEHOLDER,
                ),
            );
        }
    }

    /**
     * An absolute path for `$file`, resolved as far as the filesystem allows.
     *
     * `realpath()` answers false for anything that does not exist yet, which is every file a
     * `create` is about. Walking up to the deepest existing ancestor and re-attaching the
     * rest gives a path that can be compared with a resolved exclusion.
     */
    private static function resolveThroughAncestors(string $file): ?string
    {
        $resolved = realpath($file);

        if ($resolved !== false) {
            return $resolved;
        }
        $tail = [];
        $current = $file;

        while (true) {
            $parent = \dirname($current);

            if ($parent === $current) {
                return null;
            }
            array_unshift($tail, basename($current));
            $resolved = realpath($parent);

            if ($resolved !== false) {
                return $resolved . DIRECTORY_SEPARATOR . implode(DIRECTORY_SEPARATOR, $tail);
            }
            $current = $parent;
        }
    }
}
