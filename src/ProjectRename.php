<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node\Expr;
use PhpParser\Node\Scalar\String_;
use PhpParser\Node\Stmt;
use PhpParser\NodeTraverser;

/**
 * A method rename the file alone cannot decide: every declaration and call site across the
 * project, as guarded `set_name` edits the engine then applies in one transaction.
 *
 * The lexical rename stays for what one file does decide — a private method, or any method
 * of a final class with no parent, interface or trait. Everything else was refused, and in
 * a TYPO3 extension that is most methods: 180 of 274 in the one measured. Here the hierarchy
 * comes from the project's own sources and Composer's tables, and the call sites from
 * Phpactor. What neither can see is refused rather than guessed:
 *
 * - a declaration of the method outside the project (a vendor base class, a PHP interface) —
 *   renaming would break the contract it fulfils;
 * - an ancestor nobody can find, or a trait that declares either name;
 * - the new name already taken anywhere in the hierarchy;
 * - a call Phpactor could not attribute to a class (`risky`), which may be one of ours.
 *
 * Mentions of the old name outside PHP — Services.yaml, TypoScript, Fluid property access —
 * and PHP string literals that read it — a PHPUnit `->method('fetch')`, a callable — are not
 * renamed and not refused; they are listed, because only a person or a model reading them
 * can say whether they meant this method.
 */
final class ProjectRename
{
    private const LISTED = 20;

    private const NAMED = 'The resolver named %s, %s; nothing was changed.';

    private readonly NodeLocator $locator;

    /** @param \Closure(string): array{0: string, 1: list<Stmt>} $parse the engine's own parse of a file */
    public function __construct(
        private readonly ?ReferenceFinder $finder,
        private readonly \Closure $parse,
    ) {
        $this->locator = new NodeLocator();
    }

    /**
     * @param list<Stmt> $roots
     * @return array{
     *     files: array<string, array{sha256: string, edits: list<array<string, mixed>>}>,
     *     report: array<string, mixed>,
     * }
     */
    public function plan(
        string $path,
        array $roots,
        NodeLocation $location,
        string $to,
        string $reason,
    ): array {
        $method = $location->node;
        $owner = $location->parent;

        if (!$method instanceof Stmt\ClassMethod || !$owner instanceof Stmt\ClassLike) {
            throw new EditException('rename_method targets a method declaration.');
        }
        $from = $method->name->toString();

        if (!preg_match('/^[A-Za-z_\x80-\xff][A-Za-z0-9_\x80-\xff]*$/', $to)) {
            throw new EditException('rename_method: "' . $to . '" is not a method name.');
        }

        if (str_starts_with(strtolower($from), '__') || str_starts_with(strtolower($to), '__')) {
            throw new EditException('rename_method cannot rename to or from a magic-method name.');
        }
        $ownerName = ProjectIndex::nameOf($owner, $roots);

        if ($ownerName === null) {
            throw new EditException(
                'rename_method cannot resolve a method of an anonymous class across the project.',
            );
        }
        $finder = $this->finder ?? throw new EditException(
            sprintf(
                'rename_method on %s::%s needs the whole project, because %s, and the call sites come from Phpactor, which is not set up here. %s',
                $ownerName,
                $from,
                $reason,
                PhpactorReferenceFinder::installHint(),
            ),
        );
        $index = ProjectIndex::for($path);

        if (!$index->isProjectFile($path)) {
            throw new EditException(
                $path . ' is not one of the project files git knows about outside the repository exclusions, so its callers cannot be looked up.',
            );
        }
        [$family, $hierarchy] = $this->family($index, $ownerName, $method, $from, $to);
        $sites = [];
        $risky = [];
        $resolver = '';

        foreach ($this->queries($index, $family) as $class) {
            $found = $finder->references($index->root, $class, $from);
            $resolver = $found['resolver'];

            foreach ($found['references'] as $site) {
                $file = realpath($site['file']) ?: $site['file'];
                $sites[$file][$site['start']] = $site;
            }

            foreach ($found['risky'] as $site) {
                $risky[$site['file'] . ':' . $site['line']] = $site['text'];
            }
        }

        if ($risky !== []) {
            throw new EditException(
                sprintf(
                    'rename_method on %s::%s stops at %d call(s) whose receiver type Phpactor could not determine; any of them may call this method: %s. Give those receivers a type, or rename those sites yourself with set_name.',
                    $ownerName,
                    $from,
                    count($risky),
                    implode(
                        '; ',
                        array_slice(
                            array_map(
                                static fn (string $site, string $text): string => $site . ' ' . $text,
                                array_keys($risky),
                                $risky,
                            ),
                            0,
                            10,
                        ),
                    ),
                ),
            );
        }

        // The resolver names call sites; the declarations are the hierarchy's own. Both
        // go through the same check, so one it left out is still renamed and one it got
        // wrong is refused.
        foreach ($family as $member) {
            $name = null;

            foreach ($member['node']->getMethods() as $candidate) {
                if (strcasecmp($candidate->name->toString(), $from) === 0) {
                    $name = $candidate->name;
                }
            }

            if ($name !== null) {
                $start = $name->getStartFilePos();
                $sites[$member['file']][$start] = [
                    'file' => $member['file'],
                    'start' => $start,
                    'end' => $name->getEndFilePos() + 1,
                    'line' => $name->getStartLine(),
                ];
            }
        }
        $files = [];
        $declarations = 0;
        $references = 0;

        foreach ($sites as $file => $ranges) {
            if (!$index->isProjectFile($file)) {
                throw new EditException(
                    sprintf(
                        'Phpactor named a call site in %s, which is not a project file; nothing was changed.',
                        $file,
                    ),
                );
            }
            [$source, $fileRoots] = ($this->parse)($file);
            ksort($ranges);
            $edits = [];

            foreach ($ranges as $range) {
                $site = $this->site($fileRoots, $source, $range, $from, $file);
                $site->parent instanceof Stmt\ClassMethod ? ++$declarations : ++$references;
                $edits[] = [
                    'operation' => 'set_name',
                    'target' => ['ref' => $site->path, 'kind' => 'Identifier'],
                    'expect' => [
                        'name' => substr($source, $range['start'], $range['end'] - $range['start']),
                        'type' => 'Identifier',
                    ],
                    'value' => $to,
                ];
            }
            $files[$file] = ['sha256' => hash('sha256', $source), 'edits' => $edits];
        }
        [$mentions, $total] = $this->mentions($index, $from);

        return [
            'files' => $files,
            'report' => [
                'method' => $ownerName . '::' . $from,
                'to' => $to,
                'declarations' => $declarations,
                'references' => $references,
                'files' => count($files),
                'hierarchy' => array_values(
                    array_map(static fn (array $member): string => $member['name'], $family),
                ),
                'resolver' => $resolver,
                'notRenamed' => $mentions,
                'notRenamedCount' => $total,
                'notRenamedMeans' => 'Mentions of the old name outside PHP — configuration, TypoScript, Fluid templates. They were not changed; each needs reading.',
                'ancestorsSeen' => $hierarchy,
                ...$this->literalReport($index, $from, $to),
            ],
        ];
    }

