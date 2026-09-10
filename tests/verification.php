<?php

declare(strict_types=1);
require_once dirname(__DIR__) . '/vendor/autoload.php';
use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\FileTransaction;
use Netresearch\PhpAstEdit\RepositoryConfig;
use Netresearch\PhpAstEdit\VerificationRunner;

$dir = sys_get_temp_dir() . '/php-ast-verification-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
$failures = [];
$count = 0;

function verificationAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}
function verificationCase(string $name, callable $check): void
{
    global $failures, $count;
    ++$count;

    try {
        $check();
    } catch (Throwable $failure) {
        $failures[] = $name . ': ' . $failure->getMessage();
    }
}
function verificationClean(string $path): void
{
    if (is_link($path) || !is_dir($path)) {
        unlink($path);

        return;
    }

    foreach (new FilesystemIterator($path) as $entry) {
        verificationClean($entry->getPathname());
    }
    rmdir($path);
}
function verificationConfig(string $root, array $verify, array $exclude = []): void
{
    file_put_contents(
        $root . '/.php-ast-edit.json',
        json_encode(
            ['canonical' => false, 'verify' => $verify, 'exclude' => $exclude],
            JSON_THROW_ON_ERROR,
        ),
    );
}
function verificationFile(
    string $path,
    string $mode = 'edit',
    bool $changed = true,
): FileTransaction {
    $existed = is_file($path);
    $file = new FileTransaction(
        $path,
        $mode,
        $existed ? file_get_contents($path) : null,
        [],
        null,
        null,
        $existed,
    );
    $file->changed = $changed;

    return $file;
}
function verificationRecorder(string $label): array
{
    return [
        PHP_BINARY,
        '-r',
        'file_put_contents("calls.jsonl", json_encode(["cwd" => getcwd(), "args" => $argv]) . "\n", FILE_APPEND);',
        $label,
    ];
}
function verificationCalls(string $root): array
{
    $path = $root . '/calls.jsonl';

    return is_file($path) ? array_map(
        static fn (string $line): array => json_decode($line, true, 512, JSON_THROW_ON_ERROR),
        file($path, FILE_IGNORE_NEW_LINES),
    ) : [];
}

