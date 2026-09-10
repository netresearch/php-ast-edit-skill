<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use PhpParser\Node;
use PhpParser\Node\Scalar\String_;
use PhpParser\Node\Stmt;
use PhpParser\NodeVisitorAbstract;

/**
 * Every string literal whose value is one name, with the selector of the outermost named
 * declaration around it — the scope a `replace_expression` with `match` can be given to set
 * them all. A literal outside any named declaration has no such scope.
 */
final class NameLiterals extends NodeVisitorAbstract
{
    /** @var list<array{0: ?string, 1: String_}> */
    public array $found = [];

    /** @var list<?string> the outermost named declaration, once per level entered */
    private array $scopes = [];

    public function __construct(private readonly string $name) {}

    public function enterNode(Node $node): ?int
    {
        if ($node instanceof Stmt\ClassLike || $node instanceof Stmt\Function_) {
            $this->scopes[] = $this->scopes === [] ? self::selector($node) : end($this->scopes);
        }

        if ($node instanceof String_ && $node->value === $this->name) {
            $this->found[] = [$this->scopes === [] ? null : end($this->scopes), $node];
        }

        return null;
    }

    public function leaveNode(Node $node): ?int
    {
        if ($node instanceof Stmt\ClassLike || $node instanceof Stmt\Function_) {
            array_pop($this->scopes);
        }

        return null;
    }

    private static function selector(Stmt\ClassLike|Stmt\Function_ $node): ?string
    {
        $kind = match (true) {
            $node instanceof Stmt\Function_ => 'function',
            $node instanceof Stmt\Interface_ => 'interface',
            $node instanceof Stmt\Trait_ => 'trait',
            $node instanceof Stmt\Enum_ => 'enum',
            default => 'class',
        };

        return $node->name === null ? null : $kind . ':' . $node->name->toString();
    }
}
