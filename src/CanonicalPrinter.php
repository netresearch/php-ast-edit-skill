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
 * Two hooks carry it: pMaybeMultiline covers call arguments, array items and attribute
 * arguments; pParams covers parameter lists. With both at a budget of 80 the same extension
 * printed at max 318 characters against the authors' 294 — the remainder are string
 * concatenations, which no list hook can break and which the authors did not break either.
 */
final class CanonicalPrinter extends Standard
{
    public const DEFAULT_WIDTH = 80;

    private readonly int $width;

    /**
     * Set for the length of one re-print, and consumed by the first list that
     * asks whether it fits. See `widthAware()`.
     */
    private bool $forceNextBreak = false;

    public function __construct(?PhpVersion $phpVersion = null, int $width = self::DEFAULT_WIDTH)
    {
        parent::__construct($phpVersion === null ? [] : ['phpVersion' => $phpVersion]);
        $this->width = max(RepositoryConfig::MIN_WIDTH, $width);
    }

    public function width(): int
    {
        return $this->width;
    }

    protected function pExpr_FuncCall(Expr\FuncCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_FuncCall($node));
    }

    protected function pExpr_MethodCall(Expr\MethodCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_MethodCall($node));
    }

    protected function pExpr_NullsafeMethodCall(Expr\NullsafeMethodCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_NullsafeMethodCall($node));
    }

    protected function pExpr_StaticCall(Expr\StaticCall $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_StaticCall($node));
    }

    protected function pExpr_New(Expr\New_ $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_New($node));
    }

    protected function pExpr_Array(Expr\Array_ $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_Array($node));
    }

    protected function pExpr_List(Expr\List_ $node): string
    {
        return $this->widthAware(fn (): string => parent::pExpr_List($node));
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
     */
    private function widthAware(callable $print): string
    {
        $result = $print();

        // Already broken, or short enough. A re-print in progress is left to
        // finish: the flag it set belongs to the list it is breaking.
        if ($this->forceNextBreak || str_contains($result, "\n")) {
            return $result;
        }

        if ($this->indentLevel + strlen($result) <= $this->width) {
            return $result;
        }

        $this->forceNextBreak = true;

        try {
            return $print();
        } finally {
            $this->forceNextBreak = false;
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
            return $this->pCommaSeparatedMultiline($params, $this->phpVersion->supportsTrailingCommaInParamList()) . $this->nl;
        }
        $single = $this->fitsOnOneLine($params);

        if ($single !== null) {
            return $single;
        }

        return $this->pCommaSeparatedMultiline($params, $this->phpVersion->supportsTrailingCommaInParamList()) . $this->nl;
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
        if ($this->forceNextBreak) {
            // Consumed by the outermost list of the re-print, so that the lists
            // nested inside it are judged on their own merits again.
            $this->forceNextBreak = false;

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
