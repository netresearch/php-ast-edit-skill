<?php

declare(strict_types=1);

/**
 * Table-driven grammar and operation coverage.
 *
 * Every case declares the files it starts from, the apply document it sends, and what must
 * hold afterwards. The matrix walks the PHP grammar (file root, namespace, use, class,
 * interface, trait, enum, members, params, types, modifiers, statements, expressions,
 * arrays, match, attributes, anonymous classes and closures, comments, empty containers)
 * plus the transaction failure modes.
 */
$root = dirname(__DIR__);
$autoload = $root . '/vendor/autoload.php';

if (!is_file($autoload)) {
    fwrite(
        STDERR,
        "SKIP: vendor/autoload.php missing; run composer install to execute the matrix.\n",
    );
    exit(0);
}
require_once $autoload;
use Netresearch\PhpAstEdit\Editor;

const EMPTY_CLASS = "<?php\nclass Foo\n{\n}\n";
const EMPTY_FUNCTION = "<?php\nfunction foo()\n{\n}\n";
const ONE_LINE_CLASS = "<?php\nclass Foo {}\n";
const CLASS_REF = 'stmts[0]';
const CLASS_NAME_REF = 'stmts[0].name';
const FIRST_MEMBER_REF = 'stmts[0].stmts[0]';
const FIRST_PARAM_REF = 'stmts[0].params[0]';
const USE_ITEM = 'C\D as E';

/**
 * @var list<array{
 *   name: string,
 *   files?: array<string, string>,
 *   edits?: list<array<string, mixed>>,
 *   document?: callable(array<string, string>): array,
 *   contains?: list<array{0: string, 1: string}>,
 *   notContains?: list<array{0: string, 1: string}>,
 *   inspect?: array<string, int>,
 *   unchanged?: list<string>,
 *   absent?: list<string>,
 *   present?: list<string>,
 *   error?: string
 * }>
 */
/**
 * Notation helpers. Spelling out `'files' => ['a.php' => …]` and `'contains' => [['a.php',
 * …]]` in every row repeats the same token sequence dozens of times — duplication in the
 * literal sense and noise in the reading sense.
 */
/** Depth-first removal: a case may create directories several levels deep. */
function removeTree(string $directory): void
{
    foreach (glob($directory . '/*') ?: [] as $entry) {
        if (is_dir($entry)) {
            removeTree($entry);

            continue;
        }
        @unlink($entry);
    }
    @rmdir($directory);
}

/**
 * A transaction document, so a case names its file specs and nothing else. Repeating the
 * `['files' => [[ … ]]]` scaffolding once per case is duplication in the literal sense and
 * noise in the reading sense.
 *
 * @param array<string, mixed> ...$fileSpecs
 */
/**
 * One edit, named positionally. Spelling out `['target' => ['ref' => …], 'operation' => …]`
 * per case is seven lines of the same shape once the canonical printer has broken it up.
 *
 * @param array<string, mixed> $rest anything else the operation needs — php, value, property, …
 */
function at(string $ref, string $operation, array $rest = [], ?string $kind = null): array
{
    return ['target' => array_filter(['ref' => $ref, 'kind' => $kind]), 'operation' => $operation] + $rest;
}
function tx(array ...$fileSpecs): array
{
    return ['files' => array_values($fileSpecs)];
}
function src(string $php): array
{
    return ['a.php' => $php];
}

