<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Comment\Doc;
use PhpParser\Modifiers;
use PhpParser\Node;
use PhpParser\Node\Arg;
use PhpParser\Node\ArrayItem;
use PhpParser\Node\Attribute;
use PhpParser\Node\AttributeGroup;
use PhpParser\Node\ClosureUse;
use PhpParser\Node\ComplexType;
use PhpParser\Node\Const_;
use PhpParser\Node\Expr;
use PhpParser\Node\Expr\CallLike;
use PhpParser\Node\Expr\Variable;
use PhpParser\Node\Identifier;
use PhpParser\Node\MatchArm;
use PhpParser\Node\Name;
use PhpParser\Node\Param;
use PhpParser\Node\PropertyItem;
use PhpParser\Node\Scalar\String_;
use PhpParser\Node\StaticVar;
use PhpParser\Node\Stmt;
use PhpParser\Node\UseItem;
use PhpParser\Node\VarLikeIdentifier;
use PhpParser\NodeDumper;
use PhpParser\NodeFinder;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitor;
use PhpParser\NodeVisitor\CloningVisitor;
use PhpParser\NodeVisitorAbstract;
use PhpParser\Parser;
use PhpParser\ParserFactory;
use PhpParser\PhpVersion;

final class Editor
{
    private readonly NodeLocator $locator;

    /** @var list<array<string, mixed>> what each project-wide rename in this apply resolved */
    private array $projectRenames = [];

    /** @param ?ReferenceFinder $finder null: Phpactor, where the repository points at one */
    public function __construct(private readonly ?ReferenceFinder $finder = null)
    {
        $this->locator = new NodeLocator();
    }

    public function inspect(string $path, array $target, ?string $phpVersion = null): array
    {
        [$source, , $roots] = $this->parseFile($path, $phpVersion);
        $offset = $this->targetOffset($source, $target);
        $locations = $this->locator->ancestry($roots, $offset);

        if (isset($target['kind'])) {
            $kind = (string) $target['kind'];
            $locations = array_values(
                array_filter(
                    $locations,
                    static fn (
                        NodeLocation $location,
                    ): bool => $location->node->getType() === $kind || $location->node::class === $kind,
                ),
            );
        }

        return [
            'file' => $path,
            'sha256' => hash('sha256', $source),
            'offset' => $offset,
            'nodes' => array_map(
                fn (NodeLocation $location): array => $this->describe($location, $source),
                $locations,
            ),
        ];
    }

    public function validate(string $path, ?string $phpVersion = null): array
    {
        [$source, , $roots] = $this->parseFile($path, $phpVersion);
        $lint = (new PhpLint())->check($source, $path, $phpVersion);

        return [
            'file' => $path,
            'sha256' => hash('sha256', $source),
            'statements' => count($roots),
            'parsed' => true,
            'valid' => true,
            'validation' => ['parser' => 'passed', 'lint' => $lint, 'checks' => 'not_run'],
        ];
    }

    public function apply(array $document, bool $forceDryRun = false): array
    {
        $this->verifyResults = [];
        $report = $this->reportMode($document);
        $files = $document['files'] ?? null;

        if (!is_array($files) || $files === []) {
            // The shape belongs in the message. A caller that got here wrote a document
            // of some other shape — usually a bare array of edits — and being told which
            // key is missing leaves it guessing at the two levels above that key.
            throw new EditException(self::SHAPE_REQUIRED);
        }
        $dryRun = $forceDryRun || (bool) ($document['dryRun'] ?? false);
        $this->projectRenames = [];
        $transactions = $this->prepareAll($this->expandProjectRenames($files));

        foreach ($transactions as $transaction) {
            $this->mutate($transaction);
        }

        foreach ($transactions as $transaction) {
            $this->render($transaction);
        }

        if (!$dryRun) {
            $verification = (new VerificationRunner())->prepare($transactions);
            $this->commit($transactions, $verification);
        }

        if ($report === 'agent') {
            return $this->agentResult($transactions, $dryRun);
        }
        $compact = $report === 'compact';
        $open = $this->open($transactions);
        $result = [
            ...$open === null ? [] : ['open' => $open],
            'files' => array_map(
                fn (FileTransaction $file): array => $this->report($file, $dryRun, $compact),
                $transactions,
            ),
            'checksPassed' => $this->verifyResults === [] ? null : !in_array(false, array_column($this->verifyResults, 'ok'), true),
        ];
        $alreadyRun = $this->alreadyRun();

        if ($alreadyRun !== null) {
            $result['alreadyRun'] = $alreadyRun;
        }

        if ($this->projectRenames !== []) {
            $result['renames'] = $this->projectRenames;
        }

        if ($compact) {
            $result['verify'] = $this->verifyResults;
        }

        return $result;
    }

    /**
     * What a project-wide rename left for the caller, said before anything else.
     *
     * Measured: a gated run received 67 listed mock literals, saw the project's analysis
     * pass, and stopped — the literals sat in `renames` below the file reports, and 174 unit
     * tests failed. Static analysis does not read strings, so its pass is no evidence here.
     * A file this apply edited is counted again on its final tree: literals set in the same
     * transaction are no longer open.
     *
     * @param list<FileTransaction> $transactions
     */
    private function open(array $transactions): ?string
    {
        $open = [];

        foreach ($this->projectRenames as $i => $rename) {
            $method = (string) $rename['method'];
            [$count, $files] = $this->remainingLiterals(
                $rename['literals'] ?? [],
                substr($method, (int) strrpos($method, ':') + 1),
                $transactions,
            );

            if ($count > 0) {
                $open[] = sprintf(
                    '%d string literal(s) in %d file(s) still read %s (renames[%d].literals)',
                    $count,
                    $files,
                    substr($method, (int) strrpos($method, ':') + 1),
                    $i,
                );
            }
        }

        return $open === [] ? null : sprintf(
            'Review method-name literals: %s. They may name the renamed method or be unrelated data. Update only confirmed references; preserve unrelated literals. Passing checks alone do not classify these strings.',
            implode('; ', $open),
        );
    }

    /**
     * @param list<array{file: string, lines: list<int>}> $literals
     * @param list<FileTransaction> $transactions
     * @return array{0: int, 1: int} literals still reading `$name`, and the files they are in
     */
    private function remainingLiterals(array $literals, string $name, array $transactions): array
    {
        $perFile = [];

        foreach ($literals as $entry) {
            $perFile[$entry['file']] = ($perFile[$entry['file']] ?? 0) + count($entry['lines']);
        }

        foreach (array_keys($perFile) as $file) {
            foreach ($transactions as $transaction) {
                if ($transaction->mode === 'edit' && str_ends_with($this->canonicalPath($transaction->path), DIRECTORY_SEPARATOR . $file)) {
                    $visitor = new NameLiterals($name);
                    (new NodeTraverser($visitor))->traverse($transaction->roots);
                    $perFile[$file] = count($visitor->found());
                }
            }
        }
        $perFile = array_filter($perFile);

        return [array_sum($perFile), count($perFile)];
    }

    /**
     * The project checks this apply ran and passed, said as the repeat work they save.
     *
     * Measured on a three-change task: after applies whose project checks had passed, the
     * gated arm still ran the project's analysis by hand, and its own check runs took 303
     * seconds of tool time across eight sessions against 171 without the skill. The fields
     * carried the proof — command, scope, ok — and nothing said what it was good for. Only
     * project scope is named: a changed_files check saw the edited files, not the project.
     */
    private function alreadyRun(): ?string
    {
        if ($this->verifyResults === [] || in_array(false, array_column($this->verifyResults, 'ok'), true)) {
            return null;
        }
        $commands = [];

        foreach ($this->verifyResults as $check) {
            if ($check['scope'] === 'project') {
                $commands[$check['command']] = true;
            }
        }

        if ($commands === []) {
            return null;
        }

        return sprintf(
            'Passed over the whole project on the files as written: %s. With no file, dependency or check tool changed since, running it again by hand repeats this result.',
            implode('; ', array_keys($commands)),
        );
    }

    /**
     * Every rename_method one file cannot decide, turned into the project-wide edits that
     * carry it.
     *
     * Done before any file is prepared, so what follows is an ordinary transaction: each
     * touched file carries the hash its sites were computed against, and the stale-source
     * guard, the duplicate check and verification treat it like any other multi-file apply.
     * A file the caller already edits keeps its own entry, with the rename's edits first:
     * they were located on the file as it is on disk.
     *
     * @param  array<mixed> $files
     * @return array<mixed>
     */
    private function expandProjectRenames(array $files): array
    {
        $extra = [];

        foreach ($files as $i => $spec) {
            if (!is_array($spec) || !is_string($spec['path'] ?? null) || !is_array($spec['edits'] ?? null) || ($spec['mode'] ?? 'edit') !== 'edit') {
                continue;
            }
            $edits = [];
            $here = $this->canonicalPath($spec['path']);

            foreach ($spec['edits'] as $edit) {
                $plan = is_array($edit) ? $this->projectRename($spec, $this->acceptSynonyms($edit)) : null;

                if ($plan === null) {
                    $edits[] = $edit;

                    continue;
                }

                foreach ($plan['files'] as $file => $entry) {
                    $key = $this->canonicalPath($file);

                    if ($key === $here) {
                        array_push($edits, ...$entry['edits']);

                        continue;
                    }
                    $extra[$key] ??= ['path' => $file, 'sha256' => $entry['sha256'], 'edits' => []];
                    array_push($extra[$key]['edits'], ...$entry['edits']);
                }
                $this->projectRenames[] = $plan['report'];
            }
            $files[$i]['edits'] = $edits;
        }

        foreach ($files as $i => $spec) {
            $key = is_array($spec) && is_string($spec['path'] ?? null) ? $this->canonicalPath($spec['path']) : null;

            if ($key === null || !isset($extra[$key])) {
                continue;
            }

            if (($spec['mode'] ?? 'edit') !== 'edit') {
                throw new EditException(
                    sprintf(
                        'rename_method has call sites in %s, which this transaction %s.',
                        $spec['path'],
                        $spec['mode'] === 'delete' ? 'deletes' : 'creates',
                    ),
                );
            }
            $files[$i]['edits'] = [...$extra[$key]['edits'], ...is_array($spec['edits'] ?? null) ? $spec['edits'] : []];
            unset($extra[$key]);
        }

        return [...$files, ...array_values($extra)];
    }

    private function projectRename(array $spec, array $edit): ?array
    {
        $options = $this->projectRenameOptions($edit);

        if ($options === null) {
            return null;
        }
        [$target, $mocks, $project] = $options;
        $path = $spec['path'];
        [$source, , $roots] = $this->parseFile($path, null);
        $this->assertSha($spec, $path, hash('sha256', $source));
        $location = is_string($target['ref'] ?? null) ? $this->locator->resolveRef($roots, $target['ref']) : $this->locator->resolveSelect($roots, $target['select']);
        $this->assertKind($location, $target['kind'] ?? null);

        $reason = null;

        if ($location->node instanceof Stmt\ClassMethod) {
            $reason = $project ? 'project scope was requested' : RenameMethod::projectWideBecause($location->node, $location->parent);
        }

        if ($reason === null) {
            return null;
        }
        $finder = $this->finder;

        if ($finder === null) {
            $phar = PhpactorReferenceFinder::locate(RepositoryConfig::discover($path));
            $finder = $phar === null ? null : new PhpactorReferenceFinder($phar);
        }
        $parse = function (string $file): array {
            [$source, , $fileRoots] = $this->parseFile($file, null);

            return [$source, $fileRoots];
        };

        return (new ProjectRename($finder, $parse))->plan(
            $path,
            $roots,
            $location,
            $edit['to'],
            $reason,
            $mocks,
        );
    }

    /**
     * The requested response shape, or a refusal naming every shape there is.
     *
     * @param array<string, mixed> $document
     */
    private function reportMode(array $document): string
    {
        $report = array_key_exists('report', $document) ? $document['report'] : 'full';

        if (!in_array($report, ['full', 'compact', 'agent'], true)) {
            throw new EditException('apply report must be "full", "compact" or "agent".');
        }

        return $report;
    }

