<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;
use PhpParser\Node\Expr;
use PhpParser\Node\Param;
use PhpParser\Node\Stmt;

/** Local lexical bindings only; preflight the complete plan before changing any name. */
final class RenameVariable
{
    private const SPECIAL_VARIABLES = ['GLOBALS', '_SERVER', '_GET', '_POST', '_FILES', '_COOKIE', '_SESSION', '_REQUEST', '_ENV'];

    /** @param array<int, string> $functionNames Resolved names keyed by original call identity. */
    public function __construct(private readonly array $functionNames = []) {}

    public function rename(Node $scope, string $from, string $to): int
    {
        $from = ltrim($from, '$');
        $to = ltrim($to, '$');

        foreach ([$from, $to] as $name) {
            if (!preg_match('/^[A-Za-z_\x80-\xff][A-Za-z0-9_\x80-\xff]*$/', $name)) {
                throw new EditException('rename_variable: "' . $name . '" is not a variable name.');
            }

            if ($name === 'this') {
                throw new EditException('rename_variable will not rename $this.');
            }

            if (in_array($name, self::SPECIAL_VARIABLES, true)) {
                throw new EditException('rename_variable cannot rename superglobal bindings.');
            }
        }

        if ($this->captures($scope, $from)) {
            throw new EditException(
                'rename_variable: the selected function captures $' . $from . '; target its outer scope so the binding and its uses move together.',
            );
        }
        $variables = [];
        $this->plan($scope, $from, $to, $variables);

        if ($variables === []) {
            throw new EditException(
                sprintf('rename_variable: $%s does not occur in %s.', $from, $scope->getType()),
            );
        }

        foreach ($variables as $variable) {
            $variable->name = $to;
        }

        return count($variables);
    }

    /** @param array<int, Expr\Variable> $variables */
    private function plan(Node $node, string $from, string $to, array &$variables): void
    {
        if ($node instanceof Expr\Variable) {
            if (!is_string($node->name) || $node->name === 'GLOBALS') {
                throw new EditException(
                    'rename_variable cannot resolve dynamic variables or $GLOBALS in an affected scope.',
                );
            }

            if ($from !== $to && $node->name === $to) {
                $this->collision($to);
            }

            if ($node->name === $from) {
                $variables[spl_object_id($node)] = $node;
            }
        }

        if ($node instanceof Param && $node->var instanceof Expr\Variable && $node->var->name === $from && $node->isPromoted()) {
            throw new EditException(
                'rename_variable cannot rename a promoted parameter without its property references.',
            );
        }

        if ($node instanceof Stmt\Global_) {
            foreach ($node->vars as $variable) {
                if ($variable instanceof Expr\Variable && in_array($variable->name, [$from, $to], true)) {
                    throw new EditException(
                        'rename_variable cannot rename a global binding as a local variable.',
                    );
                }
            }
        }

        if ($node instanceof Expr\Eval_ || $node instanceof Expr\Include_ || $this->usesSymbolTable($node)) {
            throw new EditException(
                'rename_variable cannot resolve symbol-table access, eval or include in an affected scope.',
            );
        }

        foreach ($this->children($node) as $child) {
            if ($child instanceof Stmt\Function_ || $child instanceof Stmt\ClassMethod || $child instanceof Stmt\ClassLike) {
                continue;
            }

            if ($child instanceof Expr\Closure || $child instanceof Expr\ArrowFunction) {
                if ($this->captures($child, $from)) {
                    $this->plan($child, $from, $to, $variables);
                } elseif ($from !== $to && $this->captures($child, $to)) {
                    // This is an outer destination use even when the closure never uses the source.
                    $this->collision($to);
                }

                continue;
            }
            $this->plan($child, $from, $to, $variables);
        }
    }

    /** Whether a nested function imports this literal variable name from its parent. */
    private function captures(Node $node, string $name): bool
    {
        if ($node instanceof Expr\Closure) {
            foreach ($node->uses as $use) {
                if ($use->var->name === $name) {
                    return true;
                }
            }

            return false;
        }

        if (!$node instanceof Expr\ArrowFunction) {
            return false;
        }

        foreach ($node->params as $parameter) {
            if ($parameter->var instanceof Expr\Variable && $parameter->var->name === $name) {
                return false;
            }
        }

        return $this->references($node->expr, $name);
    }

    private function references(Node $node, string $name): bool
    {
        if ($node instanceof Expr\Variable && $node->name === $name) {
            return true;
        }

        if ($node instanceof Expr\Closure || $node instanceof Expr\ArrowFunction) {
            return $this->captures($node, $name);
        }

        if ($node instanceof Stmt\Function_ || $node instanceof Stmt\ClassMethod || $node instanceof Stmt\ClassLike) {
            return false;
        }

        foreach ($this->children($node) as $child) {
            if ($this->references($child, $name)) {
                return true;
            }
        }

        return false;
    }

    private function usesSymbolTable(Node $node): bool
    {
        if (!$node instanceof Expr\FuncCall || !$node->name instanceof Node\Name) {
            return false;
        }

        // Callback forwarding may be compiled as a direct call into this local symbol table.
        // Do not infer callback targets from expressions or runtime values.
        return in_array(
            $this->functionNames[spl_object_id($node)] ?? strtolower($node->name->getLast()),
            [
                'compact',
                'extract',
                'get_defined_vars',
                'parse_str',
                'mb_parse_str',
                'import_request_variables',
                'call_user_func',
                'call_user_func_array',
            ],
            true,
        );
    }

    private function collision(string $name): never
    {
        throw new EditException(
            'rename_variable: destination $' . $name . ' is already used or bound in an affected scope; the rename would merge or capture variables.',
        );
    }

    /** @return iterable<Node> */
    private function children(Node $node): iterable
    {
        foreach ($node->getSubNodeNames() as $property) {
            $value = $node->{$property};

            foreach ($value instanceof Node ? [$value] : (is_array($value) ? $value : []) as $child) {
                if ($child instanceof Node) {
                    yield $child;
                }
            }
        }
    }
}
