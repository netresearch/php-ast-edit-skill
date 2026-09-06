<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/vendor/autoload.php';

use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\RepositoryConfig;

$dir = sys_get_temp_dir() . '/php-ast-renames-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
file_put_contents($dir . '/composer.json', "{}\n");
file_put_contents($dir . '/.editorconfig', "root = true\n[*]\nmax_line_length = 100\n");
RepositoryConfig::write($dir, 100);
$failed = [];
$passed = 0;

function renameCheck(string $name, bool $condition): void
{
    global $failed, $passed;

    if ($condition) {
        ++$passed;
    } else {
        $failed[] = $name;
    }
}

function renameFixture(string $code): string
{
    global $dir;
    $path = $dir . '/' . bin2hex(random_bytes(5)) . '.php';
    (new Editor())->apply(
        ['files' => [['path' => $path, 'mode' => 'create', 'php' => '<?php ' . $code]]],
    );

    return $path;
}

function renameEdit(string $path, array $edit): array
{
    return (new Editor())->apply(
        ['files' => [['path' => $path, 'sha256' => hash_file('sha256', $path), 'edits' => [$edit]]]],
    )['files'][0];
}

$variableEdit = [
    'target' => ['select' => 'function:calc'],
    'operation' => 'rename_variable',
    'from' => 'x',
    'to' => 'y',
];
$variableFailures = [
    'arrow destination parameter captures renamed source' => 'function calc($x) { $f = fn($y) => $x + $y; return $f(2); }',
    'destination parameter already exists' => 'function calc($x, $y) { return $x + $y; }',
    'destination local already exists' => 'function calc($x) { $y = 2; return $x + $y; }',
    'destination foreach binding exists' => 'function calc($x) { foreach ([2] as $y) { return $x + $y; } }',
    'destination catch binding exists' => 'function calc($x) { try { return $x; } catch (Exception $y) { return 0; } }',
    'destination static local exists' => 'function calc($x) { static $y = 2; return $x + $y; }',
    'destination destructured local exists' => 'function calc($x) { [$y] = [2]; return $x + $y; }',
    'capturing closure has destination parameter' => 'function calc($x) { $f = function ($y) use ($x) { return $x + $y; }; return $f(2); }',
    'capturing closure has destination local' => 'function calc($x) { $f = function () use ($x) { $y = 2; return $x + $y; }; return $f(); }',
    'capturing closure has destination capture' => 'function calc($x) { $f = function () use ($x, $y) { return $x + $y; }; return $f(); }',
    'other closure captures destination from selected scope' => 'function calc($x) { $f = function () use ($y) { return $y; }; return $x; }',
    'shadowing arrow still captures outer destination' => 'function calc($x) { $f = fn($x) => $x + $y; return $x; }',
    'deep arrow destination parameter captures source' => 'function calc($x) { $f = fn() => fn($y) => $x + $y; return $f()(2); }',
    'global source is not a local binding' => 'function calc() { global $x; return $x; }',
    'dynamic variables make bindings unresolved' => 'function calc($x, $name) { return $x + $$name; }',
    'compact refers to local names through strings' => 'function calc($x) { return compact("x"); }',
];

foreach ($variableFailures as $name => $code) {
    $path = renameFixture($code);
    $before = file_get_contents($path);

    try {
        renameEdit($path, $variableEdit);
        renameCheck($name . ' refuses operation', false);
    } catch (EditException $error) {
        renameCheck(
            $name . ' explains refusal',
            str_contains($error->getMessage(), 'rename_variable'),
        );
    }
    renameCheck($name . ' preserves bytes', file_get_contents($path) === $before);
}

$methodEdit = ['target' => ['select' => 'method:W::old'], 'operation' => 'rename_method', 'to' => 'fresh'];
$methodFailures = [
    'existing method declaration conflicts' => 'class W { private function old() {} private function fresh() {} }',
    'existing method declaration conflicts without regard to case' => 'class W { private function old() {} private function FRESH() {} }',
    'parent dispatch is never renamed as the child declaration' => 'class P { public function old() {} } class W extends P { public function old() { parent::old(); } }',
    'nonprivate method of extensible class has unresolved overrides' => 'class W { public function old() {} public function run() { return $this->old(); } }',
    'late static dispatch in extensible class is unresolved' => 'class W { private static function old() {} public static function run() { return static::old(); } }',
    'trait dispatch requires consumers' => 'trait W { private function old() {} }',
    'interface declaration requires implementations' => 'interface W { public function old(); }',
    'trait composition may contain destination method' => 'trait T { private function fresh() {} } class W { use T; private function old() {} }',
    'implemented contract may contain destination method' => 'interface I {} final class W implements I { private function old() {} }',
];

