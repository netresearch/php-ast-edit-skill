<?php

declare(strict_types=1);

use Netresearch\PhpAstEdit\NodeLocation;
use Netresearch\PhpAstEdit\NodeLocator;
use PhpParser\Node\Expr;
use PhpParser\Node\Stmt;
use PhpParser\ParserFactory;

function intentRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new InvalidArgumentException($message);
    }
}

function intentSource(array $file, string $root): array
{
    intentRequire(is_string($file['path'] ?? null), 'Missing source path');
    $path = realpath($file['path']);
    intentRequire(
        is_string($path) && str_starts_with($path, $root . DIRECTORY_SEPARATOR),
        'Source outside root',
    );
    $source = file_get_contents($path);
    intentRequire(is_string($source), 'Cannot read source');
    intentRequire(
        is_string($file['sha256'] ?? null) && hash('sha256', $source) === $file['sha256'],
        'Stale source',
    );
    $parser = (new ParserFactory())->createForNewestSupportedVersion();

    return [$source, $parser->parse($source) ?? []];
}

function intentMethodLocation(
    NodeLocator $locator,
    array $roots,
    int $start,
    int $end,
): NodeLocation {
    $location = $locator->locate($roots, $start, 'Identifier');
    intentRequire(
        $location->start() === $start && $location->end() + 1 === $end,
        'Edit range is not one complete Identifier',
    );
    intentRequire($location->property === 'name', 'Edit is not a name slot');
    intentRequire(
        $location->parent instanceof Stmt\ClassMethod || $location->parent instanceof Expr\MethodCall || $location->parent instanceof Expr\NullsafeMethodCall || $location->parent instanceof Expr\StaticCall,
        'Only static method names are supported',
    );

    return $location;
}

function intentCollision(
    NodeLocator $locator,
    array $roots,
    NodeLocation $location,
    string $newName,
): void {
    if (!$location->parent instanceof Stmt\ClassMethod) {
        return;
    }

    foreach ($locator->ancestry($roots, $location->start()) as $ancestor) {
        if (!$ancestor->node instanceof Stmt\ClassLike) {
            continue;
        }

        foreach ($ancestor->node->getMethods() as $method) {
            intentRequire(
                strcasecmp((string) $method->name, $newName) !== 0,
                'Target method already exists',
            );
        }

        return;
    }

    throw new InvalidArgumentException('Method declaration has no class-like owner');
}

function intentAnchor(array $request, string $root, string $newName): array
{
    intentRequire(is_array($request['file'] ?? null), 'Missing anchor file');
    [, $roots] = intentSource($request['file'], $root);
    $select = $request['select'] ?? null;
    intentRequire(
        is_string($select) && str_starts_with($select, 'method:'),
        'Only method selectors are supported',
    );
    $locator = new NodeLocator();
    $selected = $locator->resolveSelect($roots, $select);
    intentRequire($selected->node instanceof Stmt\ClassMethod, 'Selector must identify a method');
    $name = $selected->node->name;
    $location = intentMethodLocation($locator, $roots, $name->getStartFilePos(), $name->getEndFilePos() + 1);
    $old = (string) $name;
    intentRequire(!str_starts_with($old, '__'), 'Magic method rename is unsupported');
    intentCollision($locator, $roots, $location, $newName);

    return [
        'name' => $old,
        'start' => $location->start(),
        'end' => $location->end() + 1,
        'ref' => $location->path,
    ];
}

function intentTranslateFile(array $file, string $root, string $newName, string $oldName): array
{
    [$source, $roots] = intentSource($file, $root);
    $locator = new NodeLocator();
    $edits = [];
    intentRequire(
        is_array($file['ranges'] ?? null) && $file['ranges'] !== [],
        'Missing edit ranges',
    );

    foreach ($file['ranges'] as $range) {
        intentRequire(
            is_array($range) && is_int($range['start'] ?? null) && is_int($range['end'] ?? null),
            'Invalid byte range',
        );
        $location = intentMethodLocation($locator, $roots, $range['start'], $range['end']);
        $actual = substr($source, $range['start'], $range['end'] - $range['start']);
        intentRequire(strcasecmp($actual, $oldName) === 0, 'Identifier differs from renamed method');
        intentCollision($locator, $roots, $location, $newName);
        $edits[] = [
            'operation' => 'set_name',
            'target' => ['ref' => $location->path, 'kind' => 'Identifier'],
            'expect' => ['name' => $actual, 'type' => 'Identifier'],
            'value' => $newName,
        ];
    }

    return ['path' => $file['path'], 'sha256' => $file['sha256'], 'edits' => $edits];
}

try {
    $autoload = getenv('PHP_AST_INTENT_AUTOLOAD');
    intentRequire(
        is_string($autoload) && is_file($autoload),
        'PHP_AST_INTENT_AUTOLOAD must name the engine autoloader',
    );
    require_once $autoload;
    $request = json_decode(stream_get_contents(STDIN), true, 512, JSON_THROW_ON_ERROR);
    intentRequire(is_array($request), 'Expected a request object');
    $root = $request['root'] ?? null;
    intentRequire(
        is_string($root) && realpath($root) === $root && is_dir($root),
        'Expected a canonical source root',
    );
    $newName = $request['to'] ?? null;
    intentRequire(
        is_string($newName) && preg_match('/^[A-Za-z_]\w*$/D', $newName) === 1,
        'New name must be an ASCII identifier',
    );
    intentRequire(!str_starts_with($newName, '__'), 'Magic method rename is unsupported');

    if (($request['mode'] ?? null) === 'anchor') {
        $result = intentAnchor($request, $root, $newName);
    } else {
        intentRequire(($request['mode'] ?? null) === 'translate', 'Unknown analysis mode');
        intentRequire(is_string($request['old_name'] ?? null), 'Missing old method name');
        intentRequire(
            is_array($request['files'] ?? null) && array_is_list($request['files']),
            'Expected file list',
        );
        $result = ['files' => []];

        foreach ($request['files'] as $file) {
            intentRequire(is_array($file), 'Invalid file request');
            $result['files'][] = intentTranslateFile($file, $root, $newName, $request['old_name']);
        }
    }
    echo json_encode($result, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), "\n";
} catch (Throwable $failure) {
    echo json_encode(['ok' => false, 'error' => $failure->getMessage()], JSON_THROW_ON_ERROR), "\n";
    exit(2);
}