    /** @return array<string, mixed> the `literals` fields of the report, empty when there are none */
    private function literalReport(ProjectIndex $index, string $from, string $to): array
    {
        [$literals, $count, $unread] = $this->literals($index, $from);

        return [
            ...$literals === [] ? [] : [
                'literals' => $literals,
                'literalsCount' => $count,
                'literalsMeans' => sprintf(
                    "PHP string literals that read %1\$s, such as a PHPUnit ->method('%1\$s') or a callable. Not changed: which class each one names is not known here, and another class may have a method of that name. Where every literal of an entry means this method, a replace_expression on it — target.select as listed, match \"'%1\$s'\", php \"'%2\$s'\" — sets all of them; otherwise, or where an entry has no select, set_string on the refs that do (lines and refs are in the same order).",
                    $from,
                    $to,
                ),
            ],
            ...$unread === [] ? [] : ['literalsUnread' => $unread],
        ];
    }

    /**
     * The classes that declare the method together — the owner, the project ancestors whose
     * declaration it overrides or implements, and the project descendants that override it.
     *
     * @return array{0: array<string, array{name: string, file: string, node: Stmt\ClassLike, project: bool}>, 1: int}
     */
    private function family(
        ProjectIndex $index,
        string $ownerName,
        Stmt\ClassMethod $method,
        string $from,
        string $to,
    ): array {
        $owner = $index->find($ownerName) ?? throw new EditException('The project index does not contain ' . $ownerName . '.');
        $family = [strtolower($owner['name']) => $owner];
        $lowerFrom = strtolower($from);
        $lowerTo = strtolower($to);
        $ancestors = $index->ancestors($owner['name']);

        foreach ($ancestors as $ancestor) {
            if ($ancestor['where'] === 'missing') {
                throw new EditException(
                    sprintf(
                        '%s inherits from %s, which is in neither the project nor Composer\'s class tables, so whether it declares %s is unknown.',
                        $owner['name'],
                        $ancestor['name'],
                        $from,
                    ),
                );
            }

            // A private method is not inherited and overrides nothing, so a same-named
            // method above it is a different method. Only the new name can collide.
            if ($method->isPrivate() || !in_array($lowerFrom, $ancestor['methods'], true)) {
                continue;
            }

            if ($ancestor['where'] !== 'project') {
                throw new EditException(
                    sprintf(
                        '%s::%s implements or overrides %s::%s, declared outside the project (%s); renaming it would break that contract.',
                        $owner['name'],
                        $from,
                        $ancestor['name'],
                        $from,
                        $ancestor['where'],
                    ),
                );
            }

            if ($ancestor['trait']) {
                throw new EditException(
                    sprintf(
                        '%s::%s comes with trait %s; a rename through trait composition is not resolved.',
                        $owner['name'],
                        $from,
                        $ancestor['name'],
                    ),
                );
            }
            $family[strtolower($ancestor['name'])] = $index->find($ancestor['name']);
        }

        if (!$method->isPrivate()) {
            foreach ($index->projectClasses() as $candidate) {
                $key = strtolower($candidate['name']);

                if (isset($family[$key])) {
                    continue;
                }
                $above = array_map(
                    static fn (array $ancestor): string => strtolower($ancestor['name']),
                    $index->ancestors($candidate['name']),
                );

                if (array_intersect($above, array_keys($family)) !== [] && $this->declares($candidate['node'], $lowerFrom)) {
                    $family[$key] = $candidate;
                }
            }
        }
        $seen = 0;
        // A change of case only: PHP method names are case-insensitive, so every name that
        // matches the new one is the method itself. Nothing can collide.
        $caseOnly = $lowerTo === $lowerFrom;

        foreach ($family as $member) {
            if (!$caseOnly && $this->declares($member['node'], $lowerTo)) {
                throw new EditException(
                    sprintf('rename_method: %s already declares %s.', $member['name'], $to),
                );
            }

            foreach ($index->ancestors($member['name']) as $ancestor) {
                ++$seen;

                if (!$caseOnly && in_array($lowerTo, $ancestor['methods'], true)) {
                    throw new EditException(
                        sprintf(
                            'rename_method: %s, an ancestor of %s, already declares %s.',
                            $ancestor['name'],
                            $member['name'],
                            $to,
                        ),
                    );
                }

                if ($ancestor['trait'] && in_array($lowerFrom, $ancestor['methods'], true)) {
                    throw new EditException(
                        sprintf(
                            '%s uses trait %s, which declares %s; a rename through trait composition is not resolved.',
                            $member['name'],
                            $ancestor['name'],
                            $from,
                        ),
                    );
                }
            }
        }

        foreach ($index->projectClasses() as $candidate) {
            if ($caseOnly || isset($family[strtolower($candidate['name'])]) || !$this->declares($candidate['node'], $lowerTo)) {
                continue;
            }
            $above = array_map(
                static fn (array $ancestor): string => strtolower($ancestor['name']),
                $index->ancestors($candidate['name']),
            );

            if (array_intersect($above, array_keys($family)) !== []) {
                throw new EditException(
                    sprintf(
                        'rename_method: %s, below %s, already declares %s.',
                        $candidate['name'],
                        $owner['name'],
                        $to,
                    ),
                );
            }
        }

        return [$family, $seen];
    }