foreach ($methodFailures as $name => $code) {
    $path = renameFixture($code);
    $before = file_get_contents($path);

    try {
        renameEdit($path, $methodEdit);
        renameCheck($name . ' refuses operation', false);
    } catch (EditException $error) {
        renameCheck(
            $name . ' explains refusal',
            str_contains($error->getMessage(), 'rename_method'),
        );
    }
    renameCheck($name . ' preserves bytes', file_get_contents($path) === $before);
}

$path = renameFixture(
    'function calc($x) { $shadow = fn($x) => $x; $independent = function ($y) { return $y; }; $capture = function () use (&$x) { return fn() => $x; }; $arrow = fn() => $x; return $capture()() + $arrow() + $shadow(2) + $independent(1); } echo calc(3);',
);
renameEdit($path, $variableEdit);
$code = (string) file_get_contents($path);
renameCheck(
    'source and linked capture names move',
    str_contains($code, 'use (&$y)') && substr_count($code, '=> $y') === 2,
);
renameCheck('shadowed arrow keeps independent source', str_contains($code, 'fn($x) => $x'));
renameCheck('independent closure destination is allowed', str_contains($code, 'function ($y)'));
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($path), $output, $status);
renameCheck(
    'lexical variable rename preserves execution',
    $status === 0 && implode('', $output) === '9',
);

$path = renameFixture(
    'class W { private function old() { return 2; } public function run() { $f = fn() => $this->OLD(); return $f() + self::old() + $this?->old(); } } echo (new W())->run();',
);
$result = renameEdit($path, $methodEdit);
$code = (string) file_get_contents($path);
renameCheck(
    'private method and lexical receiver calls move case insensitively',
    ($result['effects'][0]['renamed'] ?? null) === 4 && str_contains($code, '$this?->fresh()'),
);
$output = [];
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($path), $output, $status);
renameCheck(
    'private method rename preserves execution',
    $status === 0 && implode('', $output) === '6',
);

$path = renameFixture(
    'final class W { public static function old() { return 3; } public static function run() { return static::old(); } } echo W::run();',
);
renameEdit($path, $methodEdit);
$output = [];
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($path), $output, $status);
renameCheck(
    'final class permits bound late static dispatch',
    $status === 0 && implode('', $output) === '3',
);

$path = renameFixture(
    'class W { private function old() {} public function run($other) { function nested() { return function () { return $this->old(); }; } $this->old(); return new class($this->old()) { public function __construct($x) {} public function run() { return $this->old(); } }; } }',
);
$result = renameEdit($path, $methodEdit);
$code = (string) file_get_contents($path);
renameCheck(
    'named nested function keeps its independently bindable closure',
    substr_count($code, 'return $this->old();') === 2,
);
renameCheck(
    'anonymous class constructor argument uses outer receiver',
    str_contains($code, 'new class($this->fresh())'),
);
renameCheck(
    'anonymous class body retains its own receiver',
    str_contains($code, 'return $this->old();'),
);
renameCheck(
    'unresolved receiver occurrences remain counted',
    ($result['effects'][0]['otherReceivers'] ?? null) === 2,
);

$path = renameFixture('$x = 1; $f = function () use ($x) { return $x; };');
$before = file_get_contents($path);

try {
    renameEdit(
        $path,
        [
            'target' => ['ref' => 'stmts[1].expr.expr'],
            'operation' => 'rename_variable',
            'from' => 'x',
            'to' => 'y',
        ],
    );
    renameCheck('selected closure capture needs outer scope', false);
} catch (EditException $error) {
    renameCheck(
        'selected closure capture needs outer scope',
        str_contains($error->getMessage(), 'outer scope'),
    );
}
renameCheck('selected closure refusal preserves bytes', file_get_contents($path) === $before);

$path = renameFixture('$x = 1; $f = fn() => $x;');
$before = file_get_contents($path);

try {
    renameEdit(
        $path,
        [
            'target' => ['ref' => 'stmts[1].expr.expr'],
            'operation' => 'rename_variable',
            'from' => 'x',
            'to' => 'y',
        ],
    );
    renameCheck('selected arrow capture needs outer scope', false);
} catch (EditException $error) {
    renameCheck(
        'selected arrow capture needs outer scope',
        str_contains($error->getMessage(), 'outer scope'),
    );
}
renameCheck('selected arrow refusal preserves bytes', file_get_contents($path) === $before);
$moreFailures = [
    [
        'promoted source parameter preserves property binding',
        'class W { public function __construct(public int $x) {} }',
        [
            'target' => ['select' => 'method:W::__construct'],
            'operation' => 'rename_variable',
            'from' => 'x',
            'to' => 'y',
        ],
    ],
    [
        'magic source method is refused',
        'class W { public function __construct() {} }',
        [
            'target' => ['select' => 'method:W::__construct'],
            'operation' => 'rename_method',
            'to' => 'fresh',
        ],
    ],
    [
        'magic destination method is refused',
        'class W { private function old() {} }',
        array_replace($methodEdit, ['to' => '__invoke']),
    ],
    [
        'selected closure local conflicts with a captured destination',
        '$y = 2; $f = function ($x) use ($y) { return $x + $y; };',
        [
            'target' => ['ref' => 'stmts[1].expr.expr'],
            'operation' => 'rename_variable',
            'from' => 'x',
            'to' => 'y',
        ],
    ],
    [
        'source superglobal is refused',
        'function calc() { return $_GET; }',
        array_replace($variableEdit, ['from' => '_GET']),
    ],
    ['eval hides bindings', 'function calc($x) { eval("return 1;"); return $x; }', $variableEdit],
    [
        'GLOBALS hides name-based bindings',
        'function calc($x) { return $x + $GLOBALS["x"]; }',
        $variableEdit,
    ],
];

