<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Comment\Doc;
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
use PhpParser\Modifiers;
use PhpParser\Parser;
use PhpParser\ParserFactory;
use PhpParser\PhpVersion;
use PhpParser\PrettyPrinter\Standard;

final class Editor
{
    private readonly NodeLocator $locator;

    public function __construct()
    {
        $this->locator = new NodeLocator();
    }

    public function inspect(string $path, array $target, ?string $phpVersion = null): array
    {
        [$source, , $roots] = $this->parseFile($path, $phpVersion);
        $offset = $this->targetOffset($source, $target);
        $locations = $this->locator->ancestry($roots, $offset);

        return [
            'file' => $path,
            'sha256' => hash('sha256', $source),
            'offset' => $offset,
            'nodes' => array_map(fn (NodeLocation $location): array => $this->describe($location, $source), $locations),
        ];
    }

    public function validate(string $path, ?string $phpVersion = null): array
    {
        [$source, , $roots] = $this->parseFile($path, $phpVersion);
        return [
            'file' => $path,
            'sha256' => hash('sha256', $source),
            'statements' => count($roots),
            'valid' => true,
        ];
    }

    /**
     * Apply a transaction across one or more files.
     *
     * Every file is read, guarded, resolved, mutated, printed and re-parsed before the first
     * byte is written. A failure in any phase leaves the working tree untouched; a failure
     * during the write phase rolls the already written files back.
     */
    public function apply(array $document, bool $forceDryRun = false): array
    {
        $files = $document['files'] ?? null;
        if (!is_array($files) || $files === []) {
            throw new EditException('apply input requires a non-empty files array.');
        }

        $dryRun = $forceDryRun || (bool) ($document['dryRun'] ?? false);

        // Phase 1 — read, guard and resolve every target against its pristine snapshot.
        $transactions = [];
        $seen = [];
        foreach ($files as $spec) {
            if (!is_array($spec)) {
                throw new EditException('Each files entry must be an object.');
            }
            $transaction = $this->prepare($spec);
            if (isset($seen[$transaction->path])) {
                throw new EditException('Duplicate path in one transaction: '.$transaction->path);
            }
            $seen[$transaction->path] = true;
            $transactions[] = $transaction;
        }

        // Phase 2 — mutate in memory.
        foreach ($transactions as $transaction) {
            $this->mutate($transaction);
        }

        // Phase 3 — print and re-parse; nothing invalid reaches the working tree.
        foreach ($transactions as $transaction) {
            $this->render($transaction);
        }

        // Phase 4 — commit, with best-effort rollback.
        if (!$dryRun) {
            $this->commit($transactions);
        }

        return ['files' => array_map(
            fn (FileTransaction $transaction): array => $this->report($transaction, $dryRun),
            $transactions,
        )];
    }

