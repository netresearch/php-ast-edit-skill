<?php

declare(strict_types=1);

/**
 * The formatting contract: canonical by declaration, format-preserving as the announced
 * fallback, and a printer whose output a human can read.
 */
$root = dirname(__DIR__);
$autoload = $root . '/vendor/autoload.php';

if (!is_file($autoload)) {
    fwrite(STDERR, "SKIP: vendor/autoload.php missing; run composer install.\n");
    exit(0);
}
require_once $autoload;
use Netresearch\PhpAstEdit\CanonicalPrinter;
use PhpParser\PhpVersion;
use Netresearch\PhpAstEdit\Doctor;
use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\EditorConfig;
use Netresearch\PhpAstEdit\Formatter;
use Netresearch\PhpAstEdit\RepositoryConfig;
use PhpParser\ParserFactory;

$problems = [];
$passed = 0;
function check(string $name, bool $condition, string $detail = ''): void
{
    global $problems, $passed;

    if ($condition) {
        ++$passed;

        return;
    }
    $problems[] = $name . ($detail === '' ? '' : ': ' . $detail);
}
function workspace(): string
{
    $dir = sys_get_temp_dir() . '/php-ast-edit-fmt-' . bin2hex(random_bytes(6));
    mkdir($dir, 0700, true);
    // A repository root, so the marker lands where RepositoryConfig looks for it.
    file_put_contents($dir . '/composer.json', "{}\n");
    // The width is the project's declaration, so a workspace that wants canonical printing
    // has to make it — the same thing the tool asks of a real repository.
    file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nmax_line_length = 80\n");

    return $dir;
}
function removeTree(string $directory): void
{
    foreach (glob($directory . '/*') ?: [] as $entry) {
        is_dir($entry) ? removeTree($entry) : @unlink($entry);
    }
    @rmdir($directory);
}
$parser = (new ParserFactory())->createForHostVersion();
// ---- The printer breaks by width -------------------------------------------------------
$long = "<?php\n\$x = foo('aaaaaaaaaaaaaaaaaaaa', 'bbbbbbbbbbbbbbbbbbbb', 'cccccccccccccccccccc', 'dddddddddddddddddddd');\n";
$wide = (new CanonicalPrinter(null, 200))->prettyPrintFile($parser->parse($long));
$narrow = (new CanonicalPrinter(null, 40))->prettyPrintFile($parser->parse($long));
check('a list within budget stays on one line', substr_count(trim($wide), "\n") === 2, trim($wide));
check('a list over budget is broken', substr_count($narrow, "\n") > 4, trim($narrow));
check('breaking puts one argument per line', str_contains($narrow, "'aaaaaaaaaaaaaaaaaaaa',\n"));
$params = "<?php\nfunction f(string \$aaaaaaaaaaaaaaaaaaaa, string \$bbbbbbbbbbbbbbbbbbbb, string \$cccccccccccccccccccc) {}\n";
$narrowParams = (new CanonicalPrinter(null, 40))->prettyPrintFile($parser->parse($params));
check('a parameter list over budget is broken', substr_count($narrowParams, "\n") > 4, trim($narrowParams));

// The width must actually be the lever, and printing must be a fixed point of itself.
foreach ([40, 80, 200] as $width) {
    $printer = new CanonicalPrinter(null, $width);
    $once = $printer->prettyPrintFile($parser->parse($long));
    $twice = $printer->prettyPrintFile($parser->parse($once));
    check("printing is idempotent at width {$width}", $once === $twice);
}
// ---- The declaration decides the printer -----------------------------------------------
$dir = workspace();
file_put_contents(
    $dir . '/a.php',
    "<?php\nclass Foo\n{\n    public function bar()\n    {\n        return 1;\n    }\n}\n",
);
$editor = new Editor();
$document = static fn (string $path): array => [
    'files' => [
        [
            'path' => $path,
            'edits' => [
                [
                    'target' => ['ref' => 'stmts[0].name'],
                    'operation' => 'set_name',
                    'value' => 'Renamed',
                ],
            ],
        ],
    ],
];
$result = $editor->apply($document($dir . '/a.php'), true)['files'][0];
check(
    'without a declaration the fallback is format-preserving',
    $result['printer'] === 'format-preserving',
    $result['printer'],
);
check('and it says so', str_contains($result['warning'] ?? '', 'NOT_CANONICAL'));
check(
    'the fallback changes only the edited line',
    $result['changedLines'] === 2,
    (string) $result['changedLines'],
);
RepositoryConfig::write($dir, 80);
$result = $editor->apply($document($dir . '/a.php'), true)['files'][0];
check('a declared repository prints canonically', $result['printer'] === 'canonical', $result['printer']);
check('and carries no warning', !isset($result['warning']), $result['warning'] ?? '');
// A repository declared canonical before the width moved into .editorconfig still prints —
// by the width its normalisation recorded — and is told what to add.
unlink($dir . '/.editorconfig');
$migrating = $editor->apply($document($dir . '/a.php'), true)['files'][0];
check(
    'a repository without a declared width still prints canonically',
    $migrating['printer'] === 'canonical',
);
check(
    'and is told the width belongs in .editorconfig',
    str_contains($migrating['warning'] ?? '', 'NO_DECLARED_WIDTH'),
);
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nmax_line_length = 80\n");
$forced = $editor->apply(
    [
        'files' => [
            [
                'path' => $dir . '/a.php',
                'printer' => 'format-preserving',
                'edits' => [
                    [
                        'target' => ['ref' => 'stmts[0].name'],
                        'operation' => 'set_name',
                        'value' => 'Renamed',
                    ],
                ],
            ],
        ],
    ],
    true,
)['files'][0];
check('an explicit printer overrides the declaration', $forced['printer'] === 'format-preserving');

