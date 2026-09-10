<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

/**
 * Where a class member is used across a project, as the resolver saw it.
 *
 * The engine decides what to write; a finder only reports sites. Every range it returns
 * is checked against the parsed file before it becomes an edit, so a finder that is wrong
 * about an offset produces a refusal, never a write.
 */
interface ReferenceFinder
{
    /**
     * @return array{
     *     references: list<array{file: string, start: int, end: int, line: int}>,
     *     risky: list<array{file: string, line: int, text: string}>,
     *     resolver: string,
     * }
     */
    public function references(string $root, string $class, string $member): array;
}
