<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node\Stmt;
use PhpParser\NodeFinder;
use PhpParser\ParserFactory;

/** Translate a named method change into one snapshot-guarded engine transaction. */
final class MethodRenameCommand
{
    private const FLAGS = ['method', 'to', 'path', 'file', 'sha256', 'report', 'mocks', 'dry-run'];

    public function document(array $options): array
    {
        $this->validateOptions($options);
        $symbol = $this->text($options, 'method');
        $to = $this->text($options, 'to');
        [$owner, $method] = $this->symbol($symbol);

        if (!$this->identifier($to)) {
            throw new EditException('--to must be a PHP method name.');
        }
        $files = $this->discoveryFiles($options);
        $matches = $this->declarations($files, $owner, $method);

        $found = $this->uniqueMatch($matches, $symbol);

        if (isset($options['sha256']) && !hash_equals($this->text($options, 'sha256'), $found['sha256'])) {
            throw new EditException(
                'STALE_SOURCE: ' . $found['path'] . ' no longer matches expected sha256.',
            );
        }
        $mocks = $options['mocks'] ?? false;

        return [
            'report' => $this->text($options, 'report', 'compact'),
            'files' => [
                [
                    'path' => $found['path'],
                    'sha256' => $found['sha256'],
                    'edits' => [
                        [
                            'operation' => 'rename_method',
                            'target' => ['ref' => $found['ref'], 'kind' => 'Stmt_ClassMethod'],
                            'to' => $to,
                            'project' => !$found['private'] || $mocks,
                            'mocks' => $mocks,
                        ],
                    ],
                ],
            ],
        ];
    }

    /** @param array<string, mixed> $options */
    private function validateOptions(array $options): void
    {
        $unknown = array_diff(array_keys($options), self::FLAGS);

        if ($unknown !== []) {
            throw new EditException(
                'rename does not accept --' . implode(', --', $unknown) . '. Use --method Class::old --to new; file and caller discovery are automatic.',
            );
        }

        foreach (['mocks', 'dry-run'] as $flag) {
            if (array_key_exists($flag, $options) && $options[$flag] !== true) {
                throw new EditException('--' . $flag . ' takes no value.');
            }
        }

        if (!in_array($this->text($options, 'report', 'compact'), ['agent', 'full', 'compact'], true)) {
            throw new EditException('--report must be agent, full or compact.');
        }
    }

    /** @param array<string, mixed> $options */
    private function text(array $options, string $key, ?string $default = null): string
    {
        $value = $options[$key] ?? $default;

        if (!is_string($value) || trim($value) === '') {
            throw new EditException('rename requires --' . $key . ' with a non-empty value.');
        }

        return $value;
    }

    private function identifier(string $name): bool
    {
        return preg_match('/^[A-Za-z_\x80-\xff][A-Za-z0-9_\x80-\xff]*$/D', $name) === 1;
    }

    private function declarations(array $files, string $owner, string $method): array
    {
        $matches = [];
        $qualified = str_contains($owner, '\\');
        $owner = ltrim($owner, '\\');
        $parser = (new ParserFactory())->createForHostVersion();

        foreach ($files as $file) {
            $source = file_get_contents($file);

            if ($source === false) {
                throw new EditException('Cannot read ' . $file);
            }
            $roots = $parser->parse($source) ?? [];

            foreach ((new NodeFinder())->findInstanceOf($roots, Stmt\ClassLike::class) as $class) {
                $name = ProjectIndex::nameOf($class, $roots);

                if ($name === null || strcasecmp($qualified ? $name : (string) $class->name, $owner) !== 0) {
                    continue;
                }
                array_push(
                    $matches,
                    ...$this->methodMatches($class, $roots, $file, $source, $name, $method),
                );
            }
        }

        return $matches;
    }

    /** @return list<string> */
    private function containedFiles(ProjectIndex $index, string $path): array
    {
        if ($path !== $index->root) {
            throw new EditException('--path must name the project root: ' . $index->root);
        }
        $files = $index->phpFiles();
        $prefix = rtrim($index->root, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;

        foreach ($files as $file) {
            if (!str_starts_with($file, $prefix)) {
                throw new EditException('Project discovery escapes its root through a symlink: ' . $file);
            }
        }

        return $files;
    }

    private function symbol(string $symbol): array
    {
        $parts = explode('::', $symbol);

        if (count($parts) !== 2 || !$this->identifier($parts[1])) {
            throw new EditException('--method must name Class::method or Namespace\Class::method.');
        }
        [$owner, $method] = $parts;

        foreach (explode('\\', ltrim($owner, '\\')) as $part) {
            if (!$this->identifier($part)) {
                throw new EditException('--method must name Class::method or Namespace\Class::method.');
            }
        }

        return [$owner, $method];
    }

    private function discoveryFiles(array $options): array
    {
        $path = realpath($this->text($options, 'path', '.'));

        if ($path === false || !is_dir($path)) {
            throw new EditException('--path must name an existing project directory.');
        }
        $index = ProjectIndex::for($path);
        $files = $this->containedFiles($index, array_key_exists('path', $options) ? $path : $index->root);

        if (isset($options['file'])) {
            $requested = $this->text($options, 'file');
            $requested = str_starts_with($requested, DIRECTORY_SEPARATOR) ? $requested : $path . DIRECTORY_SEPARATOR . $requested;
            $file = realpath($requested);

            if ($file === false || is_link($requested) || !$index->isProjectFile($file)) {
                throw new EditException(
                    '--file must name a non-symlink PHP file in this project, outside its exclusions.',
                );
            }
            $files = [$file];
        }

        return $files;
    }

    private function uniqueMatch(array $matches, string $symbol): array
    {
        if (count($matches) !== 1) {
            $names = array_map(
                static fn (array $entry): string => $entry['symbol'] . ' in ' . $entry['path'],
                $matches,
            );

            throw new EditException(
                $matches === [] ? 'No declaration matches ' . $symbol . '. Name the declaring class, not an inherited-only receiver; check --path and project exclusions.' : 'Ambiguous method ' . $symbol . ': ' . implode('; ', $names) . '. Use the fully qualified class name and, if needed, --file.',
            );
        }
        $found = $matches[0];

        return $found;
    }

    private function methodMatches(
        Stmt\ClassLike $class,
        array $roots,
        string $file,
        string $source,
        string $name,
        string $method,
    ): array {
        $matches = [];
        $locator = new NodeLocator();

        foreach ($class->getMethods() as $declaration) {
            if (strcasecmp($declaration->name->toString(), $method) !== 0) {
                continue;
            }
            $location = $locator->locate($roots, $declaration->getStartFilePos(), 'Stmt_ClassMethod');
            $matches[] = [
                'path' => $file,
                'symbol' => $name . '::' . $declaration->name,
                'ref' => $location->path,
                'sha256' => hash('sha256', $source),
                'private' => $declaration->isPrivate(),
            ];
        }

        return $matches;
    }
}
