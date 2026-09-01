<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use PhpParser\Node;
use PhpParser\Node\Expr;
use PhpParser\PhpVersion;
use PhpParser\PrettyPrinter\Standard;

/**
 * The canonical printer: one output per AST, and one a human can read.
 *
 * nikic's Standard printer emits every comma-separated list on a single line, however long.
 * That is canonical but not readable — on a real TYPO3 extension it produced a 1745-character
 * line where the authors' longest was 294. And no PHP formatter fixes it afterwards: of
 * php-cs-fixer's 303 fixers not one has a concept of line width, and PHP_CodeSniffer's
 * LineLengthSniff only reports (it calls addError, never addFixableError). Line breaking is
 * therefore the printer's job or nobody's.
 *
 * Three hooks carry it: pMaybeMultiline covers call arguments and array items, pParams
 * covers parameter lists, and pAttribute routes attribute arguments through the first —
 * nikic prints those with pCommaSeparated, which has no width at all. With both at a budget of 80 the same extension
 * printed at max 318 characters against the authors' 294 — the remainder are string
 * concatenations, which no list hook can break and which the authors did not break either.
 */
final class CanonicalPrinter extends Standard
{
    public const DEFAULT_WIDTH = 80;

    private readonly int $width;

    /**
     * The list a re-print is breaking, or null outside one.
     *
     * Identity, not a flag: `pExpr_MethodCall()` renders its receiver before
     * its own argument list, so on `$q->a($x)->b($y)` a flag set for the outer
     * list is consumed by the inner one — the short list breaks and the long
     * line stays. See `widthAware()`.
     *
     * @var (Node|null)[]|null
     */
    private ?array $breakTarget = null;

    public function __construct(?PhpVersion $phpVersion = null, int $width = self::DEFAULT_WIDTH)
    {
        parent::__construct($phpVersion === null ? [] : ['phpVersion' => $phpVersion]);
        $this->width = max(RepositoryConfig::MIN_WIDTH, $width);
    }

    public function width(): int
    {
        return $this->width;
    }

    /**
     * Attribute arguments, which nikic prints with `pCommaSeparated()` — no width
     * involved, so `#[AsCommand(name: …, description: …)]` came out on one line
     * whatever its length. Routed through the same hook as a call's arguments.
     */
    protected function pAttribute(Node\Attribute $node): string
    {
        if ($node->args === []) {
            return $this->p($node->name);
        }

        return $this->widthAware(
            fn (): string => $this->p($node->name) . '(' . $this->pMaybeMultiline($node->args) . ')',
            $node->args,
        );
    }

    protected function pExpr_FuncCall(Expr\FuncCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_FuncCall($node), $node->args);
    }

    protected function pExpr_MethodCall(Expr\MethodCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_MethodCall($node), $node->args);
    }

    protected function pExpr_NullsafeMethodCall(Expr\NullsafeMethodCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_NullsafeMethodCall($node), $node->args);
    }

    protected function pExpr_StaticCall(Expr\StaticCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_StaticCall($node), $node->args);
    }

    protected function pExpr_New(Expr\New_ $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_New($node), $node->args);
    }

    protected function pExpr_Array(Expr\Array_ $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_Array($node), $node->items);
    }

    protected function pExpr_List(Expr\List_ $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_List($node), $node->items);
    }

    /**
     * Prints the node, and prints it again with its list broken when the result
     * does not fit.
     *
     * `fitsOnOneLine()` measures the list alone, because that is all it is given.
     * What stands in front of it on the line — `$this->logger->warning(`,
     * `new JsonResponse(` — is known here, one level up, where the whole
     * expression has been rendered. Measuring it turns the largest class of
     * over-long output into broken lists: on a 119-file corpus, 203 of the 477
     * lines over 120 columns were calls whose argument list fit the budget
     * while the call did not.
     *
     * Still an approximation: what stands before the *expression* — `return `,
     * `$x = ` — is a level further up again, and reaching it needs the document
     * IR this printer deliberately does not build.
     *
     * @param callable(): string $print
     * @param (Node|null)[]|null  $list  the node's own list — the one to break
     */
    private function widthAware(callable $print, ?array $list): string
    {
        $result = $print();

        // Already broken, or short enough. A re-print in progress is left to
        // finish: the target it set belongs to the list it is breaking.
        if ($list === null || $this->breakTarget !== null || str_contains($result, "\n")) {
            return $result;
        }

        if ($this->indentLevel + strlen($result) <= $this->width) {
            return $result;
        }
        $this->breakTarget = $list;

        try {
            return $print();
        } finally {
            $this->breakTarget = null;
        }
    }

    /** @param (Node|null)[] $nodes */
    protected function pMaybeMultiline(array $nodes, bool $trailingComma = false): string
    {
        $single = $this->fitsOnOneLine($nodes);

        if ($single !== null) {
            return $single;
        }

        return $this->pCommaSeparatedMultiline($nodes, $trailingComma) . $this->nl;
    }

    /** @param Node\Param[] $params */
    protected function pParams(array $params): string
    {
        // A parameter carrying an attribute is only expressible inline from PHP 8.0 on; the
        // parent class breaks in that case regardless of width, and so must this one.
        if (!$this->phpVersion->supportsAttributes() && $this->anyParamHasAttributes($params)) {
            return $this->pCommaSeparatedMultiline(
                $params,
                $this->phpVersion->supportsTrailingCommaInParamList(),
            ) . $this->nl;
        }
        $single = $this->fitsOnOneLine($params);

        if ($single !== null) {
            return $single;
        }

        return $this->pCommaSeparatedMultiline(
            $params,
            $this->phpVersion->supportsTrailingCommaInParamList(),
        ) . $this->nl;
    }

    /**
     * Standard keeps its own copy of this private, so the subclass carries one.
     *
     * @param Node\Param[] $params
     */
    private function anyParamHasAttributes(array $params): bool
    {
        foreach ($params as $param) {
            if ($param->attrGroups !== []) {
                return true;
            }
        }

        return false;
    }

    /**
     * The single-line rendering, or null when the list has to be broken.
     *
     * The budget is compared against the indentation plus the list itself, because the list
     * is all this method is given. What precedes it on the line is measured one level up, in
     * `widthAware()`, which re-prints the node with its list broken when the whole expression
     * does not fit.
     *
     * @param (Node|null)[] $nodes
     */
    private function fitsOnOneLine(array $nodes): ?string
    {
        if ($this->breakTarget !== null && $nodes === $this->breakTarget) {
            // This is the list the re-print is for. Cleared straight away, so
            // the lists nested inside it are judged on their own merits.
            $this->breakTarget = null;

            return null;
        }

        if ($this->hasNodeWithComments($nodes)) {
            return null;
        }
        $single = $this->pCommaSeparated($nodes);

        if (str_contains($single, "\n")) {
            return null;
        }

        return $this->indentLevel + strlen($single) <= $this->width ? $single : null;
    }
}
