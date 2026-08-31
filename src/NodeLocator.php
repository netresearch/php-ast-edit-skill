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
        $matches = $this->ancestry($roots, $offset);

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

        return $matches[0];
    }

    /** @param list<Node\Stmt> $roots @return list<NodeLocation> */
    public function ancestry(array $roots, int $offset): array
    {
        $matches = [];
        foreach ($roots as $index => $node) {
            $this->walk($node, null, null, null, $index, 0, 'stmts['.$index.']', $offset, $matches);
        }

        usort($matches, static function (NodeLocation $a, NodeLocation $b): int {
            $aSize = $a->end() - $a->start();
            $bSize = $b->end() - $b->start();
            return $aSize <=> $bSize ?: $b->depth <=> $a->depth;
        });

        return $matches;
    }

    /**
     * Resolve a structural AST reference such as `stmts[1].stmts[3].params[0]` or
     * `stmts[0].returnType`. A reference is only valid together with the source snapshot it
     * was produced from.
     *
     * @param list<Node\Stmt> $roots
     */
    public function resolveRef(array $roots, string $ref): NodeLocation
    {
        $ref = trim($ref);
        if ($ref === '') {
            throw new EditException('target.ref must not be empty.');
        }

        $segments = explode('.', $ref);
        $pattern = '/^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$/';

        if (!preg_match($pattern, $segments[0], $first) || $first[1] !== 'stmts' || !isset($first[2])) {
            throw new EditException('target.ref must start with stmts[<index>], got: '.$segments[0]);
        }

        $rootIndex = (int) $first[2];
        if (!array_key_exists($rootIndex, $roots)) {
            throw new EditException(sprintf('target.ref root index %d does not exist.', $rootIndex));
        }

        $location = new NodeLocation($roots[$rootIndex], null, null, null, $rootIndex, 0, 'stmts['.$rootIndex.']');
        $path = $location->path;

        foreach (array_slice($segments, 1) as $depth => $segment) {
            if (!preg_match($pattern, $segment, $parts)) {
                throw new EditException('Malformed target.ref segment: '.$segment);
            }
            $property = $parts[1];
            $node = $location->node;
            if (!in_array($property, $node->getSubNodeNames(), true)) {
                throw new EditException(sprintf(
                    'target.ref "%s": %s has no sub node "%s".',
                    $ref,
                    $node->getType(),
                    $property,
                ));
            }
            $value = $node->{$property};
            $path .= '.'.$segment;

            if (isset($parts[2])) {
                $index = (int) $parts[2];
                if (!is_array($value) || !array_key_exists($index, $value) || !$value[$index] instanceof Node) {
                    throw new EditException(sprintf('target.ref "%s" does not resolve to a node.', $ref));
                }
                $location = new NodeLocation($value[$index], $node, $property, $index, null, $depth + 1, $path);
                continue;
            }

            if (!$value instanceof Node) {
                throw new EditException(sprintf('target.ref "%s" does not resolve to a node.', $ref));
            }
            $location = new NodeLocation($value, $node, $property, null, null, $depth + 1, $path);
        }

        return $location;
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

    /** Is $needle the same node as $haystack, or somewhere inside it? */
    public function contains(Node $haystack, Node $needle): bool
    {
        return $this->containsIdentity($haystack, $needle);
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
        string $path,
        int $offset,
        array &$matches,
    ): void {
        $start = $node->getStartFilePos();
        $end = $node->getEndFilePos();

        if ($start < 0 || $end < 0 || $offset < $start || $offset > $end) {
            return;
        }

        $matches[] = new NodeLocation($node, $parent, $property, $index, $rootIndex, $depth, $path);

        foreach ($node->getSubNodeNames() as $subNodeName) {
            $value = $node->{$subNodeName};
            if ($value instanceof Node) {
                $this->walk($value, $node, $subNodeName, null, null, $depth + 1, $path.'.'.$subNodeName, $offset, $matches);
                continue;
            }
            if (!is_array($value)) {
                continue;
            }
            foreach ($value as $childIndex => $child) {
                if ($child instanceof Node) {
                    $this->walk(
                        $child,
                        $node,
                        $subNodeName,
                        $childIndex,
                        null,
                        $depth + 1,
                        $path.'.'.$subNodeName.'['.$childIndex.']',
                        $offset,
                        $matches,
                    );
                }
            }
        }
    }
}
