<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;
use PhpParser\Node\Arg;
use PhpParser\Node\Expr;
use PhpParser\Node\Expr\CallLike;
use PhpParser\Node\Expr\Variable;
use PhpParser\Node\Identifier;
use PhpParser\Node\Name;
use PhpParser\Node\Scalar\String_;
use PhpParser\Node\Stmt;
use PhpParser\Node\VarLikeIdentifier;
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
        [$source, $parser, $roots] = $this->parseFile($path, $phpVersion);
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

    public function apply(array $document, bool $forceDryRun = false): array
    {
        $files = $document['files'] ?? null;
        if (!is_array($files) || $files === []) {
            throw new EditException('apply input requires a non-empty files array.');
        }

        $results = [];
        foreach ($files as $fileSpec) {
            if (!is_array($fileSpec)) {
                throw new EditException('Each files entry must be an object.');
            }
            $results[] = $this->applyFile($fileSpec, $forceDryRun || (bool) ($document['dryRun'] ?? false));
        }

        return ['files' => $results];
    }

    private function applyFile(array $spec, bool $dryRun): array
    {
        $path = $this->requiredString($spec, 'path');
        $phpVersion = isset($spec['phpVersion']) ? (string) $spec['phpVersion'] : null;
        [$source, $parser, $roots] = $this->parseFile($path, $phpVersion);
        $beforeHash = hash('sha256', $source);

        if (isset($spec['sha256']) && !hash_equals((string) $spec['sha256'], $beforeHash)) {
            throw new EditException(sprintf('STALE_SOURCE: %s no longer matches expected sha256.', $path));
        }

        $edits = $spec['edits'] ?? null;
        if (!is_array($edits) || $edits === []) {
            throw new EditException(sprintf('%s requires a non-empty edits array.', $path));
        }

        $resolved = [];
        foreach ($edits as $index => $edit) {
            if (!is_array($edit)) {
                throw new EditException(sprintf('Edit %d must be an object.', $index));
            }
            $target = $edit['target'] ?? null;
            if (!is_array($target)) {
                throw new EditException(sprintf('Edit %d requires a target object.', $index));
            }
            $offset = $this->targetOffset($source, $target);
            $kind = isset($target['kind']) ? (string) $target['kind'] : null;
            $location = $this->locator->locate($roots, $offset, $kind);
            $this->assertExpectations($location->node, $edit['expect'] ?? []);
            $resolved[] = ['edit' => $edit, 'location' => $location, 'index' => $index];
        }

        $snippetParser = new SnippetParser($parser);

        foreach ($resolved as $entry) {
            if (!$this->locator->isAttached($roots, $entry['location']->node)) {
                throw new EditException(sprintf(
                    'Edit %d was invalidated by an earlier edit in the same transaction.',
                    $entry['index'],
                ));
            }
            $this->applyOperation($entry['location'], $entry['edit'], $roots, $snippetParser);
        }

        $printerOptions = [];
        if ($phpVersion !== null) {
            $printerOptions['phpVersion'] = PhpVersion::fromString($phpVersion);
        }
        $printer = new Standard($printerOptions);
        $output = rtrim($printer->prettyPrintFile($roots), "\r\n")."\n";

        $validationParser = $this->parser($phpVersion);
        $validationParser->parse($output);

        $afterHash = hash('sha256', $output);
        $changed = $source !== $output;

        if (!$dryRun && $changed) {
            $this->atomicWrite($path, $output);
        }

        $result = [
            'path' => $path,
            'beforeSha256' => $beforeHash,
            'afterSha256' => $afterHash,
            'changed' => $changed,
            'editsApplied' => count($resolved),
            'dryRun' => $dryRun,
        ];
        if ($dryRun) {
            $result['code'] = $output;
        }
        return $result;
    }

    private function applyOperation(NodeLocation $location, array $edit, array &$roots, SnippetParser $snippets): void
    {
        $operation = $this->requiredString($edit, 'operation');
        $node = $location->node;

        switch ($operation) {
            case 'set_name':
                $this->setName($location, $this->requiredString($edit, 'value'), $roots);
                return;

            case 'set_string':
                if (!$node instanceof String_) {
                    throw new EditException('set_string requires a Scalar_String target.');
                }
                $node->value = $this->requiredString($edit, 'value');
                $attributes = $node->getAttributes();
                unset($attributes['rawValue']);
                $node->setAttributes($attributes);
                return;

            case 'replace_expression':
                if (!$node instanceof Expr) {
                    throw new EditException('replace_expression requires an Expr target.');
                }
                $location->replace($snippets->expression($this->requiredString($edit, 'php')), $roots);
                return;

            case 'replace_statement':
                if (!$node instanceof Stmt) {
                    throw new EditException('replace_statement requires a Stmt target.');
                }
                $location->replace($snippets->statement($this->requiredString($edit, 'php')), $roots);
                return;

            case 'insert_before':
                if (!$node instanceof Stmt) {
                    throw new EditException('insert_before requires a Stmt target.');
                }
                $location->insertBefore($snippets->statements($this->requiredString($edit, 'php')), $roots);
                return;

            case 'insert_after':
                if (!$node instanceof Stmt) {
                    throw new EditException('insert_after requires a Stmt target.');
                }
                $location->insertAfter($snippets->statements($this->requiredString($edit, 'php')), $roots);
                return;

            case 'delete':
                $location->remove($roots);
                return;

            case 'replace_argument':
            case 'add_argument':
            case 'remove_argument':
                if (!$node instanceof CallLike) {
                    throw new EditException($operation.' requires an Expr_*Call target.');
                }
                $this->editArgument($node, $edit, $snippets, $operation);
                return;

            default:
                throw new EditException('Unsupported operation: '.$operation);
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

    private function editArgument(CallLike $call, array $edit, SnippetParser $snippets, string $operation): void
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

        $expr = $snippets->expression($this->requiredString($edit, 'php'));
        if ($operation === 'replace_argument') {
            if (!array_key_exists($index, $args) || !$args[$index] instanceof Arg) {
                throw new EditException('Argument index out of range.');
            }
            $args[$index]->value = $expr;
        } else {
            if ($index > count($args)) {
                throw new EditException('Argument insertion index out of range.');
            }
            array_splice($args, $index, 0, [new Arg($expr)]);
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
        $source = file_get_contents($path);
        if ($source === false) {
            throw new EditException('Cannot read file: '.$path);
        }
        $parser = $this->parser($phpVersion);
        $roots = $parser->parse($source);
        if ($roots === null) {
            $roots = [];
        }
        return [$source, $parser, $roots];
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
            throw new EditException('Target requires offset or 1-based integer line and column.');
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
        $temp = tempnam($directory, '.php-ast-edit-');
        if ($temp === false) {
            throw new EditException('Cannot create temporary file next to '.$path);
        }
        try {
            $mode = fileperms($path);
            if (file_put_contents($temp, $contents) === false) {
                throw new EditException('Cannot write temporary file for '.$path);
            }
            if ($mode !== false) {
                chmod($temp, $mode & 0777);
            }
            if (!rename($temp, $path)) {
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
