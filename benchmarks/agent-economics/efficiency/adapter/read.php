<?php

declare(strict_types=1);

use Netresearch\PhpAstEdit\NodeLocator;
use PhpParser\Node;
use PhpParser\Node\Stmt;
use PhpParser\ParserFactory;

/** Return the exact node text, including its attached comments. */
function sourceOf(string $source, Node $node): string
{
    $start = $node->getStartFilePos();

    foreach ($node->getComments() as $comment) {
        $start = min($start, $comment->getStartFilePos());
    }

    return substr($source, $start, $node->getEndFilePos() - $start + 1);
}

/** Return the declaration up to its body opener, ignoring braces inside attributes/defaults. */
function declarationOf(string $source, Node $node, array $tokens): string
{
    $depth = 0;

    for ($i = $node->getStartTokenPos(); $i <= $node->getEndTokenPos(); ++$i) {
        $token = $tokens[$i];

        if (in_array($token->id, [ord('('), ord('['), T_ATTRIBUTE], true)) {
            ++$depth;
        } elseif (in_array($token->id, [ord(')'), ord(']')], true)) {
            --$depth;
        } elseif ($depth === 0 && in_array($token->id, [ord('{'), ord(';')], true)) {
            return substr($source, $node->getStartFilePos(), $token->pos - $node->getStartFilePos() + 1);
        }
    }

    return sourceOf($source, $node);
}

/** Compact declarations only; the selected source is never truncated. */
function outlineOf(array $nodes, string $source, array $tokens, ?string $owner = null): array
{
    $outline = [];

    foreach ($nodes as $node) {
        if ($node instanceof Stmt\Namespace_) {
            array_push($outline, ...outlineOf($node->stmts, $source, $tokens));

            continue;
        }
        $kind = match (true) {
            $node instanceof Stmt\Class_ => 'class',
            $node instanceof Stmt\Interface_ => 'interface',
            $node instanceof Stmt\Trait_ => 'trait',
            $node instanceof Stmt\Enum_ => 'enum',
            $node instanceof Stmt\Function_ => 'function',
            $node instanceof Stmt\ClassMethod => 'method',
            default => null,
        };

        if ($kind === null || $node->name === null) {
            continue;
        }
        $name = (string) $node->name;
        $declaration = declarationOf($source, $node, $tokens);
        $entry = [
            'select' => $kind . ':' . ($owner === null ? '' : $owner . '::') . $name,
            'line' => $node->getStartLine(),
            'declaration' => mbSafePrefix($declaration, 300),
            'body_omitted' => true,
        ];

        if (strlen($declaration) > 300) {
            $entry['declaration_truncated'] = true;
        }
        $outline[] = $entry;

        if ($node instanceof Stmt\ClassLike) {
            array_push($outline, ...outlineOf($node->stmts, $source, $tokens, $name));
        }
    }

    return $outline;
}

function mbSafePrefix(string $text, int $bytes): string
{
    $prefix = substr($text, 0, $bytes);

    while ($prefix !== '' && preg_match('//u', $prefix) !== 1) {
        $prefix = substr($prefix, 0, -1);
    }

    return $prefix;
}

function sourceView(string $source, string $mode, ?string $select): array
{
    if ($mode === 'full' || $select === null) {
        return ['mode' => 'full', 'source' => $source];
    }
    $parser = (new ParserFactory())->createForNewestSupportedVersion();
    $roots = $parser->parse($source) ?? [];
    $tokens = $parser->getTokens();
    $locator = new NodeLocator();
    $selected = $locator->resolveSelect($roots, $select);
    $scope = $roots;
    $context = ['namespace' => null, 'imports' => [], 'class_declaration' => null];

    foreach ($locator->ancestry($roots, $selected->start()) as $location) {
        $node = $location->node;

        if ($node instanceof Stmt\Namespace_) {
            $scope = $node->stmts;
            $context['namespace'] = declarationOf($source, $node, $tokens);
        }

        if ($node instanceof Stmt\ClassLike && $node !== $selected->node) {
            $context['class_declaration'] = declarationOf($source, $node, $tokens);
        }
    }

    foreach ($scope as $node) {
        if ($node instanceof Stmt\Use_ || $node instanceof Stmt\GroupUse) {
            $context['imports'][] = sourceOf($source, $node);
        }
    }
    $outline = outlineOf($roots, $source, $tokens);

    return [
        'mode' => 'focused',
        'select' => $select,
        'context' => $context,
        'source' => sourceOf($source, $selected->node),
        'lines' => [
            min(
                [
                    $selected->node->getStartLine(),
                    ...array_map(
                        static fn ($comment): int => $comment->getStartLine(),
                        $selected->node->getComments(),
                    ),
                ],
            ),
            $selected->node->getEndLine(),
        ],
        'outline' => array_slice($outline, 0, 100),
        'outline_truncated' => count($outline) > 100,
    ];
}

try {
    $autoload = getenv('PHP_AST_AGENT_AUTOLOAD');

    if ($autoload === false || !is_file($autoload)) {
        throw new RuntimeException(
            'PHP_AST_EDIT_BIN must point to a source runtime with vendor/autoload.php',
        );
    }
    require $autoload;
    $request = json_decode(stream_get_contents(STDIN), true, 512, JSON_THROW_ON_ERROR);
    $views = [];

    foreach ($request['sources'] as $source) {
        $views[] = sourceView($source, $request['mode'], $request['select']);
    }
    echo json_encode($views, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
} catch (Throwable $failure) {
    fwrite(STDERR, $failure->getMessage() . "\n");
    exit(2);
}
