<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\ConstExprEvaluationException;
use PhpParser\ConstExprEvaluator;
use PhpParser\Node;
use PhpParser\Node\Stmt;
use PhpParser\NodeFinder;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitor\NameResolver;
use PhpParser\ParserFactory;

/**
 * The project's class-likes, and where each ancestor of one lives.
 *
 * Project files are the PHP files git knows about — tracked, or untracked and not ignored
 * — minus the repository's exclusions: the set the engine edits. An ancestor outside that
 * set is found through Composer's generated class map and PSR-4 table, which are plain
 * arrays. The autoloader itself is never loaded: a TYPO3 project's executes code.
 */
final class ProjectIndex
{
    /** @var array<string, array{name: string, file: string, node: Stmt\ClassLike, project: bool}> */
    private array $classes = [];

    /** @var array<string, true>|null */
    private ?array $projectFiles = null;

    /** @var array{classmap: array<string, string>, psr4: array<string, list<string>>}|null */
    private ?array $autoload = null;

    private bool $scanned = false;

    private function __construct(
        public readonly string $root,
        private readonly RepositoryConfig $config,
    ) {}

    public static function for(string $file): self
    {
        $config = RepositoryConfig::discover($file);
        $root = $config->path !== null ? \dirname($config->path) : RepositoryConfig::rootFor($file);

        return new self(realpath($root) ?: $root, $config);
    }

    /** @return list<string> absolute paths of the project's PHP files */
    public function phpFiles(): array
    {
        return array_keys($this->projectFiles());
    }

    /** @return list<string> absolute paths of the project's files that are not PHP */
    public function otherFiles(): array
    {
        return array_values(
            array_filter(
                $this->gitFiles([]),
                fn (
                    string $path,
                ): bool => !str_ends_with($path, '.php') && !$this->config->excludes($path),
            ),
        );
    }

    public function isProjectFile(string $path): bool
    {
        $real = realpath($path);

        return $real !== false && isset($this->projectFiles()[$real]);
    }

    /**
     * A class-like by name, from the project or through Composer's tables.
     *
     * @return array{name: string, file: string, node: Stmt\ClassLike, project: bool}|null
     */
    public function find(string $name): ?array
    {
        $key = strtolower(ltrim($name, '\\'));
        $this->scan();

        if (!isset($this->classes[$key])) {
            $file = $this->autoloadFile(ltrim($name, '\\'));

            if ($file !== null) {
                $this->load($file, false);
            }
        }

        return $this->classes[$key] ?? null;
    }

    /** @return list<array{name: string, file: string, node: Stmt\ClassLike, project: bool}> */
    public function projectClasses(): array
    {
        $this->scan();

        return array_values(
            array_filter($this->classes, static fn (array $entry): bool => $entry['project']),
        );
    }

