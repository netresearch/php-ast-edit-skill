<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;
use PhpParser\Node\Expr;
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

    /** How many declared names a "matched nothing" message carries before it says how many more. */
    private const DECLARED_IN_MESSAGE = 8;

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
            // A selector that matched nothing is almost always a near miss — a method on the
            // wrong class, a name remembered from another file, a rename that already ran.
            // Naming what the file does declare of that kind answers the next question in
            // the same message instead of costing an `inspect` round trip to find out.
            $declared = $this->declaredOfKind($roots, $kind);

            throw new EditException(
                sprintf(
                    'target.select "%s" matched nothing in this file.%s',
                    $select,
                    $declared === [] ? sprintf(' It declares no %s at all.', $kind) : sprintf(' It declares %s: %s.', $kind, implode(', ', $declared)),
                ),
            );
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

        if ($node instanceof Stmt\ClassLike) {
            // An anonymous class has no name to be the owner of anything, and it is not part of
            // the class it sits inside: leaving `$inside` alone would let `method:Outer::run`
            // resolve a method declared in an anonymous class within Outer, and edit that.
            $inside = $node->name === null ? null : $node->name->toString();
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
    /**
     * The selectors of one kind this file would accept, for a message that has to say what
     * is there rather than only what is not.
     *
     * Capped, because a large file has more members than a message can carry and the point
     * is to orient the caller, not to reproduce the file. Members are qualified with their
     * owner, because that is the form the selector takes.
     *
     * @param list<Node\Stmt> $roots
     *
     * @return list<string>
     */
    private function declaredOfKind(array $roots, string $kind): array
    {
        $found = [];

        foreach ($roots as $root) {
            $this->gatherOfKind($root, $kind, null, $found);
        }
        sort($found);
        $found = array_values(array_unique($found));

        if (count($found) <= self::DECLARED_IN_MESSAGE) {
            return $found;
        }
        $shown = array_slice($found, 0, self::DECLARED_IN_MESSAGE);
        $shown[] = sprintf('and %d more', count($found) - self::DECLARED_IN_MESSAGE);

        return $shown;
    }

    /**
     * Walk one subtree gathering the names of `$kind`, qualified by their owner.
     *
     * @param list<string> $found
     */
    private function gatherOfKind(Node $node, string $kind, ?string $inside, array &$found): void
    {
        $named = static fn (?Node $identifier): ?string => $identifier === null ? null : (string) $identifier;
        $qualify = static fn (string $name): string => $inside === null ? $name : $inside . '::' . $name;

        $name = match ($kind) {
            'class' => $node instanceof Stmt\Class_ ? $named($node->name) : null,
            'interface' => $node instanceof Stmt\Interface_ ? $named($node->name) : null,
            'trait' => $node instanceof Stmt\Trait_ ? $named($node->name) : null,
            'enum' => $node instanceof Stmt\Enum_ ? $named($node->name) : null,
            'function' => $node instanceof Stmt\Function_ ? $named($node->name) : null,
            'method' => $node instanceof Stmt\ClassMethod ? $qualify((string) $node->name) : null,
            default => null,
        };

        if ($name !== null) {
            $found[] = $name;
        }

        if ($kind === 'property' && $node instanceof Stmt\Property) {
            foreach ($node->props as $property) {
                $found[] = $qualify('$' . $property->name->toString());
            }
        }

        if ($kind === 'const' && $node instanceof Stmt\ClassConst) {
            foreach ($node->consts as $constant) {
                $found[] = $qualify($constant->name->toString());
            }
        }

        if ($node instanceof Stmt\ClassLike) {
            $inside = $node->name === null ? null : $node->name->toString();
        }

        foreach ($node->getSubNodeNames() as $subNodeName) {
            $value = $node->{$subNodeName};

            if ($value instanceof Node) {
                $this->gatherOfKind($value, $kind, $inside, $found);
            } elseif (is_array($value)) {
                foreach ($value as $child) {
                    if ($child instanceof Node) {
                        $this->gatherOfKind($child, $kind, $inside, $found);
                    }
                }
            }
        }
    }

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
            'property' => ($node instanceof Stmt\Property && $this->declaresName($node->props, ltrim($name, '$')) || $this->promotesProperty($node, ltrim($name, '$'))) && $ownerAgrees,
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

    /**
     * Whether this parameter declares a property rather than merely receiving a value.
     *
     * Constructor promotion is how a modern extension writes its dependencies: measured on
     * one TYPO3 extension, 58 of its 65 properties are promoted and 7 are declared in the
     * class body. A `property:` selector that only saw `Stmt_Property` therefore found the
     * exception and missed the rule.
     *
     * The parser answers the question itself, and answers it wider than a flags check would:
     * a parameter with property hooks and no visibility modifier is promoted too.
     */
    private function promotesProperty(Node $node, string $name): bool
    {
        return $node instanceof Node\Param && $node->isPromoted() && $node->var instanceof Expr\Variable && is_string($node->var->name) && $node->var->name === $name;
    }
}