try {
    $editor->apply(
        [
            'files' => [
                [
                    'path' => $dir . '/a.php',
                    'printer' => 'nonsense',
                    'edits' => [
                        [
                            'target' => ['ref' => 'stmts[0].name'],
                            'operation' => 'set_name',
                            'value' => 'X',
                        ],
                    ],
                ],
            ],
        ],
        true,
    );
    check('an unknown printer is refused', false, 'accepted');
} catch (Throwable $throwable) {
    check('an unknown printer is refused', str_contains($throwable->getMessage(), 'printer must be'));
}
removeTree($dir);
// ---- Format-preserving must hold for every operation class, not just renames ------------
// printFormatPreserving() falls back to full printing for a subtree it cannot map, silently.
// Each class is therefore measured, not assumed.
$cases = [
    'set_name' => [
        "<?php\nclass Foo\n{\n    public function bar()\n    {\n        return 1;\n    }\n}\n",
        ['target' => ['ref' => 'stmts[0].stmts[0].name'], 'operation' => 'set_name', 'value' => 'baz'],
        2,
    ],
    'set_string' => [
        "<?php\n\$a = 'old';\n\$b = 2;\n\$c = 3;\n",
        ['target' => ['ref' => 'stmts[0].expr.expr'], 'operation' => 'set_string', 'value' => 'new'],
        2,
    ],
    'insert_into' => [
        "<?php\nclass Foo\n{\n    public int \$a = 1;\n}\n",
        [
            'target' => ['ref' => 'stmts[0]'],
            'operation' => 'add_member',
            'php' => 'public int $b = 2;',
        ],
        2,
    ],
    'delete_node' => [
        "<?php\nfunction f()\n{\n    \$a = 1;\n    \$b = 2;\n    \$c = 3;\n}\n",
        ['target' => ['ref' => 'stmts[0].stmts[1]'], 'operation' => 'delete_node'],
        1,
    ],
    'set_doc_comment' => [
        "<?php\nclass Foo\n{\n    public function bar()\n    {\n        return 1;\n    }\n}\n",
        [
            'target' => ['ref' => 'stmts[0].stmts[0]'],
            'operation' => 'set_doc_comment',
            'value' => 'Docs.',
        ],
        3,
    ],
    'replace_expression' => [
        "<?php\n\$a = 1;\n\$b = 2;\n\$c = 3;\n",
        [
            'target' => ['ref' => 'stmts[1].expr.expr'],
            'operation' => 'replace_expression',
            'php' => '99',
        ],
        2,
    ],
];