    /**
     * One transaction per file spec, refusing two specs that name the same file.
     *
     * Two entries for one path would each print from their own snapshot, and the second
     * write would silently drop the first one's edits.
     *
     * @param  array<mixed> $files
     * @return list<FileTransaction>
     */
    private function prepareAll(array $files): array
    {
        $transactions = [];
        $seen = [];

        foreach ($files as $spec) {
            if (!is_array($spec)) {
                throw new EditException('Each files entry must be an object.');
            }
            $transaction = $this->prepare($spec);
            $key = $this->canonicalPath($transaction->path);

            if (isset($seen[$key])) {
                throw new EditException(
                    sprintf(
                        'Duplicate path in one transaction: %s and %s are the same file.',
                        $seen[$key],
                        $transaction->path,
                    ),
                );
            }
            $seen[$key] = $transaction->path;
            $transactions[] = $transaction;
        }

        return $transactions;
    }

    /**
     * The decision-shaped response: what happened, what is still open, nothing twice.
     *
     * `checksPassed` stays alongside `checks` because the CLI's exit code is derived from it
     * and one command must not have two verdicts — the same reason the flag form and the
     * JSON form were unified. `checks` is what a caller should read: it separates "every
     * declared check passed" from "this repository declares none", which the boolean cannot.
     *
     * @param  list<FileTransaction> $transactions
     * @return array<string, mixed>
     */
    private function agentResult(array $transactions, bool $dryRun): array
    {
        $failed = [];
        $verifications = [];
        $passed = 0;

        foreach ($this->verifyResults as $check) {
            // Every execution is named, passing ones included. A caller deciding whether it
            // may skip a check it already ran needs to know which command that was and where
            // it ran; a bare count says a check passed without saying which. The per-file
            // `checkIds` and `afterSha256` supply the rest — which files it saw, at what
            // bytes — so the whole proof is in this response without repeating a path.
            $verifications[] = array_intersect_key($check, array_flip(['id', 'scope', 'cwd', 'command', 'ok']));

            if ($check['ok'] === true) {
                ++$passed;

                continue;
            }
            // A passing check's output is the routine noise this mode exists to drop. A
            // failing one is the whole reason the caller is still reading.
            $failed[] = array_intersect_key($check, array_flip(['id', 'scope', 'command', 'output']));
        }
        $declared = $this->verifyResults !== [];
        $allPassed = $failed === [];

        if (!$declared) {
            $checks = 'none_declared';
        } elseif ($allPassed) {
            $checks = 'passed';
        } else {
            $checks = 'failed';
        }

        if ($dryRun) {
            $outcome = 'dry_run';
        } elseif ($allPassed) {
            $outcome = 'applied';
        } else {
            $outcome = 'applied_checks_failed';
        }

        return [
            'reportVersion' => EditReport::AGENT_VERSION,
            'report' => 'agent',
            ...$this->open($transactions) === null ? [] : ['open' => $this->open($transactions)],
            'outcome' => $outcome,
            'checks' => $checks,
            'checksPassed' => $declared ? $allPassed : null,
            'checksPassedCount' => $passed,
            'checksFailed' => $failed,
            'verifications' => $verifications,
            ...$this->alreadyRun() === null ? [] : ['alreadyRun' => $this->alreadyRun()],
            ...$this->projectRenames === [] ? [] : ['renames' => $this->projectRenames],
            // What this response does NOT establish about reuse. The engine knows the
            // command, the directory, the files and their bytes; it cannot see the check
            // tool's version, the dependency tree it resolved, or anything else in the
            // environment. A caller keyed only on what is above will reuse a stale pass
            // after a dependency bump — so the limit is stated rather than left to be
            // discovered.
            'proofExcludes' => ['dependencies', 'checkToolVersions', 'runtime', 'environment'],
            'files' => array_map(
                static fn (FileTransaction $file): array => EditReport::agentFile($file, $dryRun),
                $transactions,
            ),
        ];
    }

    private function prepare(array $spec): FileTransaction
    {
        $path = $this->requiredString($spec, 'path');

        if (($spec['mode'] ?? 'edit') === 'create' && is_link($path) && !is_file($path)) {
            throw new EditException('DANGLING_SYMLINK: refusing creation through ' . $path);
        }
        $mode = (string) ($spec['mode'] ?? 'edit');

        if (!in_array($mode, ['edit', 'create', 'delete'], true)) {
            throw new EditException('mode must be edit, create or delete.');
        }
        $phpVersion = isset($spec['phpVersion']) ? $this->assertPhpVersion((string) $spec['phpVersion']) : null;
        $printer = $spec['printer'] ?? 'auto';

        if (!in_array($printer, ['auto', 'canonical', 'format-preserving'], true)) {
            throw new EditException('printer must be auto, canonical or format-preserving.');
        }

        if ($mode === 'delete') {
            if (!is_file($path)) {
                throw new EditException('Cannot delete missing file: ' . $path);
            }
            $source = $this->readFile($path);
            $this->assertSha($spec, $path, hash('sha256', $source));

            return new FileTransaction($path, 'delete', $source, [], null, $phpVersion, true);
        }

        if ($mode === 'create') {
            $existed = is_file($path);

            if ($existed && ($spec['expectAbsent'] ?? true) !== false) {
                throw new EditException(
                    sprintf(
                        'FILE_EXISTS: %s already exists. Pass "expectAbsent": false to overwrite deliberately.',
                        $path,
                    ),
                );
            }
            $source = $existed ? $this->readFile($path) : null;

            if ($source !== null) {
                $this->assertSha($spec, $path, hash('sha256', $source));
            } elseif (isset($spec['sha256'])) {
                throw new EditException(
                    'STALE_SOURCE: ' . $path . ' does not exist for the supplied sha256.',
                );
            }
            $parser = $this->parser($phpVersion);
            $roots = (new ContextParser($parser))->file($this->requiredString($spec, 'php'));
            $transaction = new FileTransaction($path, 'create', $source, $roots, $parser, $phpVersion, $existed);
            $this->resolveTargets($transaction, $spec, $this->requiredString($spec, 'php'));

            return $transaction;
        }
        [$source, $parser, $roots] = $this->parseFile($path, $phpVersion);
        $this->assertSha($spec, $path, hash('sha256', $source));
        $tokens = $parser->getTokens();
        $mutable = (new NodeTraverser(new CloningVisitor()))->traverse($roots);
        $transaction = new FileTransaction(
            $path,
            'edit',
            $source,
            $mutable,
            $parser,
            $phpVersion,
            true,
            $roots,
            $tokens,
        );
        $edits = $spec['edits'] ?? null;

        if (!is_array($edits) || $edits === []) {
            throw new EditException(sprintf('%s requires a non-empty edits array.', $path));
        }
        $this->choosePrinter($transaction, (string) $printer);
        $this->resolveTargets($transaction, $spec, $source);

        return $transaction;
    }

    private function choosePrinter(FileTransaction $transaction, string $requested): void
    {
        if ($requested !== 'auto') {
            $transaction->printer = $requested;

            return;
        }
        $config = RepositoryConfig::discover($transaction->path);
        $declared = RepositoryConfig::widthFor($transaction->path);

        if ($config->excludes($transaction->path)) {
            $transaction->printer = 'format-preserving';
            $transaction->warning = 'EXCLUDED: using format-preserving output; project formatter is excluded for this path.';

            return;
        }

        if ($config->canonical) {
            $transaction->printer = 'canonical';

            if ($declared['width'] === null) {
                $transaction->warning = sprintf(
                    'NO_DECLARED_WIDTH: using recorded width %d; declare max_line_length in .editorconfig.',
                    $declared['recorded'] ?? CanonicalPrinter::DEFAULT_WIDTH,
                );
            }

            return;
        }
        $transaction->printer = 'format-preserving';
        $transaction->warning = 'NOT_CANONICAL: using format-preserving output. Canonical normalization is optional.';
    }

    /**
     * Operations that belong to the file rather than to a node in it.
     *
     * An import is not attached to anything: `use Foo\Bar;` sits in the file's import section
     * and applies to every name below it. Making the caller name a target for it would be
     * asking for a coordinate the operation then ignores — and worse, `use` inside a class
     * body means something else entirely (a trait), so a class target would read as that.
     *
     * @var list<string>
     */
    public const FILE_SCOPED = ['add_use'];

    /**
     * What a caller that wrote the wrong document shape is told.
     *
     * It arrives instead of the documentation, not alongside it, so naming the missing key
     * is not enough: a bare array of edits is missing the two levels above that key as well.
     * The shape is spelled out, and the flag form beside it, because a single named edit
     * needs no document at all.
     */
    private const SHAPE_REQUIRED = 'apply input requires a non-empty files array: {"files":[{"path":"src/Foo.php","edits":[{"target":{"select":"method:Foo::bar"},"operation":"rename_variable","from":"nonce","to":"nonceValue"}]}]}. One edit against one named target needs no document at all: apply --file src/Foo.php --select method:Foo::bar --op rename_variable --from nonce --to nonceValue.';

    /**
     * The file's import section, as a location an edit can be resolved against.
     *
     * One namespace declaration owns it; without one the file's own statement list does. Two
     * namespaces in one file give two import sections and no answer to "the file's imports",
     * so that is refused rather than resolved to the first.
     *
     * @param list<Node\Stmt> $roots
     */
    private function fileScope(array $roots): NodeLocation
    {
        $namespaces = [];

        foreach ($roots as $index => $root) {
            if ($root instanceof Stmt\Namespace_) {
                $namespaces[$index] = $root;
            }
        }

        if (count($namespaces) > 1) {
            throw new EditException(
                sprintf(
                    'This file declares %d namespaces, so it has no single import section. Add the import with insert_into on the namespace you mean.',
                    count($namespaces),
                ),
            );
        }

        if ($namespaces !== []) {
            $index = array_key_first($namespaces);

            return new NodeLocation(
                $namespaces[$index],
                null,
                null,
                null,
                $index,
                0,
                'stmts[' . $index . ']',
            );
        }

        if ($roots === []) {
            throw new EditException(
                'An empty file has nowhere to put an import. Write its contents first.',
            );
        }

        return new NodeLocation($roots[0], null, null, null, 0, 0, 'stmts[0]');
    }

    private function resolveTargets(FileTransaction $transaction, array $spec, string $source): void
    {
        $edits = $spec['edits'] ?? [];

        if (!is_array($edits)) {
            throw new EditException(sprintf('%s: edits must be an array.', $transaction->path));
        }

        foreach ($edits as $index => $edit) {
            if (!is_array($edit)) {
                throw new EditException(sprintf('Edit %d must be an object.', $index));
            }
            $edit = $this->acceptSynonyms($edit);
            $operation = $this->requiredString($edit, 'operation');
            $target = $edit['target'] ?? null;

            if (in_array($operation, self::FILE_SCOPED, true)) {
                if ($target !== null) {
                    throw new EditException(
                        sprintf(
                            'Edit %d: %s writes a file-level import and takes no target. A `use` inside a class body imports a trait, which is add_member with php: "use SomeTrait;".',
                            $index,
                            $operation,
                        ),
                    );
                }
                $location = $this->fileScope($transaction->roots);
            } elseif (!is_array($target)) {
                throw new EditException(sprintf('Edit %d requires a target object.', $index));
            } elseif (isset($target['select'])) {
                if (isset($target['ref'])) {
                    throw new EditException('An edit names its target by ref or by select, not both.');
                }
                $location = $this->locator->resolveSelect($transaction->roots, (string) $target['select']);
                $this->assertKind($location, $target['kind'] ?? null);
            } elseif (isset($target['ref'])) {
                $location = $this->locator->resolveRef($transaction->roots, (string) $target['ref']);
                $this->assertKind($location, $target['kind'] ?? null);
            } else {
                $location = $this->locator->locate(
                    $transaction->roots,
                    $this->targetOffset($source, $target),
                    isset($target['kind']) ? (string) $target['kind'] : null,
                );
            }
            $this->assertOperationArguments($operation, $edit);
            $this->assertExpectations($location->node, $edit['expect'] ?? []);
            $transaction->resolved[] = ['edit' => $edit, 'location' => $location, 'index' => (int) $index];
        }
    }

