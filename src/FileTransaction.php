<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use PhpParser\Node\Stmt;
use PhpParser\Parser;
use PhpParser\Token;

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

    /** Which printer produced {@see $output}. */
    public string $printer = 'canonical';

    /** Set when the repository has not declared itself canonically formatted. */
    public ?string $warning = null;

    /** Lines the write actually changes, measured after printing. */
    public ?int $changedLines = null;

    /**
     * @param 'edit'|'create'|'delete' $mode
     * @param list<Stmt> $roots the tree the edits mutate
     * @param list<Stmt>|null $original the pristine tree, kept for format-preserving printing
     * @param list<Token>|null $tokens the pristine token stream, likewise
     */
    public function __construct(
        public readonly string $path,
        public readonly string $mode,
        public readonly ?string $source,
        public array $roots,
        public readonly ?Parser $parser,
        public readonly ?string $phpVersion,
        public readonly bool $existed,
        public readonly ?array $original = null,
        public readonly ?array $tokens = null,
    ) {}

    public function beforeSha(): ?string
    {
        return $this->source === null ? null : hash('sha256', $this->source);
    }
}
