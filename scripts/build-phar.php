<?php

declare(strict_types=1);
$root = dirname(__DIR__);
$vendorAutoload = $root . '/vendor/autoload.php';

if (!is_file($vendorAutoload)) {
    fwrite(STDERR, "Run composer install before building the PHAR.\n");
    exit(2);
}

if ((int) ini_get('phar.readonly') !== 0) {
    fwrite(STDERR, "Run with php -d phar.readonly=0 scripts/build-phar.php\n");
    exit(2);
}
require_once $vendorAutoload;

if ((Composer\InstalledVersions::getRootPackage()['dev'] ?? true) !== false) {
    fwrite(
        STDERR,
        "Refusing to bundle development dependencies. Use bash scripts/build-release.sh or install with composer install --no-dev in a clean checkout.\n",
    );
    exit(2);
}
$dist = $root . '/dist';

if (!is_dir($dist)) {
    mkdir($dist, 0777, true);
}
$target = $dist . '/php-ast-edit.phar';
@unlink($target);
$phar = new Phar($target);
$phar->startBuffering();
$phar->setSignatureAlgorithm(Phar::SHA256);

foreach (['bin', 'src', 'vendor'] as $directory) {
    $base = $root . '/' . $directory;
    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($base, FilesystemIterator::SKIP_DOTS),
    );

    foreach ($iterator as $file) {
        if ($file->isLink()) {
            throw new RuntimeException('Refusing to package symlink: ' . $file->getPathname());
        }

        if (!$file->isFile()) {
            continue;
        }
        $local = substr($file->getPathname(), strlen($root) + 1);
        $phar->addFile($file->getPathname(), $local);
    }
}

foreach (['LICENSE-MIT', 'LICENSE-CC-BY-SA-4.0'] as $license) {
    $phar->addFile($root . '/' . $license, $license);
}
$stub = <<<'PHP'
#!/usr/bin/env php
<?php
Phar::mapPhar('php-ast-edit.phar');
require 'phar://php-ast-edit.phar/bin/php-ast-edit';
__HALT_COMPILER();
PHP;
$phar->setStub($stub);
$phar->stopBuffering();
chmod($target, 0755);
echo $target . "\n";