    /**
     * The classes to ask about: every family member with no ancestor in the family. Asked
     * about the topmost declaration, Phpactor returns the calls through every subtype and
     * through the interface; asked about a subclass, it misses the calls through the
     * interface (measured on a fixture: Base found four of five, Contract all five).
     *
     * @param array<string, array{name: string, file: string, node: Stmt\ClassLike, project: bool}> $family
     * @return list<string>
     */
    private function queries(ProjectIndex $index, array $family): array
    {
        $queries = [];

        foreach ($family as $key => $member) {
            $above = array_map(
                static fn (array $ancestor): string => strtolower($ancestor['name']),
                $index->ancestors($member['name']),
            );

            if (array_intersect($above, array_keys($family)) === []) {
                $queries[$key] = $member['name'];
            }
        }

        return array_values($queries);
    }

    private function declares(Stmt\ClassLike $node, string $lowerName): bool
    {
        foreach ($node->getMethods() as $method) {
            if (strtolower($method->name->toString()) === $lowerName) {
                return true;
            }
        }

        return false;
    }

    /**
     * @param list<Stmt> $roots
     * @param array{start: int, end: int, line: int} $range
     */
    private function site(
        array $roots,
        string $source,
        array $range,
        string $from,
        string $file,
    ): NodeLocation {
        $where = sprintf('%s:%d', $file, $range['line']);

        try {
            $location = $this->locator->locate($roots, $range['start'], 'Identifier');
        } catch (EditException) {
            throw new EditException(sprintf(self::NAMED, $where, 'where there is no method name'));
        }
        $parent = $location->parent;
        $callable = $parent instanceof Stmt\ClassMethod || $parent instanceof Expr\MethodCall || $parent instanceof Expr\NullsafeMethodCall || $parent instanceof Expr\StaticCall;

        if ($location->start() !== $range['start'] || $location->end() + 1 !== $range['end'] || $location->property !== 'name' || !$callable) {
            throw new EditException(
                sprintf(self::NAMED, $where, 'which is not a method name the engine can rename'),
            );
        }

        if (strcasecmp(substr($source, $range['start'], $range['end'] - $range['start']), $from) !== 0) {
            throw new EditException(sprintf(self::NAMED, $where, 'which does not read ' . $from));
        }

        return $location;
    }