    private function mutate(FileTransaction $transaction): void
    {
        if ($transaction->mode === 'delete') {
            return;
        }
        $snippets = new ContextParser($transaction->parser ?? $this->parser($transaction->phpVersion));

        foreach ($transaction->resolved as $entry) {
            if (!$this->locator->isAttached($transaction->roots, $entry['location']->node)) {
                throw new EditException(
                    sprintf(
                        '%s: edit %d was invalidated by an earlier edit in the same transaction.',
                        $transaction->path,
                        $entry['index'],
                    ),
                );
            }
            $this->lastEffect = [];
            $this->mutating = $transaction->path;
            $this->applyOperation(
                $entry['location'],
                $entry['edit'],
                $transaction->roots,
                $snippets,
            );

            if ($this->lastEffect !== []) {
                $transaction->effects[$entry['index']] = $this->lastEffect + ['operation' => (string) $entry['edit']['operation']];
            }
        }
    }

    private function render(FileTransaction $transaction): void
    {
        if ($transaction->mode === 'delete') {
            $transaction->changed = true;

            return;
        }

        try {
            $output = rtrim($this->print($transaction), "\r\n") . "\n";
            $this->parser($transaction->phpVersion)->parse($output);
        } catch (EditException $failure) {
            throw $failure;
        } catch (\Throwable $failure) {
            throw new EditException(
                sprintf(
                    'INVALID_RESULT: %s could not be printed and re-parsed after the edits: %s',
                    $transaction->path,
                    $failure->getMessage(),
                ),
            );
        }
        $transaction->lint = (new PhpLint())->check($output, $transaction->path, $transaction->phpVersion);
        $transaction->output = $output;
        $transaction->changed = $transaction->source !== $output;
        $transaction->changedLines = $transaction->source === null ? substr_count($output, "\n") : $this->countChangedLines($transaction->source, $output);
    }

    /**
     * Print the mutated tree with the printer this file is entitled to.
     *
     * Canonical printing is the intended mode: it gives one output per AST, so an edit to a
     * repository that already sits on that fixed point changes only the lines the edit
     * touches. On a repository that does not, it rewrites everything it disagrees with — 105
     * lines for a one-identifier rename in the case this was measured on. Format-preserving
     * printing is the fallback for exactly that situation, and it is never silent.
     */
    private function print(FileTransaction $transaction): string
    {
        $version = $transaction->phpVersion === null ? null : PhpVersion::fromString($transaction->phpVersion);
        $printer = new CanonicalPrinter($version, $this->widthFor($transaction));

        if ($transaction->printer === 'format-preserving' && $transaction->original !== null && $transaction->tokens !== null) {
            return $printer->printFormatPreserving(
                $transaction->roots,
                $transaction->original,
                $transaction->tokens,
            );
        }
        $transaction->printer = 'canonical';

        return $printer->prettyPrintFile($transaction->roots);
    }

    private function widthFor(FileTransaction $transaction): int
    {
        $declared = RepositoryConfig::widthFor($transaction->path);

        // The declaration wins over the recorded value. If a project raises max_line_length
        // and this kept using what the last normalisation ran at, `apply` and `format` would
        // print the same file at two different widths and fight each other forever.
        return $declared['width'] ?? $declared['recorded'] ?? CanonicalPrinter::DEFAULT_WIDTH;
    }

    /**
     * Lines this write changes on disk, as a diff would count them.
     *
     * Reported for information, never as a decision: after canonical printing the number
     * also contains everything the project's formatter will put back when it runs — blank
     * lines, operator alignment, the licence header — so on a healthy repository it is
     * expected to be larger than the edit. What it does answer honestly is the
     * format-preserving case, where it is the edit's real footprint, and it exposes a
     * silent fallback to full printing for a subtree that printer could not map.
     */
    private function countChangedLines(string $before, string $after): int
    {
        if ($before === $after) {
            return 0;
        }
        $a = explode("\n", $before);
        $b = explode("\n", $after);
        $head = 0;
        $lastA = count($a) - 1;
        $lastB = count($b) - 1;

        while ($head <= $lastA && $head <= $lastB && $a[$head] === $b[$head]) {
            ++$head;
        }

        while ($lastA >= $head && $lastB >= $head && $a[$lastA] === $b[$lastB]) {
            --$lastA;
            --$lastB;
        }
        $a = array_slice($a, $head, $lastA - $head + 1);
        $b = array_slice($b, $head, $lastB - $head + 1);

        if ($a === [] || $b === []) {
            return count($a) + count($b);
        }

        // A full LCS is quadratic and these are whole files; cap it and fall back to the
        // block size, which is what a reviewer sees anyway when the change is that large.
        if (count($a) * count($b) > 4000000) {
            return count($a) + count($b);
        }
        $lcs = $this->longestCommonSubsequence($a, $b);

        return count($a) - $lcs + (count($b) - $lcs);
    }

    /**
     * @param list<string> $a
     * @param list<string> $b
     */
    private function longestCommonSubsequence(array $a, array $b): int
    {
        $previous = array_fill(0, count($b) + 1, 0);

        foreach ($a as $lineA) {
            $current = [0];

            foreach ($b as $j => $lineB) {
                $current[$j + 1] = $lineA === $lineB ? $previous[$j] + 1 : max($previous[$j + 1], $current[$j]);
            }
            $previous = $current;
        }

        return $previous[count($b)];
    }

    private function commit(array $transactions, array $verification): void
    {
        foreach ($transactions as $transaction) {
            if ($transaction->changed) {
                $this->assertUnchangedOnDisk($transaction);
                $link = is_link($transaction->path) ? readlink($transaction->path) : null;

                if ($link !== $transaction->linkTarget) {
                    throw new EditException('CONCURRENT_CHANGE: symlink changed at ' . $transaction->path);
                }
            }
        }
        $done = [];

        try {
            foreach ($transactions as $transaction) {
                if (!$transaction->changed) {
                    continue;
                }
                $done[] = $transaction;

                if ($transaction->mode === 'delete') {
                    if (!@unlink($transaction->path)) {
                        throw new EditException('Cannot delete ' . $transaction->path);
                    }

                    continue;
                }
                $this->atomicWrite($transaction->path, (string) $transaction->output);
            }
            $this->runFormatter($transactions);
            $this->verifyResults = (new VerificationRunner())->run($verification);
        } catch (\Throwable $failure) {
            $restoreErrors = [];
            $restorer = new FileRestorer();

            foreach (array_reverse($done) as $transaction) {
                try {
                    $restorer->restore($transaction);
                } catch (\Throwable $restoreFailure) {
                    $restoreErrors[] = $transaction->path . ': ' . $restoreFailure->getMessage();
                }
            }
            $message = 'COMMIT_FAILED: ' . $failure->getMessage();
            $message .= $restoreErrors === [] ? ' All files were rolled back.' : ' Rollback incomplete for ' . implode('; ', $restoreErrors);

            throw new EditException($message);
        }
    }

    private function assertUnchangedOnDisk(FileTransaction $transaction): void
    {
        $exists = is_file($transaction->path);

        if ($transaction->source === null) {
            if ($exists) {
                throw new EditException(
                    sprintf(
                        'CONCURRENT_CHANGE: %s appeared while the transaction was being prepared.',
                        $transaction->path,
                    ),
                );
            }

            return;
        }

        if (!$exists) {
            throw new EditException(
                sprintf(
                    'CONCURRENT_CHANGE: %s disappeared while the transaction was being prepared.',
                    $transaction->path,
                ),
            );
        }

        if (!hash_equals(
            hash('sha256', $this->readFile($transaction->path)),
            (string) $transaction->beforeSha(),
        )) {
            throw new EditException(
                sprintf(
                    'CONCURRENT_CHANGE: %s changed while the transaction was being prepared; nothing was written.',
                    $transaction->path,
                ),
            );
        }
    }

    private function report(FileTransaction $transaction, bool $dryRun, bool $compact): array
    {
        return EditReport::file($transaction, $dryRun, $this->unifiedDiff($transaction), $compact);
    }

    private function applyOperation(
        NodeLocation $location,
        array $edit,
        array &$roots,
        ContextParser $snippets,
    ): void {
        $operation = $this->requiredString($edit, 'operation');

        $applied = $this->applyPrimitive($operation, $location, $edit, $roots, $snippets) || $this->applyComment($operation, $location, $edit) || $this->applyShorthand($operation, $location, $edit, $roots, $snippets) || $this->applySemantic($operation, $location, $edit, $roots, $snippets);

        if (!$applied) {
            throw new EditException(
                'Unsupported operation: ' . $operation . $this->nearestOperations($operation),
            );
        }
    }

    /**
     * The mutation algebra: every construct is reachable through these.
     *
     * @return bool true when the operation belonged to this group and was applied.
     */
    private function applyPrimitive(
        string $operation,
        NodeLocation $location,
        array $edit,
        array &$roots,
        ContextParser $snippets,
    ): bool {
        $node = $location->node;

        switch ($operation) {
            // ---- Primitives -------------------------------------------------------------
            case 'replace_node':
                $context = $this->context($edit, $location);
                $location->replace(
                    $snippets->parseOne($context, $this->requiredString($edit, 'php')),
                    $roots,
                );

                return true;
            case 'delete_node':
            case 'delete':
                $location->remove($roots);

                return true;
            case 'insert_into':
                $property = $this->requiredString($edit, 'property');
                $location->insertInto(
                    $property,
                    $snippets->parseFirst(
                        $this->contextsForProperty($edit, $location, $property),
                        $this->requiredString($edit, 'php'),
                    ),
                    $this->position($edit),
                );

                return true;
            case 'replace_child':
                $property = $this->requiredString($edit, 'property');
                $location->replaceChild(
                    $property,
                    $this->optionalIndex($edit),
                    $snippets->parseFirstOne(
                        $this->contextsForProperty($edit, $location, $property),
                        $this->requiredString($edit, 'php'),
                    ),
                );

                return true;
            case 'delete_child':
                $location->removeChild(
                    $this->requiredString($edit, 'property'),
                    $this->optionalIndex($edit),
                );

                return true;
            case 'move_node':
                $this->moveNode($location, $edit, $roots);

                return true;
            default:
                return false;
        }
    }

    /**
     * Comments and docblocks — the one area regular AST child nodes do not cover.
     *
     * @return bool true when the operation belonged to this group and was applied.
     */
    private function applyComment(string $operation, NodeLocation $location, array $edit): bool
    {
        $node = $location->node;

        switch ($operation) {
            // ---- Comments ---------------------------------------------------------------
            case 'set_doc_comment':
                $this->setDocComment($node, $this->requiredString($edit, 'value'));

                return true;
            case 'remove_doc_comment':
                $this->setDocComment($node, null);

                return true;
            default:
                return false;
        }
    }