try {
    verificationCase(
        'legacy argv lists and explicit scopes parse',
        function () use ($dir): void {
            $root = $dir . '/schema';
            mkdir($root);
            $legacy = [PHP_BINARY, '-r', 'exit(0);', '{files}'];
            $project = ['scope' => 'project', 'command' => [PHP_BINARY, '-r', 'exit(0);']];
            $changed = ['scope' => 'changed_files', 'command' => $legacy];
            verificationConfig($root, [$legacy, $project, $changed]);
            $config = RepositoryConfig::fromFile($root . '/.php-ast-edit.json');
            verificationAssert(
                $config->verify === [$legacy, $project, $changed],
                'parsed configuration changed compatible entries',
            );
        },
    );
    verificationCase(
        'invalid verification shapes are rejected',
        function () use ($dir): void {
            $path = $dir . '/invalid.json';
            $entries = [
                '{}',
                'true',
                '"check"',
                '[{}]',
                '[[]]',
                '[{"0":"php","1":"{files}"}]',
                '[{"scope":"unknown","command":["php"]}]',
                '[{"scope":"project","command":["php","{files}"]}]',
                '[{"scope":"project","command":["php","--paths={files}"]}]',
                '[{"scope":"changed_files","command":["php"]}]',
                '[{"scope":"changed_files","command":["php","{files}","{files}"]}]',
                '[{"scope":"project","command":[]}]',
                '[{"scope":"project","command":{}}]',
                '[{"scope":"project","command":["php",null]}]',
                '[{"scope":"project","command":["php",false]}]',
                '[{"scope":"project","command":["php",""]}]',
                '[{"scope":"project","command":["php","a\u0000b"]}]',
                '[{"scope":"project"}]',
                '[{"command":["php"]}]',
                '[{"scope":"project","command":["php"],"cwd":"elsewhere"}]',
            ];

            foreach ($entries as $entry) {
                file_put_contents($path, '{"verify":' . $entry . '}');
                $refused = false;

                try {
                    RepositoryConfig::fromFile($path);
                } catch (EditException $failure) {
                    $refused = str_contains($failure->getMessage(), 'verify');
                }
                verificationAssert($refused, 'accepted invalid verify: ' . $entry);
            }
        },
    );
    verificationCase(
        'mixed changes execute once per scope with accurate coverage',
        function () use ($dir): void {
            $root = $dir . '/mixed';
            mkdir($root);
            $keep = $root . '/keep.php';
            $create = $root . '/new.php';
            $delete = $root . '/removed.php';
            $same = $root . '/same.php';
            $excluded = $root . '/excluded.php';

            foreach ([$keep, $delete, $same, $excluded] as $path) {
                file_put_contents($path, '<?php');
            }
            $legacy = [...verificationRecorder('files'), '{files}'];
            $project = ['scope' => 'project', 'command' => verificationRecorder('project')];
            verificationConfig($root, [$legacy, $project], ['excluded.php']);
            $files = [
                verificationFile($keep),
                verificationFile($create, 'create'),
                verificationFile($delete, 'delete'),
                verificationFile($same, 'edit', false),
                verificationFile($excluded),
            ];
            $runner = new VerificationRunner();
            $prepared = $runner->prepare($files);
            unlink($delete);
            file_put_contents($create, '<?php');
            $reports = $runner->run($prepared);
            $calls = verificationCalls($root);
            verificationAssert(
                count($calls) === 2 && count($reports) === 2,
                'checks were skipped or duplicated',
            );
            verificationAssert(
                $calls[0]['args'] === ['Standard input code', 'files', $keep, $create],
                'changed-file argv contains unrelated or deleted paths',
            );
            verificationAssert(
                $calls[1]['args'] === ['Standard input code', 'project'],
                'project received a files argument',
            );
            verificationAssert(
                array_column($reports, 'scope') === ['changed_files', 'project'],
                'scope metadata differs',
            );
            verificationAssert(
                $reports[0]['cwd'] === $root && $reports[1]['cwd'] === $root,
                'cwd metadata differs',
            );
            verificationAssert(
                $reports[0]['id'] !== $reports[1]['id'],
                'distinct executions share identity',
            );
            verificationAssert(
                $files[0]->verify === $reports && $files[1]->verify === $reports,
                'changed-file coverage differs',
            );
            verificationAssert(
                $files[2]->verify === [$reports[1]],
                'deletion claims changed-files coverage',
            );
            verificationAssert(
                $files[3]->verify === [] && $files[4]->verify === [],
                'unchanged or excluded files claim checks',
            );
        },
    );
    verificationCase(
        'delete-only project checks survive config changes after preparation',
        function () use ($dir): void {
            $root = $dir . '/delete';
            mkdir($root);
            $path = $root . '/last.php';
            file_put_contents($path, '<?php');
            verificationConfig(
                $root,
                [
                    [...verificationRecorder('files'), '{files}'],
                    ['scope' => 'project', 'command' => verificationRecorder('original')],
                ],
            );
            $file = verificationFile($path, 'delete');
            $runner = new VerificationRunner();
            $prepared = $runner->prepare([$file]);
            unlink($path);
            verificationConfig(
                $root,
                [['scope' => 'project', 'command' => verificationRecorder('replacement')]],
            );
            $reports = $runner->run($prepared);
            verificationAssert(
                count($reports) === 1 && $reports[0]['scope'] === 'project',
                'delete-only scope scheduling differs',
            );
            verificationAssert(
                verificationCalls($root)[0]['args'][1] === 'original',
                'prepared command was rediscovered after writes',
            );
            verificationAssert(
                $file->verify === $reports,
                'deleted file lacks actual project report',
            );
        },
    );
    verificationCase(
        'excluded deleted paths remain excluded after unlink',
        function () use ($dir): void {
            $root = $dir . '/excluded-delete';
            mkdir($root);
            $path = $root . '/excluded.php';
            file_put_contents($path, '<?php');
            verificationConfig(
                $root,
                [['scope' => 'project', 'command' => verificationRecorder('excluded')]],
                ['excluded.php'],
            );
            $file = verificationFile($path, 'delete');
            $runner = new VerificationRunner();
            $prepared = $runner->prepare([$file]);
            unlink($path);
            verificationAssert(
                $runner->run($prepared) === [] && verificationCalls($root) === [] && $file->verify === [],
                'deletion lost exclusion snapshot',
            );
        },
    );
    verificationCase(
        'nested configuration roots retain separate execution identities',
        function () use ($dir): void {
            $root = $dir . '/roots';
            $nested = $root . '/nested';
            mkdir($nested, 0700, true);
            $command = ['scope' => 'project', 'command' => verificationRecorder('same-command')];
            verificationConfig($root, [$command]);
            verificationConfig($nested, [$command]);
            $first = $root . '/a.php';
            $second = $nested . '/b.php';
            file_put_contents($first, '<?php');
            file_put_contents($second, '<?php');
            $runner = new VerificationRunner();
            $reports = $runner->run($runner->prepare([verificationFile($first), verificationFile($second)]));
            verificationAssert(count($reports) === 2, 'different roots were deduplicated');
            verificationAssert(
                array_column($reports, 'cwd') === [$root, $nested],
                'root ordering or cwd differs',
            );
            verificationAssert(
                $reports[0]['id'] !== $reports[1]['id'],
                'different roots share execution identity',
            );
            verificationAssert(
                count(verificationCalls($root)) === 1 && count(verificationCalls($nested)) === 1,
                'a root did not execute exactly once',
            );
        },
    );
    verificationCase(
        'nonzero checks retain bounded output and argv boundaries',
        function () use ($dir): void {
            $root = $dir . '/failure';
            mkdir($root);
            $path = $root . '/a.php';
            file_put_contents($path, '<?php');
            $literal = 'space ; $(touch SHOULD_NOT_EXIST)';
            $command = [
                PHP_BINARY,
                '-r',
                'echo $argv[1], "\n", str_repeat("X", 6000); fwrite(STDERR, "stderr"); exit(3);',
                $literal,
            ];
            verificationConfig($root, [['scope' => 'project', 'command' => $command]]);
            $runner = new VerificationRunner();
            $reports = $runner->run($runner->prepare([verificationFile($path)]));
            verificationAssert(
                $reports[0]['ok'] === false && strlen($reports[0]['output']) === 4000,
                'failure output is not bounded to 4000 bytes',
            );
            verificationAssert(
                str_starts_with($reports[0]['output'], "stderr\n" . $literal . "\n"),
                'argv data was interpreted by a shell',
            );
            verificationAssert(
                $reports[0]['command'] === implode(' ', $command),
                'legacy command report changed',
            );
            verificationAssert(!file_exists($root . '/SHOULD_NOT_EXIST'), 'shell syntax executed');
        },
    );
    verificationCase(
        'invalid delete-only configuration fails before any write',
        function () use ($dir): void {
            $root = $dir . '/invalid-delete';
            mkdir($root);
            $path = $root . '/delete.php';
            $first = $dir . '/must-not-create.php';
            file_put_contents($path, '<?php');
            file_put_contents(
                $root . '/.php-ast-edit.json',
                '{"verify":[{"scope":"project","command":["php","{files}"]}]}',
            );
            $refused = false;

            try {
                (new Editor())->apply(
                    [
                        'files' => [
                            ['path' => $first, 'mode' => 'create', 'php' => '<?php echo 1;'],
                            ['path' => $path, 'mode' => 'delete'],
                        ],
                    ],
                );
            } catch (EditException $failure) {
                $refused = str_contains($failure->getMessage(), 'verify');
            }
            verificationAssert(
                $refused && is_file($path) && !file_exists($first),
                'configuration failure happened after mutation',
            );
        },
    );
    verificationCase(
        'project check detects an unchanged consumer broken by valid PHP rename',
        function () use ($dir): void {
            $root = $dir . '/consumer';
            mkdir($root);
            $path = $root . '/Api.php';
            file_put_contents($path, '<?php function oldApi(): int { return 1; }');
            file_put_contents(
                $root . '/Consumer.php',
                '<?php require __DIR__ . "/Api.php"; oldApi();',
            );
            verificationConfig(
                $root,
                [['scope' => 'project', 'command' => [PHP_BINARY, 'Consumer.php']]],
            );
            $result = (new Editor())->apply(
                [
                    'files' => [
                        [
                            'path' => $path,
                            'edits' => [
                                [
                                    'target' => ['select' => 'function:oldApi'],
                                    'operation' => 'set_name',
                                    'value' => 'newApi',
                                ],
                            ],
                        ],
                    ],
                ],
            );
            verificationAssert(
                $result['checksPassed'] === false,
                'broken unchanged consumer passed',
            );
            verificationAssert(
                $result['files'][0]['validation']['parser'] === 'passed' && $result['files'][0]['validation']['checks'] === 'failed',
                'syntax and project result conflated',
            );
            verificationAssert(
                str_contains(file_get_contents($path), 'newApi'),
                'failed check unexpectedly rolled back the intended edit',
            );
            verificationAssert(
                $result['files'][0]['verify'][0]['ok'] === false,
                'failed project check was not reported',
            );
        },
    );
    verificationCase(
        'project verification runs after formatting and never during dry run',
        function () use ($dir): void {
            $root = $dir . '/format';
            mkdir($root);
            file_put_contents(
                $root . '/.editorconfig',
                "root = true\n[*.php]\nmax_line_length = 100\n",
            );
            file_put_contents(
                $root . '/.php-ast-edit.json',
                json_encode(
                    [
                        'canonical' => true,
                        'formatter' => [PHP_BINARY, '-r', 'file_put_contents("formatted", "yes");', '{files}'],
                        'verify' => [
                            [
                                'scope' => 'project',
                                'command' => [PHP_BINARY, '-r', 'exit(is_file("formatted") ? 0 : 1);'],
                            ],
                        ],
                    ],
                    JSON_THROW_ON_ERROR,
                ),
            );
            $path = $root . '/new.php';
            $document = ['files' => [['path' => $path, 'mode' => 'create', 'php' => '<?php echo 1;']]];
            $dry = (new Editor())->apply($document, true);
            verificationAssert(
                !is_file($root . '/formatted') && !is_file($path) && $dry['checksPassed'] === null,
                'dry run executed project tools',
            );
            $result = (new Editor())->apply($document);
            verificationAssert(
                $result['checksPassed'] === true,
                'project check ran before formatter',
            );
        },
    );
    verificationCase(
        'relative nested creates preserve preparation cwd',
        function () use ($dir): void {
            $root = $dir . '/relative';
            mkdir($root);
            verificationConfig($root, [[...verificationRecorder('relative'), '{files}']]);
            $previous = getcwd();
            chdir($dir);

            try {
                $file = verificationFile('relative/nested/New.php', 'create');
                $runner = new VerificationRunner();
                $prepared = $runner->prepare([$file]);
                mkdir($root . '/nested');
                file_put_contents($root . '/nested/New.php', '<?php');
                $reports = $runner->run($prepared);
                verificationAssert(
                    count($reports) === 1 && $reports[0]['ok'],
                    'relative create check did not execute',
                );
                verificationAssert(
                    verificationCalls($root)[0]['args'][2] === $root . '/nested/New.php',
                    'relative path was interpreted against check cwd',
                );
            } finally {
                chdir($previous);
            }
        },
    );
    verificationCase(
        'delete-only apply executes project checks after deletion',
        function () use ($dir): void {
            $root = $dir . '/delete-integration';
            mkdir($root);
            $path = $root . '/gone.php';
            file_put_contents($path, '<?php');
            verificationConfig(
                $root,
                [
                    [...verificationRecorder('files'), '{files}'],
                    [
                        'scope' => 'project',
                        'command' => [
                            PHP_BINARY,
                            '-r',
                            'file_put_contents("observed", "called"); exit(is_file("gone.php") ? 1 : 0);',
                        ],
                    ],
                ],
            );
            $result = (new Editor())->apply(
                ['report' => 'compact', 'files' => [['path' => $path, 'mode' => 'delete']]],
            );
            verificationAssert(
                !is_file($path) && is_file($root . '/observed') && $result['checksPassed'] === true,
                'delete-only check did not observe deletion',
            );
            verificationAssert(
                verificationCalls($root) === [],
                'changed-files command executed for delete-only apply',
            );
            verificationAssert(
                count($result['verify']) === 1 && $result['verify'][0]['scope'] === 'project',
                'delete-only actual executions differ',
            );
            verificationAssert(
                $result['files'][0]['checkIds'] === [$result['verify'][0]['id']],
                'deleted file lacks its project check identity',
            );
        },
    );
    verificationCase(
        'a passing project check is named as already run, and only then',
        function () use ($dir): void {
            $pass = [PHP_BINARY, '-r', 'exit(0);'];
            $fail = [PHP_BINARY, '-r', 'exit(1);'];
            $shapes = [
                'project passes' => [[['scope' => 'project', 'command' => $pass]], true],
                'only changed files' => [[['scope' => 'changed_files', 'command' => [...$pass, '{files}']]], false],
                'a check fails' => [
                    [
                        ['scope' => 'project', 'command' => $pass],
                        ['scope' => 'project', 'command' => $fail],
                    ],
                    false,
                ],
                'nothing declared' => [[], false],
            ];

            foreach ($shapes as $label => [$verify, $named]) {
                $root = $dir . '/already-' . md5($label);
                mkdir($root);
                verificationConfig($root, $verify);
                $path = $root . '/a.php';

                foreach (['full', 'compact', 'agent'] as $report) {
                    file_put_contents($path, "<?php\nfunction a(): int { return 1; }\n");
                    $result = (new Editor())->apply(
                        [
                            'report' => $report,
                            'files' => [
                                [
                                    'path' => $path,
                                    'edits' => [
                                        [
                                            'target' => ['select' => 'function:a'],
                                            'operation' => 'set_name',
                                            'value' => 'b',
                                        ],
                                    ],
                                ],
                            ],
                        ],
                    );
                    verificationAssert(
                        array_key_exists('alreadyRun', $result) === $named,
                        $label . ' in ' . $report . ': alreadyRun ' . ($named ? 'missing' : 'present'),
                    );

                    if ($named) {
                        verificationAssert(
                            str_contains($result['alreadyRun'], 'exit(0);') && !str_contains($result['alreadyRun'], '{files}'),
                            $label . ' in ' . $report . ': alreadyRun does not name the project command',
                        );
                    }
                }
            }
        },
    );
} finally {
    verificationClean($dir);
}

foreach ($failures as $failure) {
    fwrite(STDERR, "FAIL: " . $failure . "\n");
}
echo "verification: " . $count . " cases, " . count($failures) . " failures\n";
exit($failures === [] ? 0 : 1);
