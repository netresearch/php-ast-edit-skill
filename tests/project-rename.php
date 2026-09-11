<?php

declare(strict_types=1);

// rename_method across a project: the hierarchy from the sources and Composer's tables, the
// call sites from a ReferenceFinder. Offline cases use a finder that reports every call of
// the name without type information, which is enough to exercise planning and every refusal.
// With PHP_AST_EDIT_PHPACTOR pointing at the pinned PHAR, one case runs the real resolver.
require_once dirname(__DIR__) . '/vendor/autoload.php';

use Netresearch\PhpAstEdit\Doctor;
use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\PhpactorReferenceFinder;
use Netresearch\PhpAstEdit\ReferenceFinder;
use PhpParser\Node;
use PhpParser\NodeFinder;
use PhpParser\ParserFactory;

const BASE_FILE = 'src/Base.php';
const USE_FILE = 'src/Use1.php';
const CALLABLES_FILE = 'config/callables.php';

$failures = [];
$count = 0;
$base = sys_get_temp_dir() . '/php-ast-project-rename-' . bin2hex(random_bytes(6));

final class CallsByName implements ReferenceFinder
{
    public int $queries = 0;

    /** @param list<array{file: string, line: int, text: string}> $risky */
    public function __construct(
        private readonly array $risky = [],
        private readonly ?array $override = null,
    ) {}

    public function references(string $root, string $class, string $member): array
    {
        ++$this->queries;

        if ($this->override !== null) {
            return ['references' => $this->override, 'risky' => $this->risky, 'resolver' => 'fixture'];
        }
        $sites = [];

        foreach (new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($root . '/src', FilesystemIterator::SKIP_DOTS),
        ) as $file) {
            $roots = (new ParserFactory())
                ->createForHostVersion()
                ->parse((string) file_get_contents((string) $file)) ?? [];
            $calls = (new NodeFinder())->find(
                $roots,
                static fn (
                    Node $node,
                ): bool => ($node instanceof Node\Expr\MethodCall || $node instanceof Node\Expr\StaticCall || $node instanceof Node\Expr\NullsafeMethodCall) && $node->name instanceof Node\Identifier && strcasecmp($node->name->toString(), $member) === 0,
            );

            foreach ($calls as $call) {
                $sites[] = [
                    'file' => (string) $file,
                    'start' => $call->name->getStartFilePos(),
                    'end' => $call->name->getEndFilePos() + 1,
                    'line' => $call->getStartLine(),
                ];
            }
        }

        return ['references' => $sites, 'risky' => $this->risky, 'resolver' => 'fixture'];
    }
}

function projectCase(string $name, callable $check): void
{
    global $failures, $count;
    ++$count;

    try {
        $check();
    } catch (Throwable $failure) {
        $failures[] = $name . ': ' . $failure->getMessage();
    }
}

function projectAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

/** @param array<string, string> $files */
function projectFixture(string $name, array $files): string
{
    global $base;
    $root = $base . '/' . $name;

    foreach ($files as $path => $content) {
        @mkdir(dirname($root . '/' . $path), 0700, true);
        file_put_contents($root . '/' . $path, $content);
    }
    exec('git -C ' . escapeshellarg($root) . ' init -q 2>&1', $output, $status);
    projectAssert($status === 0, 'git init failed');

    return $root;
}

function projectRename(
    string $root,
    string $file,
    string $select,
    string $to,
    ?ReferenceFinder $finder,
): array {
    return (new Editor($finder))->apply(
        [
            'report' => 'compact',
            'files' => [
                [
                    'path' => $root . '/' . $file,
                    'edits' => [
                        [
                            'target' => ['select' => $select],
                            'operation' => 'rename_method',
                            'to' => $to,
                        ],
                    ],
                ],
            ],
        ],
    );
}

function projectRefusal(callable $call): string
{
    try {
        $call();
    } catch (EditException $refusal) {
        return $refusal->getMessage();
    }

    throw new RuntimeException('expected a refusal');
}

