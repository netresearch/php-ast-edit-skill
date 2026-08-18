<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node\Expr;
use PhpParser\Node\Stmt;
use PhpParser\Node\Stmt\Expression;
use PhpParser\Parser;

final class SnippetParser
{
    public function __construct(private readonly Parser $parser)
    {
    }

    public function expression(string $code): Expr
    {
        $code = trim($code);
        if (str_contains($code, '<?')) {
            throw new EditException('Expression snippets must not contain PHP open tags.');
        }
        $code = rtrim($code, "; \t\n\r\0\x0B");
        $stmts = $this->parser->parse('<?php '.$code.';');
        if ($stmts === null || count($stmts) !== 1 || !$stmts[0] instanceof Expression) {
            throw new EditException('Snippet must parse as exactly one PHP expression.');
        }
        return $stmts[0]->expr;
    }

    /** @return list<Stmt> */
    public function statements(string $code): array
    {
        $code = trim($code);
        if (str_contains($code, '<?')) {
            throw new EditException('Statement snippets must not contain PHP open tags.');
        }
        $stmts = $this->parser->parse('<?php '.$code);
        if ($stmts === null || $stmts === []) {
            throw new EditException('Snippet must contain at least one PHP statement.');
        }
        return $stmts;
    }

    public function statement(string $code): Stmt
    {
        $stmts = $this->statements($code);
        if (count($stmts) !== 1) {
            throw new EditException('Snippet must parse as exactly one PHP statement.');
        }
        return $stmts[0];
    }
}