foreach ($cases as $label => [$source, $edit, $budget]) {
    $dir = workspace();
    file_put_contents($dir . '/a.php', $source);
    $result = (new Editor())->apply(
        [
            'files' => [['path' => $dir . '/a.php', 'printer' => 'format-preserving', 'edits' => [$edit]]],
        ],
        true,
    )['files'][0];
    check(
        "format-preserving keeps {$label} local",
        $result['changedLines'] <= $budget,
        $result['changedLines'] . ' changed lines, budget ' . $budget,
    );
    removeTree($dir);
}
// ---- format and normalize ---------------------------------------------------------------
$dir = workspace();
file_put_contents($dir . '/a.php', "<?php\nclass  Foo{\npublic function bar(){return 1;}\n}\n");
$before = (string) file_get_contents($dir . '/a.php');
$dry = (new Formatter())->format([$dir], 80, true);
check(
    'format --dry-run reports the file',
    $dry['changed'] === [$dir . '/a.php'],
    implode(',', $dry['changed']),
);
check('format --dry-run writes nothing', file_get_contents($dir . '/a.php') === $before);
$run = (new Formatter())->format([$dir], 80, false);
check('format rewrites the file', file_get_contents($dir . '/a.php') !== $before);
check('format reports no failures', $run['failed'] === []);
$again = (new Formatter())->format([$dir], 80, false);
check('format is idempotent', $again['changed'] === [], implode(',', $again['changed']));
$path = RepositoryConfig::write($dir, 100);
$config = RepositoryConfig::discover($dir . '/a.php');
check('the declaration is found from a file', $config->canonical && $config->width === 100);
check('the marker names its own path', $config->path === $path);
check('the root is where composer.json is', RepositoryConfig::rootFor($dir . '/a.php') === realpath($dir));
// A broken declaration must be named, not ignored.
file_put_contents($dir . '/' . RepositoryConfig::FILE, "{ not json\n");

try {
    RepositoryConfig::discover($dir);
    check('invalid declaration JSON is refused', false, 'accepted');
} catch (Throwable $throwable) {
    check('invalid declaration JSON is refused', str_contains($throwable->getMessage(), 'not valid JSON'));
}
removeTree($dir);
// ---- normalize must not declare what it did not do -------------------------------------
$dir = workspace();
mkdir($dir . '/sub', 0700, true);
file_put_contents($dir . '/sub/a.php', "<?php\nclass  Foo{}\n");
$app = static function (array $argv) use ($dir): array {
    $out = [];
    exec(
        escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(dirname(__DIR__) . '/bin/php-ast-edit') . ' ' . implode(' ', array_map('escapeshellarg', $argv)) . ' 2>/dev/null',
        $out,
    );

    return json_decode(implode("\n", $out), true) ?? [];
};
$partial = $app(['normalize', '--path', $dir . '/sub']);
// `?? ` treats an explicit null as absent, which is exactly the value under test here.
check(
    'a partial normalize does not declare the repository',
    array_key_exists('declared', $partial) && $partial['declared'] === null,
    json_encode($partial['declared'] ?? '<missing>'),
);
check('and says why', str_contains($partial['next'] ?? '', 'whole'));
check('no marker was written', !is_file($dir . '/' . RepositoryConfig::FILE));
$whole = $app(['normalize', '--path', $dir]);
check('a full normalize declares the repository', is_string($whole['declared'] ?? null));
removeTree($dir);
// A width the read path would reject must never be written.
$dir = workspace();
file_put_contents($dir . '/a.php', "<?php\nclass Foo {}\n");

