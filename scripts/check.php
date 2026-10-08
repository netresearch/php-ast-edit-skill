<?php

/*
 * SPDX-License-Identifier: MIT
 * SPDX-FileCopyrightText: Netresearch DTT GmbH
 */

declare(strict_types=1);
$root = dirname(__DIR__);
$paths = [
    $root . '/src',
    $root . '/bin/php-ast-edit',
    $root . '/scripts/build-phar.php',
    $root . '/tests/run.php',
    $root . '/scripts/check.php',
    $root . '/tests/matrix.php',
    $root . '/tests/catalog.php',
    $root . '/tests/corpus.php',
    $root . '/tests/formatting.php',
    $root . '/tests/php-floor.php',
    $root . '/tests/transactions.php',
    $root . '/tests/renames.php',
    $root . '/tests/distribution.php',
];
$files = [];
$missing = [];

foreach ($paths as $path) {
    if (is_dir($path)) {
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($path, FilesystemIterator::SKIP_DOTS),
        );

        foreach ($iterator as $file) {
            if ($file->isFile() && $file->getExtension() === 'php') {
                $files[] = $file->getPathname();
            }
        }
    } elseif (is_file($path)) {
        $files[] = $path;
    } else {
        $missing[] = $path;
    }
}

if ($missing !== []) {
    fwrite(STDERR, 'Listed path does not exist: ' . implode(', ', $missing) . "\n");
    exit(1);
}
$failed = false;

foreach ($files as $file) {
    $command = escapeshellarg(PHP_BINARY) . ' -l ' . escapeshellarg($file) . ' 2>&1';
    // nosemgrep: php.lang.security.exec-use.exec-use -- PHP_BINARY and the file path are each escapeshellarg()-quoted; the files are this repository's own tracked PHP sources
    exec($command, $output, $status);

    if ($status !== 0) {
        $failed = true;
        fwrite(STDERR, implode("\n", $output) . "\n");
    }
    $output = [];
}

if ($failed) {
    exit(1);
}
echo 'PHP syntax OK (' . count($files) . " files)\n";
