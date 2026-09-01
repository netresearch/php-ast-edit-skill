<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;

final class NodeLocation
{
    public function __construct(
        public readonly Node $node,
        public readonly ?Node $parent,
        public readonly ?string $property,
        public readonly ?int $index,
        public readonly ?int $rootIndex,
        public readonly int $depth,
        public readonly string $path = '',
    ) {}

    public function start(): int
    {
        return $this->node->getStartFilePos();
    }

    public function end(): int
    {
        return $this->node->getEndFilePos();
    }

    public function replace(Node $replacement, array &$roots): void
    {
        if ($this->rootIndex !== null) {
            $index = $this->findIdentityIndex($roots);
            $roots[$index] = $replacement;

            return;
        }

        if ($this->parent === null || $this->property === null) {
            throw new EditException('Cannot replace detached AST node.');
        }

        if ($this->index === null) {
            if ($this->parent->{$this->property} !== $this->node) {
                throw new EditException('AST target is no longer attached at its original property.');
            }
            $this->parent->{$this->property} = $replacement;

            return;
        }
        $items = $this->parent->{$this->property};
        $index = $this->findIdentityIndex($items);
        $items[$index] = $replacement;
        $this->parent->{$this->property} = $items;
    }

    /**
     * Remove the node from its container. List members are spliced out; a node stored in a
     * single slot is nulled. The transaction's reparse gate rejects a slot that must not be
     * empty, so nullability is not modelled per property here.
     */
    public function remove(array &$roots): void
    {
        if ($this->rootIndex !== null) {
            array_splice($roots, $this->findIdentityIndex($roots), 1);

            return;
        }

        if ($this->parent === null || $this->property === null) {
            throw new EditException('Cannot delete a detached AST node.');
        }

        if ($this->index === null) {
            if ($this->parent->{$this->property} !== $this->node) {
                throw new EditException('AST target is no longer attached at its original property.');
            }
            $type = (new \ReflectionProperty($this->parent, $this->property))->getType();

            if ($type !== null && !$type->allowsNull()) {
                throw new EditException(
                    sprintf(
                        'Property "%s" of %s cannot be empty. Use replace_node to put something else there.',
                        $this->property,
                        $this->parent->getType(),
                    ),
                );
            }
            $this->parent->{$this->property} = null;

            return;
        }
        $items = $this->parent->{$this->property};
        array_splice($items, $this->findIdentityIndex($items), 1);
        $this->parent->{$this->property} = $items;
    }

    /** @param list<Node> $nodes */
    public function insertBefore(array $nodes, array &$roots): void
    {
        $this->insert($nodes, $roots, 0);
    }

    /** @param list<Node> $nodes */
    public function insertAfter(array $nodes, array &$roots): void
    {
        $this->insert($nodes, $roots, 1);
    }

    /**
     * Insert nodes into a child list of THIS node, without requiring an existing sibling anchor.
     *
     * @param list<Node> $nodes
     * @param int|'start'|'end' $position
     */
    public function insertInto(string $property, array $nodes, int|string $position): void
    {
        $items = $this->childList($property);
        $index = $this->resolvePosition($position, count($items), $property, true);
        array_splice($items, $index, 0, $nodes);
        $this->node->{$property} = $items;
    }

    /**
     * Replace a child slot of THIS node: the whole slot when `$index` is null, otherwise one
     * list element.
     */
    public function replaceChild(string $property, ?int $index, Node $replacement): void
    {
        $this->assertProperty($property);

        if ($index === null) {
            if ($this->isList($property)) {
                throw new EditException(
                    sprintf(
                        'Property "%s" holds a list; replace_child requires an index.',
                        $property,
                    ),
                );
            }
            $this->node->{$property} = $replacement;

            return;
        }
        $items = $this->childList($property);

        if (!array_key_exists($index, $items)) {
            throw new EditException(sprintf('Index %d is out of range for "%s".', $index, $property));
        }
        $items[$index] = $replacement;
        $this->node->{$property} = $items;
    }

