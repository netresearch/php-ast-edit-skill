<?php

declare (strict_types=1);
$root = dirname(__DIR__);
$autoload = $root . '/vendor/autoload.php';
if (!is_file($autoload)) {
    fwrite(
        STDERR,
        "SKIP: vendor/autoload.php missing; run composer install to execute integration tests.\n",
    );
    exit(0);
}
require $autoload;
use Netresearch\PhpAstEdit\Editor;

function check(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}
$source = file_get_contents(__DIR__ . '/fixtures/sample.php');
$tmpBase = tempnam(sys_get_temp_dir(), 'php-ast-edit-test-');
if ($tmpBase === false) {
    throw new RuntimeException('Could not create test file.');
}
$tmp = $tmpBase . '.php';
rename($tmpBase, $tmp);
file_put_contents($tmp, $source);
try {
    $editor = new Editor();
    $inspect = $editor->inspect($tmp, ['line' => 9, 'column' => 40]);
    check($inspect['nodes'] !== [], 'inspect returned no nodes');
    check(
        $inspect['nodes'][0]['type'] === 'Identifier',
        'smallest node at method name should be Identifier',
    );
    $hash = hash_file('sha256', $tmp);
    $result = $editor->apply(
        [
            'files' => [
                [
                    'path' => $tmp,
                    'sha256' => $hash,
                    'edits' => [
                        [
                            'target' => ['line' => 9, 'column' => 40, 'kind' => 'Identifier'],
                            'expect' => ['name' => 'oldFind'],
                            'operation' => 'set_name',
                            'value' => 'find',
                        ],
                        [
                            'target' => ['line' => 8, 'column' => 17, 'kind' => 'Scalar_String'],
                            'expect' => ['value' => 'SELECT * FROM customer WHERE id = ?'],
                            'operation' => 'set_string',
                            'value' => 'SELECT name FROM customer WHERE id = ?',
                        ],
                    ],
                ],
            ],
        ],
    );
    check($result['files'][0]['changed'] === true, 'first transaction should change file');
    $changed = file_get_contents($tmp);
    check(str_contains($changed, '->find($id)'), 'method name was not changed');
    check(
        str_contains($changed, "'SELECT name FROM customer WHERE id = ?'"),
        'string value was not changed',
    );
    // Multiple edits may deliberately target the same AST node when earlier edits keep it attached.
    $hash = hash_file('sha256', $tmp);
    $lines = file($tmp);
    $callLine = null;
    $callColumn = null;
    foreach ($lines as $i => $line) {
        $pos = strpos($line, '->find(');
        if ($pos !== false) {
            $callLine = $i + 1;
            $callColumn = $pos + 3;
            break;
        }
    }
    check($callLine !== null && $callColumn !== null, 'could not locate method call');
    $editor->apply(
        [
            'files' => [
                [
                    'path' => $tmp,
                    'sha256' => $hash,
                    'edits' => [
                        [
                            'target' => [
                                'line' => $callLine,
                                'column' => $callColumn,
                                'kind' => 'Expr_MethodCall',
                            ],
                            'expect' => ['name' => 'find'],
                            'operation' => 'set_name',
                            'value' => 'lookup',
                        ],
                        [
                            'target' => [
                                'line' => $callLine,
                                'column' => $callColumn,
                                'kind' => 'Expr_MethodCall',
                            ],
                            'operation' => 'replace_argument',
                            'index' => 0,
                            'php' => '$id + 1',
                        ],
                    ],
                ],
            ],
        ],
    );
    $changed = file_get_contents($tmp);
    check(str_contains($changed, '->lookup($id + 1)'), 'same-node multi-edit transaction failed');
    $hash = hash_file('sha256', $tmp);
    $lines = file($tmp);
    $returnLine = null;
    foreach ($lines as $i => $line) {
        if (str_contains($line, 'return $customer->name;')) {
            $returnLine = $i + 1;
            break;
        }
    }
    check($returnLine !== null, 'could not find return statement after canonical print');
    $editor->apply(
        [
            'files' => [
                [
                    'path' => $tmp,
                    'sha256' => $hash,
                    'edits' => [
                        [
                            'target' => ['line' => $returnLine, 'column' => 9, 'kind' => 'Stmt_Return'],
                            'operation' => 'insert_before',
                            'php' => 'if ($customer === null) { throw new RuntimeException("missing"); }',
                        ],
                    ],
                ],
            ],
        ],
    );
    $changed = file_get_contents($tmp);
    check(str_contains($changed, 'if ($customer === null)'), 'statement insertion failed');
    // Verify two list edits remain stable even if the first insertion shifts the second target's index.
    $hash = hash_file('sha256', $tmp);
    $lines = file($tmp);
    $sqlLine = null;
    $returnLine = null;
    foreach ($lines as $i => $line) {
        if (str_contains($line, '$sql =')) {
            $sqlLine = $i + 1;
        }
        if (str_contains($line, 'return $customer->name;')) {
            $returnLine = $i + 1;
        }
    }
    check($sqlLine !== null && $returnLine !== null, 'could not locate transaction targets');
    $editor->apply(
        [
            'files' => [
                [
                    'path' => $tmp,
                    'sha256' => $hash,
                    'edits' => [
                        [
                            'target' => ['line' => $sqlLine, 'column' => 9, 'kind' => 'Stmt_Expression'],
                            'operation' => 'insert_before',
                            'php' => '$started = true;',
                        ],
                        [
                            'target' => ['line' => $returnLine, 'column' => 9, 'kind' => 'Stmt_Return'],
                            'operation' => 'replace_statement',
                            'php' => 'return strtoupper($customer->name);',
                        ],
                    ],
                ],
            ],
        ],
    );
    $changed = file_get_contents($tmp);
    check(str_contains($changed, '$started = true;'), 'list insertion failed');
    check(str_contains($changed, 'return strtoupper($customer->name);'), 'later list target became stale');
    echo "OK\n";
} finally {
    @unlink($tmp);
}