    /**
     * Established shorthands over the primitives, kept for compactness and safety.
     *
     * @return bool true when the operation belonged to this group and was applied.
     */
    private function applyShorthand(
        string $operation,
        NodeLocation $location,
        array $edit,
        array &$roots,
        ContextParser $snippets,
    ): bool {
        $node = $location->node;

        switch ($operation) {
            case 'rename_method':
                $this->lastEffect = $this->renameMethod($location, $this->requiredString($edit, 'to'), $roots);

                return true;
            case 'rename_variable':
                if (!$node instanceof Stmt\ClassMethod && !$node instanceof Stmt\Function_ && !$node instanceof Expr\Closure && !$node instanceof Expr\ArrowFunction) {
                    throw new EditException(
                        'rename_variable targets the scope the variable lives in: a method, function, closure or arrow function.',
                    );
                }
                $this->lastEffect = [
                    'renamed' => $this->renameVariable(
                        $node,
                        $this->requiredString($edit, 'from'),
                        $this->requiredString($edit, 'to'),
                        $roots,
                    ),
                    'remainingInFile' => $this->remainingVariables($roots, $this->requiredString($edit, 'from')),
                ];

                return true;
                // ---- Convenience shorthands over the primitives ------------------------------
            case 'set_name':
                $this->refuseDeclarationOnlyRename($location, $edit, $roots);
                $this->setName($location, $this->requiredString($edit, 'value'), $roots);

                return true;
            case 'set_string':
                if (!$node instanceof String_) {
                    throw new EditException('set_string requires a Scalar_String target.');
                }
                $node->value = $this->requiredString($edit, 'value');
                $attributes = $node->getAttributes();
                unset($attributes['rawValue']);
                $node->setAttributes($attributes);

                return true;
            case 'replace_expression':
                if (isset($edit['match'])) {
                    $this->replaceMatches($location, $edit, $snippets, 'expr');

                    return true;
                }

                if (!$node instanceof Expr) {
                    throw new EditException(
                        'replace_expression requires an Expr target. ' . $this->scopedForm('replace_expression', $edit, $location),
                    );
                }
                $location->replace(
                    $snippets->parseOne('expr', $this->requiredString($edit, 'php')),
                    $roots,
                );

                return true;
            case 'replace_statement':
                if (isset($edit['match'])) {
                    $this->replaceMatches($location, $edit, $snippets, 'stmt');

                    return true;
                }

                // A method, property or class is a Stmt to the parser, so the class check
                // alone let replace_statement swap a declaration for a statement. The file
                // then failed only at the reparse gate, with a syntax error on a line the
                // caller never wrote — eight times across sixteen measured sessions.
                if (!$node instanceof Stmt || $this->isDeclaration($node)) {
                    throw new EditException(
                        'replace_statement requires a Stmt target. ' . $this->scopedForm('replace_statement', $edit, $location),
                    );
                }
                $location->replace(
                    $snippets->parseOne('stmt', $this->requiredString($edit, 'php')),
                    $roots,
                );

                return true;
            case 'insert_before':
            case 'insert_after':
                $context = $this->context($edit, $location, 'stmt');
                $nodes = $snippets->parse($context, $this->requiredString($edit, 'php'));

                if ($operation === 'insert_before') {
                    $location->insertBefore($nodes, $roots);
                } else {
                    $location->insertAfter($nodes, $roots);
                }

                return true;
            case 'replace_argument':
            case 'add_argument':
            case 'remove_argument':
                if (!$node instanceof CallLike) {
                    throw new EditException($operation . ' requires an Expr_*Call target.');
                }
                $this->editArgument($node, $edit, $snippets, $operation);

                return true;
            default:
                return false;
        }
    }

    /**
     * Semantic shorthands that name a language concept rather than an AST slot.
     *
     * @return bool true when the operation belonged to this group and was applied.
     */
    private function applySemantic(
        string $operation,
        NodeLocation $location,
        array $edit,
        array &$roots,
        ContextParser $snippets,
    ): bool {
        $node = $location->node;

        switch ($operation) {
            // ---- Semantic convenience ----------------------------------------------------
            case 'add_member':
                // A member as target means "next to this one": measured, a caller selected the
                // method it wanted the new one beside and met a refusal for not naming the class.
                if (!$node instanceof Stmt\ClassLike && $location->parent instanceof Stmt\ClassLike && $location->property === 'stmts') {
                    if (isset($edit['position'])) {
                        throw new EditException(
                            'add_member with a member as its target puts the new member directly after that member, so position has nothing to say. For start, end or an index, target the class.',
                        );
                    }
                    $location->insertAfter(
                        $snippets->parseFirst(
                            $this->memberContexts($location->parent),
                            $this->requiredString($edit, 'php'),
                        ),
                        $roots,
                    );

                    return true;
                }
                $this->assertType(
                    $node,
                    Stmt\ClassLike::class,
                    'add_member requires a class-like target, or a member to put the new one after.',
                );
                $location->insertInto(
                    'stmts',
                    $snippets->parseFirst(
                        $this->memberContexts($node),
                        $this->requiredString($edit, 'php'),
                    ),
                    $this->position($edit, 'end'),
                );

                return true;
            case 'add_parameter':
                if (!$node instanceof Node\FunctionLike) {
                    throw new EditException('add_parameter requires a function-like target.');
                }
                $location->insertInto(
                    'params',
                    $snippets->parse('param', $this->requiredString($edit, 'php')),
                    $this->position($edit, 'end'),
                );

                return true;
            case 'add_attribute':
                $location->insertInto(
                    'attrGroups',
                    $snippets->parse('attribute', $this->requiredString($edit, 'php')),
                    $this->position($edit, 'end'),
                );

                return true;
            case 'set_return_type':
                $location->replaceChild(
                    'returnType',
                    null,
                    $snippets->parseOne('type', $this->requiredString($edit, 'php')),
                );

                return true;
            case 'set_type':
                $location->replaceChild(
                    'type',
                    null,
                    $snippets->parseOne('type', $this->requiredString($edit, 'php')),
                );

                return true;
            case 'set_visibility':
                $this->setVisibility($node, $this->requiredString($edit, 'value'));

                return true;
            case 'add_implements':
                $this->assertType(
                    $node,
                    Stmt\Class_::class,
                    'add_implements requires a Stmt_Class target.',
                );
                $location->insertInto(
                    'implements',
                    [$snippets->parseOne('type', $this->requiredString($edit, 'php'))],
                    $this->position($edit, 'end'),
                );

                return true;
            case 'add_use':
                $this->addUse($location, $roots, $edit);

                return true;
            case 'set_extends':
                $location->replaceChild(
                    'extends',
                    $this->optionalIndex($edit),
                    $snippets->parseOne('type', $this->requiredString($edit, 'php')),
                );

                return true;
            default:
                return false;
        }
    }

    /**
     * Add a class import to the file, once.
     *
     * Idempotence is the whole point: an agent that has to find out whether the import is
     * already there pays for a read, a grep and a decision before it may write, and gets it
     * wrong when the class is imported inside a group use. So the operation answers the
     * question itself and reports what it found — `alreadyPresent` with the local name the
     * class is available under, which is what the caller actually needed to know.
     *
     * The two ways an import can be impossible are both refused rather than papered over:
     * importing a class that is already there under a different alias would leave the caller
     * writing a short name the file does not bind, and importing a different class under a
     * name that is taken would change what existing code means.
     *
     * @param list<Node\Stmt>     $roots
     * @param array<string, mixed> $edit
     */
    private function addUse(NodeLocation $scope, array &$roots, array $edit): void
    {
        $name = ltrim(trim($this->requiredString($edit, 'value')), '\\');

        if ($name === '') {
            throw new EditException(
                'add_use needs the class to import in "value", for example "Vendor\Package\Thing".',
            );
        }
        $alias = isset($edit['alias']) ? trim((string) $edit['alias']) : '';
        $short = str_contains($name, '\\') ? substr($name, (int) strrpos($name, '\\') + 1) : $name;
        $local = $alias !== '' ? $alias : $short;
        $namespace = $scope->node instanceof Stmt\Namespace_ ? $scope->node : null;
        $statements = $namespace instanceof Stmt\Namespace_ ? $namespace->stmts : $roots;

        if ($this->importIsSettled($this->importsIn($statements), $name, $local)) {
            return;
        }
        // Constructed, not parsed: it carries no line attributes for the printer to read as
        // paragraphing, so there is nothing to clear.
        $import = new Stmt\Use_([new UseItem(new Name($name), $alias !== '' ? $alias : null)]);
        array_splice($statements, $this->importPosition($statements), 0, [$import]);

        if ($namespace instanceof Stmt\Namespace_) {
            $namespace->stmts = $statements;
        } else {
            $roots = $statements;
        }
        $this->lastEffect = ['imported' => $name, 'as' => $local, 'alreadyPresent' => false];
    }

    /**
     * Whether the file already settles this import, one way or another.
     *
     * Returns true when the class is there under the name asked for — the caller has nothing
     * left to do, and the effect says so. The two ways an import can be impossible throw
     * instead: a class present under a different alias would leave the caller writing a short
     * name the file does not bind, and a name already bound to another class would change
     * what existing code means. Class and alias names are matched the way PHP resolves them,
     * without regard to case.
     *
     * @param list<array{0: string, 1: string}> $imports
     */
    private function importIsSettled(array $imports, string $name, string $local): bool
    {
        foreach ($imports as [$importedName, $importedLocal]) {
            $sameClass = strcasecmp($importedName, $name) === 0;
            $sameLocal = strcasecmp($importedLocal, $local) === 0;

            if ($sameClass && $sameLocal) {
                $this->lastEffect = ['imported' => $name, 'as' => $importedLocal, 'alreadyPresent' => true];

                return true;
            }

            if ($sameClass) {
                throw new EditException(
                    sprintf(
                        '%s is already imported as %s. Use that name, or pass alias to import it under another one.',
                        $name,
                        $importedLocal,
                    ),
                );
            }

            if ($sameLocal) {
                throw new EditException(
                    sprintf(
                        'The name %s is already bound to %s in this file. Pass alias to import %s under a different name.',
                        $local,
                        $importedName,
                        $name,
                    ),
                );
            }
        }

        return false;
    }

    /**
     * Every class this statement list imports, as [fully qualified name, local name].
     *
     * Group uses are read too. `use Vendor\Ext\{Alpha, Beta};` imports Beta as surely as a
     * line of its own does, and a check that only reads `Stmt\Use_` would add a second import
     * of a class the file already has.
     *
     * @param  list<Node\Stmt> $statements
     * @return list<array{0: string, 1: string}>
     */
    private function importsIn(array $statements): array
    {
        $imports = [];

        foreach ($statements as $statement) {
            if (!$statement instanceof Stmt\Use_ && !$statement instanceof Stmt\GroupUse) {
                continue;
            }
            // The type sits on whichever of the two nodes knows it: a plain `use X;` carries it
            // on the statement and leaves the item unknown, a group use the other way round, and
            // a mixed group (`use A\{B, function c}`) per item. Reading only one of them missed
            // every group use, which is exactly the case a caller cannot see by grepping.
            $prefix = $statement instanceof Stmt\GroupUse ? $statement->prefix->toString() . '\\' : '';

            foreach ($statement->uses as $item) {
                $type = $statement->type === Stmt\Use_::TYPE_UNKNOWN ? $item->type : $statement->type;

                if ($type !== Stmt\Use_::TYPE_NORMAL) {
                    continue;
                }
                $imports[] = [$prefix . $item->name->toString(), $item->getAlias()->toString()];
            }
        }

        return $imports;
    }

    /**
     * Where the next import goes: after the last one, or ahead of everything a file may not
     * have imports in front of. `declare()` has to stay the first statement.
     *
     * No sorting. Where a formatter is declared it owns the order (php-cs-fixer's
     * `ordered_imports` and its equivalents), and where none is, an unsorted import list is
     * still valid PHP — reordering somebody's imports is a change they did not ask for.
     *
     * @param list<Node\Stmt> $statements
     */
    private function importPosition(array $statements): int
    {
        $position = 0;

        foreach ($statements as $index => $statement) {
            if ($statement instanceof Stmt\Use_ || $statement instanceof Stmt\GroupUse || $statement instanceof Stmt\Declare_) {
                $position = $index + 1;
            }
        }

        return $position;
    }

    private function moveNode(NodeLocation $location, array $edit, array &$roots): void
    {
        $into = $edit['into'] ?? null;

        if (!is_array($into) || !isset($into['ref']) || !isset($into['property'])) {
            throw new EditException('move_node requires into.ref and into.property.');
        }
        $node = $location->node;
        $targetLocation = $this->locator->resolveRef($roots, (string) $into['ref']);

        if ($this->locator->contains($node, $targetLocation->node)) {
            throw new EditException('move_node cannot move a node into itself or into its own subtree.');
        }
        $location->remove($roots);
        $targetLocation->insertInto(
            (string) $into['property'],
            [$node],
            $this->position(['position' => $into['position'] ?? 'end'], 'end'),
        );
    }

