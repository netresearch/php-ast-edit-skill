<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use PhpParser\Node\Stmt;
use PhpParser\Parser;

/**
 * One file inside an apply transaction. Instances carry every intermediate state so that
 * mutation, printing and re-parsing all complete before the first byte reaches the working
 * tree.
 */
final class FileTransaction
{
    /** @var list<array{edit: array<string, mixed>, location: NodeLocation, index: int}> */
    public array $resolved = [];

    public ?string $output = null;

    public bool $changed = false;

    /**
     * @param 'edit'|'create'|'delete' $mode
     * @param list<Stmt> $roots
     */
    public function __construct(
        public readonly string $path,
        public readonly string $mode,
        public readonly ?string $source,
        public array $roots,
        public readonly ?Parser $parser,
        public readonly ?string $phpVersion,
        public readonly bool $existed,
    ) {
    }

    public function beforeSha(): ?string
    {
        return $this->source === null ? null : hash('sha256', $this->source);
    }
}