    /** Remove one child of THIS node, addressed by property and optional index. */
    public function removeChild(string $property, ?int $index): void
    {
        $this->assertProperty($property);

        if ($index === null) {
            if ($this->isList($property)) {
                throw new EditException(
                    sprintf(
                        'Property "%s" holds a list; deleting from it requires an index.',
                        $property,
                    ),
                );
            }
            $this->assertNullable($property);
            $this->node->{$property} = null;

            return;
        }
        $items = $this->childList($property);

        if (!array_key_exists($index, $items)) {
            throw new EditException(sprintf('Index %d is out of range for "%s".', $index, $property));
        }
        array_splice($items, $index, 1);
        $this->node->{$property} = $items;
    }

    /** @return list<mixed> */
    public function childList(string $property): array
    {
        $this->assertList($property);
        $items = $this->node->{$property};

        return is_array($items) ? array_values($items) : [];
    }

    /**
     * A nullable single slot and an empty list both read as "nothing there", so the current
     * value cannot tell them apart. php-parser declares its sub nodes as typed properties,
     * so ask the declaration instead of guessing — otherwise assigning a list into a slot
     * raises a TypeError from deep inside the printer rather than a usable message here.
     */
    private function assertList(string $property): void
    {
        if ($this->isList($property)) {
            return;
        }

        throw new EditException(
            sprintf(
                'Property "%s" of %s holds a single node, not a list. Use replace_child or delete_child.',
                $property,
                $this->node->getType(),
            ),
        );
    }

    /** @param int|'start'|'end' $position */
    private function resolvePosition(
        int|string $position,
        int $count,
        string $property,
        bool $allowEnd,
    ): int {
        if ($position === 'start') {
            return 0;
        }

        if ($position === 'end') {
            return $count;
        }

        if (!is_int($position)) {
            throw new EditException('position must be an integer, "start" or "end".');
        }
        $max = $allowEnd ? $count : max(0, $count - 1);

        if ($position < 0 || $position > $max) {
            throw new EditException(
                sprintf(
                    'position %d is out of range for "%s" (%d entries).',
                    $position,
                    $property,
                    $count,
                ),
            );
        }

        return $position;
    }

    /**
     * A slot that is not declared nullable cannot be emptied — `Param::$var` must always
     * hold an expression. Assigning null anyway raises a TypeError at the assignment, which
     * tells the caller nothing about which edit was wrong.
     */
    private function assertNullable(string $property): void
    {
        $type = (new \ReflectionProperty($this->node, $property))->getType();

        if ($type !== null && !$type->allowsNull()) {
            throw new EditException(
                sprintf(
                    'Property "%s" of %s cannot be empty. Use replace_child to put something else there.',
                    $property,
                    $this->node->getType(),
                ),
            );
        }
    }

    public function isList(string $property): bool
    {
        $this->assertProperty($property);

        if (is_array($this->node->{$property})) {
            return true;
        }
        $type = (new \ReflectionProperty($this->node, $property))->getType();

        return $type instanceof \ReflectionNamedType && $type->getName() === 'array';
    }

    private function assertProperty(string $property): void
    {
        if (!in_array($property, $this->node->getSubNodeNames(), true)) {
            throw new EditException(
                sprintf(
                    '%s has no sub node "%s". Available: %s.',
                    $this->node->getType(),
                    $property,
                    implode(', ', $this->node->getSubNodeNames()),
                ),
            );
        }
    }

    /** @param list<Node> $nodes */
    private function insert(array $nodes, array &$roots, int $delta): void
    {
        if ($this->rootIndex !== null) {
            $index = $this->findIdentityIndex($roots);
            array_splice($roots, $index + $delta, 0, $nodes);

            return;
        }

        if ($this->parent === null || $this->property === null || $this->index === null) {
            throw new EditException(
                'insert_before/insert_after require a node stored in a list. Use insert_into for empty or slot-based containers.',
            );
        }
        $items = $this->parent->{$this->property};
        $index = $this->findIdentityIndex($items);
        array_splice($items, $index + $delta, 0, $nodes);
        $this->parent->{$this->property} = $items;
    }

    private function findIdentityIndex(array $items): int
    {
        foreach ($items as $index => $item) {
            if ($item === $this->node) {
                return $index;
            }
        }

        throw new EditException('AST target is no longer attached; an earlier edit invalidated it.');
    }
}
