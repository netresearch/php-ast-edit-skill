<?php

declare(strict_types=1);

$phar = new Phar($argv[1]);

foreach (['src/distribution-untracked.txt', 'bin/distribution-untracked.txt'] as $entry) {
    if (isset($phar[$entry])) {
        throw new RuntimeException('Untracked build source leaked into PHAR: ' . $entry);
    }
}

foreach ([
    'bin/php-ast-edit',
    'src/Application.php',
    'vendor/autoload.php',
    'vendor/nikic/php-parser/lib/PhpParser/ParserFactory.php',
    'LICENSE-MIT',
    'LICENSE-CC-BY-SA-4.0',
] as $required) {
    if (!isset($phar[$required])) {
        throw new RuntimeException('PHAR is missing ' . $required);
    }
}
$installed = json_decode($phar['vendor/composer/installed.json']->getContent(), true, 512, JSON_THROW_ON_ERROR);

if ($installed['dev'] !== false) {
    throw new RuntimeException('PHAR contains a development installation.');
}

foreach ($installed['packages'] as $package) {
    if ($package['name'] === 'friendsofphp/php-cs-fixer') {
        throw new RuntimeException('PHAR contains development tools.');
    }
}

foreach (new RecursiveIteratorIterator($phar) as $file) {
    $path = $file->getPathname();

    if (str_contains($path, '/vendor/friendsofphp/') || str_contains($path, '/.git/')) {
        throw new RuntimeException('Unexpected archive entry: ' . $path);
    }
}

if (($phar->getSignature()['hash_type'] ?? '') !== 'SHA-256') {
    throw new RuntimeException('PHAR must use a SHA-256 integrity signature.');
}
echo "OK: PHAR contains runtime dependencies, licenses and SHA-256 integrity metadata only\n";
