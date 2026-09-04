<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;
use PhpParser\Node\Stmt;

final class NodeLocator
{
    /** @param list<Node\Stmt> $roots */
    public function locate(array $roots, int $offset, ?string $kind = null): NodeLocation
    {
        $matches = $this->ancestry($roots, $offset);

        if ($kind !== null) {
            $matches = array_values(
                array_filter(
                    $matches,
                    static fn (
                        NodeLocation $location,
                    ): bool => $location->node->getType() === $kind || $location->node::class === $kind,
                ),
            );
        }

        if ($matches === []) {
            throw new EditException(
                sprintf(
                    'No%s AST node covers byte offset %d.',
                    $kind === null ? '' : ' ' . $kind,
                    $offset,
                ),
            );
        }

        return $matches[0];
    }

    /** @param list<Node\Stmt> $roots @return list<NodeLocation> */
    public function ancestry(array $roots, int $offset): array
    {
        $matches = [];

        foreach ($roots as $index => $node) {
            $this->walk(
                $node,
                null,
                null,
                null,
                $index,
                0,
                'stmts[' . $index . ']',
                $offset,
                $matches,
            );
        }
        usort(
            $matches,
            static function (NodeLocation $a, NodeLocation $b): int {
                $aSize = $a->end() - $a->start();
                $bSize = $b->end() - $b->start();

                return $aSize <=> $bSize ?: $b->depth <=> $a->depth;
            },
        );

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
        $pattern = '/^([A-Za-z_]\w*)(?:\[(\d+)\])?$/';

        if (!preg_match($pattern, $segments[0], $first) || $first[1] !== 'stmts' || !isset($first[2])) {
            throw new EditException('target.ref must start with stmts[<index>], got: ' . $segments[0]);
        }
        $rootIndex = (int) $first[2];

        if (!array_key_exists($rootIndex, $roots)) {
            throw new EditException(sprintf('target.ref root index %d does not exist.', $rootIndex));
        }
        $location = new NodeLocation(
            $roots[$rootIndex],
            null,
            null,
            null,
            $rootIndex,
            0,
            'stmts[' . $rootIndex . ']',
        );
        $path = $location->path;

        foreach (array_slice($segments, 1) as $depth => $segment) {
            if (!preg_match($pattern, $segment, $parts)) {
                throw new EditException('Malformed target.ref segment: ' . $segment);
            }
            $property = $parts[1];
            $node = $location->node;

            if (!in_array($property, $node->getSubNodeNames(), true)) {
                throw new EditException(
                    sprintf(
                        'target.ref "%s": %s has no sub node "%s".',
                        $ref,
                        $node->getType(),
                        $property,
                    ),
                );
            }
            $value = $node->{$property};
            $path .= '.' . $segment;

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
                $this->walk(
                    $value,
                    $node,
                    $subNodeName,
                    null,
                    null,
                    $depth + 1,
                    $path . '.' . $subNodeName,
                    $offset,
                    $matches,
                );

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
                        $path . '.' . $subNodeName . '[' . $childIndex . ']',
                        $offset,
                        $matches,
                    );
                }
            }
        }
    }

    /** The kinds a selector can name. */
    public const SELECTABLE = ['class', 'interface', 'trait', 'enum', 'function', 'method', 'property', 'const'];

    /**
     * Resolve a target named by what it is, rather than by where it sits.
     *
     * A `ref` is exact and survives nothing: it has to be read out of an `inspect` first, and
     * finding the coordinate to inspect at costs its own round trips — in a measured
     * comparison, locating a method by line and column took two to four calls before any edit
     * was written. A name is what the caller already knows.
     *
     * `class:Foo`, `interface:Foo`, `trait:Foo`, `enum:Foo`, `function:foo`,
     * `method:Foo::bar`, `property:Foo::$bar`, `const:Foo::BAR`. The class part of a member
     * selector may be left out where the file holds one class. An ambiguous selector is
     * refused with the paths it matched, never resolved to the first hit.
     *
     * @param list<Node\Stmt> $roots
     */
    public function resolveSelect(array $roots, string $select): NodeLocation
    {
        $select = trim($select);

        if (!str_contains($select, ':')) {
            throw new EditException(
                'target.select must read <kind>:<name>, for example method:Foo::bar. Got: ' . $select,
            );
        }
        [$kind, $name] = explode(':', $select, 2);
        $kind = strtolower(trim($kind));
        $name = trim($name);

        if (!in_array($kind, self::SELECTABLE, true)) {
            throw new EditException(
                sprintf(
                    'target.select kind "%s" is unknown. Known kinds: %s.',
                    $kind,
                    implode(', ', self::SELECTABLE),
                ),
            );
        }
        $owner = null;

        if (str_contains($name, '::')) {
            [$owner, $name] = explode('::', $name, 2);
        }
        $matches = [];

        foreach ($roots as $rootIndex => $root) {
            $this->collect(
                $root,
                null,
                null,
                null,
                $rootIndex,
                0,
                'stmts[' . $rootIndex . ']',
                $kind,
                $name,
                $owner,
                null,
                $matches,
            );
        }

        if ($matches === []) {
            throw new EditException(sprintf('target.select "%s" matched nothing in this file.', $select));
        }

        if (count($matches) > 1) {
            throw new EditException(
                sprintf(
                    'target.select "%s" matched %d nodes: %s. Name the owner, or address it by ref.',
                    $select,
                    count($matches),
                    implode(
                        ', ',
                        array_map(static fn (NodeLocation $m): string => $m->path, $matches),
                    ),
                ),
            );
        }

        return $matches[0];
    }

    /**
     * Walk the tree gathering the nodes a selector names.
     *
     * `$owner` is the class, interface, trait or enum a member selector asked for, and
     * `$inside` the name of the one currently being walked; a member matches when the caller
     * named no owner or the two agree.
     *
     * @param list<NodeLocation> $matches
     */
    private function collect(
        Node $node,
        ?Node $parent,
        ?string $property,
        ?int $index,
        ?int $rootIndex,
        int $depth,
        string $path,
        string $kind,
        string $name,
        ?string $owner,
        ?string $inside,
        array &$matches,
    ): void {
        if ($this->selectorMatches($node, $kind, $name, $owner, $inside)) {
            $matches[] = new NodeLocation($node, $parent, $property, $index, $rootIndex, $depth, $path);
        }

        if ($node instanceof Stmt\ClassLike && $node->name !== null) {
            $inside = $node->name->toString();
        }

        foreach ($node->getSubNodeNames() as $subNodeName) {
            $value = $node->{$subNodeName};

            if ($value instanceof Node) {
                $this->collect(
                    $value,
                    $node,
                    $subNodeName,
                    null,
                    null,
                    $depth + 1,
                    $path . '.' . $subNodeName,
                    $kind,
                    $name,
                    $owner,
                    $inside,
                    $matches,
                );

                continue;
            }

            if (!is_array($value)) {
                continue;
            }

            foreach ($value as $childIndex => $child) {
                if ($child instanceof Node) {
                    $this->collect(
                        $child,
                        $node,
                        $subNodeName,
                        $childIndex,
                        null,
                        $depth + 1,
                        $path . '.' . $subNodeName . '[' . $childIndex . ']',
                        $kind,
                        $name,
                        $owner,
                        $inside,
                        $matches,
                    );
                }
            }
        }
    }

    /**
     * Whether one node is what a selector asked for.
     *
     * A property selector names the declaration that holds the variable, not the variable
     * itself, because that is the node an edit works on.
     */
    private function selectorMatches(
        Node $node,
        string $kind,
        string $name,
        ?string $owner,
        ?string $inside,
    ): bool {
        $named = static fn (?Node $identifier): ?string => $identifier === null ? null : (string) $identifier;
        $ownerAgrees = $owner === null || $owner === $inside;

        return match ($kind) {
            'class' => $node instanceof Stmt\Class_ && $named($node->name) === $name,
            'interface' => $node instanceof Stmt\Interface_ && $named($node->name) === $name,
            'trait' => $node instanceof Stmt\Trait_ && $named($node->name) === $name,
            'enum' => $node instanceof Stmt\Enum_ && $named($node->name) === $name,
            'function' => $node instanceof Stmt\Function_ && $named($node->name) === $name,
            'method' => $node instanceof Stmt\ClassMethod && $named($node->name) === $name && $ownerAgrees,
            'property' => $node instanceof Stmt\Property && $ownerAgrees && $this->declaresName($node->props, ltrim($name, '$')),
            'const' => $node instanceof Stmt\ClassConst && $ownerAgrees && $this->declaresName($node->consts, $name),
            default => false,
        };
    }

    /**
     * Whether one of these declarations carries `$name`.
     *
     * A single `private int $a = 1, $b = 2;` is one node holding two names, so the selector
     * has to look inside rather than at the statement.
     *
     * @param array<Node\PropertyItem|Node\Const_> $declarations
     */
    private function declaresName(array $declarations, string $name): bool
    {
        foreach ($declarations as $declaration) {
            if ((string) $declaration->name === $name) {
                return true;
            }
        }

        return false;
    }
}