    private function prepare(array $spec): FileTransaction
    {
        $path = $this->requiredString($spec, 'path');
        $mode = (string) ($spec['mode'] ?? 'edit');
        if (!in_array($mode, ['edit', 'create', 'delete'], true)) {
            throw new EditException('mode must be edit, create or delete.');
        }
        $phpVersion = isset($spec['phpVersion']) ? (string) $spec['phpVersion'] : null;

        if ($mode === 'delete') {
            if (!is_file($path)) {
                throw new EditException('Cannot delete missing file: '.$path);
            }
            $source = $this->readFile($path);
            $this->assertSha($spec, $path, hash('sha256', $source));
            return new FileTransaction($path, 'delete', $source, [], null, $phpVersion, true);
        }

        if ($mode === 'create') {
            $existed = is_file($path);
            if ($existed && ($spec['expectAbsent'] ?? true) !== false) {
                throw new EditException(sprintf(
                    'FILE_EXISTS: %s already exists. Pass "expectAbsent": false to overwrite deliberately.',
                    $path,
                ));
            }
            $parser = $this->parser($phpVersion);
            $roots = (new ContextParser($parser))->file($this->requiredString($spec, 'php'));
            $transaction = new FileTransaction(
                $path,
                'create',
                $existed ? $this->readFile($path) : null,
                $roots,
                $parser,
                $phpVersion,
                $existed,
            );
            // Targets inside a freshly constructed file resolve against the construction syntax.
            $this->resolveTargets($transaction, $spec, $this->requiredString($spec, 'php'));
            return $transaction;
        }

        [$source, $parser, $roots] = $this->parseFile($path, $phpVersion);
        $this->assertSha($spec, $path, hash('sha256', $source));
        $transaction = new FileTransaction($path, 'edit', $source, $roots, $parser, $phpVersion, true);
        $edits = $spec['edits'] ?? null;
        if (!is_array($edits) || $edits === []) {
            throw new EditException(sprintf('%s requires a non-empty edits array.', $path));
        }
        $this->resolveTargets($transaction, $spec, $source);
        return $transaction;
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
            $target = $edit['target'] ?? null;
            if (!is_array($target)) {
                throw new EditException(sprintf('Edit %d requires a target object.', $index));
            }

            if (isset($target['ref'])) {
                $location = $this->locator->resolveRef($transaction->roots, (string) $target['ref']);
                if (isset($target['kind'])) {
                    $kind = (string) $target['kind'];
                    if ($location->node->getType() !== $kind && $location->node::class !== $kind) {
                        throw new EditException(sprintf(
                            'target.ref resolves to %s, expected %s.',
                            $location->node->getType(),
                            $kind,
                        ));
                    }
                }
            } else {
                $offset = $this->targetOffset($source, $target);
                $kind = isset($target['kind']) ? (string) $target['kind'] : null;
                $location = $this->locator->locate($transaction->roots, $offset, $kind);
            }

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
                throw new EditException(sprintf(
                    '%s: edit %d was invalidated by an earlier edit in the same transaction.',
                    $transaction->path,
                    $entry['index'],
                ));
            }
            $this->applyOperation($entry['location'], $entry['edit'], $transaction->roots, $snippets);
        }
    }

    private function render(FileTransaction $transaction): void
    {
        if ($transaction->mode === 'delete') {
            $transaction->changed = true;
            return;
        }

        $printerOptions = [];
        if ($transaction->phpVersion !== null) {
            $printerOptions['phpVersion'] = PhpVersion::fromString($transaction->phpVersion);
        }
        $printer = new Standard($printerOptions);
        $output = rtrim($printer->prettyPrintFile($transaction->roots), "\r\n")."\n";

        $this->parser($transaction->phpVersion)->parse($output);

        $transaction->output = $output;
        $transaction->changed = $transaction->source !== $output;
    }

    /** @param list<FileTransaction> $transactions */
    private function commit(array $transactions): void
    {
        /** @var list<array{path: string, previous: ?string}> $done */
        $done = [];
        try {
            foreach ($transactions as $transaction) {
                if (!$transaction->changed) {
                    continue;
                }
                if ($transaction->mode === 'delete') {
                    $done[] = ['path' => $transaction->path, 'previous' => $transaction->source];
                    if (!@unlink($transaction->path)) {
                        throw new EditException('Cannot delete '.$transaction->path);
                    }
                    continue;
                }
                $done[] = ['path' => $transaction->path, 'previous' => $transaction->existed ? $transaction->source : null];
                $this->atomicWrite($transaction->path, (string) $transaction->output);
            }
        } catch (\Throwable $failure) {
            $restoreErrors = [];
            foreach (array_reverse($done) as $entry) {
                try {
                    if ($entry['previous'] === null) {
                        if (is_file($entry['path'])) {
                            @unlink($entry['path']);
                        }
                        continue;
                    }
                    $this->atomicWrite($entry['path'], $entry['previous']);
                } catch (\Throwable $restoreFailure) {
                    $restoreErrors[] = $entry['path'].': '.$restoreFailure->getMessage();
                }
            }
            $message = 'COMMIT_FAILED: '.$failure->getMessage();
            if ($restoreErrors !== []) {
                $message .= ' Rollback incomplete for '.implode('; ', $restoreErrors);
            } else {
                $message .= ' All files were rolled back.';
            }
            throw new EditException($message);
        }
    }

    private function report(FileTransaction $transaction, bool $dryRun): array
    {
        $result = [
            'path' => $transaction->path,
            'mode' => $transaction->mode,
            'beforeSha256' => $transaction->beforeSha(),
            'afterSha256' => $transaction->output === null ? null : hash('sha256', $transaction->output),
            'changed' => $transaction->changed,
            'editsApplied' => count($transaction->resolved),
            'dryRun' => $dryRun,
        ];
        if ($dryRun && $transaction->output !== null) {
            $result['code'] = $transaction->output;
        }
        return $result;
    }

    private function applyOperation(NodeLocation $location, array $edit, array &$roots, ContextParser $snippets): void
    {
        $operation = $this->requiredString($edit, 'operation');

        $applied = $this->applyPrimitive($operation, $location, $edit, $roots, $snippets)
            || $this->applyComment($operation, $location, $edit)
            || $this->applyShorthand($operation, $location, $edit, $roots, $snippets)
            || $this->applySemantic($operation, $location, $edit, $snippets);

        if (!$applied) {
            throw new EditException('Unsupported operation: '.$operation);
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
                $location->replace($snippets->parseOne($context, $this->requiredString($edit, 'php')), $roots);
                return true;

            case 'delete_node':
            case 'delete':
                $location->remove($roots);
                return true;

            case 'insert_into':
                $property = $this->requiredString($edit, 'property');
                $php = $this->requiredString($edit, 'php');
                $nodes = !isset($edit['parseAs']) && $property === 'stmts' && $node instanceof Stmt\ClassLike
                    ? $snippets->parseFirst($this->memberContexts($node), $php)
                    : $snippets->parse($this->contextForProperty($edit, $property), $php);
                $location->insertInto($property, $nodes, $this->position($edit));
                return true;

            case 'replace_child':
                $property = $this->requiredString($edit, 'property');
                $context = $this->contextForProperty($edit, $property);
                $location->replaceChild(
                    $property,
                    $this->optionalIndex($edit),
                    $snippets->parseOne($context, $this->requiredString($edit, 'php')),
                );
                return true;

            case 'delete_child':
                $location->removeChild($this->requiredString($edit, 'property'), $this->optionalIndex($edit));
                return true;

            case 'move_node':
                $this->moveNode($location, $edit, $roots);
                return true;
        }

        return false;
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
        }

        return false;
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
            // ---- Convenience shorthands over the primitives ------------------------------
            case 'set_name':
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
                if (!$node instanceof Expr) {
                    throw new EditException('replace_expression requires an Expr target.');
                }
                $location->replace($snippets->parseOne('expr', $this->requiredString($edit, 'php')), $roots);
                return true;

            case 'replace_statement':
                if (!$node instanceof Stmt) {
                    throw new EditException('replace_statement requires a Stmt target.');
                }
                $location->replace($snippets->parseOne('stmt', $this->requiredString($edit, 'php')), $roots);
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
                    throw new EditException($operation.' requires an Expr_*Call target.');
                }
                $this->editArgument($node, $edit, $snippets, $operation);
                return true;
        }

        return false;
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
        ContextParser $snippets,
    ): bool {
        $node = $location->node;

        switch ($operation) {
            // ---- Semantic convenience ----------------------------------------------------
            case 'add_member':
                $this->assertType($node, Stmt\ClassLike::class, 'add_member requires a class-like target.');
                $location->insertInto(
                    'stmts',
                    $snippets->parseFirst($this->memberContexts($node), $this->requiredString($edit, 'php')),
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
                $this->assertType($node, Stmt\Class_::class, 'add_implements requires a Stmt_Class target.');
                $location->insertInto(
                    'implements',
                    [$snippets->parseOne('type', $this->requiredString($edit, 'php'))],
                    $this->position($edit, 'end'),
                );
                return true;

            case 'set_extends':
                $location->replaceChild(
                    'extends',
                    $this->optionalIndex($edit),
                    $snippets->parseOne('type', $this->requiredString($edit, 'php')),
                );
                return true;
        }

        return false;
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
        if ($text === null) {
            unset($attributes['comments']);
            $node->setAttributes($attributes);
            return;
        }

        $text = trim($text);
        if (!str_starts_with($text, '/**')) {
            $lines = preg_split('/\R/', $text) ?: [];
            $text = "/**\n".implode("\n", array_map(
                static fn (string $line): string => rtrim(' * '.$line),
                $lines,
            ))."\n */";
        }

        $comments = array_values(array_filter(
            $node->getComments(),
            static fn (\PhpParser\Comment $comment): bool => !$comment instanceof Doc,
        ));
        $comments[] = new Doc($text);
        $attributes['comments'] = $comments;
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
        $node->flags = ($node->flags & ~Modifiers::VISIBILITY_MASK) | $map[$visibility];
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
        throw new EditException(sprintf(
            'Cannot infer a parse context for %s; pass "parseAs" explicitly.',
            $location->node->getType(),
        ));
    }

    private function contextForProperty(array $edit, string $property): string
    {
        if (isset($edit['parseAs'])) {
            return (string) $edit['parseAs'];
        }
        $context = self::PROPERTY_CONTEXTS[$property] ?? null;
        if ($context === null) {
            throw new EditException(sprintf(
                'Cannot infer a parse context for property "%s"; pass "parseAs" explicitly.',
                $property,
            ));
        }
        return $context;
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

    /** Property name → synthetic parse context. */
    private const PROPERTY_CONTEXTS = [
        'stmts' => 'member',
        'params' => 'param',
        'args' => 'arg',
        'items' => 'array_item',
        'arms' => 'match_arm',
        'attrGroups' => 'attribute',
        'uses' => 'closure_use',
        'catches' => 'catch',
        'consts' => 'const',
        'props' => 'property_item',
        'vars' => 'static_var',
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
            ($node instanceof Identifier || $node instanceof Name)
                && in_array($location->property, ['type', 'returnType', 'implements', 'extends'], true) => 'type',
            $node instanceof Expr => 'expr',
            $node instanceof Stmt\ClassMethod,
            $node instanceof Stmt\Property,
            $node instanceof Stmt\ClassConst,
            $node instanceof Stmt\TraitUse => 'member',
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
        throw new EditException('position must be an integer, "start" or "end".');
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
            throw new EditException($message.' Got '.$node->getType().'.');
        }
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

    private function editArgument(CallLike $call, array $edit, ContextParser $snippets, string $operation): void
    {
        if ($call->isFirstClassCallable()) {
            throw new EditException($operation.' is not valid for first-class callable syntax.');
        }
        if (!property_exists($call, 'args')) {
            throw new EditException($operation.' target does not expose an argument list.');
        }

        $index = $edit['index'] ?? null;
        if (!is_int($index) || $index < 0) {
            throw new EditException($operation.' requires a non-negative integer index.');
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
            throw new EditException(sprintf('Expected node type %s, got %s.', $expect['type'], $node->getType()));
        }
        if (array_key_exists('name', $expect)) {
            $actual = $this->nodeName($node);
            if ($actual !== (string) $expect['name']) {
                throw new EditException(sprintf('Expected node name %s, got %s.', $expect['name'], $actual ?? '<none>'));
            }
        }
        if (array_key_exists('value', $expect)) {
            $actual = $this->nodeValue($node);
            if ($actual !== (string) $expect['value']) {
                throw new EditException(sprintf('Expected node value %s, got %s.', $expect['value'], $actual ?? '<none>'));
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
        $code = substr($source, $start, $end - $start + 1);
        if (strlen($code) > 240) {
            $code = substr($code, 0, 237).'...';
        }
        return array_filter([
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
        ], static fn (mixed $value): bool => $value !== null);
    }

    /** @return array{0:string,1:Parser,2:list<Stmt>} */
    private function parseFile(string $path, ?string $phpVersion): array
    {
        if (!is_file($path)) {
            throw new EditException('File not found: '.$path);
        }
        $source = $this->readFile($path);
        $parser = $this->parser($phpVersion);
        $roots = $parser->parse($source);
        if ($roots === null) {
            $roots = [];
        }
        return [$source, $parser, $roots];
    }

    private function readFile(string $path): string
    {
        $source = file_get_contents($path);
        if ($source === false) {
            throw new EditException('Cannot read file: '.$path);
        }
        return $source;
    }

    private function assertSha(array $spec, string $path, string $actual): void
    {
        if (isset($spec['sha256']) && !hash_equals((string) $spec['sha256'], $actual)) {
            throw new EditException(sprintf('STALE_SOURCE: %s no longer matches expected sha256.', $path));
        }
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
        $directory = dirname($path);
        if (!is_dir($directory) && !@mkdir($directory, 0777, true) && !is_dir($directory)) {
            throw new EditException('Cannot create directory '.$directory);
        }
        if (!is_writable($directory)) {
            throw new EditException('Directory is not writable: '.$directory);
        }
        $existed = is_file($path);
        $temp = @tempnam($directory, '.php-ast-edit-');
        if ($temp === false || realpath(dirname($temp)) !== realpath($directory)) {
            // tempnam() silently falls back to the system temp directory, which would turn
            // the rename below into a cross-device move and lose atomicity.
            if (is_string($temp) && is_file($temp)) {
                @unlink($temp);
            }
            throw new EditException('Cannot create temporary file next to '.$path);
        }
        try {
            $mode = $existed ? fileperms($path) : false;
            if (@file_put_contents($temp, $contents) === false) {
                throw new EditException('Cannot write temporary file for '.$path);
            }
            @chmod($temp, $mode !== false ? ($mode & 0777) : (0666 & ~umask()));
            if (!@rename($temp, $path)) {
                throw new EditException('Atomic rename failed for '.$path);
            }
        } finally {
            if (is_file($temp)) {
                @unlink($temp);
            }
        }
    }

    private function requiredString(array $data, string $key): string
    {
        $value = $data[$key] ?? null;
        if (!is_string($value) || $value === '') {
            throw new EditException($key.' must be a non-empty string.');
        }
        return $value;
    }
}