    /**
     * Every ancestor — parent, interface, used trait — transitively, with where it lives.
     *
     * `where` is `project`, `vendor`, `internal` (a PHP built-in, read by reflection) or
     * `missing`: named in the source, found nowhere. A caller that needs certainty about the
     * hierarchy treats `missing` as a reason to refuse, not as an empty ancestor.
     *
     * @return list<array{name: string, where: string, methods: list<string>, trait: bool}>
     */
    public function ancestors(string $name): array
    {
        $seen = [];
        $pending = $this->parents($this->find($name));
        $result = [];

        while ($pending !== []) {
            [$parent, $trait] = array_shift($pending);
            $key = strtolower($parent);

            if (isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $entry = $this->find($parent);

            if ($entry !== null) {
                $result[] = [
                    'name' => $entry['name'],
                    'where' => $entry['project'] ? 'project' : 'vendor',
                    'methods' => array_map(
                        static fn (
                            Stmt\ClassMethod $method,
                        ): string => strtolower($method->name->toString()),
                        $entry['node']->getMethods(),
                    ),
                    'trait' => $trait,
                ];
                array_push($pending, ...$this->parents($entry));

                continue;
            }

            if ((class_exists($parent, false) || interface_exists($parent, false) || trait_exists($parent, false)) && (new \ReflectionClass($parent))->isInternal()) {
                $result[] = [
                    'name' => $parent,
                    'where' => 'internal',
                    'methods' => array_map(
                        static fn (
                            \ReflectionMethod $method,
                        ): string => strtolower($method->getName()),
                        (new \ReflectionClass($parent))->getMethods(),
                    ),
                    'trait' => $trait,
                ];

                continue;
            }
            $result[] = ['name' => $parent, 'where' => 'missing', 'methods' => [], 'trait' => $trait];
        }

        return $result;
    }

    /** The fully qualified name of a class-like as the file declares it, or null for an anonymous one. */
    public static function nameOf(Stmt\ClassLike $node, array $roots): ?string
    {
        if ($node->name === null) {
            return null;
        }

        foreach ($roots as $root) {
            if ($root instanceof Stmt\Namespace_ && (new NodeFinder())->findFirst(
                $root->stmts,
                static fn (Node $candidate): bool => $candidate === $node,
            ) !== null) {
                return ($root->name === null ? '' : $root->name->toString() . '\\') . $node->name->toString();
            }
        }

        return $node->name->toString();
    }

    /**
     * @param array{name: string, file: string, node: Stmt\ClassLike, project: bool}|null $entry
     * @return list<array{string, bool}>
     */
    private function parents(?array $entry): array
    {
        if ($entry === null) {
            return [];
        }
        $node = $entry['node'];
        $names = [];

        if ($node instanceof Stmt\Class_) {
            $names = [...$node->extends === null ? [] : [$node->extends], ...$node->implements];
        } elseif ($node instanceof Stmt\Interface_) {
            $names = $node->extends;
        } elseif ($node instanceof Stmt\Enum_) {
            $names = $node->implements;
        }
        $parents = array_map(static fn (Node\Name $name): array => [$name->toString(), false], $names);

        foreach ($node->stmts as $statement) {
            if ($statement instanceof Stmt\TraitUse) {
                foreach ($statement->traits as $trait) {
                    $parents[] = [$trait->toString(), true];
                }
            }
        }

        return $parents;
    }

    /** @return array<string, true> */
    private function projectFiles(): array
    {
        if ($this->projectFiles === null) {
            $this->projectFiles = [];

            foreach ($this->gitFiles(['*.php']) as $path) {
                if (!$this->config->excludes($path)) {
                    $this->projectFiles[realpath($path) ?: $path] = true;
                }
            }
        }

        return $this->projectFiles;
    }

    /**
     * @param list<string> $pathspec
     * @return list<string>
     */
    private function gitFiles(array $pathspec): array
    {
        $command = [
            'git',
            '-C',
            $this->root,
            'ls-files',
            '-z',
            '--cached',
            '--others',
            '--exclude-standard',
            '--',
            ...$pathspec,
        ];
        $process = proc_open($command, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);

        if (!is_resource($process)) {
            throw new EditException('Cannot run git to list the project files.');
        }
        $output = (string) stream_get_contents($pipes[1]);
        $errors = (string) stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        if (proc_close($process) !== 0) {
            throw new EditException(
                'A project-wide rename needs git to say which files are the project, and git refused in ' . $this->root . ': ' . trim($errors),
            );
        }
        $files = [];

        foreach (explode("\x00", $output) as $relative) {
            $path = $this->root . DIRECTORY_SEPARATOR . $relative;

            if ($relative !== '' && is_file($path) && !is_link($path)) {
                $files[] = $path;
            }
        }

        return $files;
    }

    private function scan(): void
    {
        // On the instance, not in a static keyed by object id: ids are reused once an index
        // is freed, and a later index that inherited a "scanned" mark would see no project
        // classes — no descendants, so an override would keep the old name.
        if ($this->scanned) {
            return;
        }
        $this->scanned = true;

        foreach ($this->phpFiles() as $file) {
            $this->load($file, true);
        }
    }

    private function load(string $file, bool $project): void
    {
        $source = file_get_contents($file);

        if ($source === false) {
            throw new EditException('Cannot read ' . $file);
        }

        try {
            $roots = (new ParserFactory())->createForHostVersion()->parse($source) ?? [];
        } catch (\PhpParser\Error $failure) {
            if ($project) {
                throw new EditException(
                    sprintf(
                        '%s does not parse, so the project hierarchy is unknown: %s',
                        $file,
                        $failure->getMessage(),
                    ),
                );
            }

            return;
        }
        $traverser = new NodeTraverser(new NameResolver());
        $roots = $traverser->traverse($roots);

        foreach ((new NodeFinder())->findInstanceOf($roots, Stmt\ClassLike::class) as $node) {
            $name = $node->namespacedName?->toString();

            if ($name === null) {
                continue;
            }
            $this->remember($name, $file, $node, $project);
        }
    }

    /**
     * One of Composer's generated tables, evaluated rather than included.
     *
     * The files are two assignments — `$vendorDir`, `$baseDir`, each a `dirname()` chain
     * over `__DIR__` — and a `return array(…)` of string concatenations. Including one would
     * run whatever the repository being edited put there; evaluating that grammar runs
     * nothing, and anything outside it makes the table empty rather than executed.
     *
     * @return array<string, mixed>
     */
    private static function composerTable(string $path): array
    {
        if (!is_file($path)) {
            return [];
        }
        $roots = (new ParserFactory())->createForHostVersion()->parse((string) file_get_contents($path)) ?? [];
        $variables = [];
        $evaluator = null;
        $evaluator = new ConstExprEvaluator(
            static function (Node\Expr $expr) use (&$evaluator, &$variables, $path): string {
                if ($expr instanceof Node\Scalar\MagicConst\Dir) {
                    return \dirname($path);
                }

                if ($expr instanceof Node\Expr\Variable && is_string($expr->name) && isset($variables[$expr->name])) {
                    return $variables[$expr->name];
                }

                if ($expr instanceof Node\Expr\FuncCall && $expr->name instanceof Node\Name && $expr->name->toLowerString() === 'dirname' && count($expr->args) === 1 && $expr->args[0] instanceof Node\Arg) {
                    return \dirname((string) $evaluator->evaluateDirectly($expr->args[0]->value));
                }

                throw new ConstExprEvaluationException('Not part of a generated Composer table.');
            },
        );

        try {
            foreach ($roots as $statement) {
                if ($statement instanceof Stmt\Expression && $statement->expr instanceof Node\Expr\Assign && $statement->expr->var instanceof Node\Expr\Variable && is_string($statement->expr->var->name)) {
                    $variables[$statement->expr->var->name] = (string) $evaluator->evaluateDirectly($statement->expr->expr);
                } elseif ($statement instanceof Stmt\Return_ && $statement->expr !== null) {
                    $value = $evaluator->evaluateDirectly($statement->expr);

                    return is_array($value) ? $value : [];
                }
            }
        } catch (ConstExprEvaluationException) {
            return [];
        }

        return [];
    }

    private function autoloadFile(string $name): ?string
    {
        if ($this->autoload === null) {
            $this->autoload = ['classmap' => [], 'psr4' => []];
            $vendor = $this->root . DIRECTORY_SEPARATOR . 'vendor';
            $manifest = $this->root . DIRECTORY_SEPARATOR . 'composer.json';

            if (is_file($manifest)) {
                $declared = json_decode((string) file_get_contents($manifest), true);
                $directory = is_array($declared) ? $declared['config']['vendor-dir'] ?? null : null;

                if (is_string($directory) && $directory !== '') {
                    $vendor = str_starts_with($directory, '/') ? $directory : $this->root . DIRECTORY_SEPARATOR . $directory;
                }
            }
            $this->autoload['classmap'] = array_change_key_case(self::composerTable($vendor . '/composer/autoload_classmap.php'));
            $psr4 = self::composerTable($vendor . '/composer/autoload_psr4.php');
            uksort($psr4, static fn (string $a, string $b): int => strlen($b) <=> strlen($a));
            $this->autoload['psr4'] = $psr4;
        }
        $mapped = $this->autoload['classmap'][strtolower($name)] ?? null;

        if (is_string($mapped) && is_file($mapped)) {
            return $mapped;
        }

        foreach ($this->autoload['psr4'] as $prefix => $directories) {
            if (!str_starts_with($name, $prefix)) {
                continue;
            }
            $relative = str_replace('\\', DIRECTORY_SEPARATOR, substr($name, strlen($prefix))) . '.php';

            foreach ((array) $directories as $directory) {
                $candidate = $directory . DIRECTORY_SEPARATOR . $relative;

                if (is_file($candidate)) {
                    return $candidate;
                }
            }
        }

        return null;
    }

    private function remember(string $name, string $file, Stmt\ClassLike $node, bool $project): void
    {
        $key = strtolower($name);
        $physicalFile = realpath($file) ?: $file;
        $previous = $this->classes[$key] ?? null;

        if ($previous !== null && ($previous['file'] !== $physicalFile || $previous['node']->getStartFilePos() !== $node->getStartFilePos())) {
            throw new EditException(
                sprintf(
                    'Duplicate class-like %s in %s and %s makes the project hierarchy ambiguous. Exclude inactive copies before a project-wide rename.',
                    $name,
                    $previous['file'],
                    $physicalFile,
                ),
            );
        }
        $this->classes[$key] ??= ['name' => $name, 'file' => $physicalFile, 'node' => $node, 'project' => $project];
    }
}