try {
    RepositoryConfig::write($dir, 10);
    check('a width below the minimum is refused', false, 'accepted');
} catch (Throwable $throwable) {
    check('a width below the minimum is refused', str_contains($throwable->getMessage(), 'at least'));
}
check('and no marker was left behind', !is_file($dir . '/' . RepositoryConfig::FILE));
removeTree($dir);
// ---- writing through a symlink must not replace the link -------------------------------
// rename() over a symlink swaps the link for a regular file: the topology changes and the
// file everybody else reads stays untouched. Both writers went through it.
$dir = workspace();
mkdir($dir . '/real', 0700, true);
file_put_contents($dir . '/real/a.php', "<?php\nclass  Foo{}\n");
symlink('real/a.php', $dir . '/link.php');
(new Formatter())->format([$dir . '/link.php'], 80, false);
check('format keeps the symlink a symlink', is_link($dir . '/link.php'));
check(
    'format writes through to the target',
    str_contains((string) file_get_contents($dir . '/real/a.php'), 'class Foo'),
);
RepositoryConfig::write($dir, 80);
(new Editor())->apply(
    [
        'files' => [
            [
                'path' => $dir . '/link.php',
                'printer' => 'canonical',
                'edits' => [
                    [
                        'target' => ['ref' => 'stmts[0].name'],
                        'operation' => 'set_name',
                        'value' => 'Renamed',
                    ],
                ],
            ],
        ],
    ],
);
check('apply keeps the symlink a symlink', is_link($dir . '/link.php'));
check(
    'apply writes through to the target',
    str_contains((string) file_get_contents($dir . '/real/a.php'), 'class Renamed'),
);
removeTree($dir . '/real');
removeTree($dir);
// ---- the width is the project's declaration, read from .editorconfig ---------------------
$dir = workspace();
check('a width under [*] is read', EditorConfig::discover($dir)->maxLineLength === 80);
file_put_contents(
    $dir . '/.editorconfig',
    "root = true\n\n[*]\nmax_line_length = 80\n\n[*.php]\nmax_line_length = 120\n",
);
check('a php-specific section outranks the catch-all', EditorConfig::discover($dir)->maxLineLength === 120);
file_put_contents(
    $dir . '/.editorconfig',
    "root = true\n\n[*.php]\nmax_line_length = 120\n\n[*]\nmax_line_length = 80\n",
);
check('and does so whatever the order', EditorConfig::discover($dir)->maxLineLength === 120);
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nmax_line_length = off\n");
check('"off" is not a width', EditorConfig::discover($dir)->maxLineLength === null);
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*.md]\nmax_line_length = 80\n");
check('a section for other files is ignored', EditorConfig::discover($dir)->maxLineLength === null);
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nindent_size = 4\n");
check('a config without the key declares nothing', EditorConfig::discover($dir)->maxLineLength === null);
// The nearest file wins, and root = true stops the walk.
mkdir($dir . '/nested', 0700, true);
file_put_contents($dir . '/nested/.editorconfig', "[*]\nmax_line_length = 60\n");
check('the nearest declaration wins', EditorConfig::discover($dir . '/nested')->maxLineLength === 60);
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nmax_line_length = 80\n");
unlink($dir . '/nested/.editorconfig');
check(
    'a nested directory inherits upwards',
    EditorConfig::discover($dir . '/nested')->maxLineLength === 80,
);
removeTree($dir);
// normalize refuses to declare a repository canonical when the project states no width.
$dir = sys_get_temp_dir() . '/php-ast-edit-nowidth-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
file_put_contents($dir . '/composer.json', "{}\n");
file_put_contents($dir . '/a.php', "<?php\nclass  Foo{}\n");
$out = [];
exec(
    escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(dirname(__DIR__) . '/bin/php-ast-edit') . ' normalize --path ' . escapeshellarg($dir) . ' 2>/dev/null',
    $out,
);
$report = json_decode(implode("\n", $out), true) ?? [];
check(
    'no declared width, no declaration',
    array_key_exists('declared', $report) && $report['declared'] === null,
);
check('and the reason names .editorconfig', str_contains($report['next'] ?? '', 'max_line_length'));
check('the marker was not written', !is_file($dir . '/' . RepositoryConfig::FILE));
removeTree($dir);
// A width the project declares but nothing can use is refused where it is read, before any
// file is rewritten — not after the formatter has already been through them.
$dir = workspace();
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nmax_line_length = 10\n");
file_put_contents($dir . '/a.php', "<?php\nclass  Foo{}\n");
$before = (string) file_get_contents($dir . '/a.php');

try {
    RepositoryConfig::widthFor($dir . '/a.php');
    check('a declared width below the minimum is refused', false, 'accepted');
} catch (Throwable $throwable) {
    check(
        'a declared width below the minimum is refused',
        str_contains($throwable->getMessage(), 'at least'),
    );
}
check('and nothing was rewritten', file_get_contents($dir . '/a.php') === $before);
removeTree($dir);
// The declaration outranks what the last normalisation recorded, so `apply` and `format`
// cannot end up printing the same file at two different widths.
$dir = workspace();
file_put_contents($dir . '/.editorconfig', "root = true\n\n[*]\nmax_line_length = 120\n");
RepositoryConfig::write($dir, 40);
$width = RepositoryConfig::widthFor($dir . '/a.php');
check('the declaration outranks the recorded width', $width['width'] === 120 && $width['recorded'] === 40);
removeTree($dir);
// ---- exclusions: a fixture is input data, not source ------------------------------------
$dir = workspace();
mkdir($dir . '/fixtures', 0700, true);
file_put_contents($dir . '/a.php', "<?php\nclass  Foo{}\n");
file_put_contents($dir . '/fixtures/keep.php', "<?php\nclass  Untouched{}\n");
$fixture = (string) file_get_contents($dir . '/fixtures/keep.php');
$run = (new Formatter())->format([$dir], 80, false, ['fixtures'], $dir);
check('an excluded path is left alone', file_get_contents($dir . '/fixtures/keep.php') === $fixture);
check('everything else is still formatted', file_get_contents($dir . '/a.php') !== "<?php\nclass  Foo{}\n");
check(
    'and the excluded file is not reported as changed',
    !in_array($dir . '/fixtures/keep.php', $run['changed'], true),
);
// Scanning from a relative path must exclude the same files as scanning from an absolute
// one — the resolved path is what is compared, not the string the scan happened to produce.
$cwd = getcwd();
chdir($dir);
file_put_contents($dir . '/a.php', "<?php\nclass  Foo{}\n");
(new Formatter())->format(['.'], 80, false, ['fixtures'], $dir);
chdir((string) $cwd);
check(
    'a relative scan honours the same exclusions',
    file_get_contents($dir . '/fixtures/keep.php') === $fixture,
);
RepositoryConfig::write($dir, 80, ['fixtures']);
check('the exclusions are recorded', RepositoryConfig::discover($dir)->exclude === ['fixtures']);
removeTree($dir);