    private function setDocComment(Node $node, ?string $text): void
    {
        $attributes = $node->getAttributes();
        $others = array_values(
            array_filter(
                $node->getComments(),
                static fn (\PhpParser\Comment $comment): bool => !$comment instanceof Doc,
            ),
        );

        if ($text === null) {
            // Only the docblock goes; line and block comments on the same node are not ours
            // to delete.
            if ($others === []) {
                unset($attributes['comments']);
            } else {
                $attributes['comments'] = $others;
            }
            $node->setAttributes($attributes);

            return;
        }
        $text = trim($text);

        if (!str_starts_with($text, '/**')) {
            $lines = preg_split('/\R/', $text) ?: [];
            $text = "/**\n" . implode(
                "\n",
                array_map(static fn (string $line): string => rtrim(' * ' . $line), $lines),
            ) . "\n */";
        }
        $others[] = new Doc($text);
        $attributes['comments'] = $others;
        $node->setAttributes($attributes);
    }

    private function setVisibility(Node $node, string $visibility): void
    {
        $map = [
            'public' => Modifiers::PUBLIC,
            'protected' => Modifiers::PROTECTED,
            'private' => Modifiers::PRIVATE,
        ];

        if (!isset($map[$visibility])) {
            throw new EditException('set_visibility requires public, protected or private.');
        }

        if (!property_exists($node, 'flags')) {
            throw new EditException('set_visibility target has no modifier flags.');
        }
        $node->flags = $node->flags & ~Modifiers::VISIBILITY_MASK | $map[$visibility];
    }

    /** Determine the parse context for a snippet, honouring an explicit parseAs. */
    private function context(array $edit, NodeLocation $location, ?string $fallback = null): string
    {
        if (isset($edit['parseAs'])) {
            return (string) $edit['parseAs'];
        }
        $inferred = $this->inferContext($location);

        if ($inferred !== null) {
            return $inferred;
        }

        if ($fallback !== null) {
            return $fallback;
        }

        throw new EditException(
            sprintf(
                'Cannot infer a parse context for %s; pass "parseAs" explicitly.',
                $location->node->getType(),
            ),
        );
    }

    /**
     * Which parse contexts may produce a child of `$property` on this node?
     *
     * Several sub node names are shared by nodes that hold entirely different children:
     * `stmts` is a member list on a class but a statement list on a function, `uses` is a
     * closure binding on a Closure but an imported name on a use statement, `vars` is a
     * static variable on `static` but an expression on `unset`. Resolving the name alone
     * would answer confidently and wrongly, so the node decides, and where the node still
     * admits more than one shape the parser does.
     *
     * @return non-empty-list<string>
     */
    private function contextsForProperty(
        array $edit,
        NodeLocation $location,
        string $property,
    ): array {
        if (isset($edit['parseAs'])) {
            return [(string) $edit['parseAs']];
        }
        $node = $location->node;
        $context = match ($property) {
            'stmts' => $node instanceof Stmt\ClassLike ? $this->memberContexts($node) : ['stmt'],
            'uses' => $node instanceof Expr\Closure ? ['closure_use'] : ['use'],
            'vars' => $node instanceof Stmt\Static_ ? ['static_var'] : ['expr'],
            default => self::PROPERTY_CONTEXTS[$property] ?? null,
        };

        if ($context === null) {
            throw new EditException(
                sprintf(
                    'Cannot infer a parse context for property "%s" of %s; pass "parseAs" explicitly.',
                    $property,
                    $node->getType(),
                ),
            );
        }

        return is_array($context) ? $context : [$context];
    }

    /**
     * A class-like body accepts different members depending on the host construct, and an
     * enum body accepts methods and constants as well as cases. Rather than guessing from
     * the snippet text, offer the plausible hosts in order and let the parser decide.
     *
     * @return non-empty-list<string>
     */
    private function memberContexts(Node $node): array
    {
        return $node instanceof Stmt\Enum_ ? ['enum_case', 'member'] : ['member', 'enum_case'];
    }

    /**
     * Property name → synthetic parse context, for the names that mean the same thing on
     * every node that has them. The ambiguous ones — `stmts`, `uses`, `vars` — are resolved
     * against the node in contextsForProperty() and deliberately absent here.
     */
    private const PROPERTY_CONTEXTS = [
        'params' => 'param',
        'args' => 'arg',
        'items' => 'array_item',
        'arms' => 'match_arm',
        'attrGroups' => 'attribute',
        'catches' => 'catch',
        'consts' => 'const',
        'props' => 'property_item',
        'type' => 'type',
        'returnType' => 'type',
        'implements' => 'type',
        'extends' => 'type',
        'default' => 'expr',
        'expr' => 'expr',
        'cond' => 'expr',
        'value' => 'expr',
        'var' => 'expr',
    ];

    private function inferContext(NodeLocation $location): ?string
    {
        $node = $location->node;

        return match (true) {
            $node instanceof Param => 'param',
            $node instanceof Arg => 'arg',
            $node instanceof ArrayItem => 'array_item',
            $node instanceof MatchArm => 'match_arm',
            $node instanceof AttributeGroup => 'attribute',
            $node instanceof Attribute => 'attribute',
            $node instanceof ClosureUse => 'closure_use',
            $node instanceof Const_ => 'const',
            $node instanceof UseItem => 'use',
            $node instanceof PropertyItem => 'property_item',
            $node instanceof StaticVar => 'static_var',
            $node instanceof Stmt\Catch_ => 'catch',
            $node instanceof ComplexType => 'type',
            ($node instanceof Identifier || $node instanceof Name) && in_array($location->property, ['type', 'returnType', 'implements', 'extends'], true) => 'type',
            $node instanceof Expr => 'expr',
            $node instanceof Stmt\ClassMethod, $node instanceof Stmt\Property, $node instanceof Stmt\ClassConst, $node instanceof Stmt\TraitUse => 'member',
            $node instanceof Stmt\EnumCase => 'enum_case',
            $node instanceof Stmt => 'stmt',
            default => null,
        };
    }

    /** @return int|'start'|'end' */
    private function position(array $edit, string $default = 'end'): int|string
    {
        $position = $edit['position'] ?? $default;

        if (is_int($position) || in_array($position, ['start', 'end'], true)) {
            return $position;
        }

        if (is_string($position) && filter_var($position, FILTER_VALIDATE_INT) !== false) {
            return (int) $position;
        }

        throw new EditException(
            sprintf(
                'position must be "start", "end" or a zero-based index; the default is "end". Got: %s',
                is_scalar($position) ? var_export($position, true) : get_debug_type($position),
            ),
        );
    }

    private function optionalIndex(array $edit): ?int
    {
        if (!array_key_exists('index', $edit) || $edit['index'] === null) {
            return null;
        }
        $index = $edit['index'];

        if (!is_int($index) || $index < 0) {
            throw new EditException('index must be a non-negative integer.');
        }

        return $index;
    }

    private function assertType(Node $node, string $class, string $message): void
    {
        if (!$node instanceof $class) {
            throw new EditException($message . ' Got ' . $node->getType() . '.');
        }
    }

    /**
     * `set_name` on a method declaration renames the declaration and nothing that calls it.
     *
     * Measured: a gated run asked for exactly that on a public method with 29 callers, the
     * project's analysis failed on every caller, and the run then renamed them one by one in
     * 51 tool calls, the last through `sed` around the hook. `rename_method` does all of it
     * in one edit. Where the declaration alone is meant, `declarationOnly` says so; the
     * project-wide rename marks its own declaration edits the same way. A method nothing
     * calls loses nothing, so it is renamed as asked.
     *
     * @param array<string, mixed> $edit
     * @param list<Stmt> $roots
     */
    private function refuseDeclarationOnlyRename(
        NodeLocation $location,
        array $edit,
        array $roots,
    ): void {
        $node = $location->node;
        $method = match (true) {
            $node instanceof Stmt\ClassMethod => $node,
            $node instanceof Identifier && $location->parent instanceof Stmt\ClassMethod && $location->property === 'name' => $location->parent,
            default => null,
        };

        if ($method === null || ($edit['declarationOnly'] ?? false) === true) {
            return;
        }
        [$calls, $files] = $this->callsByName($method->name->toString());

        if ($calls === 0) {
            return;
        }
        $owner = null;

        foreach ($this->locator->ancestry($roots, $method->getStartFilePos()) as $around) {
            if ($around->node instanceof Stmt\ClassLike && $around->node->name !== null) {
                $owner = $around->node->name->toString();

                break;
            }
        }
        $select = 'method:' . ($owner === null ? '' : $owner . '::') . $method->name->toString();

        throw new EditException(
            sprintf(
                'set_name on %s renames the declaration only; %d call(s) in %d file(s) would keep the old name. rename_method renames the declaration and its callers across the project: {"target": {"select": "%s"}, "operation": "rename_method", "to": %s}. If the declaration alone is meant, add "declarationOnly": true.',
                $select,
                $calls,
                $files,
                $select,
                json_encode($this->requiredString($edit, 'value')),
            ),
        );
    }

    /** The file an edit is being applied to, for checks that look beyond its tree. */
    private string $mutating = '';

    /**
     * Calls of a method name — `->name()`, `?->name()`, `::name()` — in the project's PHP
     * files, or in the edited file alone where there is no project to list. Names, not
     * types: it only decides whether a declaration-only rename would leave anything behind.
     * A file is parsed only when its text names the method; a comment or string that does
     * is not a call. A file that does not parse counts its textual hits, since they may be.
     *
     * @return array{0: int, 1: int} calls, and the files they are in
     */
    private function callsByName(string $name): array
    {
        try {
            $files = ProjectIndex::for($this->mutating)->phpFiles();
        } catch (EditException) {
            $files = [];
        }
        $pattern = '/(?:->|::)\s*' . preg_quote($name, '/') . '\s*\(/i';
        $calls = 0;
        $holding = 0;

        foreach ($files === [] ? [$this->mutating] : $files as $file) {
            $source = $this->readFile($file);
            $found = preg_match_all($pattern, $source);

            if ($found > 0) {
                $found = $this->callNodes($source, $name) ?? $found;
            }

            if ($found > 0) {
                $calls += $found;
                ++$holding;
            }
        }

        return [$calls, $holding];
    }

    /** Method and static calls of `$name` in `$source`, or null when it does not parse. */
    private function callNodes(string $source, string $name): ?int
    {
        try {
            $roots = $this->parser(null)->parse($source) ?? [];
        } catch (\PhpParser\Error) {
            return null;
        }

        return count(
            (new NodeFinder())->find(
                $roots,
                static fn (
                    Node $node,
                ): bool => ($node instanceof Expr\MethodCall || $node instanceof Expr\NullsafeMethodCall || $node instanceof Expr\StaticCall) && $node->name instanceof Identifier && strcasecmp($node->name->toString(), $name) === 0,
            ),
        );
    }

    private function setName(NodeLocation $location, string $value, array &$roots): void
    {
        $node = $location->node;

        if ($node instanceof VarLikeIdentifier) {
            $location->replace(new VarLikeIdentifier($value, $node->getAttributes()), $roots);

            return;
        }

        if ($node instanceof Identifier) {
            $location->replace(new Identifier($value, $node->getAttributes()), $roots);

            return;
        }

        if ($node instanceof Name) {
            $class = $node::class;
            $location->replace(new $class($value, $node->getAttributes()), $roots);

            return;
        }

        if ($node instanceof Variable && is_string($node->name)) {
            $node->name = $value;

            return;
        }

        if (!property_exists($node, 'name')) {
            throw new EditException('set_name target has no name property.');
        }
        $current = $node->name;

        if ($current instanceof VarLikeIdentifier) {
            $node->name = new VarLikeIdentifier($value, $current->getAttributes());

            return;
        }

        if ($current instanceof Identifier) {
            $node->name = new Identifier($value, $current->getAttributes());

            return;
        }

        if ($current instanceof Name) {
            $class = $current::class;
            $node->name = new $class($value, $current->getAttributes());

            return;
        }

        if (is_string($current)) {
            $node->name = $value;

            return;
        }

        throw new EditException('set_name cannot replace a dynamic name expression.');
    }

