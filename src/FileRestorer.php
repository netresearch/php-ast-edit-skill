<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;

/** Restores bytes, permission bits and a directly addressed symlink after a failed write. */
final class FileRestorer
{
    public function restore(FileTransaction $file): void
    {
        if (!$file->existed) {
            if ((is_file($file->path) || is_link($file->path)) && !@unlink($file->path)) {
                throw new EditException('Cannot remove newly created ' . $file->path);
            }

            return;
        }

        if ($file->mode !== 'delete' || $file->linkTarget === null) {
            $path = $file->resolvedPath ?? $file->path;

            if (is_link($path) && !@unlink($path)) {
                throw new EditException('Cannot remove replacement symlink at ' . $path);
            }
            (new AtomicWriter())->write($path, (string) $file->source);

            if ($file->permissions !== null && !@chmod($path, $file->permissions)) {
                throw new EditException('Cannot restore permissions on ' . $path);
            }
        }

        if ($file->linkTarget !== null && (!is_link($file->path) || readlink($file->path) !== $file->linkTarget)) {
            if ((file_exists($file->path) || is_link($file->path)) && !@unlink($file->path)) {
                throw new EditException('Cannot restore symlink at ' . $file->path);
            }

            if (!@symlink($file->linkTarget, $file->path)) {
                throw new EditException('Cannot recreate symlink at ' . $file->path);
            }
        }
    }
}
