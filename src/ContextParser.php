<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Error as ParserError;
use PhpParser\Node;
use PhpParser\Node\Stmt;
use PhpParser\NodeFinder;
use PhpParser\Parser;

/**
 * Parses compact PHP syntax into AST nodes by embedding the snippet into a synthetic
 * host construct and extracting the requested node from the resulting tree.
 *
 * The grammar therefore always comes from nikic/php-parser; no language construct is
 * modelled a second time inside this package.
 */
final class ContextParser
{
    /**
     * Synthetic hosts. `%s` receives the snippet; `extract` names the path that carries
     * the produced nodes inside the parsed host.
     *
     * @var array<string, array{template: string, extract: callable(array<Stmt>): list<Node>}>
     */
    private array $contexts;

    public function __construct(private readonly Parser $parser)
    {
        $this->contexts = [
            'expr' => [
                'template' => '<?php %s;',
                'extract' => static function (array $stmts): array {
                    if (count($stmts) !== 1 || !$stmts[0] instanceof Stmt\Expression) {
                        throw new EditException('Snippet must parse as exactly one PHP expression.');
                    }
                    return [$stmts[0]->expr];
                },
            ],
            'stmt' => [
                'template' => '<?php %s',
                'extract' => static fn (array $stmts): array => $stmts,
            ],
            'member' => [
                'template' => '<?php class __AstContext { %s }',
                'extract' => static fn (array $stmts): array => $stmts[0]->stmts,
            ],
            'enum_case' => [
                'template' => '<?php enum __AstContext { %s }',
                'extract' => static fn (array $stmts): array => $stmts[0]->stmts,
            ],
            'param' => [
                'template' => '<?php function __astContext(%s) {}',
                'extract' => static fn (array $stmts): array => $stmts[0]->params,
            ],
            'arg' => [
                'template' => '<?php __astContext(%s);',
                'extract' => static fn (array $stmts): array => $stmts[0]->expr->args,
            ],
            'type' => [
                'template' => '<?php function __astContext(): %s {}',
                'extract' => static function (array $stmts): array {
                    $type = $stmts[0]->returnType;
                    if ($type === null) {
                        throw new EditException('Snippet did not produce a type node.');
                    }
                    return [$type];
                },
            ],
            'array_item' => [
                'template' => '<?php [%s];',
                'extract' => static fn (array $stmts): array => array_values(array_filter(
                    $stmts[0]->expr->items,
                    static fn (mixed $item): bool => $item instanceof Node,
                )),
            ],
            'match_arm' => [
                'template' => '<?php match (__AST_CONTEXT) { %s };',
                'extract' => static fn (array $stmts): array => $stmts[0]->expr->arms,
            ],
            'attribute' => [
                'template' => '<?php %s class __AstContext {}',
                'extract' => static fn (array $stmts): array => $stmts[0]->attrGroups,
            ],
            'closure_use' => [
                'template' => '<?php function () use (%s) {};',
                'extract' => static fn (array $stmts): array => $stmts[0]->expr->uses,
            ],
            'catch' => [
                'template' => '<?php try {} %s',
                'extract' => static fn (array $stmts): array => $stmts[0]->catches,
            ],
            'const' => [
                'template' => '<?php const %s;',
                'extract' => static fn (array $stmts): array => $stmts[0]->consts,
            ],
            'use' => [
                'template' => '<?php use %s;',
                'extract' => static fn (array $stmts): array => $stmts[0]->uses,
            ],
            'property_item' => [
                'template' => '<?php class __AstContext { public $%s; }',
                'extract' => static fn (array $stmts): array => $stmts[0]->stmts[0]->props,
            ],
            'static_var' => [
                'template' => '<?php function __astContext() { static $%s; }',
                'extract' => static fn (array $stmts): array => $stmts[0]->stmts[0]->vars,
            ],
        ];
    }

    /** @return list<string> */
    public function contexts(): array
    {
        return array_keys($this->contexts);
    }