    private function editArgument(
        CallLike $call,
        array $edit,
        ContextParser $snippets,
        string $operation,
    ): void {
        if ($call->isFirstClassCallable()) {
            throw new EditException($operation . ' is not valid for first-class callable syntax.');
        }

        if (!property_exists($call, 'args')) {
            throw new EditException($operation . ' target does not expose an argument list.');
        }
        $index = $edit['index'] ?? null;

        if (!is_int($index) || $index < 0) {
            throw new EditException($operation . ' requires a non-negative integer index.');
        }
        $args = $call->args;

        if ($operation === 'remove_argument') {
            if (!array_key_exists($index, $args) || !$args[$index] instanceof Arg) {
                throw new EditException('Argument index out of range.');
            }
            array_splice($args, $index, 1);
            $call->args = $args;

            return;
        }
        $php = $this->requiredString($edit, 'php');

        if ($operation === 'replace_argument') {
            if (!array_key_exists($index, $args) || !$args[$index] instanceof Arg) {
                throw new EditException('Argument index out of range.');
            }
            $args[$index]->value = $snippets->parseOne('expr', $php);
        } else {
            if ($index > count($args)) {
                throw new EditException('Argument insertion index out of range.');
            }
            $node = $snippets->parseOne(isset($edit['parseAs']) ? (string) $edit['parseAs'] : 'expr', $php);
            array_splice($args, $index, 0, [$node instanceof Arg ? $node : new Arg($node)]);
        }
        $call->args = $args;
    }

    private function assertExpectations(Node $node, mixed $expect): void
    {
        if ($expect === null || $expect === []) {
            return;
        }

        if (!is_array($expect)) {
            throw new EditException('expect must be an object.');
        }

        if (isset($expect['type']) && $node->getType() !== (string) $expect['type']) {
            throw new EditException(
                sprintf('Expected node type %s, got %s.', $expect['type'], $node->getType()),
            );
        }

        if (array_key_exists('name', $expect)) {
            $actual = $this->nodeName($node);

            if ($actual !== (string) $expect['name']) {
                throw new EditException(
                    sprintf('Expected node name %s, got %s.', $expect['name'], $actual ?? '<none>'),
                );
            }
        }

        if (array_key_exists('value', $expect)) {
            $actual = $this->nodeValue($node);

            if ($actual !== (string) $expect['value']) {
                throw new EditException(
                    sprintf(
                        'Expected node value %s, got %s.',
                        $expect['value'],
                        $actual ?? '<none>',
                    ),
                );
            }
        }
    }

    private function nodeName(Node $node): ?string
    {
        if ($node instanceof Identifier || $node instanceof VarLikeIdentifier || $node instanceof Name) {
            return (string) $node;
        }

        if ($node instanceof Variable && is_string($node->name)) {
            return $node->name;
        }

        if (property_exists($node, 'name')) {
            $name = $node->name;

            if ($name instanceof Identifier || $name instanceof VarLikeIdentifier || $name instanceof Name) {
                return (string) $name;
            }

            if (is_string($name)) {
                return $name;
            }
        }

        return null;
    }

    private function nodeValue(Node $node): ?string
    {
        if ($node instanceof String_) {
            return $node->value;
        }

        return $this->nodeName($node);
    }

    private function describe(NodeLocation $location, string $source): array
    {
        $node = $location->node;
        $start = $location->start();
        $end = $location->end();
        $code = $this->excerpt(substr($source, $start, $end - $start + 1));

        return array_filter(
            [
                'type' => $node->getType(),
                'class' => $node::class,
                'ref' => $location->path,
                'property' => $location->property,
                'index' => $location->index,
                'slots' => $node->getSubNodeNames(),
                'start' => $start,
                'end' => $end,
                'startLine' => $node->getStartLine(),
                'endLine' => $node->getEndLine(),
                'name' => $this->nodeName($node),
                'value' => $node instanceof String_ ? $node->value : null,
                'code' => $code,
            ],
            static fn (mixed $value): bool => $value !== null,
        );
    }

    /**
     * A short, JSON-safe excerpt of the node's source.
     *
     * Cutting at a fixed byte count lands in the middle of a multi-byte character often
     * enough to matter — and the CLI encodes its answer with JSON_THROW_ON_ERROR, so the
     * broken sequence would take down `inspect` on any file with umlauts in the wrong place.
     */
    private function excerpt(string $code, int $limit = 240): string
    {
        if (strlen($code) > $limit) {
            $code = substr($code, 0, $limit - 3);

            // Drop a trailing incomplete UTF-8 sequence. preg's /u check needs no extension
            // beyond PCRE, which ext-mbstring would have added to the package requirements.
            while ($code !== '' && preg_match('//u', $code) !== 1) {
                $code = substr($code, 0, -1);
            }
            $code .= '...';
        }

        return $code;
    }

    /** @return array{0:string,1:Parser,2:list<Stmt>} */
    private function parseFile(string $path, ?string $phpVersion): array
    {
        if (!is_file($path)) {
            throw new EditException('File not found: ' . $path);
        }
        $source = $this->readFile($path);
        $parser = $this->parser($phpVersion);
        $roots = $parser->parse($source);

        if ($roots === null) {
            $roots = [];
        }

        return [$source, $parser, $roots];
    }

    /**
     * Identity of a path, for the duplicate guard.
     *
     * Two spellings of one file must not become two transactions: both would resolve their
     * targets against the same pristine source and the second write would silently discard
     * the first one's edits.
     */
    private function canonicalPath(string $path): string
    {
        $real = realpath($path);

        if ($real !== false) {
            return $real;
        }
        // realpath() fails for every ancestor that does not exist yet, so collapse the path
        // textually first and then resolve the deepest ancestor that does exist. Two creates
        // under the same missing directory must still collide, however they were spelled.
        $collapsed = $this->collapse($path);
        $directory = dirname($collapsed);
        $suffix = [basename($collapsed)];

        while (($resolved = realpath($directory)) === false) {
            $parent = dirname($directory);

            if ($parent === $directory) {
                return $collapsed;
            }
            array_unshift($suffix, basename($directory));
            $directory = $parent;
        }

        return $resolved . DIRECTORY_SEPARATOR . implode(DIRECTORY_SEPARATOR, $suffix);
    }

    /**
     * Resolve `.` and `..` textually.
     *
     * Only ever applied to a path that does not exist yet, where there is no symlink for the
     * lexical answer to disagree with.
     */
    private function collapse(string $path): string
    {
        $absolute = str_starts_with($path, DIRECTORY_SEPARATOR);
        $segments = [];

        foreach (explode(DIRECTORY_SEPARATOR, $path) as $segment) {
            if ($segment === '' || $segment === '.') {
                continue;
            }

            if ($segment === '..' && $segments !== [] && end($segments) !== '..') {
                array_pop($segments);

                continue;
            }
            $segments[] = $segment;
        }

        return ($absolute ? DIRECTORY_SEPARATOR : '') . implode(DIRECTORY_SEPARATOR, $segments);
    }

    private function readFile(string $path): string
    {
        $source = file_get_contents($path);

        if ($source === false) {
            throw new EditException('Cannot read file: ' . $path);
        }

        return $source;
    }

    private function assertSha(array $spec, string $path, string $actual): void
    {
        if (isset($spec['sha256']) && !hash_equals((string) $spec['sha256'], $actual)) {
            throw new EditException(sprintf('STALE_SOURCE: %s no longer matches expected sha256.', $path));
        }
    }

    private function assertPhpVersion(string $phpVersion): string
    {
        try {
            PhpVersion::fromString($phpVersion);
        } catch (\Throwable $failure) {
            throw new EditException(
                sprintf(
                    'phpVersion "%s" is not a PHP version; use a "major.minor" string such as "8.4". Newest supported: %s.',
                    $phpVersion,
                    $this->versionLabel(PhpVersion::getNewestSupported()),
                ),
            );
        }

        return $phpVersion;
    }

    private function versionLabel(PhpVersion $version): string
    {
        return intdiv($version->id, 10000) . '.' . intdiv($version->id, 100) % 100;
    }

    private function parser(?string $phpVersion): Parser
    {
        $factory = new ParserFactory();

        if ($phpVersion !== null) {
            return $factory->createForVersion(PhpVersion::fromString($phpVersion));
        }

        return $factory->createForHostVersion();
    }

    private function targetOffset(string $source, array $target): int
    {
        if (isset($target['offset'])) {
            $offset = $target['offset'];

            if (!is_int($offset) || $offset < 0 || $offset >= strlen($source)) {
                throw new EditException('target.offset must be a valid zero-based byte offset.');
            }

            return $offset;
        }
        $line = $target['line'] ?? null;
        $column = $target['column'] ?? null;

        if (!is_int($line) || $line < 1 || !is_int($column) || $column < 1) {
            throw new EditException('Target requires ref, offset, or 1-based integer line and column.');
        }
        $currentLine = 1;
        $lineStart = 0;
        $length = strlen($source);

        for ($i = 0; $i < $length && $currentLine < $line; ++$i) {
            if ($source[$i] === "\n") {
                ++$currentLine;
                $lineStart = $i + 1;
            }
        }

        if ($currentLine !== $line) {
            throw new EditException('Target line is outside the file.');
        }
        $lineEnd = strpos($source, "\n", $lineStart);

        if ($lineEnd === false) {
            $lineEnd = $length;
        }
        $offset = $lineStart + $column - 1;

        if ($offset < $lineStart || $offset >= $lineEnd) {
            throw new EditException('Target column is outside the line.');
        }

        return $offset;
    }

    private function atomicWrite(string $path, string $contents): void
    {
        (new AtomicWriter())->write($path, $contents);
    }

    private function requiredString(array $data, string $key): string
    {
        $value = $data[$key] ?? null;

        if (!is_string($value) || $value === '') {
            throw new EditException($key . ' must be a non-empty string.');
        }

        return $value;
    }

    /**
     * Run the formatter the project declared, on the files this write produced.
     *
     * The fixed point belongs to the printer and the formatter together, so a write that
     * stops after printing leaves a shape nobody wants: adding one 9-line method to a
     * canonical TYPO3 extension reported 34 changed lines, the remainder trailing commas and
     * `declare` spacing that only the formatter restores. Running it here makes the write one
     * step for whoever calls this, and makes `changedLines` describe the file that survives.
     *
     * Only the files this write produced, never the tree: formatting everything would put
     * unrelated files into the diff of whatever change happened to be made. Files printed
     * format-preserving are left out too — the project either excluded them or has not
     * declared itself canonical, and in both cases the formatter is not ours to run.
     *
     * @param list<FileTransaction> $transactions
     */
    private function runFormatter(array $transactions): void
    {
        /** @var array<string, array{formatter: list<string>, transactions: list<FileTransaction>}> $groups */
        $groups = [];

        foreach ($transactions as $transaction) {
            if (!$transaction->changed || $transaction->mode === 'delete' || $transaction->printer !== 'canonical') {
                continue;
            }
            $config = RepositoryConfig::discover($transaction->path);

            if ($config->formatter === null || $config->path === null) {
                continue;
            }

            if ($config->excludes($transaction->path)) {
                // A file being created cannot be printed format-preserving — there is nothing to
                // preserve — so the printer is no proxy for the exclusion here. Ask the declaration.
                continue;
            }
            $root = \dirname($config->path);
            $groups[$root] ??= ['formatter' => $config->formatter, 'transactions' => []];
            $groups[$root]['transactions'][] = $transaction;
        }

        foreach ($groups as $root => $group) {
            $command = [];

            foreach ($group['formatter'] as $argument) {
                if ($argument !== RepositoryConfig::FILES_PLACEHOLDER) {
                    $command[] = $argument;

                    continue;
                }

                foreach ($group['transactions'] as $transaction) {
                    // Absolute, because the command runs from the repository root while the
                    // caller may have named the file from anywhere: a relative path would
                    // reach a different file there, or none.
                    $command[] = realpath($transaction->path) ?: $transaction->path;
                }
            }
            $this->executeFormatter($command, $root);

            foreach ($group['transactions'] as $transaction) {
                $this->adoptFormatterResult($transaction);
            }
        }
    }

