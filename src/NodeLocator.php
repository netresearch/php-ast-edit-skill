<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;

final class NodeLocator
{
    /** @param list<Node\Stmt> $roots */
    public function locate(array $roots, int $offset, ?string $kind = null): NodeLocation
    {
        $matches = [];
        foreach ($roots as $index => $node) {
            $this->walk($node, null, null, null, $index, 0, $offset, $matches);
        }

        if ($kind !== null) {
            $matches = array_values(array_filter(
                $matches,
                static fn (NodeLocation $location): bool => $location->node->getType() === $kind
                    || $location->node::class === $kind,
            ));
        }

        if ($matches === []) {
            throw new EditException(sprintf(
                'No%s AST node covers byte offset %d.',
                $kind === null ? '' : ' '.$kind,
                $offset,
            ));
        }

        usort($matches, static function (NodeLocation $a, NodeLocation $b): int {
            $aSize = $a->end() - $a->start();
            $bSize = $b->end() - $b->start();
            return $aSize <=> $bSize ?: $b->depth <=> $a->depth;
        });

        return $matches[0];
    }

    /** @param list<Node\Stmt> $roots @return list<NodeLocation> */
    public function ancestry(array $roots, int $offset): array
    {
        $matches = [];
        foreach ($roots as $index => $node) {
            $this->walk($node, null, null, null, $index, 0, $offset, $matches);
        }

        usort($matches, static function (NodeLocation $a, NodeLocation $b): int {
            $aSize = $a->end() - $a->start();
            $bSize = $b->end() - $b->start();
            return $aSize <=> $bSize ?: $b->depth <=> $a->depth;
        });

        return $matches;
    }

    /** @param list<Node\Stmt> $roots */
    public function isAttached(array $roots, Node $needle): bool
    {
        foreach ($roots as $node) {
            if ($this->containsIdentity($node, $needle)) {
                return true;
            }
        }
        return false;
    }

    private function containsIdentity(Node $node, Node $needle): bool
    {
        if ($node === $needle) {
            return true;
        }
        foreach ($node->getSubNodeNames() as $subNodeName) {
            $value = $node->{$subNodeName};
            if ($value instanceof Node && $this->containsIdentity($value, $needle)) {
                return true;
            }
            if (is_array($value)) {
                foreach ($value as $child) {
                    if ($child instanceof Node && $this->containsIdentity($child, $needle)) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    /** @param list<NodeLocation> $matches */
    private function walk(
        Node $node,
        ?Node $parent,
        ?string $property,
        ?int $index,
        ?int $rootIndex,
        int $depth,
        int $offset,
        array &$matches,
    ): void {
        $start = $node->getStartFilePos();
        $end = $node->getEndFilePos();

        if ($start < 0 || $end < 0 || $offset < $start || $offset > $end) {
            return;
        }

        $matches[] = new NodeLocation($node, $parent, $property, $index, $rootIndex, $depth);

        foreach ($node->getSubNodeNames() as $subNodeName) {
            $value = $node->{$subNodeName};
            if ($value instanceof Node) {
                $this->walk($value, $node, $subNodeName, null, null, $depth + 1, $offset, $matches);
                continue;
            }
            if (!is_array($value)) {
                continue;
            }
            foreach ($value as $childIndex => $child) {
                if ($child instanceof Node) {
                    $this->walk($child, $node, $subNodeName, $childIndex, null, $depth + 1, $offset, $matches);
                }
            }
        }
    }
}
