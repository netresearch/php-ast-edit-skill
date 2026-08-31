<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Error as ParserError;
use PhpParser\ParserFactory;
use PhpParser\PhpVersion;

/**
 * Prints a tree of PHP files through the canonical printer.
 *
 * This is one half of the fixed point, never the whole of it. The project's own formatter
 * runs after it and has the last word on everything the printer has no opinion about —
 * blank lines, operator alignment, import order, the licence header. Which is why there is
 * no `--check` here: on a correctly normalised repository this printer's output differs
 * from disk in most files, because the formatter touched them afterwards. A check that is
 * red on the intended state is not a check. The gate is the whole chain:
 *
 *     php-ast-edit format && <project formatter> && git diff --exit-code
 */
final class Formatter
{
    public function __construct(
        private readonly ?string $phpVersion = null,
    ) {
    }

    /**
     * @param list<string> $paths files or directories
     * @return array{scanned: int, changed: list<string>, failed: array<string, string>}
     */
    public function format(array $paths, int $width, bool $dryRun): array
    {
        $version = $this->phpVersion === null ? null : PhpVersion::fromString($this->phpVersion);
        $parser = $version === null
            ? (new ParserFactory())->createForHostVersion()
            : (new ParserFactory())->createForVersion($version);
        $printer = new CanonicalPrinter($version, $width);

        $scanned = 0;
        $changed = [];
        $failed = [];

        foreach ($this->collect($paths) as $file) {
            ++$scanned;
            $source = file_get_contents($file);
            if ($source === false) {
                $failed[$file] = 'cannot read';
                continue;
            }
            try {
                $roots = $parser->parse($source) ?? [];
                $output = rtrim($printer->prettyPrintFile($roots), "\r\n")."\n";
                // The same net as a transaction: nothing unparseable is written.
                $parser->parse($output);
            } catch (ParserError $error) {
                $failed[$file] = $error->getRawMessage();
                continue;
            }
            if ($output === $source) {
                continue;
            }
            $changed[] = $file;
            if ($dryRun) {
                continue;
            }
            try {
                // Same discipline as a transaction: a crash mid-write must not truncate
                // somebody's source file.
                $this->atomicWrite($file, $output);
            } catch (EditException $failure) {
                $failed[$file] = $failure->getMessage();
            }
        }

        return ['scanned' => $scanned, 'changed' => $changed, 'failed' => $failed];
    }

    private function atomicWrite(string $path, string $contents): void
    {
        $directory = dirname($path);
        if (!is_writable($directory)) {
            throw new EditException('Directory is not writable: '.$directory);
        }
        $temp = @tempnam($directory, '.php-ast-edit-');
        if ($temp === false || realpath(dirname($temp)) !== realpath($directory)) {
            if (is_string($temp) && is_file($temp)) {
                @unlink($temp);
            }
            throw new EditException('Cannot create a temporary file next to '.$path);
        }
        try {
            $mode = fileperms($path);
            if (@file_put_contents($temp, $contents) === false) {
                throw new EditException('Cannot write a temporary file for '.$path);
            }
            @chmod($temp, $mode !== false ? ($mode & 0777) : (0666 & ~umask()));
            if (!@rename($temp, $path)) {
                throw new EditException('Atomic rename failed for '.$path);
            }
        } finally {
            if (is_file($temp)) {
                @unlink($temp);
            }
        }
    }

    /**
     * @param list<string> $paths
     * @return list<string>
     */
    private function collect(array $paths): array
    {
        $files = [];
        foreach ($paths as $path) {
            if (is_file($path)) {
                $files[] = $path;
                continue;
            }
            if (!is_dir($path)) {
                throw new EditException('No such file or directory: '.$path);
            }
            $iterator = new \RecursiveIteratorIterator(
                new \RecursiveDirectoryIterator($path, \FilesystemIterator::SKIP_DOTS),
            );
            foreach ($iterator as $entry) {
                if (!$entry->isFile() || $entry->getExtension() !== 'php') {
                    continue;
                }
                $real = $entry->getPathname();
                // Nobody's dependencies are ours to reformat.
                if (preg_match('#(^|/)(vendor|node_modules|\.Build|\.git)/#', $real) === 1) {
                    continue;
                }
                $files[] = $real;
            }
        }
        sort($files);
        return array_values(array_unique($files));
    }
}