    /**
     * Run one declared formatter command, from the repository root.
     *
     * No shell: the declaration is an argv list, so a path carrying a space stays one
     * argument and nothing in it can chain a second command. A non-zero exit is a failure of
     * the write — the caller rolls the files back and reports what the formatter said.
     *
     * Both streams go to files rather than pipes. Reading one pipe to EOF before the other
     * deadlocks as soon as the formatter fills the pipe it is not being read from, and
     * php-cs-fixer is talkative on stderr — that would hang the write with the tree already
     * modified and no rollback.
     *
     * @param list<string> $command
     */
    private function executeFormatter(array $command, string $root): void
    {
        $out = tempnam(sys_get_temp_dir(), 'php-ast-edit-fmt-');
        $err = tempnam(sys_get_temp_dir(), 'php-ast-edit-fmt-');

        if ($out === false || $err === false) {
            throw new EditException('Cannot create a temporary file for the formatter output.');
        }

        try {
            $descriptors = [1 => ['file', $out, 'w'], 2 => ['file', $err, 'w']];
            $pipes = [];
            $process = proc_open($command, $descriptors, $pipes, $root);

            if (!is_resource($process)) {
                throw new EditException('Cannot run the declared formatter: ' . implode(' ', $command));
            }
            $status = proc_close($process);

            if ($status === 0) {
                return;
            }
            $said = trim((string) file_get_contents($err) . "\n" . (string) file_get_contents($out));

            throw new EditException(
                sprintf(
                    'The declared formatter exited %d: %s%s',
                    $status,
                    implode(' ', $command),
                    $said === '' ? '' : "\n" . $said,
                ),
            );
        } finally {
            @unlink($out);
            @unlink($err);
        }
    }

    private function adoptFormatterResult(FileTransaction $transaction): void
    {
        $after = file_get_contents($transaction->path);

        if ($after === false) {
            throw new EditException(
                'Cannot re-read ' . $transaction->path . ' after the declared formatter ran.',
            );
        }

        try {
            $this->parser($transaction->phpVersion)->parse($after);
        } catch (\Throwable $failure) {
            throw new EditException(
                sprintf(
                    'The declared formatter left %s unparseable: %s',
                    $transaction->path,
                    $failure->getMessage(),
                ),
            );
        }
        $transaction->lint = (new PhpLint())->check($after, $transaction->path, $transaction->phpVersion);
        $transaction->output = $after;
        $transaction->changed = $transaction->source !== $after;
        $transaction->changedLines = $transaction->source === null ? substr_count($after, "\n") : $this->countChangedLines($transaction->source, $after);
        $transaction->formatter = 'ran';
    }

    /**
     * Hold a named target to the type the caller expected.
     *
     * A `ref` or a `select` says where to look; `kind` says what should be there. The offset
     * form has no need of this — it passes the kind to the locator, which uses it to pick the
     * node out of the ancestry rather than to check one afterwards.
     */
    private function assertKind(NodeLocation $location, mixed $kind): void
    {
        if ($kind === null) {
            return;
        }
        $expected = (string) $kind;

        if ($location->node->getType() !== $expected && $location->node::class !== $expected) {
            throw new EditException(
                sprintf(
                    'The target resolves to %s, expected %s.',
                    $location->node->getType(),
                    $expected,
                ),
            );
        }
    }

    /** @param list<Stmt> $roots */
    private function renameVariable(Node $scope, string $from, string $to, array $roots): int
    {
        // Resolve imports on a separate tree: analysis must not alter the printable AST.
        $clones = (new NodeTraverser(new CloningVisitor()))->traverse($roots);
        $resolved = (new NodeTraverser(new \PhpParser\NodeVisitor\NameResolver(null, ['replaceNodes' => false])))->traverse(
            $clones,
        );
        $functionNames = [];

        foreach ((new NodeFinder())->findInstanceOf($resolved, Expr\FuncCall::class) as $call) {
            $original = $call->getAttribute('origNode');

            if (!$original instanceof Expr\FuncCall || !$call->name instanceof Node\Name) {
                continue;
            }
            $name = $call->name->getAttribute('resolvedName', $call->name);
            $functionNames[spl_object_id($original)] = strtolower($name->getLast());
        }

        return (new RenameVariable($functionNames))->rename($scope, $from, $to);
    }

    /**
     * What each operation needs, beside its target.
     *
     * The catalogue used to list operation names and nothing else, so a caller reading
     * `contexts` or `--help` had to guess the argument names — and guessed by analogy with
     * whatever it had seen last. Measured on a controlled run: a model given the task of
     * renaming a variable sent `expect` and `value`, the shape `set_name` uses, three times
     * over before finding `from` and `to`. Four of its six `apply` calls failed on the
     * contract rather than on the code, and it gave up on selectors afterwards and renamed
     * one scope at a time — leaving two of eleven occurrences behind.
     *
     * `tests/catalog.php` requires an entry here for every dispatched operation, so the table
     * cannot fall behind the dispatcher.
     *
     * @var array<string, array{requires: list<string>, optional: list<string>}>
     */
    /**
     * Operation names a measured caller used for a real operation, and the engine then
     * refused while naming the real one. `set_docblock` was the most frequent unknown name.
     */
    private const OPERATION_SYNONYMS = ['set_docblock' => 'set_doc_comment', 'update_docblock' => 'set_doc_comment'];

    private const OPERATION_ARGUMENTS = [
        'replace_node' => ['requires' => ['php'], 'optional' => ['parseAs']],
        'delete_node' => ['requires' => [], 'optional' => []],
        'insert_into' => ['requires' => ['property', 'php'], 'optional' => ['position', 'parseAs']],
        'replace_child' => ['requires' => ['property', 'php'], 'optional' => ['index', 'parseAs']],
        'delete_child' => ['requires' => ['property'], 'optional' => ['index']],
        'move_node' => ['requires' => ['into'], 'optional' => ['position']],
        'set_doc_comment' => ['requires' => ['value'], 'optional' => []],
        'remove_doc_comment' => ['requires' => [], 'optional' => []],
        'set_name' => ['requires' => ['value'], 'optional' => ['declarationOnly']],
        'set_string' => ['requires' => ['value'], 'optional' => []],
        'replace_expression' => ['requires' => ['php'], 'optional' => ['match']],
        'replace_statement' => ['requires' => ['php'], 'optional' => ['match']],
        'insert_before' => ['requires' => ['php'], 'optional' => ['parseAs']],
        'insert_after' => ['requires' => ['php'], 'optional' => ['parseAs']],
        'delete' => ['requires' => [], 'optional' => []],
        'replace_argument' => ['requires' => ['index', 'php'], 'optional' => []],
        'add_argument' => ['requires' => ['index', 'php'], 'optional' => ['parseAs']],
        'remove_argument' => ['requires' => ['index'], 'optional' => []],
        'add_member' => ['requires' => ['php'], 'optional' => ['position', 'parseAs']],
        'add_parameter' => ['requires' => ['php'], 'optional' => ['position']],
        'add_attribute' => ['requires' => ['php'], 'optional' => ['position']],
        'set_return_type' => ['requires' => ['php'], 'optional' => []],
        'set_type' => ['requires' => ['php'], 'optional' => []],
        'set_visibility' => ['requires' => ['value'], 'optional' => []],
        'add_implements' => ['requires' => ['php'], 'optional' => ['position']],
        'add_use' => ['requires' => ['value'], 'optional' => ['alias']],
        'set_extends' => ['requires' => ['php'], 'optional' => ['position']],
        'rename_variable' => ['requires' => ['from', 'to'], 'optional' => []],
        'rename_method' => ['requires' => ['to'], 'optional' => ['mocks', 'project']],
    ];

