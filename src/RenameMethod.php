<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;
use PhpParser\Node\Expr;
use PhpParser\Node\Stmt;
use PhpParser\NodeFinder;

/** Bounded lexical method rename; inheritance and receiver type inference are not modeled. */
final class RenameMethod
{
    /** @param list<Node\Stmt> $roots
     * @return array{renamed: int, otherReceivers: int}
     */
    public function rename(NodeLocation $location, string $to, array $roots): array
    {
        $method = $location->node;

        if (!$method instanceof Stmt\ClassMethod) {
            throw new EditException('rename_method targets a method declaration.');
        }

        if (!preg_match('/^[A-Za-z_\x80-\xff][A-Za-z0-9_\x80-\xff]*$/', $to)) {
            throw new EditException('rename_method: "' . $to . '" is not a method name.');
        }
        $from = $method->name->toString();
        $owner = $location->parent;

        if (!$owner instanceof Stmt\Class_ || $owner->extends !== null || $owner->implements !== []) {
            throw new EditException(
                'rename_method requires a concrete class without inheritance, interfaces or trait composition; resolve those contracts explicitly.',
            );
        }

        if ($method->isAbstract() || !$method->isPrivate() && !$owner->isFinal()) {
            throw new EditException(
                'rename_method requires a private method or a final class; inherited overrides cannot be resolved within this edit.',
            );
        }

        if (str_starts_with(strtolower($from), '__') || str_starts_with(strtolower($to), '__')) {
            throw new EditException('rename_method cannot rename to or from a magic-method name.');
        }

        foreach ($owner->stmts as $member) {
            if ($member instanceof Stmt\TraitUse) {
                throw new EditException('rename_method cannot resolve trait composition or aliases.');
            }

            if ($member instanceof Stmt\ClassMethod && $member !== $method && strcasecmp($member->name->toString(), $to) === 0) {
                throw new EditException(
                    'rename_method: destination method ' . $to . ' already exists in this class.',
                );
            }
        }
        $calls = [];

        foreach ($owner->stmts as $member) {
            // Methods and property hooks share the declaring class receiver.
            // The walk stops at nested named functions and classes.
            $this->collect($member, $from, $owner->isFinal(), $calls);
        }
        // No mutation happens until every declaration and dispatch check has passed.
        $method->name = new Node\Identifier($to, $method->name->getAttributes());

        foreach ($calls as $call) {
            $call->name = new Node\Identifier($to, $call->name->getAttributes());
        }
        $others = 0;

        foreach ((new NodeFinder())->find($roots, static fn (Node $node): bool => self::names($node, $from)) as $node) {
            if (!isset($calls[spl_object_id($node)])) {
                ++$others;
            }
        }

        return ['renamed' => 1 + count($calls), 'otherReceivers' => $others];
    }

    /** @param array<int, Expr\MethodCall|Expr\NullsafeMethodCall|Expr\StaticCall> $calls */
    private function collect(Node $node, string $name, bool $finalClass, array &$calls): void
    {
        foreach ($node->getSubNodeNames() as $property) {
            $value = $node->{$property};

            foreach ($value instanceof Node ? [$value] : (is_array($value) ? $value : []) as $child) {
                if (!$child instanceof Node || $child instanceof Stmt\ClassLike || $child instanceof Stmt\Function_ || $child instanceof Stmt\ClassMethod) {
                    continue;
                }

                if (self::names($child, $name)) {
                    if ($child instanceof Expr\StaticCall && $child->class instanceof Node\Name) {
                        $receiver = $child->class->toLowerString();

                        if ($receiver === 'static' && !$finalClass) {
                            throw new EditException(
                                'rename_method cannot resolve late static dispatch in a non-final class.',
                            );
                        }

                        if ($receiver === 'self' || $receiver === 'static' && $finalClass) {
                            $calls[spl_object_id($child)] = $child;
                        }
                    } elseif (($child instanceof Expr\MethodCall || $child instanceof Expr\NullsafeMethodCall) && $child->var instanceof Expr\Variable && $child->var->name === 'this') {
                        $calls[spl_object_id($child)] = $child;
                    }
                }
                // For an anonymous class, its arguments remain in the outer scope. The class node itself is skipped above.
                $this->collect($child, $name, $finalClass, $calls);
            }
        }
    }

    private static function names(Node $node, string $name): bool
    {
        return ($node instanceof Expr\MethodCall || $node instanceof Expr\NullsafeMethodCall || $node instanceof Expr\StaticCall) && $node->name instanceof Node\Identifier && strcasecmp($node->name->toString(), $name) === 0;
    }
}