// An exclusion that names nothing excludes everything, and the formatting gate would then
// pass without having looked at a single file.
foreach ([[''], ['   '], ['.'], ['./']] as $blank) {
    try {
        RepositoryConfig::assertExclusions($blank);
        check('a blank exclusion is refused: ' . json_encode($blank), false, 'accepted');
    } catch (Throwable $throwable) {
        check(
            'a blank exclusion is refused: ' . json_encode($blank),
            str_contains($throwable->getMessage(), 'excludes everything'),
        );
    }
}
check(
    'a real path is still accepted',
    (static function (): bool {
        RepositoryConfig::assertExclusions(['tests/fixtures']);

        return true;
    })(),
);
// ---- doctor ------------------------------------------------------------------------------
$dir = workspace();
$report = (new Doctor())->examine($dir);
check('a bare repository is not ready', $report['status'] === 'warn');
check(
    'and the missing formatter is named',
    str_contains(implode(' ', $report['findings']), 'No formatter configuration'),
);
mkdir($dir . '/.github/workflows', 0700, true);
// A configuration that actually carries the restoring rules — doctor reads it as text.
file_put_contents(
    $dir . '/.php-cs-fixer.php',
    "<?php\nreturn ['class_attributes_separation' => true, " . "'blank_line_before_statement' => true, 'blank_line_after_opening_tag' => true, " . "'declare_parentheses' => true];\n",
);
file_put_contents($dir . '/.github/workflows/ci.yml', "run: php-cs-fixer fix --dry-run\n");
RepositoryConfig::write($dir, 80);
$report = (new Doctor())->examine($dir);
check(
    'a repository meeting the contract is ready',
    $report['status'] === 'ready',
    implode(' | ', $report['findings']),
);
check('and the formatter is identified', ($report['formatters'][0]['tool'] ?? '') === 'php-cs-fixer');
removeTree($dir);

// The whole call is measured, not just its argument list. `pMaybeMultiline()`
// is handed the arguments alone, so a call whose arguments fit while the call
// does not used to come out on one long line — 203 of the 477 over-long lines
// in a 119-file corpus were exactly that.
$printer = new CanonicalPrinter(PhpVersion::fromString('8.2'), 60);
$parser  = (new ParserFactory())->createForVersion(PhpVersion::fromString('8.2'));

// The argument list alone is 16 characters and fits a 60-column budget twice
// over; the call around it does not. What sits in front of the *expression* —
// the `return ` — is a level further up still and is not measured, so the case
// is built on the call alone.
$source = "<?php\nclass C { public function f(\$aaa, \$bbb, \$ccc) { new AnExtremelyLongClassNameForThisTest(\$aaa, \$bbb, \$ccc); } }\n";
$wide   = $printer->prettyPrintFile($parser->parse($source) ?? []);

$longest = 0;

foreach (explode("\n", $wide) as $line) {
    $longest = max($longest, strlen($line));
}

check(
    'a call is broken when the call, not just its arguments, exceeds the width',
    $longest <= 60,
    'longest line is ' . $longest . ":\n" . $wide,
);

// Printing is still a fixed point: the broken form prints back to itself.
$again = $printer->prettyPrintFile($parser->parse($wide) ?? []);

check('and the broken form prints back to itself', $again === $wide, $again);

if ($problems !== []) {
    fwrite(
        STDERR,
        'FAIL: ' . count($problems) . " formatting check(s)\n  - " . implode("\n  - ", $problems) . "\n",
    );
    exit(1);
}
printf("OK: %d formatting checks passed.\n", $passed);