    /**
     * Hold an edit to the arguments its operation actually takes.
     *
     * Checked before the target's own `expect`, so a caller that guessed the shape is told
     * the shape rather than meeting whatever error the wrong field happens to trip first.
     *
     * The message shows the edit rather than listing field names. Naming them was not enough:
     * told `rename_variable requires "from" and "to". This edit carries value.`, a model put
     * `from` and `to` inside `value` and met the same error again. A caller who has the shape
     * wrong needs to see the shape.
     *
     * @param array<string, mixed> $edit
     */
    private function assertOperationArguments(string $operation, array $edit): void
    {
        $spec = self::OPERATION_ARGUMENTS[$operation] ?? null;

        if ($spec === null) {
            return;
        }
        $missing = [];

        foreach ($spec['requires'] as $required) {
            if (!isset($edit[$required])) {
                $missing[] = $required;
            }
        }

        if ($missing === []) {
            return;
        }
        $shape = ['target' => '…', 'operation' => $operation];

        foreach ($spec['requires'] as $required) {
            // `into` is an object, and a placeholder that says otherwise sends the caller
            // through a second error to learn the type.
            $shape[$required] = $required === 'into' ? ['ref' => '…', 'property' => '…'] : '…';
        }
        // `parseAs` is a published argument, so an edit carrying it is not carrying none.
        $given = array_values(array_diff(array_keys($edit), ['operation', 'target', 'expect']));

        throw new EditException(
            sprintf(
                '%s takes its arguments beside "operation", not inside another field: %s.%s This edit carries %s.',
                $operation,
                json_encode($shape, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
                $spec['optional'] === [] ? '' : ' Optional: ' . implode(', ', $spec['optional']) . '.',
                $given === [] ? 'none of them' : implode(', ', $given),
            ),
        );
    }

    /** The catalogue name an operation is known by, where the caller used a synonym. */
    public static function canonicalOperation(string $operation): string
    {
        return self::OPERATION_SYNONYMS[$operation] ?? $operation;
    }

    /**
     * What each operation takes, for the catalogue to publish.
     *
     * `contexts` listed operation names and nothing else, so a caller had to guess the
     * argument names or find them in a reference file it may not have. Publishing the table
     * makes one call answer the question the guessing was for.
     *
     * @return array<string, array{requires: list<string>, optional: list<string>}>
     */
    public static function operationArguments(): array
    {
        return self::OPERATION_ARGUMENTS;
    }

    /**
     * The values an enumerated argument accepts, for the catalogue to publish.
     *
     * `contexts --operation insert_into` named `position` as optional and stopped, so the
     * value domain was discoverable only by getting it wrong — which three of eight measured
     * runs did. An argument whose values are a closed set says so where it is listed.
     *
     * @return array<string, array{values: list<string>, default?: string}>
     */
    public static function argumentValues(): array
    {
        return [
            'position' => ['values' => ['start', 'end', '<zero-based index>'], 'default' => 'end'],
            'index' => ['values' => ['<zero-based index>']],
        ];
    }

    /**
     * The catalogue entries closest to a name that is not in it.
     *
     * A rejected operation name is almost always a plausible synonym for a real one —
     * `set_docblock` for `set_doc_comment` was the single most frequent failure in a
     * measured run — and the bare rejection sends the caller to `contexts` to read the
     * whole catalogue back. Naming the near misses answers it in the same message.
     */
    private function nearestOperations(string $operation): string
    {
        $verb = strtok($operation, '_');
        $distances = [];

        foreach (array_keys(self::OPERATION_ARGUMENTS) as $known) {
            $distance = levenshtein($operation, $known);
            // Two ways to be close, because a wrong name is wrong in two ways. A typo stays
            // near in edit distance (`rename_metod`), while a plausible synonym does not —
            // `set_docblock` is six edits from `set_doc_comment` — but shares the verb. The
            // verb is what the caller knew; the noun is what it guessed.
            $near = $distance <= (int) ceil(max(strlen($operation), strlen($known)) / 3);
            $sameVerb = $verb !== false && $verb !== '' && str_starts_with($known, $verb . '_');

            if ($near || $sameVerb) {
                $distances[$known] = $distance;
            }
        }

        if ($distances === []) {
            return '. Run `php-ast-edit contexts` for the catalogue.';
        }
        asort($distances);
        $nearest = array_slice(array_keys($distances), 0, 3);

        return sprintf('. Did you mean %s?', implode(', ', $nearest));
    }

    /**
     * Take the names and fields the engine used to refuse while quoting, in the same breath,
     * what the caller meant.
     *
     * Each such refusal cost a turn and settled nothing the engine did not already know:
     * `rename_method` refused `new_name`, `set_doc_comment` refused `docComment` and `php`,
     * each with a message that repeated the field back. The rule is narrow on purpose. An
     * edit that lacks exactly one required argument and carries exactly one field its
     * operation does not take has one reading, and that is the one taken. Two unknown
     * fields, or a missing argument with nothing to fill it, are still refused: there the
     * engine would be guessing, and a guess it acts on is worse than a refusal.
     *
     * @param array<string, mixed> $edit
     *
     * @return array<string, mixed>
     */
    private function acceptSynonyms(array $edit): array
    {
        $operation = $edit['operation'] ?? null;

        if (is_string($operation) && isset(self::OPERATION_SYNONYMS[$operation])) {
            $operation = self::OPERATION_SYNONYMS[$operation];
            $edit['operation'] = $operation;
        }
        $spec = is_string($operation) ? self::OPERATION_ARGUMENTS[$operation] ?? null : null;

        if ($spec === null) {
            return $edit;
        }
        $missing = array_values(
            array_filter($spec['requires'], static fn (string $name): bool => !isset($edit[$name])),
        );
        $known = array_merge($spec['requires'], $spec['optional'], ['operation', 'target', 'expect']);
        $unknown = array_values(array_diff(array_keys($edit), $known));

        if (count($missing) === 1 && count($unknown) === 1) {
            $edit[$missing[0]] = $edit[$unknown[0]];
            unset($edit[$unknown[0]]);
        }

        return $edit;
    }

    /**
     * Replace every expression or statement inside the target that is the same code as
     * `match`, each with its own freshly parsed copy of `php`.
     *
     * "Inside resetLockout(), replace X with Y" was the edit measured agent sessions could
     * not express: the engine wanted that one node by line and column, and reaching it cost
     * an inspect round trip per attempt. The target stays a name, and the node is found by
     * what it says. Equality is structural — the node dump without positions or comments —
     * so spacing, quoting and line breaks in `match` do not matter, while names, arguments
     * and operators do.
     *
     * Matches are collected on the untouched tree and the outermost wins, so a pattern
     * nested inside another occurrence of itself is replaced once. The target itself is not
     * a candidate: without `match` the same operation replaces it directly.
     *
     * @param 'expr'|'stmt' $context
     */
    private function replaceMatches(
        NodeLocation $location,
        array $edit,
        ContextParser $snippets,
        string $context,
    ): void {
        $match = $this->requiredString($edit, 'match');
        $php = $this->requiredString($edit, 'php');
        $pattern = $snippets->parseOne($context, $match);
        $root = $location->node;
        $finder = new class (
            $root,
            $context === 'expr' ? Expr::class : Stmt::class,
            $pattern,
        ) extends NodeVisitorAbstract {
            public \SplObjectStorage $found;

            private readonly NodeDumper $dumper;

            private readonly string $wanted;

            /** @param class-string<Node> $kind */
            public function __construct(
                private readonly Node $root,
                private readonly string $kind,
                private readonly Node $pattern,
            ) {
                $this->found = new \SplObjectStorage();
                $this->dumper = new NodeDumper();
                $this->wanted = $this->dumper->dump($pattern);
            }

            public function enterNode(Node $node): ?int
            {
                if ($node === $this->root || !$node instanceof $this->kind || $node->getType() !== $this->pattern->getType()) {
                    return null;
                }

                if ($this->dumper->dump($node) !== $this->wanted) {
                    return null;
                }
                $this->found->attach($node);

                return NodeVisitor::DONT_TRAVERSE_CHILDREN;
            }
        };
        (new NodeTraverser($finder))->traverse([$root]);

        // Nothing to replace, but the replacement already stands in scope: the edit's end state
        // holds, so it is a reported no-op, as add_use is for an import that is already there.
        // Measured four times in eight runs: rename_method renamed the call sites, and a second
        // edit in the same transaction asked for the very rename by `match` and found nothing.
        if ($finder->found->count() === 0) {
            $present = new $finder(
                $root,
                $context === 'expr' ? Expr::class : Stmt::class,
                $snippets->parseOne($context, $php),
            );
            (new NodeTraverser($present))->traverse([$root]);

            if ($present->found->count() > 0) {
                $this->lastEffect = ['replaced' => 0, 'alreadyPresent' => $present->found->count()];

                return;
            }
        }

        if ($finder->found->count() === 0) {
            throw new EditException(
                sprintf(
                    'No %s inside %s is the same code as `%s`. The comparison is structural: spacing and quoting do not matter; names, arguments and operators do.',
                    $context === 'expr' ? 'expression' : 'statement',
                    $this->targetName($edit, $location),
                    $match,
                ),
            );
        }
        // One parse per occurrence: a node shared between two places would be one object
        // hanging in two parents, and the next edit to either would move both.
        $replacer = new class (
            $finder->found,
            static fn (): Node => $snippets->parseOne($context, $php),
        ) extends NodeVisitorAbstract {
            /** @param \Closure(): Node $parse */
            public function __construct(
                private readonly \SplObjectStorage $targets,
                private readonly \Closure $parse,
            ) {}

            public function leaveNode(Node $node): ?Node
            {
                if (!$this->targets->contains($node)) {
                    return null;
                }
                $replacement = ($this->parse)();
                // It takes the replaced node's lines, as NodeLocation::replace() does, or the
                // printer reads line 1 of the snippet as a gap and answers with blank lines.
                $replacement->setAttribute('startLine', $node->getStartLine());
                $replacement->setAttribute('endLine', $node->getEndLine());

                return $replacement;
            }
        };
        (new NodeTraverser($replacer))->traverse([$root]);
        $this->lastEffect = ['replaced' => $finder->found->count()];
    }

    /**
     * The form an edit takes when its target is the scope rather than the node: shown where
     * a caller named a declaration and meant something inside it.
     */
    private function scopedForm(string $operation, array $edit, NodeLocation $location): string
    {
        $what = $operation === 'replace_expression' ? 'expression' : 'statement';
        $example = [
            'target' => $edit['target'] ?? '…',
            'operation' => $operation,
            'match' => '<the ' . $what . ' as it is written>',
            'php' => '<its replacement>',
        ];

        return sprintf(
            'This target is a %s. To replace a %s inside it, keep the target and name the %s with "match": %s. replace_node replaces the target itself.',
            $location->node->getType(),
            $what,
            $what,
            json_encode($example, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        );
    }

    /** A declaration a selector can name; replacing one with a statement is never meant. */
    private function isDeclaration(Node $node): bool
    {
        return $node instanceof Stmt\ClassLike || $node instanceof Stmt\Function_ || $node instanceof Stmt\ClassMethod || $node instanceof Stmt\Property || $node instanceof Stmt\ClassConst || $node instanceof Stmt\EnumCase || $node instanceof Stmt\TraitUse;
    }

    private function targetName(array $edit, NodeLocation $location): string
    {
        $target = $edit['target'] ?? null;

        return is_array($target) && isset($target['select']) ? (string) $target['select'] : $location->node->getType();
    }

    /**
     * What the operation now running has to report, or an empty array.
     *
     * Read by `mutate()` straight after the dispatcher and cleared before each edit, so an
     * operation that counts something can say so without every handler in the chain having to
     * carry a return value it does not use.
     *
     * @var array<string, int|string>
     */
    private array $lastEffect = [];

    /**
     * How often the old name still occurs in the file, outside the scope just renamed.
     *
     * A rename is scoped, and a caller cannot know from the request whether the name lives in
     * other scopes too. Measured: told nothing, a model renamed two of three scopes, checked
     * with a `grep`, then sent a second `apply` — and in an earlier run stopped after two and
     * left the third alone. Counting what is left turns that into one number the write
     * already has.
     *
     * @param list<Node\Stmt> $roots
     */
    private function remainingVariables(array $roots, string $name): int
    {
        $name = ltrim($name, '$');
        $found = 0;

        foreach ((new NodeFinder())->findInstanceOf($roots, Expr\Variable::class) as $variable) {
            if (is_string($variable->name) && $variable->name === $name) {
                ++$found;
            }
        }

        return $found;
    }

    /** Above this many changed lines a diff stops being an answer and becomes the file again. */
    private const DIFF_LINE_CAP = 200;

    /**
     * A unified diff of what this write did, or null when it is too large to be an answer.
     *
     * The point of returning it is that nobody has to read the file back. Measured on a
     * controlled run: after a successful rename the model spent a `grep`, two `Read`s and a
     * `tail` establishing what had happened — four calls the write could have answered.
     *
     * A first normalisation rewrites the whole file, and a diff of that is not an answer to
     * anything; above the cap the caller is told the number instead.
     */
    private function unifiedDiff(FileTransaction $transaction): ?string
    {
        if ($transaction->source === null || $transaction->output === null) {
            return null;
        }

        if (($transaction->changedLines ?? 0) > self::DIFF_LINE_CAP) {
            return null;
        }
        $before = explode("\n", $transaction->source);
        $after = explode("\n", $transaction->output);
        $out = [];
        $i = 0;
        $j = 0;

        while ($i < count($before) || $j < count($after)) {
            if ($i < count($before) && $j < count($after) && $before[$i] === $after[$j]) {
                ++$i;
                ++$j;

                continue;
            }
            $nextMatch = $this->nextCommonLine($before, $after, $i, $j);

            for (; $i < $nextMatch['before']; ++$i) {
                $out[] = '-' . $before[$i];
            }

            for (; $j < $nextMatch['after']; ++$j) {
                $out[] = '+' . $after[$j];
            }

            if ($nextMatch['before'] >= count($before) && $nextMatch['after'] >= count($after)) {
                break;
            }
        }

        return $out === [] ? null : implode("\n", $out);
    }

    /**
     * Where the two sides line up again, searched forward from a divergence.
     *
     * A whole diff algorithm is not the point here: the caller wants to see the lines that
     * changed, and a bounded forward search finds them for the small edits this cap admits.
     *
     * @param  list<string> $before
     * @param  list<string> $after
     * @return array{before: int, after: int}
     */
    private function nextCommonLine(array $before, array $after, int $i, int $j): array
    {
        $limit = self::DIFF_LINE_CAP;

        for ($ahead = 1; $ahead <= $limit; ++$ahead) {
            for ($b = $i; $b <= min($i + $ahead, count($before) - 1); ++$b) {
                for ($a = $j; $a <= min($j + $ahead, count($after) - 1); ++$a) {
                    if ($before[$b] === $after[$a] && $b - $i + ($a - $j) === $ahead) {
                        return ['before' => $b, 'after' => $a];
                    }
                }
            }
        }

        return ['before' => count($before), 'after' => count($after)];
    }

    /** @var list<array<string, mixed>> What the declared checks said about this write. */
    private array $verifyResults = [];

    private function renameMethod(NodeLocation $location, string $to, array $roots): array
    {
        return (new RenameMethod())->rename($location, $to, $roots);
    }

    private function projectRenameOptions(array $edit): ?array
    {
        $target = $edit['target'] ?? null;

        if (($edit['operation'] ?? null) !== 'rename_method' || !is_string($edit['to'] ?? null)) {
            return null;
        }
        $mocks = array_key_exists('mocks', $edit) ? $edit['mocks'] : false;
        $project = array_key_exists('project', $edit) ? $edit['project'] : false;

        if (!is_bool($mocks)) {
            throw new EditException(
                'rename_method "mocks" is true or false: true also sets the method names PHPUnit mocks list.',
            );
        }

        if (!is_bool($project)) {
            throw new EditException(
                'rename_method "project" is true or false: true resolves callers across the project.',
            );
        }

        if (!is_array($target) || !is_string($target['select'] ?? null) && !is_string($target['ref'] ?? null)) {
            if ($project || $mocks) {
                throw new EditException(
                    'rename_method project or mocks requires target.select or target.ref.',
                );
            }

            return null;
        }

        return [$target, $mocks, $project];
    }
}
