<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;

/**
 * Replaces a file's contents without ever leaving it half-written.
 *
 * Write to a temporary file in the same directory, then rename over the target: the rename
 * is atomic, so a reader sees either the old file or the new one and never a truncated one.
 *
 * Two details that are easy to get wrong and were:
 *
 * - `tempnam()` silently falls back to the system temp directory when it cannot write the
 *   one it was given, which turns the rename into a cross-device move and loses atomicity.
 * - `rename()` over a symlink replaces the *link* with a regular file, so the link topology
 *   changes and the file everybody else reads stays untouched. The path is resolved first.
 */
final class AtomicWriter
{
    public function write(string $path, string $contents): void
    {
        $path = $this->resolveSymlink($path);
        $directory = dirname($path);

        if (!is_dir($directory) && !@mkdir($directory, 0777, true) && !is_dir($directory)) {
            throw new EditException('Cannot create directory ' . $directory);
        }

        if (!is_writable($directory)) {
            throw new EditException('Directory is not writable: ' . $directory);
        }
        $existed = is_file($path);
        $temp = @tempnam($directory, '.php-ast-edit-');

        if ($temp === false || realpath(dirname($temp)) !== realpath($directory)) {
            if (is_string($temp) && is_file($temp)) {
                @unlink($temp);
            }

            throw new EditException('Cannot create a temporary file next to ' . $path);
        }

        try {
            $mode = $existed ? fileperms($path) : false;

            if (@file_put_contents($temp, $contents) === false) {
                throw new EditException('Cannot write a temporary file for ' . $path);
            }
            @chmod($temp, $mode !== false ? $mode & 0777 : 0666 & ~umask());

            if (!@rename($temp, $path)) {
                throw new EditException('Atomic rename failed for ' . $path);
            }
        } finally {
            if (is_file($temp)) {
                @unlink($temp);
            }
        }
    }

    /** Follow a chain of links to the file that actually holds the bytes. */
    private function resolveSymlink(string $path): string
    {
        $seen = 0;

        while (is_link($path)) {
            if (++$seen > 40) {
                throw new EditException('Too many levels of symbolic links: ' . $path);
            }
            $target = readlink($path);

            if ($target === false) {
                throw new EditException('Cannot read the symlink ' . $path);
            }
            $path = str_starts_with($target, DIRECTORY_SEPARATOR) ? $target : dirname($path) . DIRECTORY_SEPARATOR . $target;
        }

        return $path;
    }
}
