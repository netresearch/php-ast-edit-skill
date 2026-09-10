<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;

/**
 * Member references from Phpactor's command line, one process per query.
 *
 * The command line rather than the language server: `references:member` answers the
 * whole question — declarations across the hierarchy, calls through any subtype or the
 * interface, `parent::` calls and first-class callables — in one JSON document, without
 * a framed protocol, an indexing handshake or a server to shut down. Measured on a TYPO3
 * extension with 130 project files and 16,000 vendor files: six to nine seconds a query,
 * and the same call sites a text search finds.
 *
 * The release is pinned by digest. A different Phpactor may resolve differently, and a
 * resolver is only trusted as far as the release it was measured with.
 */
final class PhpactorReferenceFinder implements ReferenceFinder
{
    public const RELEASE = '2026.07.22.0';

    public const SHA256 = '8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d';

    public const URL = 'https://github.com/phpactor/phpactor/releases/download/2026.07.22.0/phpactor.phar';

    public const ENVIRONMENT = 'PHP_AST_EDIT_PHPACTOR';

    private const TIMEOUT = 180;

    public function __construct(private readonly string $phar)
    {
        $digest = is_file($phar) ? hash_file('sha256', $phar) : false;

        if ($digest !== self::SHA256) {
            throw new EditException(
                sprintf(
                    '%s is not Phpactor %s (sha256 %s). %s',
                    $phar,
                    self::RELEASE,
                    self::SHA256,
                    self::installHint(),
                ),
            );
        }
    }

    /** The PHAR this repository points at, from the environment or `.php-ast-edit.json`. */
    public static function locate(RepositoryConfig $config): ?string
    {
        $fromEnvironment = getenv(self::ENVIRONMENT);

        if (is_string($fromEnvironment) && $fromEnvironment !== '') {
            return $fromEnvironment;
        }

        if ($config->phpactor === null || $config->path === null) {
            return null;
        }

        return str_starts_with($config->phpactor, '/') ? $config->phpactor : \dirname($config->path) . DIRECTORY_SEPARATOR . $config->phpactor;
    }

    public static function installHint(): string
    {
        return sprintf(
            'Download it once: curl -sSL -o .Build/bin/phpactor.phar %s, check `sha256sum .Build/bin/phpactor.phar` against %s, and set "phpactor": ".Build/bin/phpactor.phar" in .php-ast-edit.json (or %s to its path).',
            self::URL,
            self::SHA256,
            self::ENVIRONMENT,
        );
    }

    public function references(string $root, string $class, string $member): array
    {
        $state = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'php-ast-edit-phpactor' . DIRECTORY_SEPARATOR . hash('sha256', $root);
        // Phpactor reads user configuration and keeps its cache under the XDG directories.
        // Pointing them at a directory of our own keeps a developer's settings out of the
        // resolution and still lets repeated queries in one project share a cache.
        $environment = getenv();

        foreach (['XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'] as $name) {
            $directory = $state . DIRECTORY_SEPARATOR . strtolower($name);

            if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
                throw new EditException('Cannot create the resolver state directory ' . $directory);
            }
            $environment[$name] = $directory;
        }
        $command = [
            PHP_BINARY,
            $this->phar,
            'references:member',
            ltrim($class, '\\'),
            $member,
            '--format=json',
            '--risky',
            '--filesystem=git',
            '--no-interaction',
            '--working-dir=' . $root,
        ];
        [$status, $output, $errors] = $this->run($command, $root, $environment);

        if ($status !== 0) {
            throw new EditException(
                sprintf(
                    'Phpactor could not resolve %s::%s (exit %d): %s',
                    $class,
                    $member,
                    $status,
                    trim($errors) ?: trim($output),
                ),
            );
        }

        try {
            $document = json_decode($output, true, 64, JSON_THROW_ON_ERROR);
        } catch (\JsonException $failure) {
            throw new EditException(
                'Phpactor answered with something other than JSON: ' . $failure->getMessage(),
            );
        }
        $references = [];
        $risky = [];

        foreach (is_array($document['references'] ?? null) ? $document['references'] : [] as $file) {
            $path = is_string($file['file'] ?? null) ? $file['file'] : null;

            if ($path === null) {
                throw new EditException('Phpactor named a reference without its file.');
            }

            foreach ($file['references'] ?? [] as $site) {
                if (!is_int($site['start'] ?? null) || !is_int($site['end'] ?? null)) {
                    throw new EditException(
                        'Phpactor named a reference in ' . $path . ' without its offsets.',
                    );
                }
                $references[] = [
                    'file' => $path,
                    'start' => $site['start'],
                    'end' => $site['end'],
                    'line' => (int) ($site['line_no'] ?? 0),
                ];
            }

            foreach ($file['risky_references'] ?? [] as $site) {
                $risky[] = [
                    'file' => $path,
                    'line' => (int) ($site['line_no'] ?? 0),
                    'text' => trim((string) ($site['line'] ?? '')),
                ];
            }
        }

        return ['references' => $references, 'risky' => $risky, 'resolver' => 'phpactor ' . self::RELEASE];
    }

    /**
     * @param list<string>          $command
     * @param array<string, string> $environment
     * @return array{int, string, string}
     */
    private function run(array $command, string $cwd, array $environment): array
    {
        $process = proc_open(
            $command,
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
            $cwd,
            $environment,
        );

        if (!is_resource($process)) {
            throw new EditException('Cannot start Phpactor.');
        }
        fclose($pipes[0]);
        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);
        $output = '';
        $errors = '';
        $deadline = microtime(true) + self::TIMEOUT;

        while (true) {
            $read = [$pipes[1], $pipes[2]];
            $write = null;
            $except = null;

            if (stream_select($read, $write, $except, 1) === false) {
                break;
            }

            foreach ($read as $stream) {
                $chunk = (string) fread($stream, 65536);
                $stream === $pipes[1] ? $output .= $chunk : $errors .= $chunk;
            }

            if (feof($pipes[1]) && feof($pipes[2])) {
                break;
            }

            if (microtime(true) > $deadline) {
                proc_terminate($process, 9);

                throw new EditException(
                    sprintf('Phpactor did not answer within %d seconds.', self::TIMEOUT),
                );
            }
        }
        fclose($pipes[1]);
        fclose($pipes[2]);

        return [proc_close($process), $output, $errors];
    }
}
