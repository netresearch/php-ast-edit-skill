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
    ) {
    }

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

    public function remove(array &$roots): void
    {
        if ($this->rootIndex !== null) {
            array_splice($roots, $this->findIdentityIndex($roots), 1);
            return;
        }

        if ($this->parent === null || $this->property === null || $this->index === null) {
            throw new EditException('delete is only allowed for nodes stored in statement/item lists.');
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

    /** @param list<Node> $nodes */
    private function insert(array $nodes, array &$roots, int $delta): void
    {
        if ($this->rootIndex !== null) {
            $index = $this->findIdentityIndex($roots);
            array_splice($roots, $index + $delta, 0, $nodes);
            return;
        }

        if ($this->parent === null || $this->property === null || $this->index === null) {
            throw new EditException('insert_before/insert_after require a node stored in a list.');
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
