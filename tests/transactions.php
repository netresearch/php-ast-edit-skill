<?php

declare(strict_types=1);

require dirname(__DIR__) . '/vendor/autoload.php';

use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\RepositoryConfig;

$dir = sys_get_temp_dir() . '/php-ast-contract-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
$failures = [];
$count = 0;
function contractCheck(string $name, bool $passed): void
{
    global $failures, $count;
    ++$count;

    if (!$passed) {
        $failures[] = $name;
    }
}
function contractRefuses(callable $operation, string $contains): bool
{
    try {
        $operation();

        return false;
    } catch (EditException $e) {
        return str_contains($e->getMessage(), $contains);
    }
}
function contractClean(string $path): void
{
    if (is_link($path) || !is_dir($path)) {
        unlink($path);

        return;
    }

    foreach (new FilesystemIterator($path) as $entry) {
        contractClean($entry->getPathname());
    }
    rmdir($path);
}

try {
    $config = [
        'canonical' => true,
        'printWidth' => 80,
        'formatter' => ['true', '{files}'],
        'verify' => [['false', '{files}']],
        'custom' => ['preserve' => true],
    ];
    file_put_contents($dir . '/.php-ast-edit.json', json_encode($config));
    RepositoryConfig::write($dir, 100, ['excluded']);
    $after = json_decode(file_get_contents($dir . '/.php-ast-edit.json'), true);
    contractCheck(
        'normalize preserves formatter',
        ($after['formatter'] ?? null) === $config['formatter'],
    );
    contractCheck('normalize preserves verify', ($after['verify'] ?? null) === $config['verify']);
    contractCheck(
        'normalize preserves extension fields',
        ($after['custom'] ?? null) === $config['custom'],
    );
    contractCheck(
        'normalize updates owned values',
        $after['printWidth'] === 100 && $after['exclude'] === ['excluded'],
    );
    unlink($dir . '/.php-ast-edit.json');

    $path = $dir . '/existing.php';
    $original = "<?php function before(): int { return 1; }\n";
    file_put_contents($path, $original);
    $overwrite = [
        'files' => [
            [
                'path' => $path,
                'mode' => 'create',
                'expectAbsent' => false,
                'sha256' => str_repeat('0', 64),
                'php' => '<?php function after(): int { return 2; }',
            ],
        ],
    ];
    contractCheck(
        'create overwrite rejects stale SHA',
        contractRefuses(fn () => (new Editor())->apply($overwrite), 'STALE_SOURCE'),
    );
    contractCheck('stale create leaves original bytes', file_get_contents($path) === $original);
    file_put_contents($path, $original);
    $overwrite['files'][0]['sha256'] = hash('sha256', $original);
    $written = (new Editor())->apply($overwrite);
    contractCheck('matching create SHA succeeds', $written['files'][0]['changed']);

    $target = $dir . '/target.php';
    $link = $dir . '/link.php';
    file_put_contents($target, "<?php echo 1;\n");
    symlink('target.php', $link);
    mkdir($dir . '/blocked.php');
    $rollback = [
        'files' => [
            ['path' => $link, 'mode' => 'delete', 'sha256' => hash_file('sha256', $link)],
            ['path' => $dir . '/blocked.php', 'mode' => 'create', 'php' => '<?php echo 2;'],
        ],
    ];
    contractCheck(
        'write failure rejects transaction',
        contractRefuses(fn () => (new Editor())->apply($rollback), 'COMMIT_FAILED'),
    );
    contractCheck(
        'rollback restores symlink identity',
        is_link($link) && readlink($link) === 'target.php',
    );
    contractCheck('rollback leaves target bytes', file_get_contents($target) === "<?php echo 1;\n");

    $warning = $dir . '/warning.php';
    file_put_contents(
        $warning,
        '<?php class W { function a($nonce) {return $nonce;} function b($nonce) {return $nonce;} }',
    );
    $result = (new Editor())->apply(
        [
            'files' => [
                [
                    'path' => $warning,
                    'edits' => [
                        [
                            'target' => ['select' => 'method:W::a'],
                            'operation' => 'rename_variable',
                            'from' => 'nonce',
                            'to' => 'challenge',
                        ],
                    ],
                ],
            ],
        ],
    )['files'][0];
    contractCheck(
        'rename warning survives formatting warning',
        str_contains($result['warning'] ?? '', 'INCOMPLETE_RENAME') && str_contains($result['warning'] ?? '', 'NOT_CANONICAL'),
    );
    contractCheck('all warnings exposed in array', count($result['warnings'] ?? []) === 2);
    contractCheck('parser outcome explicit', ($result['parsed'] ?? false) === true);
    contractCheck(
        'host lint outcome explicit',
        ($result['validation']['lint']['status'] ?? '') === 'passed',
    );
    contractCheck(
        'absent project checks explicit',
        ($result['validation']['checks'] ?? '') === 'not_run',
    );

    $duplicate = $dir . '/duplicate.php';
    $oneMethod = "<?php class Foo { function ping(): void {} }\n";
    file_put_contents($duplicate, $oneMethod);
    $invalid = [
        'files' => [
            [
                'path' => $duplicate,
                'edits' => [
                    [
                        'target' => ['select' => 'class:Foo'],
                        'operation' => 'add_member',
                        'php' => 'function ping(): void {}',
                    ],
                ],
            ],
        ],
    ];
    contractCheck(
        'PHP compile error rejected before write',
        contractRefuses(fn () => (new Editor())->apply($invalid), 'PHP_LINT_FAILED'),
    );
    contractCheck(
        'compile error leaves bytes unchanged',
        file_get_contents($duplicate) === $oneMethod,
    );

    $verifyDir = $dir . '/verify';
    mkdir($verifyDir);
    file_put_contents(
        $verifyDir . '/.php-ast-edit.json',
        json_encode(['canonical' => false, 'verify' => [[PHP_BINARY, '-r', 'exit(1);', '{files}']]]),
    );
    $checked = $verifyDir . '/checked.php';
    file_put_contents($checked, '<?php function oldName() {}');
    $editor = new Editor();
    $result = $editor->apply(
        [
            'files' => [
                [
                    'path' => $checked,
                    'edits' => [
                        [
                            'target' => ['select' => 'function:oldName'],
                            'operation' => 'set_name',
                            'value' => 'newName',
                        ],
                    ],
                ],
            ],
        ],
    );
    contractCheck(
        'failed checks exposed at transaction level',
        ($result['checksPassed'] ?? true) === false,
    );
    contractCheck(
        'failed checks distinct from valid syntax',
        ($result['files'][0]['validation']['checks'] ?? '') === 'failed',
    );
    contractCheck(
        'failed checks keep edit for correction',
        str_contains(file_get_contents($checked), 'newName'),
    );
    $dry = $editor->apply(
        [
            'dryRun' => true,
            'files' => [
                [
                    'path' => $checked,
                    'edits' => [
                        [
                            'target' => ['select' => 'function:newName'],
                            'operation' => 'set_name',
                            'value' => 'laterName',
                        ],
                    ],
                ],
            ],
        ],
    );
    contractCheck(
        'dry run does not reuse earlier checks',
        !isset($dry['files'][0]['verify']) && ($dry['files'][0]['validation']['checks'] ?? '') === 'not_run',
    );
    $dangling = $dir . '/dangling.php';
    symlink('missing-target.php', $dangling);
    $badCreate = ['files' => [['path' => $dangling, 'mode' => 'create', 'php' => '<?php echo 1;']]];
    contractCheck(
        'dangling symlink creation refused',
        contractRefuses(fn () => (new Editor())->apply($badCreate), 'DANGLING_SYMLINK'),
    );
    contractCheck(
        'dangling link and absent target preserved',
        is_link($dangling) && readlink($dangling) === 'missing-target.php' && !file_exists($dir . '/missing-target.php'),
    );
    $swapDir = $dir . '/swap';
    mkdir($swapDir);
    $swapped = $swapDir . '/edited.php';
    $untouched = $swapDir . '/untouched.php';
    $swapOriginal = "<?php function swapOld() {}\n";
    $untouchedOriginal = "<?php echo 'untouched';\n";
    file_put_contents($swapped, $swapOriginal);
    file_put_contents($untouched, $untouchedOriginal);
    chmod($swapped, 0640);
    file_put_contents(
        $swapDir . '/.php-ast-edit.json',
        json_encode(
            [
                'canonical' => true,
                'printWidth' => 80,
                'formatter' => [
                    PHP_BINARY,
                    '-r',
                    'unlink($argv[1]); symlink($argv[2], $argv[1]); exit(1);',
                    '{files}',
                    $untouched,
                ],
            ],
        ),
    );
    $swapRequest = [
        'files' => [
            [
                'path' => $swapped,
                'edits' => [
                    [
                        'target' => ['select' => 'function:swapOld'],
                        'operation' => 'set_name',
                        'value' => 'swapNew',
                    ],
                ],
            ],
        ],
    ];
    contractCheck(
        'failing link-swapping formatter rejected',
        contractRefuses(fn () => (new Editor())->apply($swapRequest), 'COMMIT_FAILED'),
    );
    clearstatcache();
    contractCheck(
        'rollback restores regular file without following new link',
        !is_link($swapped) && file_get_contents($swapped) === $swapOriginal,
    );
    contractCheck(
        'rollback leaves unrelated link destination unchanged',
        file_get_contents($untouched) === $untouchedOriginal,
    );
    contractCheck('rollback restores permission bits', (fileperms($swapped) & 0777) === 0640);
    file_put_contents(
        $dir . '/.php-ast-edit.json',
        '{"canonical":true,"printWidth":80,"custom":{"object":{},"numeric":{"0":"x"}}}',
    );
    RepositoryConfig::write($dir, 100);
    $shape = json_decode(file_get_contents($dir . '/.php-ast-edit.json'));
    contractCheck(
        'normalize preserves empty JSON object',
        $shape->custom->object instanceof stdClass,
    );
    contractCheck(
        'normalize preserves numeric-keyed JSON object',
        $shape->custom->numeric instanceof stdClass,
    );
    unlink($dir . '/.php-ast-edit.json');
    $future = (new Netresearch\PhpAstEdit\PhpLint())->check(
        '<?php echo 1;',
        'future.php',
        PHP_MAJOR_VERSION + 1 . '.0',
    );
    contractCheck(
        'newer runtime target explicitly skips lint',
        $future['status'] === 'skipped' && $future['reason'] === 'target_newer_than_runtime',
    );
    $promoted = $dir . '/promoted.php';
    file_put_contents($promoted, "<?php function ordinary() {}\n");
    contractCheck(
        'promoted parameter outside constructor refused',
        contractRefuses(
            fn () => (new Editor())->apply(
                [
                    'files' => [
                        [
                            'path' => $promoted,
                            'edits' => [
                                [
                                    'target' => ['select' => 'function:ordinary'],
                                    'operation' => 'add_parameter',
                                    'php' => 'private readonly ?Foo $foo = null',
                                ],
                            ],
                        ],
                    ],
                ],
            ),
            'PHP_LINT_FAILED',
        ),
    );
    $cliInput = $dir . '/cli-input.json';
    file_put_contents(
        $cliInput,
        json_encode(
            [
                'files' => [
                    [
                        'path' => $checked,
                        'edits' => [
                            [
                                'target' => ['select' => 'function:newName'],
                                'operation' => 'set_name',
                                'value' => 'checkedAgain',
                            ],
                        ],
                    ],
                ],
            ],
        ),
    );
    ob_start();
    $cliExit = (new Netresearch\PhpAstEdit\Application())->run(['php-ast-edit', 'apply', '--input', $cliInput]);
    $cliResult = json_decode(ob_get_clean(), true);
    contractCheck(
        'CLI failed verify exits one',
        $cliExit === 1 && $cliResult['checksPassed'] === false,
    );
    $version = PHP_MAJOR_VERSION . '.' . PHP_MINOR_VERSION . '.0';
    $versionPath = $dir . '/version-lint.php';
    contractCheck(
        'patch-suffixed current target still rejects compile errors',
        contractRefuses(
            fn () => (new Editor())->apply(
                [
                    'files' => [
                        [
                            'path' => $versionPath,
                            'mode' => 'create',
                            'phpVersion' => $version,
                            'php' => '<?php class VersionLint { function duplicate() {} function duplicate() {} }',
                        ],
                    ],
                ],
            ),
            'PHP_LINT_FAILED',
        ),
    );
    contractCheck('failed patch-version lint creates no file', !file_exists($versionPath));
    $versionLint = (new Netresearch\PhpAstEdit\PhpLint())->check('<?php echo 1;', 'current.php', $version);
    contractCheck('patch-suffixed current target runs lint', $versionLint['status'] === 'passed');
} finally {
    contractClean($dir);
}

if ($failures !== []) {
    fwrite(STDERR, implode("\n", $failures) . "\n");
    exit(1);
}
echo "OK: {$count} transaction and validation contract checks passed.\n";
