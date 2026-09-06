<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

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

    /** Which printer produced {@see $output}. */
    public string $printer = 'canonical';

    /** Set when the repository has not declared itself canonically formatted. */
    public ?string $warning = null;

    /** Lines the write actually changes, measured after printing. */
    public ?int $changedLines = null;

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
    ) {
        $this->linkTarget = is_link($path) ? readlink($path) : null;
        $this->resolvedPath = $existed ? realpath($path) ?: $path : null;
        $modeBits = $existed ? @fileperms($path) : false;
        $this->permissions = $modeBits === false ? null : $modeBits & 0777;
    }

    public function beforeSha(): ?string
    {
        return $this->source === null ? null : hash('sha256', $this->source);
    }

    /**
     * What the project's declared formatter did, or null where none is declared or the file
     * was printed format-preserving and is therefore not the formatter's to touch.
     */
    public ?string $formatter = null;

    /**
     * What each edit did, keyed by its index in the request.
     *
     * A caller that cannot see the outcome reads the file back. Measured on a controlled run:
     * after a successful rename the model ran a `grep`, two `Read`s and a `tail` to satisfy
     * itself — four calls spent on a question the write already knew the answer to.
     *
     * @var array<int, array<string, int|string>>
     */
    public array $effects = [];

    public ?string $linkTarget = null;

    public ?string $resolvedPath = null;

    public ?int $permissions = null;

    public array $lint = [];

    public array $verify = [];
}