foreach ($moreFailures as [$name, $source, $edit]) {
    $path = renameFixture($source);
    $before = file_get_contents($path);

    try {
        renameEdit($path, $edit);
        renameCheck($name, false);
    } catch (EditException $error) {
        renameCheck($name, str_contains($error->getMessage(), $edit['operation']));
    }
    renameCheck($name . ' preserves bytes', file_get_contents($path) === $before);
}
$path = renameFixture('$f = function ($x) { return $x + 2; }; echo $f(3);');
renameEdit(
    $path,
    [
        'target' => ['ref' => 'stmts[0].expr.expr'],
        'operation' => 'rename_variable',
        'from' => 'x',
        'to' => 'y',
    ],
);
$output = [];
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($path), $output, $status);
renameCheck(
    'selected closure local parameter renames safely',
    $status === 0 && implode('', $output) === '5',
);
$path = renameFixture('$f = fn($x) => $x + 2; echo $f(3);');
renameEdit(
    $path,
    [
        'target' => ['ref' => 'stmts[0].expr.expr'],
        'operation' => 'rename_variable',
        'from' => 'x',
        'to' => 'y',
    ],
);
$output = [];
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($path), $output, $status);
renameCheck(
    'selected arrow local parameter renames safely',
    $status === 0 && implode('', $output) === '5',
);
$path = renameFixture(
    'function calc($x) { return new class($x) { public function __construct(public int $x) {} }; } echo calc(3)->x;',
);
renameEdit($path, $variableEdit);
renameCheck(
    'anonymous constructor argument remains in outer variable scope',
    str_contains((string) file_get_contents($path), 'new class($y)'),
);
$output = [];
exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($path), $output, $status);
renameCheck(
    'anonymous class property and constructor scope stay unchanged',
    $status === 0 && implode('', $output) === '3',
);
$path = renameFixture(
    'class W { private function old() {} public function run($other) { $this->old(); $other->old(); } }',
);
$result = renameEdit($path, array_replace($methodEdit, ['to' => 'OLD']));
renameCheck(
    'case-only method rename counts only unresolved calls',
    ($result['effects'][0]['renamed'] ?? null) === 2 && ($result['effects'][0]['otherReceivers'] ?? null) === 1,
);
// Keep the test file executable on PHP 8.2; parse hook syntax for its declared PHP target.
$hookPath = $dir . '/hooks.php';
(new Editor())->apply(
    [
        'files' => [
            [
                'path' => $hookPath,
                'mode' => 'create',
                'phpVersion' => '8.4',
                'php' => '<?php class W { public int $x { get => $this->old(); } public int $y { get { return self::old(); } } private function old(): int { return 1; } } echo (new W())->x + (new W())->y;',
            ],
        ],
    ],
);
$hookResult = (new Editor())->apply(
    [
        'files' => [
            [
                'path' => $hookPath,
                'phpVersion' => '8.4',
                'sha256' => hash_file('sha256', $hookPath),
                'edits' => [$methodEdit],
            ],
        ],
    ],
)['files'][0];
renameCheck(
    'property hook receivers move with their private method',
    ($hookResult['effects'][0]['renamed'] ?? null) === 3,
);
renameCheck(
    'property hook calls do not remain as unresolved receivers',
    ($hookResult['effects'][0]['otherReceivers'] ?? null) === 0,
);

if (PHP_VERSION_ID >= 80400) {
    $output = [];
    exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($hookPath) . ' 2>&1', $output, $status);
    renameCheck(
        'property hook method rename preserves execution',
        $status === 0 && implode('', $output) === '2',
    );
}

foreach (glob($dir . '/*') ?: [] as $path) {
    unlink($path);
}

foreach (glob($dir . '/.*') ?: [] as $path) {
    if (is_file($path)) {
        unlink($path);
    }
}
rmdir($dir);

if ($failed !== []) {
    fwrite(STDERR, implode("\n", $failed) . "\n");
    exit(1);
}
echo 'Renames OK (' . $passed . " checks)\n";
