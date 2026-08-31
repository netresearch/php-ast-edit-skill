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
$autoload = $root.'/vendor/autoload.php';
if (!is_file($autoload)) {
    fwrite(STDERR, "SKIP: vendor/autoload.php missing; run composer install to execute the matrix.\n");
    exit(0);
}
require $autoload;

use Netresearch\PhpAstEdit\Editor;

/**
 * @var list<array{
 *   name: string,
 *   files?: array<string, string>,
 *   document: callable(array<string, string>): array,
 *   contains?: list<array{0: string, 1: string}>,
 *   notContains?: list<array{0: string, 1: string}>,
 *   unchanged?: list<string>,
 *   absent?: list<string>,
 *   present?: list<string>,
 *   error?: string
 * }>
 */
$cases = [
    // ---- Empty containers: the operations that were impossible before ------------------
    [
        'name' => 'first method into an empty class',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'stmts', 'php' => 'public function bar(): void {}'],
        ]]]],
        'contains' => [['a.php', 'public function bar(): void']],
    ],
    [
        'name' => 'first statement into an empty function body',
        'files' => ['a.php' => "<?php\nfunction foo()\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'stmts', 'parseAs' => 'stmt', 'php' => 'return 1;'],
        ]]]],
        'contains' => [['a.php', 'return 1;']],
    ],
    [
        'name' => 'first parameter into an empty parameter list',
        'files' => ['a.php' => "<?php\nfunction foo()\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_parameter', 'php' => 'private readonly ?Foo $foo = null'],
        ]]]],
        'contains' => [['a.php', 'function foo(private readonly ?Foo $foo = null)']],
    ],
    [
        'name' => 'first item into an empty array',
        'files' => ['a.php' => "<?php\n\$a = [];\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].expr.expr'], 'operation' => 'insert_into', 'property' => 'items', 'php' => "'k' => 1"],
        ]]]],
        'contains' => [['a.php', "'k' => 1"]],
    ],

    // ---- File lifecycle ----------------------------------------------------------------
    [
        'name' => 'create_file builds a file from construction syntax and then edits its AST',
        'files' => [],
        'document' => fn (array $p): array => ['files' => [[
            'path' => $p['dir'].'/Created.php',
            'mode' => 'create',
            'php' => '<?php declare(strict_types=1); namespace Demo; final class Created {}',
            'edits' => [
                ['target' => ['ref' => 'stmts[1].stmts[0]'], 'operation' => 'add_member', 'php' => 'public const VERSION = 1;'],
            ],
        ]]],
        'present' => ['Created.php'],
        'contains' => [['Created.php', 'public const VERSION = 1;'], ['Created.php', 'namespace Demo;']],
    ],
    [
        'name' => 'create_file refuses to clobber an existing file',
        'files' => ['a.php' => "<?php\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'mode' => 'create', 'php' => '<?php class X {}']]],
        'error' => 'FILE_EXISTS',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'delete_file removes a file under a sha guard',
        'files' => ['a.php' => "<?php\nclass Gone {}\n"],
        'document' => fn (array $p): array => ['files' => [[
            'path' => $p['a.php'],
            'mode' => 'delete',
            'sha256' => hash('sha256', "<?php\nclass Gone {}\n"),
        ]]],
        'absent' => ['a.php'],
    ],
    [
        'name' => 'delete_file rejects a stale sha',
        'files' => ['a.php' => "<?php\nclass Gone {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'mode' => 'delete', 'sha256' => str_repeat('0', 64)]]],
        'error' => 'STALE_SOURCE',
        'present' => ['a.php'],
    ],

    // ---- Class-like grammar -------------------------------------------------------------
    [
        'name' => 'interface gains a method signature',
        'files' => ['a.php' => "<?php\ninterface I\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'public function run(): void;'],
        ]]]],
        'contains' => [['a.php', 'public function run(): void;']],
    ],
    [
        'name' => 'trait gains a property',
        'files' => ['a.php' => "<?php\ntrait T\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'private static array $cache = [];'],
        ]]]],
        'contains' => [['a.php', 'private static array $cache = [];']],
    ],
    [
        'name' => 'enum gains a case',
        'files' => ['a.php' => "<?php\nenum Status: string\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => "case Draft = 'draft';"],
        ]]]],
        'contains' => [['a.php', "case Draft = 'draft';"]],
    ],
    [
        'name' => 'class gains an implements entry, an attribute and a docblock',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_implements', 'php' => 'Countable'],
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_attribute', 'php' => '#[Immutable]'],
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'set_doc_comment', 'value' => "A value object.\n\n@internal"],
        ]]]],
        'contains' => [
            ['a.php', 'class Foo implements Countable'],
            ['a.php', '#[Immutable]'],
            ['a.php', '* A value object.'],
            ['a.php', '* @internal'],
        ],
    ],
    [
        'name' => 'class extends is set through replace_child',
        'files' => ['a.php' => "<?php\nclass Foo extends Bar\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'set_extends', 'php' => 'Baz'],
        ]]]],
        'contains' => [['a.php', 'class Foo extends Baz']],
        'notContains' => [['a.php', 'extends Bar']],
    ],
    [
        'name' => 'trait use is added to a class',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'use LoggerAwareTrait;'],
        ]]]],
        'contains' => [['a.php', 'use LoggerAwareTrait;']],
    ],

    // ---- Namespace and use statements ---------------------------------------------------
    [
        'name' => 'use statement is inserted at the file root',
        'files' => ['a.php' => "<?php\nnamespace App;\n\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'stmts', 'parseAs' => 'stmt', 'position' => 'start', 'php' => 'use App\\Support\\Clock;'],
        ]]]],
        'contains' => [['a.php', 'use App\\Support\\Clock;']],
    ],
    [
        'name' => 'a second use item joins an existing group',
        'files' => ['a.php' => "<?php\nuse A\\B;\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'uses', 'parseAs' => 'use', 'php' => 'C\\D as E'],
        ]]]],
        'contains' => [['a.php', 'C\\D as E']],
    ],

    // ---- Signatures, types, modifiers ----------------------------------------------------
    [
        'name' => 'union return type replaces a scalar one',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n    public function bar(): string\n    {\n        return '';\n    }\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'set_return_type', 'php' => 'string|int'],
        ]]]],
        'contains' => [['a.php', 'public function bar(): string|int']],
    ],
    [
        'name' => 'parameter type becomes an intersection type',
        'files' => ['a.php' => "<?php\nfunction foo(Countable \$c) {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].params[0]'], 'operation' => 'set_type', 'php' => 'Countable&Traversable'],
        ]]]],
        'contains' => [['a.php', 'Countable&Traversable $c']],
    ],
    [
        'name' => 'visibility modifier is changed without touching anything else',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n    public function bar(): void\n    {\n    }\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'set_visibility', 'value' => 'protected'],
        ]]]],
        'contains' => [['a.php', 'protected function bar(): void']],
    ],
    [
        'name' => 'a nullable type is removed from a slot',
        'files' => ['a.php' => "<?php\nfunction foo(): ?int\n{\n    return null;\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].returnType'], 'operation' => 'delete_node'],
        ]]]],
        'notContains' => [['a.php', '?int']],
    ],

    // ---- Expressions, arrays, match, closures, anonymous classes --------------------------
    [
        'name' => 'match arm is appended to a match expression',
        'files' => ['a.php' => "<?php\n\$r = match (\$x) {\n    1 => 'one',\n};\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].expr.expr'], 'operation' => 'insert_into', 'property' => 'arms', 'php' => "default => 'other'"],
        ]]]],
        'contains' => [['a.php', "default => 'other'"]],
    ],
    [
        'name' => 'closure use clause gains a by-reference binding',
        'files' => ['a.php' => "<?php\n\$f = function () use (\$a) {\n};\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].expr.expr'], 'operation' => 'insert_into', 'property' => 'uses', 'php' => '&$carry'],
        ]]]],
        'contains' => [['a.php', 'use ($a, &$carry)']],
    ],
    [
        'name' => 'anonymous class gains a member',
        'files' => ['a.php' => "<?php\n\$o = new class {\n};\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].expr.expr.class'], 'operation' => 'add_member', 'php' => 'public int $n = 0;'],
        ]]]],
        'contains' => [['a.php', 'public int $n = 0;']],
    ],
    [
        'name' => 'a named argument is added to a call',
        'files' => ['a.php' => "<?php\nfoo(1);\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].expr'], 'operation' => 'insert_into', 'property' => 'args', 'php' => 'flag: true'],
        ]]]],
        'contains' => [['a.php', 'foo(1, flag: true)']],
    ],
    [
        'name' => 'catch clause is added to a try statement',
        'files' => ['a.php' => "<?php\ntry {\n    foo();\n} catch (RuntimeException \$e) {\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'catches', 'php' => 'catch (LogicException $e) { throw $e; }'],
        ]]]],
        'contains' => [['a.php', 'catch (LogicException $e)']],
    ],
    [
        'name' => 'replace_node swaps a parameter node',
        'files' => ['a.php' => "<?php\nfunction foo(int \$a) {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].params[0]'], 'operation' => 'replace_node', 'php' => 'string ...$rest'],
        ]]]],
        'contains' => [['a.php', 'function foo(string ...$rest)']],
    ],
    [
        'name' => 'move_node relocates a method to another class in the same file',
        'files' => ['a.php' => "<?php\nclass A\n{\n    public function m(): void\n    {\n    }\n}\nclass B\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'move_node', 'into' => ['ref' => 'stmts[1]', 'property' => 'stmts', 'position' => 'end']],
        ]]]],
        'contains' => [['a.php', "class B\n{\n    public function m(): void"]],
        'notContains' => [['a.php', "class A\n{\n    public function m"]],
    ],

    // ---- Comments -------------------------------------------------------------------------
    [
        'name' => 'existing docblock is replaced, not duplicated',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n    /** Old text. */\n    public function bar(): void\n    {\n    }\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'set_doc_comment', 'value' => 'New text.'],
        ]]]],
        'contains' => [['a.php', 'New text.']],
        'notContains' => [['a.php', 'Old text.']],
    ],
    [
        'name' => 'docblock is removed',
        'files' => ['a.php' => "<?php\n/** Doc. */\nfunction foo() {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'remove_doc_comment'],
        ]]]],
        'notContains' => [['a.php', 'Doc.']],
    ],

    // ---- Failure modes ---------------------------------------------------------------------
    [
        'name' => 'stale sha aborts before any write',
        'files' => ['a.php' => "<?php\nclass Foo {}\n"],
        'document' => fn (array $p): array => ['files' => [[
            'path' => $p['a.php'],
            'sha256' => str_repeat('a', 64),
            'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'Bar']],
        ]]],
        'error' => 'STALE_SOURCE',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'wrong expected kind aborts',
        'files' => ['a.php' => "<?php\nclass Foo {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].name', 'kind' => 'Stmt_Class'], 'operation' => 'set_name', 'value' => 'Bar'],
        ]]]],
        'error' => 'resolves to Identifier',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'wrong expected name aborts',
        'files' => ['a.php' => "<?php\nclass Foo {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].name'], 'expect' => ['name' => 'Nope'], 'operation' => 'set_name', 'value' => 'Bar'],
        ]]]],
        'error' => 'Expected node name Nope',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'detached target aborts the transaction',
        'files' => ['a.php' => "<?php\nfunction foo()\n{\n    \$a = 1;\n    \$b = 2;\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'delete_node'],
            ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'replace_statement', 'php' => '$c = 3;'],
        ]]]],
        'error' => 'invalidated by an earlier edit',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'invalid contextual snippet aborts with the context named',
        'files' => ['a.php' => "<?php\nclass Foo {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'return 1;'],
        ]]]],
        'error' => 'not valid in the "member" context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'unknown parseAs context is reported with the known list',
        'files' => ['a.php' => "<?php\nclass Foo {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'stmts', 'parseAs' => 'nonsense', 'php' => 'public int $a = 1;'],
        ]]]],
        'error' => 'Unknown parseAs context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'unknown sub node is reported with the available slots',
        'files' => ['a.php' => "<?php\nclass Foo {}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'insert_into', 'property' => 'bogus', 'parseAs' => 'member', 'php' => 'public int $a = 1;'],
        ]]]],
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
        'document' => fn (array $p): array => ['files' => [
            ['path' => $p['a.php'], 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'A1']]],
            ['path' => $p['b.php'], 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'B1']]],
            ['path' => $p['c.php'], 'edits' => [['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'this is not php']]],
        ]],
        'error' => 'not valid in the "member" context',
        'unchanged' => ['a.php', 'b.php', 'c.php'],
    ],
    [
        'name' => 'the same path may not appear twice in one transaction',
        'files' => ['a.php' => "<?php\nclass A {}\n"],
        'document' => fn (array $p): array => ['files' => [
            ['path' => $p['a.php'], 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'A1']]],
            ['path' => $p['a.php'], 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'A2']]],
        ]],
        'error' => 'Duplicate path',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'a multi-file transaction commits every file together',
        'files' => [
            'a.php' => "<?php\nclass A {}\n",
            'b.php' => "<?php\nclass B {}\n",
        ],
        'document' => fn (array $p): array => ['files' => [
            ['path' => $p['a.php'], 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'A1']]],
            ['path' => $p['b.php'], 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'B1']]],
        ]],
        'contains' => [['a.php', 'class A1'], ['b.php', 'class B1']],
    ],

    [
        'name' => 'a method whose body contains "case " still goes into an enum as a method',
        'files' => ['a.php' => "<?php\nenum Status: string\n{\n    case Draft = 'draft';\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'public function label(): string { switch ($this) { case self::Draft: return \'d\'; } return \'\'; }'],
        ]]]],
        'contains' => [['a.php', 'public function label(): string'], ['a.php', "case Draft = 'draft';"]],
    ],
    [
        'name' => 'move_node refuses to move a node into its own subtree',
        'files' => ['a.php' => "<?php\nclass A\n{\n    public function m(): void\n    {\n    }\n}\n"],
        'document' => fn (array $p): array => ['files' => [['path' => $p['a.php'], 'edits' => [
            ['target' => ['ref' => 'stmts[0]'], 'operation' => 'move_node', 'into' => ['ref' => 'stmts[0].stmts[0]', 'property' => 'stmts']],
        ]]]],
        'error' => 'its own subtree',
        'unchanged' => ['a.php'],
    ],

    // ---- phpVersion handling ------------------------------------------------------------------
    [
        'name' => 'property hooks parse and print under phpVersion 8.4',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [[
            'path' => $p['a.php'],
            'phpVersion' => '8.4',
            'edits' => [['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'public int $n { get => 1; }']],
        ]]],
        'contains' => [['a.php', 'get =>']],
    ],
    [
        'name' => 'a readonly property is rejected when the file is pinned to PHP 8.0',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [[
            'path' => $p['a.php'],
            'phpVersion' => '8.0',
            'edits' => [['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'public readonly int $n;']],
        ]]],
        'error' => 'not valid in the "member" context',
        'unchanged' => ['a.php'],
    ],
    [
        'name' => 'the same readonly property is accepted under PHP 8.1',
        'files' => ['a.php' => "<?php\nclass Foo\n{\n}\n"],
        'document' => fn (array $p): array => ['files' => [[
            'path' => $p['a.php'],
            'phpVersion' => '8.1',
            'edits' => [['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'public readonly int $n;']],
        ]]],
        'contains' => [['a.php', 'public readonly int $n;']],
    ],
];

$failures = [];
$passed = 0;

foreach ($cases as $case) {
    $dir = sys_get_temp_dir().'/php-ast-edit-matrix-'.bin2hex(random_bytes(6));
    mkdir($dir, 0777, true);
    $paths = ['dir' => $dir];
    $originals = [];
    foreach ($case['files'] ?? [] as $name => $source) {
        $paths[$name] = $dir.'/'.$name;
        file_put_contents($paths[$name], $source);
        $originals[$name] = $source;
    }

    $error = null;
    try {
        (new Editor())->apply(($case['document'])($paths));
    } catch (Throwable $throwable) {
        $error = $throwable->getMessage();
    }

    $problems = [];

    if (isset($case['error'])) {
        if ($error === null) {
            $problems[] = 'expected failure containing "'.$case['error'].'", but the transaction succeeded';
        } elseif (!str_contains($error, $case['error'])) {
            $problems[] = 'expected failure containing "'.$case['error'].'", got "'.$error.'"';
        }
    } elseif ($error !== null) {
        $problems[] = 'unexpected failure: '.$error;
    }

    foreach ($case['contains'] ?? [] as [$name, $needle]) {
        $file = $paths[$name] ?? $dir.'/'.$name;
        $actual = is_file($file) ? (string) file_get_contents($file) : '';
        if (!str_contains($actual, $needle)) {
            $problems[] = $name.' does not contain "'.$needle.'"; got:'."\n".$actual;
        }
    }
    foreach ($case['notContains'] ?? [] as [$name, $needle]) {
        $file = $paths[$name] ?? $dir.'/'.$name;
        $actual = is_file($file) ? (string) file_get_contents($file) : '';
        if (str_contains($actual, $needle)) {
            $problems[] = $name.' still contains "'.$needle.'"';
        }
    }
    foreach ($case['unchanged'] ?? [] as $name) {
        if (file_get_contents($paths[$name]) !== $originals[$name]) {
            $problems[] = $name.' was modified although the transaction had to abort';
        }
    }
    foreach ($case['absent'] ?? [] as $name) {
        if (is_file($paths[$name] ?? $dir.'/'.$name)) {
            $problems[] = $name.' still exists';
        }
    }
    foreach ($case['present'] ?? [] as $name) {
        if (!is_file($paths[$name] ?? $dir.'/'.$name)) {
            $problems[] = $name.' was not created';
        }
    }

    if ($problems === []) {
        ++$passed;
    } else {
        $failures[] = $case['name'].":\n  - ".implode("\n  - ", $problems);
    }

    foreach (glob($dir.'/*') ?: [] as $file) {
        @unlink($file);
    }
    @rmdir($dir);
}

// The write phase itself must roll back. An unwritable directory is the cheapest real
// write failure that does not depend on the caller running as root.
if (posix_geteuid() !== 0) {
    $base = sys_get_temp_dir().'/php-ast-edit-rollback-'.bin2hex(random_bytes(6));
    mkdir($base.'/locked', 0777, true);
    file_put_contents($base.'/first.php', "<?php\nclass First {}\n");
    file_put_contents($base.'/locked/second.php', "<?php\nclass Second {}\n");
    chmod($base.'/locked', 0555);

    $error = null;
    try {
        (new Editor())->apply(['files' => [
            ['path' => $base.'/first.php', 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'FirstChanged']]],
            ['path' => $base.'/locked/second.php', 'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'SecondChanged']]],
        ]]);
    } catch (Throwable $throwable) {
        $error = $throwable->getMessage();
    }

    $first = (string) file_get_contents($base.'/first.php');
    if ($error === null || !str_contains($error, 'COMMIT_FAILED')) {
        $failures[] = 'write-phase rollback: expected COMMIT_FAILED, got '.var_export($error, true);
    } elseif (!str_contains($first, 'class First {}') && !str_contains($first, 'class First')) {
        $failures[] = 'write-phase rollback: first.php was not restored, got '."\n".$first;
    } elseif (str_contains($first, 'FirstChanged')) {
        $failures[] = 'write-phase rollback: first.php kept the aborted change';
    } else {
        ++$passed;
    }

    chmod($base.'/locked', 0755);
    @unlink($base.'/locked/second.php');
    @rmdir($base.'/locked');
    @unlink($base.'/first.php');
    @rmdir($base);
}

if ($failures !== []) {
    fwrite(STDERR, "FAIL: ".count($failures)." of ".($passed + count($failures))." matrix cases failed.\n\n");
    fwrite(STDERR, implode("\n\n", $failures)."\n");
    exit(1);
}

echo 'OK: '.$passed." matrix cases passed.\n";