/** @return list<array{0: string, 1: string}> */
function inA(string ...$needles): array
{
    return array_map(static fn (string $needle): array => ['a.php', $needle], $needles);
}
$cases = [
    // ---- Empty containers: the operations that were impossible before ------------------
    [
        'name' => 'first method into an empty class',
        'files' => src(EMPTY_CLASS),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'stmts', 'php' => 'public function bar(): void {}'],
            ),
        ],
        'contains' => inA('public function bar(): void'),
    ],
    [
        'name' => 'first statement into an empty function body',
        'files' => src(EMPTY_FUNCTION),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'stmts', 'parseAs' => 'stmt', 'php' => 'return 1;'],
            ),
        ],
        'contains' => inA('return 1;'),
    ],
    [
        'name' => 'first parameter into an empty parameter list',
        'files' => src(EMPTY_FUNCTION),
        'edits' => [at(CLASS_REF, 'add_parameter', ['php' => 'private readonly ?Foo $foo = null'])],
        'contains' => inA('function foo(private readonly ?Foo $foo = null)'),
    ],
    [
        'name' => 'first item into an empty array',
        'files' => src("<?php\n\$a = [];\n"),
        'edits' => [at('stmts[0].expr.expr', 'insert_into', ['property' => 'items', 'php' => "'k' => 1"])],
        'contains' => inA("'k' => 1"),
    ],
    // ---- File lifecycle ----------------------------------------------------------------
    [
        'name' => 'create_file builds a file from construction syntax and then edits its AST',
        'files' => [],
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['dir'] . '/Created.php',
                'mode' => 'create',
                'php' => '<?php declare(strict_types=1); namespace Demo; final class Created {}',
                'edits' => [at('stmts[1].stmts[0]', 'add_member', ['php' => 'public const VERSION = 1;'])],
            ],
        ),
        'present' => ['Created.php'],
        'contains' => [['Created.php', 'public const VERSION = 1;'], ['Created.php', 'namespace Demo;']],
    ],
    [
        'name' => 'create_file refuses to clobber an existing file',
        'files' => src("<?php\n"),
        'document' => fn (
            array $p,
        ): array => tx(['path' => $p['a.php'], 'mode' => 'create', 'php' => '<?php class X {}']),
        'error' => 'FILE_EXISTS',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'delete_file removes a file under a sha guard',
        'files' => src("<?php\nclass Gone {}\n"),
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['a.php'],
                'mode' => 'delete',
                'sha256' => hash('sha256', "<?php\nclass Gone {}\n"),
            ],
        ),
        'absent' => ['a.php'],
    ],
    [
        'name' => 'delete_file rejects a stale sha',
        'files' => src("<?php\nclass Gone {}\n"),
        'document' => fn (
            array $p,
        ): array => tx(['path' => $p['a.php'], 'mode' => 'delete', 'sha256' => str_repeat('0', 64)]),
        'error' => 'STALE_SOURCE',
        'present' => ['a.php'],
    ],
    // ---- Class-like grammar -------------------------------------------------------------
    [
        'name' => 'interface gains a method signature',
        'files' => src("<?php\ninterface I\n{\n}\n"),
        'edits' => [at(CLASS_REF, 'add_member', ['php' => 'public function run(): void;'])],
        'contains' => inA('public function run(): void;'),
    ],
    [
        'name' => 'trait gains a property',
        'files' => src("<?php\ntrait T\n{\n}\n"),
        'edits' => [at(CLASS_REF, 'add_member', ['php' => 'private static array $cache = [];'])],
        'contains' => inA('private static array $cache = [];'),
    ],
    [
        'name' => 'enum gains a case',
        'files' => src("<?php\nenum Status: string\n{\n}\n"),
        'edits' => [at(CLASS_REF, 'add_member', ['php' => "case Draft = 'draft';"])],
        'contains' => inA("case Draft = 'draft';"),
    ],
    [
        'name' => 'class gains an implements entry, an attribute and a docblock',
        'files' => src(EMPTY_CLASS),
        'edits' => [
            at(CLASS_REF, 'add_implements', ['php' => 'Countable']),
            at(CLASS_REF, 'add_attribute', ['php' => '#[Immutable]']),
            at(CLASS_REF, 'set_doc_comment', ['value' => "A value object.\n\n@internal"]),
        ],
        'contains' => [
            ['a.php', 'class Foo implements Countable'],
            ['a.php', '#[Immutable]'],
            ['a.php', '* A value object.'],
            ['a.php', '* @internal'],
        ],
    ],
    [
        'name' => 'class extends is set through replace_child',
        'files' => src("<?php\nclass Foo extends Bar\n{\n}\n"),
        'edits' => [at(CLASS_REF, 'set_extends', ['php' => 'Baz'])],
        'contains' => inA('class Foo extends Baz'),
        'notContains' => inA('extends Bar'),
    ],
    [
        'name' => 'trait use is added to a class',
        'files' => src(EMPTY_CLASS),
        'edits' => [at(CLASS_REF, 'add_member', ['php' => 'use LoggerAwareTrait;'])],
        'contains' => inA('use LoggerAwareTrait;'),
    ],
    // ---- Namespace and use statements ---------------------------------------------------
    [
        'name' => 'use statement is inserted at the file root',
        'files' => src("<?php\nnamespace App;\n\nclass Foo\n{\n}\n"),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                [
                    'property' => 'stmts',
                    'parseAs' => 'stmt',
                    'position' => 'start',
                    'php' => 'use App\Support\Clock;',
                ],
            ),
        ],
        'contains' => inA('use App\Support\Clock;'),
    ],
    [
        'name' => 'a second use item joins an existing group',
        'files' => src("<?php\nuse A\\B;\n"),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'uses', 'parseAs' => 'use', 'php' => USE_ITEM],
            ),
        ],
        'contains' => inA(USE_ITEM),
    ],
    // ---- Signatures, types, modifiers ----------------------------------------------------
    [
        'name' => 'union return type replaces a scalar one',
        'files' => src(
            "<?php\nclass Foo\n{\n    public function bar(): string\n    {\n        return '';\n    }\n}\n",
        ),
        'edits' => [at(FIRST_MEMBER_REF, 'set_return_type', ['php' => 'string|int'])],
        'contains' => inA('public function bar(): string|int'),
    ],
    [
        'name' => 'parameter type becomes an intersection type',
        'files' => src("<?php\nfunction foo(Countable \$c) {}\n"),
        'edits' => [at(FIRST_PARAM_REF, 'set_type', ['php' => 'Countable&Traversable'])],
        'contains' => inA('Countable&Traversable $c'),
    ],
    [
        'name' => 'visibility modifier is changed without touching anything else',
        'files' => src("<?php\nclass Foo\n{\n    public function bar(): void\n    {\n    }\n}\n"),
        'edits' => [at(FIRST_MEMBER_REF, 'set_visibility', ['value' => 'protected'])],
        'contains' => inA('protected function bar(): void'),
    ],
    [
        'name' => 'a nullable type is removed from a slot',
        'files' => src("<?php\nfunction foo(): ?int\n{\n    return null;\n}\n"),
        'edits' => [at('stmts[0].returnType', 'delete_node', [])],
        'notContains' => inA('?int'),
    ],
    // ---- Expressions, arrays, match, closures, anonymous classes --------------------------
    [
        'name' => 'match arm is appended to a match expression',
        'files' => src("<?php\n\$r = match (\$x) {\n    1 => 'one',\n};\n"),
        'edits' => [
            at(
                'stmts[0].expr.expr',
                'insert_into',
                ['property' => 'arms', 'php' => "default => 'other'"],
            ),
        ],
        'contains' => inA("default => 'other'"),
    ],
    [
        'name' => 'closure use clause gains a by-reference binding',
        'files' => src("<?php\n\$f = function () use (\$a) {\n};\n"),
        'edits' => [at('stmts[0].expr.expr', 'insert_into', ['property' => 'uses', 'php' => '&$carry'])],
        'contains' => inA('use ($a, &$carry)'),
    ],
    [
        'name' => 'anonymous class gains a member',
        'files' => src("<?php\n\$o = new class {\n};\n"),
        'edits' => [at('stmts[0].expr.expr.class', 'add_member', ['php' => 'public int $n = 0;'])],
        'contains' => inA('public int $n = 0;'),
    ],
    [
        'name' => 'a named argument is added to a call',
        'files' => src("<?php\nfoo(1);\n"),
        'edits' => [at('stmts[0].expr', 'insert_into', ['property' => 'args', 'php' => 'flag: true'])],
        'contains' => inA('foo(1, flag: true)'),
    ],
    [
        'name' => 'catch clause is added to a try statement',
        'files' => src("<?php\ntry {\n    foo();\n} catch (RuntimeException \$e) {\n}\n"),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'catches', 'php' => 'catch (LogicException $e) { throw $e; }'],
            ),
        ],
        'contains' => inA('catch (LogicException $e)'),
    ],
    [
        'name' => 'replace_node swaps a parameter node',
        'files' => src("<?php\nfunction foo(int \$a) {}\n"),
        'edits' => [at(FIRST_PARAM_REF, 'replace_node', ['php' => 'string ...$rest'])],
        'contains' => inA('function foo(string ...$rest)'),
    ],
    [
        'name' => 'move_node relocates a method to another class in the same file',
        'files' => src("<?php\nclass A\n{\n    public function m(): void\n    {\n    }\n}\nclass B\n{\n}\n"),
        'edits' => [
            at(
                FIRST_MEMBER_REF,
                'move_node',
                ['into' => ['ref' => 'stmts[1]', 'property' => 'stmts', 'position' => 'end']],
            ),
        ],
        'contains' => inA("class B\n{\n    public function m(): void"),
        'notContains' => inA("class A\n{\n    public function m"),
    ],
    // ---- Comments -------------------------------------------------------------------------
    [
        'name' => 'existing docblock is replaced, not duplicated',
        'files' => src(
            "<?php\nclass Foo\n{\n    /** Old text. */\n    public function bar(): void\n    {\n    }\n}\n",
        ),
        'edits' => [at(FIRST_MEMBER_REF, 'set_doc_comment', ['value' => 'New text.'])],
        'contains' => inA('New text.'),
        'notContains' => inA('Old text.'),
    ],
    [
        'name' => 'removing a docblock leaves the other comments alone',
        'files' => src("<?php\n// keep me\n/** drop me */\nfunction foo() {}\n"),
        'edits' => [at(CLASS_REF, 'remove_doc_comment', [])],
        'contains' => inA('// keep me'),
        'notContains' => inA('drop me'),
    ],
    [
        'name' => 'docblock is removed',
        'files' => src("<?php\n/** Doc. */\nfunction foo() {}\n"),
        'edits' => [at(CLASS_REF, 'remove_doc_comment', [])],
        'notContains' => inA('Doc.'),
    ],
    [
        'name' => 'a string literal may contain a PHP open tag',
        'files' => src("<?php\n\$t = '';\n"),
        'edits' => [
            at(
                'stmts[0].expr.expr',
                'replace_expression',
                ['php' => '\'<?xml version="1.0"?' . '>\''],
            ),
        ],
        'contains' => inA('<?xml version="1.0"?' . '>'),
    ],
    [
        'name' => 'a snippet that leaves the PHP context is rejected',
        'files' => src(EMPTY_FUNCTION),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                [
                    'property' => 'stmts',
                    'parseAs' => 'stmt',
                    'php' => '$a = 1; ?' . '> text <?php $b = 2;',
                ],
            ),
        ],
        'error' => 'must not leave the PHP context',
        'unchanged' => ['a.php'],
    ],
    // ---- Shared sub node names must resolve against the node, not the name -------------------
    [
        'name' => 'stmts on a function is a statement list, not a member list',
        'files' => src(EMPTY_FUNCTION),
        'edits' => [at(CLASS_REF, 'insert_into', ['property' => 'stmts', 'php' => 'return 1;'])],
        'contains' => inA('return 1;'),
    ],
    [
        'name' => 'uses on a use statement imports a name',
        'files' => src("<?php\nuse A\\B;\n"),
        'edits' => [at(CLASS_REF, 'insert_into', ['property' => 'uses', 'php' => USE_ITEM])],
        'contains' => inA(USE_ITEM),
    ],
    [
        'name' => 'uses on a closure binds a variable',
        'files' => src("<?php\n\$f = function () use (\$a) {\n};\n"),
        'edits' => [at('stmts[0].expr.expr', 'insert_into', ['property' => 'uses', 'php' => '&$b'])],
        'contains' => inA('use ($a, &$b)'),
    ],
    [
        'name' => 'vars on unset is an expression, on static it is a static variable',
        'files' => src("<?php\nunset(\$a);\n"),
        'edits' => [at(CLASS_REF, 'insert_into', ['property' => 'vars', 'php' => '$b'])],
        'contains' => inA('unset($a, $b)'),
    ],
    [
        'name' => 'inserting into a single slot is refused with a usable message',
        'files' => src("<?php\nfunction foo() {}\n"),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'returnType', 'parseAs' => 'type', 'php' => 'int'],
            ),
        ],
        'error' => 'holds a single node, not a list',
        'unchanged' => ['a.php'],
    ],
    // ---- The synthetic host must hold what the extractor reaches for -------------------------
    [
        'name' => 'a snippet that escapes its synthetic host is refused, not crashed on',
        'files' => src(EMPTY_CLASS),
        'edits' => [at(CLASS_REF, 'add_attribute', ['php' => 'echo 1;'])],
        'error' => 'does not fit the "attribute" context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'a member snippet that closes the class is refused',
        'files' => src(EMPTY_CLASS),
        'edits' => [at(CLASS_REF, 'add_member', ['php' => '} echo 1; class Y {'])],
        'error' => 'does not fit the',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'create requires the open tag rather than shifting every offset',
        'files' => [],
        'document' => fn (
            array $p,
        ): array => tx(['path' => $p['dir'] . '/NoTag.php', 'mode' => 'create', 'php' => 'class NoTag {}']),
        'error' => 'must start with the <?php open tag',
        'absent' => ['NoTag.php'],
    ],
    [
        'name' => 'a slot that cannot be empty is refused by name',
        'files' => src("<?php\nfunction foo(int \$a) {}\n"),
        'edits' => [at(FIRST_PARAM_REF, 'delete_child', ['property' => 'var'])],
        'error' => 'cannot be empty',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'two creates under the same missing directory collide',
        'files' => [],
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['dir'] . '/deep/sub/A.php',
                'mode' => 'create',
                'php' => '<?php class A {}',
            ],
            [
                'path' => $p['dir'] . '/deep/../deep/sub/A.php',
                'mode' => 'create',
                'php' => '<?php class B {}',
            ],
        ),
        'error' => 'are the same file',
        'absent' => ['deep/sub/A.php'],
    ],
    // ---- Failure modes ---------------------------------------------------------------------
    [
        'name' => 'stale sha aborts before any write',
        'files' => src(ONE_LINE_CLASS),
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['a.php'],
                'sha256' => str_repeat('a', 64),
                'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'Bar'])],
            ],
        ),
        'error' => 'STALE_SOURCE',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'wrong expected kind aborts',
        'files' => src(ONE_LINE_CLASS),
        'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'Bar'], 'Stmt_Class')],
        'error' => 'resolves to Identifier',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'wrong expected name aborts',
        'files' => src(ONE_LINE_CLASS),
        'edits' => [at(CLASS_NAME_REF, 'set_name', ['expect' => ['name' => 'Nope'], 'value' => 'Bar'])],
        'error' => 'Expected node name Nope',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'detached target aborts the transaction',
        'files' => src("<?php\nfunction foo()\n{\n    \$a = 1;\n    \$b = 2;\n}\n"),
        'edits' => [
            at(FIRST_MEMBER_REF, 'delete_node', []),
            at(FIRST_MEMBER_REF, 'replace_statement', ['php' => '$c = 3;']),
        ],
        'error' => 'invalidated by an earlier edit',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'invalid contextual snippet aborts with the context named',
        'files' => src(ONE_LINE_CLASS),
        'edits' => [at(CLASS_REF, 'add_member', ['php' => 'return 1;'])],
        'error' => 'not valid in the "member" context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'unknown parseAs context is reported with the known list',
        'files' => src(ONE_LINE_CLASS),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'stmts', 'parseAs' => 'nonsense', 'php' => 'public int $a = 1;'],
            ),
        ],
        'error' => 'Unknown parseAs context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'unknown sub node is reported with the available slots',
        'files' => src(ONE_LINE_CLASS),
        'edits' => [
            at(
                CLASS_REF,
                'insert_into',
                ['property' => 'bogus', 'parseAs' => 'member', 'php' => 'public int $a = 1;'],
            ),
        ],
        'error' => 'has no sub node "bogus"',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'a failure in the third file leaves the first two untouched',
        'files' => [
            'a.php' => "<?php\nclass A {}\n",
            'b.php' => "<?php\nclass B {}\n",
            'c.php' => "<?php\nclass C {}\n",
        ],
        'document' => fn (array $p): array => tx(
            ['path' => $p['a.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'A1'])]],
            ['path' => $p['b.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'B1'])]],
            [
                'path' => $p['c.php'],
                'edits' => [at(CLASS_REF, 'add_member', ['php' => 'this is not php'])],
            ],
        ),
        'error' => 'not valid in the "member" context',
        'unchanged' => ['a.php', 'b.php', 'c.php'],
    ],
    [
        'name' => 'two spellings of one path are recognised as the same file',
        'files' => src("<?php\nclass A {}\n"),
        'document' => fn (array $p): array => tx(
            ['path' => $p['a.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'B'])]],
            [
                'path' => $p['dir'] . '/./a.php',
                'edits' => [at(CLASS_REF, 'add_member', ['php' => 'public int $n = 1;'])],
            ],
        ),
        'error' => 'are the same file',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'the same path may not appear twice in one transaction',
        'files' => src("<?php\nclass A {}\n"),
        'document' => fn (array $p): array => tx(
            ['path' => $p['a.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'A1'])]],
            ['path' => $p['a.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'A2'])]],
        ),
        'error' => 'Duplicate path',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'a multi-file transaction commits every file together',
        'files' => ['a.php' => "<?php\nclass A {}\n", 'b.php' => "<?php\nclass B {}\n"],
        'document' => fn (array $p): array => tx(
            ['path' => $p['a.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'A1'])]],
            ['path' => $p['b.php'], 'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'B1'])]],
        ),
        'contains' => [['a.php', 'class A1'], ['b.php', 'class B1']],
    ],
    [
        'name' => 'a method whose body contains "case " still goes into an enum as a method',
        'files' => src("<?php\nenum Status: string\n{\n    case Draft = 'draft';\n}\n"),
        'edits' => [
            at(
                CLASS_REF,
                'add_member',
                [
                    'php' => 'public function label(): string { switch ($this) { case self::Draft: return \'d\'; } return \'\'; }',
                ],
            ),
        ],
        'contains' => inA('public function label(): string', "case Draft = 'draft';"),
    ],
    [
        'name' => 'move_node refuses to move a node into its own subtree',
        'files' => src("<?php\nclass A\n{\n    public function m(): void\n    {\n    }\n}\n"),
        'edits' => [
            at(
                CLASS_REF,
                'move_node',
                ['into' => ['ref' => 'stmts[0].stmts[0]', 'property' => 'stmts']],
            ),
        ],
        'error' => 'its own subtree',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'an unparseable phpVersion is refused by name',
        'files' => src(ONE_LINE_CLASS),
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['a.php'],
                'phpVersion' => 'nope',
                'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'Bar'])],
            ],
        ),
        'error' => 'is not a PHP version',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'an inspect excerpt stays valid UTF-8 when truncated mid-character',
        'files' => src("<?php\n\$s = \"" . str_repeat("ä", 200) . "\";\n"),
        'edits' => [at('stmts[0].expr.expr', 'replace_expression', ['php' => "'short'"])],
        'contains' => inA("'short'"),
        'inspect' => ['line' => 2, 'column' => 1],
    ],
    // ---- phpVersion handling ------------------------------------------------------------------
    [
        'name' => 'property hooks parse and print under phpVersion 8.4',
        'files' => src(EMPTY_CLASS),
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['a.php'],
                'phpVersion' => '8.4',
                'edits' => [at(CLASS_REF, 'add_member', ['php' => 'public int $n { get => 1; }'])],
            ],
        ),
        'contains' => inA('get =>'),
    ],
    [
        'name' => 'a readonly property is rejected when the file is pinned to PHP 8.0',
        'files' => src(EMPTY_CLASS),
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['a.php'],
                'phpVersion' => '8.0',
                'edits' => [at(CLASS_REF, 'add_member', ['php' => 'public readonly int $n;'])],
            ],
        ),
        'error' => 'not valid in the "member" context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'the same readonly property is accepted under PHP 8.1',
        'files' => src(EMPTY_CLASS),
        'document' => fn (array $p): array => tx(
            [
                'path' => $p['a.php'],
                'phpVersion' => '8.1',
                'edits' => [at(CLASS_REF, 'add_member', ['php' => 'public readonly int $n;'])],
            ],
        ),
        'contains' => inA('public readonly int $n;'),
    ],
];
$failures = [];
$passed = 0;

foreach ($cases as $case) {
    $dir = sys_get_temp_dir() . '/php-ast-edit-matrix-' . bin2hex(random_bytes(6));
    mkdir($dir, 0700, true);
    $paths = ['dir' => $dir];
    $originals = [];

    foreach ($case['files'] ?? [] as $name => $source) {
        $paths[$name] = $dir . '/' . $name;
        file_put_contents($paths[$name], $source);
        $originals[$name] = $source;
    }
    $problems = [];

    // Inspect runs against the pristine files, before any transaction touches them.
    if (isset($case['inspect'])) {
        try {
            $ancestry = (new Editor())->inspect($paths['a.php'], $case['inspect']);
            json_encode($ancestry, JSON_THROW_ON_ERROR);
        } catch (Throwable $throwable) {
            $problems[] = 'inspect failed: ' . $throwable->getMessage();
        }
    }
    $error = null;

    if (isset($case['document']) || isset($case['edits'])) {
        $document = isset($case['document']) ? $case['document']($paths) : ['files' => [['path' => $paths['a.php'], 'edits' => $case['edits']]]];

        try {
            (new Editor())->apply($document);
        } catch (Throwable $throwable) {
            $error = $throwable->getMessage();
        }
    }

    if (isset($case['error'])) {
        if ($error === null) {
            $problems[] = 'expected failure containing "' . $case['error'] . '", but the transaction succeeded';
        } elseif (!str_contains($error, $case['error'])) {
            $problems[] = 'expected failure containing "' . $case['error'] . '", got "' . $error . '"';
        }
    } elseif ($error !== null) {
        $problems[] = 'unexpected failure: ' . $error;
    }

    foreach ($case['contains'] ?? [] as [$name, $needle]) {
        $file = $paths[$name] ?? $dir . '/' . $name;
        $actual = is_file($file) ? (string) file_get_contents($file) : '';

        if (!str_contains($actual, $needle)) {
            $problems[] = $name . ' does not contain "' . $needle . '"; got:' . "\n" . $actual;
        }
    }

    foreach ($case['notContains'] ?? [] as [$name, $needle]) {
        $file = $paths[$name] ?? $dir . '/' . $name;
        $actual = is_file($file) ? (string) file_get_contents($file) : '';

        if (str_contains($actual, $needle)) {
            $problems[] = $name . ' still contains "' . $needle . '"';
        }
    }

    foreach ($case['unchanged'] ?? [] as $name) {
        if (file_get_contents($paths[$name]) !== $originals[$name]) {
            $problems[] = $name . ' was modified although the transaction had to abort';
        }
    }

    foreach ($case['absent'] ?? [] as $name) {
        if (is_file($paths[$name] ?? $dir . '/' . $name)) {
            $problems[] = $name . ' still exists';
        }
    }

    foreach ($case['present'] ?? [] as $name) {
        if (!is_file($paths[$name] ?? $dir . '/' . $name)) {
            $problems[] = $name . ' was not created';
        }
    }

    if ($problems === []) {
        ++$passed;
    } else {
        $failures[] = $case['name'] . ":\n  - " . implode("\n  - ", $problems);
    }
    removeTree($dir);
}

// The write phase itself must roll back. An unwritable directory is the cheapest real
// write failure that does not depend on the caller running as root.
// Root can write into a directory it has no write bit for, so the rollback case cannot be
// provoked there; ext-posix is also not guaranteed to be present.
if (!function_exists('posix_geteuid') || posix_geteuid() !== 0) {
    $base = sys_get_temp_dir() . '/php-ast-edit-rollback-' . bin2hex(random_bytes(6));
    mkdir($base . '/locked', 0700, true);
    file_put_contents($base . '/first.php', "<?php\nclass First {}\n");
    file_put_contents($base . '/locked/second.php', "<?php\nclass Second {}\n");
    chmod($base . '/locked', 0500);
    $error = null;

    try {
        (new Editor())->apply(
            [
                'files' => [
                    [
                        'path' => $base . '/first.php',
                        'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'FirstChanged'])],
                    ],
                    [
                        'path' => $base . '/locked/second.php',
                        'edits' => [at(CLASS_NAME_REF, 'set_name', ['value' => 'SecondChanged'])],
                    ],
                ],
            ],
        );
    } catch (Throwable $throwable) {
        $error = $throwable->getMessage();
    }
    $first = (string) file_get_contents($base . '/first.php');

    if ($error === null || !str_contains($error, 'COMMIT_FAILED')) {
        $failures[] = 'write-phase rollback: expected COMMIT_FAILED, got ' . var_export($error, true);
    } elseif (!str_contains($first, 'class First {}') && !str_contains($first, 'class First')) {
        $failures[] = 'write-phase rollback: first.php was not restored, got ' . "\n" . $first;
    } elseif (str_contains($first, 'FirstChanged')) {
        $failures[] = 'write-phase rollback: first.php kept the aborted change';
    } else {
        ++$passed;
    }
    chmod($base . '/locked', 0700);
    @unlink($base . '/locked/second.php');
    @rmdir($base . '/locked');
    @unlink($base . '/first.php');
    @rmdir($base);
}

if ($failures !== []) {
    fwrite(
        STDERR,
        "FAIL: " . count($failures) . " of " . ($passed + count($failures)) . " matrix cases failed.\n\n",
    );
    fwrite(STDERR, implode("\n\n", $failures) . "\n");
    exit(1);
}
echo 'OK: ' . $passed . " matrix cases passed.\n";