$hierarchy = [
    'src/Contract.php' => "<?php\nnamespace App;\ninterface Contract\n{\n    public function fetch(): int;\n}\n",
    BASE_FILE => "<?php\nnamespace App;\nclass Base implements Contract\n{\n    public function fetch(): int\n    {\n        return 1;\n    }\n}\n",
    'src/Child.php' => "<?php\nnamespace App;\nclass Child extends Base\n{\n    public function fetch(): int\n    {\n        return parent::fetch() + 1;\n    }\n}\n",
    'src/Leaf.php' => "<?php\nnamespace App;\nclass Leaf extends Base\n{\n}\n",
    'src/Use1.php' => "<?php\nnamespace App;\nfinal class Use1\n{\n    public function run(Contract \$c, Leaf \$l): int\n    {\n        return \$c->fetch() + \$l->fetch() + (new Child())->fetch();\n    }\n}\n",
    'config/Services.yaml' => "services:\n  App\\Base:\n    calls:\n      - fetch\n",
];

try {
    projectCase(
        'a public method in a hierarchy is renamed across every declaration and call',
        function () use ($hierarchy): void {
            $root = projectFixture('hierarchy', $hierarchy);
            $finder = new CallsByName();
            $result = projectRename($root, BASE_FILE, 'method:Base::fetch', 'load', $finder);
            $rename = $result['renames'][0] ?? [];
            projectAssert(
                ($rename['declarations'] ?? null) === 3,
                'declarations: ' . json_encode($rename),
            );
            projectAssert(
                ($rename['references'] ?? null) === 4,
                'references: ' . json_encode($rename),
            );
            projectAssert(
                $finder->queries === 1,
                'queried ' . $finder->queries . ' times; the interface alone covers the family',
            );

            foreach (['Contract', 'Base', 'Child', 'Use1'] as $class) {
                $source = (string) file_get_contents($root . '/src/' . $class . '.php');
                projectAssert(
                    !str_contains($source, 'fetch') && str_contains($source, 'load'),
                    $class . ' still says fetch',
                );
            }
            projectAssert(
                !isset($result['open']),
                'open without literals: ' . json_encode($result['open'] ?? null),
            );
            projectAssert(
                ($rename['notRenamed'] ?? []) === ['config/Services.yaml:4'],
                'yaml mention not listed: ' . json_encode($rename['notRenamed'] ?? null),
            );
        },
    );

    projectCase(
        'without a resolver the refusal says why the project is needed and how to set it up',
        function () use ($hierarchy): void {
            $root = projectFixture('no-resolver', $hierarchy);
            putenv(PhpactorReferenceFinder::ENVIRONMENT);
            $message = projectRefusal(
                static fn () => projectRename($root, BASE_FILE, 'method:Base::fetch', 'load', null),
            );
            projectAssert(
                str_contains($message, 'extends or implements'),
                'reason missing: ' . $message,
            );
            projectAssert(
                str_contains($message, PhpactorReferenceFinder::SHA256) && str_contains($message, '"phpactor"'),
                'setup missing: ' . $message,
            );
            projectAssert(
                str_contains((string) file_get_contents($root . '/' . BASE_FILE), 'fetch'),
                'file changed on refusal',
            );
        },
    );

    projectCase(
        'a method whose declaration also lives in a vendor class is refused',
        function (): void {
            $root = projectFixture(
                'vendor',
                [
                    'composer.json' => '{"autoload":{"psr-4":{"App\\\\":"src/"}}}',
                    'vendor/composer/autoload_psr4.php' => "<?php\n\$vendorDir = dirname(__DIR__);\nreturn array('Acme\\\\' => array(\$vendorDir . '/acme/src'));\n",
                    'vendor/acme/src/Entity.php' => "<?php\nnamespace Acme;\nabstract class Entity\n{\n    public function getUid(): int\n    {\n        return 0;\n    }\n}\n",
                    'src/Model.php' => "<?php\nnamespace App;\nfinal class Model extends \\Acme\\Entity\n{\n    public function getUid(): int\n    {\n        return 1;\n    }\n}\n",
                    '.gitignore' => "vendor/\n",
                ],
            );
            $message = projectRefusal(
                static fn () => projectRename(
                    $root,
                    'src/Model.php',
                    'method:Model::getUid',
                    'uid',
                    new CallsByName(),
                ),
            );
            projectAssert(
                str_contains($message, 'Acme\Entity::getUid') && str_contains($message, 'outside the project (vendor)'),
                $message,
            );
        },
    );

    projectCase(
        'an ancestor nobody can find is a refusal, not an empty ancestor',
        function (): void {
            $root = projectFixture(
                'missing',
                [
                    'src/Model.php' => "<?php\nnamespace App;\nclass Model extends \\Gone\\Base\n{\n    public function fetch(): int\n    {\n        return 1;\n    }\n}\n",
                ],
            );
            $message = projectRefusal(
                static fn () => projectRename(
                    $root,
                    'src/Model.php',
                    'method:Model::fetch',
                    'load',
                    new CallsByName(),
                ),
            );
            projectAssert(
                str_contains($message, 'Gone\Base') && str_contains($message, 'unknown'),
                $message,
            );
        },
    );

    projectCase(
        'a new name the hierarchy already declares is refused',
        function () use ($hierarchy): void {
            $root = projectFixture(
                'collision',
                [
                    ...$hierarchy,
                    'src/Child.php' => str_replace(
                        '}' . "\n" . '}',
                        "}\n    public function load(): int\n    {\n        return 2;\n    }\n}",
                        $hierarchy['src/Child.php'],
                    ),
                ],
            );
            $message = projectRefusal(
                static fn () => projectRename($root, BASE_FILE, 'method:Base::fetch', 'load', new CallsByName()),
            );
            projectAssert(str_contains($message, 'already declares load'), $message);
        },
    );

    projectCase(
        'a call the resolver could not attribute stops the rename and is named',
        function () use ($hierarchy): void {
            $root = projectFixture('risky', $hierarchy);
            $finder = new CallsByName(
                [['file' => $root . '/' . USE_FILE, 'line' => 7, 'text' => '$x->fetch()']],
            );
            $message = projectRefusal(
                static fn () => projectRename($root, BASE_FILE, 'method:Base::fetch', 'load', $finder),
            );
            projectAssert(
                str_contains($message, 'Use1.php:7') && str_contains($message, 'receiver type'),
                $message,
            );
            projectAssert(
                str_contains((string) file_get_contents($root . '/' . BASE_FILE), 'fetch'),
                'file changed on refusal',
            );
        },
    );

    projectCase(
        'a resolver offset that is not a method name writes nothing',
        function () use ($hierarchy): void {
            $root = projectFixture('wrong-offset', $hierarchy);
            $finder = new CallsByName(
                [],
                [['file' => $root . '/' . USE_FILE, 'start' => 20, 'end' => 25, 'line' => 3]],
            );
            $message = projectRefusal(
                static fn () => projectRename($root, BASE_FILE, 'method:Base::fetch', 'load', $finder),
            );
            projectAssert(str_contains($message, 'nothing was changed'), $message);

            foreach (['Base', 'Use1', 'Contract'] as $class) {
                projectAssert(
                    str_contains(
                        (string) file_get_contents($root . '/src/' . $class . '.php'),
                        'fetch',
                    ),
                    $class . ' changed on refusal',
                );
            }
        },
    );

    projectCase(
        'a private method in a class with a parent goes through the project, alone',
        function (): void {
            $root = projectFixture(
                'private',
                [
                    BASE_FILE => "<?php\nnamespace App;\nclass Base\n{\n    private function key(): string\n    {\n        return 'base';\n    }\n}\n",
                    'src/Child.php' => "<?php\nnamespace App;\nfinal class Child extends Base\n{\n    private function key(): string\n    {\n        return 'child';\n    }\n\n    public function run(): string\n    {\n        return \$this->key();\n    }\n}\n",
                ],
            );
            $result = projectRename(
                $root,
                'src/Child.php',
                'method:Child::key',
                'keyFor',
                new CallsByName([], []),
            );
            projectAssert(
                ($result['renames'][0]['declarations'] ?? null) === 1,
                json_encode($result['renames'] ?? null),
            );
            projectAssert(
                str_contains((string) file_get_contents($root . '/' . BASE_FILE), 'function key()'),
                'the parent\'s private method was renamed too',
            );
        },
    );

    projectCase(
        'what one file decides never reaches the resolver',
        function (): void {
            $root = projectFixture(
                'lexical',
                [
                    'src/Plain.php' => "<?php\nnamespace App;\nfinal class Plain\n{\n    public function a(): int\n    {\n        return \$this->b();\n    }\n\n    private function b(): int\n    {\n        return 1;\n    }\n}\n",
                ],
            );
            $finder = new CallsByName();
            $result = projectRename($root, 'src/Plain.php', 'method:Plain::b', 'c', $finder);
            projectAssert(
                $finder->queries === 0 && !isset($result['renames']),
                'lexical rename asked the resolver',
            );
            projectAssert(
                str_contains((string) file_get_contents($root . '/src/Plain.php'), '$this->c()'),
                'lexical rename did not happen',
            );
        },
    );

    projectCase(
        'an accessor lists the Fluid templates that read its property',
        function (): void {
            $root = projectFixture(
                'fluid',
                [
                    'src/Item.php' => "<?php\nnamespace App;\nclass Item\n{\n    public function getLabel(): string\n    {\n        return 'x';\n    }\n}\n",
                    'Resources/Private/Templates/List.html' => "<f:for each=\"{items}\" as=\"item\">\n  {item.label}\n</f:for>\n",
                ],
            );
            $result = projectRename(
                $root,
                'src/Item.php',
                'method:Item::getLabel',
                'label',
                new CallsByName(),
            );
            projectAssert(
                ($result['renames'][0]['notRenamed'] ?? []) === ['Resources/Private/Templates/List.html:2'],
                json_encode($result['renames'][0]['notRenamed'] ?? null),
            );
        },
    );

    projectCase(
        'string literals that read the old name are listed by scope, and the listed edits set them',
        function () use ($hierarchy): void {
            $root = projectFixture(
                'literals',
                [
                    ...$hierarchy,
                    'tests/FetchTest.php' => "<?php\nnamespace App\\Tests;\nfinal class FetchTest\n{\n    public function testIt(object \$mock, object \$c): array\n    {\n        \$mock->method('fetch');\n\n        return [[\$c, 'fetch'], 'fetcher', 'Fetch'];\n    }\n}\n",
                    CALLABLES_FILE => "<?php\nreturn ['fetch'];\n",
                    'tests/Twin.php' => "<?php\nnamespace A {\nfinal class Twin\n{\n    public const M = 'fetch';\n}\n}\nnamespace B {\nfinal class Twin\n{\n    public const M = 'fetch';\n}\n}\n",
                ],
            );
            $result = projectRename($root, BASE_FILE, 'method:Base::fetch', 'load', new CallsByName());
            $rename = $result['renames'][0] ?? [];
            projectAssert(
                ($rename['literals'] ?? null) == [
                    [
                        'file' => CALLABLES_FILE,
                        'refs' => ['stmts[0].expr.items[0].value'],
                        'lines' => [2],
                    ],
                    [
                        'file' => 'tests/FetchTest.php',
                        'select' => 'class:FetchTest',
                        'lines' => [7, 9],
                        'refs' => [
                            'stmts[0].stmts[0].stmts[0].stmts[0].expr.args[0].value',
                            'stmts[0].stmts[0].stmts[0].stmts[1].expr.items[0].value.items[1].value',
                        ],
                    ],
                    [
                        'file' => 'tests/Twin.php',
                        'refs' => [
                            'stmts[0].stmts[0].stmts[0].consts[0].value',
                            'stmts[1].stmts[0].stmts[0].consts[0].value',
                        ],
                        'lines' => [5, 11],
                    ],
                ] && ($rename['literalsCount'] ?? null) === 5,
                json_encode($rename),
            );
            projectAssert(
                array_key_first($result) === 'open' && str_contains(
                    (string) $result['open'],
                    '5 string literal(s) in 3 file(s) still read fetch (renames[0].literals)',
                ),
                json_encode($result['open'] ?? null),
            );
            projectAssert(
                str_contains(
                    (string) ($rename['literalsMeans'] ?? ''),
                    "match \"'fetch'\", php \"'load'\"",
                ),
                (string) ($rename['literalsMeans'] ?? 'no literalsMeans'),
            );
            // Literals set in the same apply are not open any more.
            $together = projectFixture(
                'literals-together',
                [
                    ...$hierarchy,
                    'tests/FetchTest.php' => (string) file_get_contents($root . '/tests/FetchTest.php'),
                    'config/callables.php' => "<?php\nreturn ['fetch'];\n",
                    'tests/Twin.php' => (string) file_get_contents($root . '/tests/Twin.php'),
                ],
            );
            $both = (new Editor(new CallsByName()))->apply(
                [
                    'report' => 'compact',
                    'files' => [
                        [
                            'path' => $together . '/' . BASE_FILE,
                            'edits' => [
                                [
                                    'target' => ['select' => 'method:Base::fetch'],
                                    'operation' => 'rename_method',
                                    'to' => 'load',
                                ],
                            ],
                        ],
                        [
                            'path' => $together . '/tests/FetchTest.php',
                            'edits' => [
                                [
                                    'target' => ['select' => 'class:FetchTest'],
                                    'operation' => 'replace_expression',
                                    'match' => "'fetch'",
                                    'php' => "'load'",
                                ],
                            ],
                        ],
                    ],
                ],
            );
            projectAssert(
                str_contains(
                    (string) ($both['open'] ?? ''),
                    '3 string literal(s) in 2 file(s) still read fetch',
                ),
                json_encode($both['open'] ?? null),
            );
            (new Editor(null))->apply(
                [
                    'files' => [
                        [
                            'path' => $root . '/tests/FetchTest.php',
                            'edits' => [
                                [
                                    'target' => ['select' => $rename['literals'][1]['select']],
                                    'operation' => 'replace_expression',
                                    'match' => "'fetch'",
                                    'php' => "'load'",
                                ],
                            ],
                        ],
                        [
                            // One of two: a ref sets a literal alone, where the scope would set both.
                            'path' => $root . '/tests/Twin.php',
                            'edits' => [
                                [
                                    'target' => ['ref' => $rename['literals'][2]['refs'][0]],
                                    'operation' => 'set_string',
                                    'value' => 'load',
                                ],
                            ],
                        ],
                        [
                            'path' => $root . '/' . CALLABLES_FILE,
                            'edits' => [
                                [
                                    'target' => ['ref' => $rename['literals'][0]['refs'][0]],
                                    'operation' => 'set_string',
                                    'value' => 'load',
                                ],
                            ],
                        ],
                    ],
                ],
            );
            $test = (string) file_get_contents($root . '/tests/FetchTest.php');
            projectAssert(
                substr_count($test, "'load'") === 2 && str_contains($test, "'fetcher', 'Fetch'") && !str_contains($test, "'fetch'"),
                $test,
            );
            $twin = (string) file_get_contents($root . '/tests/Twin.php');
            projectAssert(
                strpos($twin, "'load'") < strpos($twin, "'fetch'") && substr_count($twin, "'fetch'") === 1,
                $twin,
            );
            projectAssert(
                (string) file_get_contents($root . '/' . CALLABLES_FILE) === "<?php\nreturn ['load'];\n",
                (string) file_get_contents($root . '/' . CALLABLES_FILE),
            );
        },
    );

    projectCase(
        'mocks: true sets the names PHPUnit mocks list and leaves every other literal listed',
        function () use ($hierarchy): void {
            $root = projectFixture(
                'mocks',
                [
                    ...$hierarchy,
                    'tests/UseTest.php' => "<?php\nnamespace App\\Tests;\nfinal class UseTest extends \\PHPUnit\\Framework\\TestCase\n{\n    #[\\PHPUnit\\Framework\\Attributes\\DataProvider('fetch')]\n    public function testIt(): void\n    {\n        \$a = \$this->createMock(\\App\\Base::class);\n        \$a->method('fetch')->willReturn(1);\n        \$b = \$this->getMockBuilder(\\App\\Base::class)->onlyMethods(['fetch', 'other'])->getMock();\n        \$c = \$this->createConfiguredMock(\\App\\Base::class, ['fetch' => 2]);\n        \$d = [\$a, 'fetch'];\n    }\n}\n",
                ],
            );
            $result = (new Editor(new CallsByName()))->apply(
                [
                    'report' => 'compact',
                    'files' => [
                        [
                            'path' => $root . '/' . BASE_FILE,
                            'edits' => [
                                [
                                    'target' => ['select' => 'method:Base::fetch'],
                                    'operation' => 'rename_method',
                                    'to' => 'load',
                                    'mocks' => true,
                                ],
                            ],
                        ],
                    ],
                ],
            );
            $rename = $result['renames'][0] ?? [];
            $test = (string) file_get_contents($root . '/tests/UseTest.php');
            projectAssert(($rename['mocksSet'] ?? null) === 3, json_encode($rename));
            projectAssert(
                str_contains($test, "->method('load')") && str_contains($test, "onlyMethods(['load', 'other'])") && str_contains($test, "['load' => 2]"),
                $test,
            );
            projectAssert(
                str_contains($test, "DataProvider('fetch')") && str_contains($test, "[\$a, 'fetch']"),
                'a literal outside a mock list changed: ' . $test,
            );
            projectAssert(
                ($rename['literalsCount'] ?? null) === 2 && str_contains((string) ($result['open'] ?? ''), '2 string literal(s) in 1 file(s)'),
                json_encode([$rename['literalsCount'] ?? null, $result['open'] ?? null]),
            );
        },
    );

    projectCase(
        'a PHAR that is not the pinned release is refused, and doctor says so',
        function () use ($hierarchy): void {
            $root = projectFixture(
                'doctor',
                [
                    ...$hierarchy,
                    '.php-ast-edit.json' => '{"phpactor": "phpactor.phar"}',
                    'phpactor.phar' => '<?php echo 1;',
                ],
            );
            putenv(PhpactorReferenceFinder::ENVIRONMENT);
            $message = projectRefusal(static fn () => new PhpactorReferenceFinder($root . '/phpactor.phar'));
            projectAssert(
                str_contains($message, 'is not Phpactor ' . PhpactorReferenceFinder::RELEASE),
                $message,
            );
            $report = (new Doctor())->examine($root);
            projectAssert(
                $report['resolver']['status'] === 'wrong_release',
                json_encode($report['resolver']),
            );
            unlink($root . '/.php-ast-edit.json');
            projectAssert(
                (new Doctor())->examine($root)['resolver']['status'] === 'missing',
                'doctor did not report a missing resolver',
            );
        },
    );

    projectCase(
        'a change of case only is not a collision with itself',
        function () use ($hierarchy): void {
            $root = projectFixture('case-only', $hierarchy);
            $result = projectRename($root, BASE_FILE, 'method:Base::fetch', 'Fetch', new CallsByName());
            projectAssert(
                ($result['renames'][0]['declarations'] ?? null) === 3,
                json_encode($result['renames'] ?? null),
            );
            projectAssert(
                str_contains(
                    (string) file_get_contents($root . '/src/Child.php'),
                    'function Fetch(',
                ),
                'Child kept the old case',
            );
        },
    );

    projectCase(
        'every index sees the project classes, however many came before it',
        function () use ($hierarchy): void {
            $root = projectFixture('many-indexes', $hierarchy);

            // Object ids are reused as soon as an index is freed; a cache keyed by them would
            // hand a later index an earlier one's "already scanned" and an empty class list.
            for ($round = 0; $round < 50; ++$round) {
                $index = Netresearch\PhpAstEdit\ProjectIndex::for($root . '/' . BASE_FILE);
                projectAssert(
                    count($index->projectClasses()) === 5,
                    'round ' . $round . ' saw ' . count($index->projectClasses()) . ' classes',
                );
                unset($index);
            }
        },
    );

    $phar = getenv('PHP_AST_EDIT_PHPACTOR_TEST');

    if (is_string($phar) && is_file($phar)) {
        projectCase(
            'Phpactor resolves the hierarchy, the interface call included',
            function () use ($hierarchy, $phar): void {
                $root = projectFixture(
                    'phpactor',
                    [...$hierarchy, 'composer.json' => '{"autoload":{"psr-4":{"App\\\\":"src/"}}}'],
                );
                exec('git -C ' . escapeshellarg($root) . ' add -A');
                $result = projectRename(
                    $root,
                    BASE_FILE,
                    'method:Base::fetch',
                    'load',
                    new PhpactorReferenceFinder($phar),
                );
                projectAssert(
                    ($result['renames'][0]['references'] ?? null) === 4,
                    json_encode($result['renames'] ?? null),
                );
                projectAssert(
                    !str_contains((string) file_get_contents($root . '/' . USE_FILE), 'fetch'),
                    'Use1 still calls fetch',
                );
            },
        );
    }
} finally {
    exec('rm -rf ' . escapeshellarg($base));
}

foreach ($failures as $failure) {
    fwrite(STDERR, 'FAIL: ' . $failure . "\n");
}
echo ($failures === [] ? 'OK' : 'FAIL') . ': ' . ($count - count($failures)) . ' of ' . $count . " project-rename cases.\n";
exit($failures === [] ? 0 : 1);
