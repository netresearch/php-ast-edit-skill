<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use PhpParser\Node\Expr;
use PhpParser\Node\Stmt;
use PhpParser\Parser;

/**
 * Backwards-compatible facade over {@see ContextParser}.
 *
 * @deprecated Use ContextParser, which parses every PHP construct through a synthetic host
 *             context instead of only expressions and statements.
 */
final class SnippetParser
{
    private readonly ContextParser $contexts;

    public function __construct(Parser $parser)
    {
        $this->contexts = new ContextParser($parser);
    }

    public function expression(string $code): Expr
    {
        /** @var Expr */
        return $this->contexts->parseOne('expr', $code);
    }

    /** @return list<Stmt> */
    public function statements(string $code): array
    {
        /** @var list<Stmt> */
        return $this->contexts->parse('stmt', $code);
    }

    public function statement(string $code): Stmt
    {
        /** @var Stmt */
        return $this->contexts->parseOne('stmt', $code);
    }
}
