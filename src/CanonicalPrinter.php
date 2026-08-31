<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use PhpParser\Node;
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

    public function __construct(?PhpVersion $phpVersion = null, int $width = self::DEFAULT_WIDTH)
    {
        parent::__construct($phpVersion === null ? [] : ['phpVersion' => $phpVersion]);
        $this->width = max(RepositoryConfig::MIN_WIDTH, $width);
    }

    public function width(): int
    {
        return $this->width;
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
     * The budget is compared against the indentation plus the list itself. It deliberately
     * ignores what precedes the list on the line — `$this->logger->warning(` and the like —
     * because the printer does not know it at this point. The approximation errs towards
     * breaking too little, which the measured result (318 against 294 characters) says is
     * close enough; a faithful answer needs a document IR of the kind Prettier builds, which
     * is a different project.
     *
     * @param (Node|null)[] $nodes
     */
    private function fitsOnOneLine(array $nodes): ?string
    {
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