    /**
     * Where the old name appears outside PHP, and, for an accessor, where a Fluid template
     * reads the property it serves: `{credential.label}` calls getLabel() without naming it.
     *
     * @return array{0: list<string>, 1: int}
     */
    private function mentions(ProjectIndex $index, string $from): array
    {
        $patterns = ['/\b' . preg_quote($from, '/') . '\b/'];

        if (preg_match('/^(get|is|has)([A-Z]\w*)$/', $from, $accessor) === 1) {
            $patterns[] = '/\.' . preg_quote(lcfirst($accessor[2]), '/') . '\b/';
        }
        $listed = [];
        $total = 0;

        foreach ($index->otherFiles() as $file) {
            if (filesize($file) > 1000000) {
                continue;
            }
            $content = (string) file_get_contents($file);

            if (str_contains($content, "\x00")) {
                continue;
            }
            $template = str_ends_with($file, '.html');

            foreach (explode("\n", $content) as $number => $line) {
                $hit = preg_match($patterns[0], $line) === 1 || $template && isset($patterns[1]) && preg_match($patterns[1], $line) === 1;

                if (!$hit) {
                    continue;
                }
                ++$total;

                if (count($listed) < self::LISTED) {
                    $listed[] = substr($file, strlen($index->root) + 1) . ':' . ($number + 1);
                }
            }
        }

        return [$listed, $total];
    }

    /**
     * PHP string literals that read the old name: `->method('fetch')` in a PHPUnit mock, a
     * callable `[$service, 'fetch']`, `method_exists($x, 'fetch')`. Which class each one
     * names takes dataflow the engine does not have, and a vendor class may declare a method
     * of the same name, so none is changed. They are grouped by the declaration that holds
     * them, because that is the scope one `replace_expression` with `match` can name to set
     * every one of them; each also comes with its ref, so `set_string` can set only some —
     * a data provider's name or a backed enum value that happens to read the same is not
     * the method.
     *
     * Measured on a TYPO3 extension: renaming a service getter left 67 mock literals in nine
     * test files, and 174 of its 682 unit tests failed until they were changed as well.
     *
     * @return array{0: list<array<string, mixed>>, 1: int, 2: list<string>}
     */
    private function literals(ProjectIndex $index, string $from): array
    {
        $groups = [];
        $total = 0;
        $unread = [];

        foreach ($index->phpFiles() as $file) {
            $relative = substr($file, strlen($index->root) + 1);
            $content = filesize($file) > 1000000 ? false : file_get_contents($file);

            if ($content === false) {
                $unread[] = $relative;

                continue;
            }

            if (!str_contains($content, $from)) {
                continue;
            }

            // Every project file already parsed when the index was built, or the rename was
            // refused; a parse error cannot reach this point.
            [, $roots] = ($this->parse)($file);
            $visitor = new NameLiterals($from);
            (new NodeTraverser($visitor))->traverse($roots);

            $found = $visitor->found();
            $total += count($found);
            $this->group($groups, $relative, $found, $roots);
        }
        ksort($groups);

        return [array_values($groups), $total, $unread];
    }

    /**
     * @param array<string, array<string, mixed>> $groups
     * @param list<array{0: ?string, 1: String_}> $found
     * @param list<Stmt> $roots
     */
    private function group(array &$groups, string $relative, array $found, array $roots): void
    {
        foreach ($found as [$select, $node]) {
            $key = $relative . "\x00" . $select;
            $groups[$key] ??= ['file' => $relative] + ($select === null ? [] : ['select' => $select]) + ['lines' => [], 'refs' => []];
            $groups[$key]['lines'][] = $node->getStartLine();
            $groups[$key]['refs'][] = $this->locator->locate($roots, $node->getStartFilePos(), 'Scalar_String')->path;
        }
    }
}