    public function supports(string $context): bool
    {
        return isset($this->contexts[$context]);
    }

    /**
     * Parse a snippet inside the named synthetic context.
     *
     * @return list<Node>
     */
    public function parse(string $context, string $code): array
    {
        if ($context === 'stmts') {
            $context = 'stmt';
        }
        if ($context === 'file') {
            return $this->file($code);
        }
        if (!isset($this->contexts[$context])) {
            throw new EditException(sprintf(
                'Unknown parseAs context "%s". Known contexts: %s.',
                $context,
                implode(', ', array_merge($this->contexts(), ['stmts', 'file'])),
            ));
        }

        $code = trim($code);
        if ($code === '') {
            throw new EditException('Snippet must not be empty.');
        }
        if ($context === 'expr') {
            $code = rtrim($code, "; \t\n\r\0\x0B");
        }

        $spec = $this->contexts[$context];
        $source = sprintf($spec['template'], $code);

        try {
            $stmts = $this->parser->parse($source);
        } catch (ParserError $error) {
            throw new EditException(sprintf(
                'Snippet is not valid in the "%s" context: %s',
                $context,
                $error->getRawMessage(),
            ));
        }

        if ($stmts === null || $stmts === []) {
            throw new EditException(sprintf('Snippet produced no AST nodes in the "%s" context.', $context));
        }

        // A snippet that closes the PHP context would smuggle literal output into the tree.
        // Checking for the resulting InlineHTML node rather than for an open-tag substring
        // keeps an open tag inside a string literal perfectly legal.
        if ((new NodeFinder())->findFirstInstanceOf($stmts, Stmt\InlineHTML::class) !== null) {
            throw new EditException('Snippet must not leave the PHP context.');
        }

        $nodes = ($spec['extract'])($stmts);
        $nodes = array_values(array_filter($nodes, static fn (mixed $node): bool => $node instanceof Node));
        if ($nodes === []) {
            throw new EditException(sprintf('Snippet produced no AST nodes in the "%s" context.', $context));
        }

        return $nodes;
    }

    /**
     * Parse a snippet in the first context that accepts it.
     *
     * @param non-empty-list<string> $contexts
     * @return list<Node>
     */
    public function parseFirst(array $contexts, string $code): array
    {
        $last = null;
        foreach ($contexts as $context) {
            try {
                return $this->parse($context, $code);
            } catch (EditException $exception) {
                $last ??= $exception;
            }
        }
        throw $last ?? new EditException('No parse context was offered.');
    }

    /**
     * Parse a snippet in the first context that accepts it, requiring exactly one node.
     *
     * @param non-empty-list<string> $contexts
     */
    public function parseFirstOne(array $contexts, string $code): Node
    {
        $nodes = $this->parseFirst($contexts, $code);
        if (count($nodes) !== 1) {
            throw new EditException(sprintf(
                'Snippet must produce exactly one node, got %d.',
                count($nodes),
            ));
        }
        return $nodes[0];
    }

    /** Parse a snippet that must produce exactly one node. */
    public function parseOne(string $context, string $code): Node
    {
        $nodes = $this->parse($context, $code);
        if (count($nodes) !== 1) {
            throw new EditException(sprintf(
                'Snippet must produce exactly one %s node, got %d.',
                $context,
                count($nodes),
            ));
        }
        return $nodes[0];
    }

    /**
     * Parse a complete PHP file, open tag included.
     *
     * @return list<Stmt>
     */
    public function file(string $code): array
    {
        $code = trim($code);
        if ($code === '') {
            throw new EditException('File source must not be empty.');
        }
        if (!str_starts_with($code, '<?php')) {
            $code = "<?php\n".$code;
        }

        try {
            $stmts = $this->parser->parse($code);
        } catch (ParserError $error) {
            throw new EditException('File source is not valid PHP: '.$error->getRawMessage());
        }
        if ($stmts === null) {
            throw new EditException('File source produced no AST.');
        }

        return $stmts;
    }
}
