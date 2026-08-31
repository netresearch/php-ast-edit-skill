<?php
declare(strict_types=1);

/**
 * The formatting contract: canonical by declaration, format-preserving as the announced
 * fallback, and a printer whose output a human can read.
 */

$root = dirname(__DIR__);
$autoload = $root.'/vendor/autoload.php';
if (!is_file($autoload)) {
    fwrite(STDERR, "SKIP: vendor/autoload.php missing; run composer install.\n");
    exit(0);
}
require_once $autoload;

use Netresearch\PhpAstEdit\CanonicalPrinter;
use Netresearch\PhpAstEdit\Doctor;
use Netresearch\PhpAstEdit\Editor;
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
    $problems[] = $name.($detail === '' ? '' : ': '.$detail);
}

function workspace(): string
{
    $dir = sys_get_temp_dir().'/php-ast-edit-fmt-'.bin2hex(random_bytes(6));
    mkdir($dir, 0700, true);
    // A repository root, so the marker lands where RepositoryConfig looks for it.
    file_put_contents($dir.'/composer.json', "{}\n");
    return $dir;
}

function removeTree(string $directory): void
{
    foreach (glob($directory.'/*') ?: [] as $entry) {
        is_dir($entry) ? removeTree($entry) : @unlink($entry);
    }
    @rmdir($directory);
}

$parser = new ParserFactory()->createForHostVersion();

// ---- The printer breaks by width -------------------------------------------------------
$long = "<?php\n\$x = foo('aaaaaaaaaaaaaaaaaaaa', 'bbbbbbbbbbbbbbbbbbbb', 'cccccccccccccccccccc', 'dddddddddddddddddddd');\n";
$wide = new CanonicalPrinter(null, 200)->prettyPrintFile($parser->parse($long));
$narrow = new CanonicalPrinter(null, 40)->prettyPrintFile($parser->parse($long));
check('a list within budget stays on one line', substr_count(trim($wide), "\n") === 2, trim($wide));
check('a list over budget is broken', substr_count($narrow, "\n") > 4, trim($narrow));
check('breaking puts one argument per line', str_contains($narrow, "'aaaaaaaaaaaaaaaaaaaa',\n"));

$params = "<?php\nfunction f(string \$aaaaaaaaaaaaaaaaaaaa, string \$bbbbbbbbbbbbbbbbbbbb, string \$cccccccccccccccccccc) {}\n";
$narrowParams = new CanonicalPrinter(null, 40)->prettyPrintFile($parser->parse($params));
check('a parameter list over budget is broken', substr_count($narrowParams, "\n") > 4, trim($narrowParams));

// The width must actually be the lever, and printing must be a fixed point of itself.
foreach ([40, 80, 200] as $width) {
    $printer = new CanonicalPrinter(null, $width);
    $once = $printer->prettyPrintFile($parser->parse($long));
    $twice = $printer->prettyPrintFile($parser->parse($once));
    check("printing is idempotent at width $width", $once === $twice);
}

// ---- The declaration decides the printer -----------------------------------------------
$dir = workspace();
file_put_contents($dir.'/a.php', "<?php\nclass Foo\n{\n    public function bar()\n    {\n        return 1;\n    }\n}\n");
$editor = new Editor();

$document = static fn (string $path): array => ['files' => [[
    'path' => $path,
    'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'Renamed']],
]]];

$result = $editor->apply($document($dir.'/a.php'), true)['files'][0];
check('without a declaration the fallback is format-preserving', $result['printer'] === 'format-preserving', $result['printer']);
check('and it says so', str_contains($result['warning'] ?? '', 'NOT_CANONICAL'));
check('the fallback changes only the edited line', $result['changedLines'] === 2, (string) $result['changedLines']);

RepositoryConfig::write($dir, 80);
$result = $editor->apply($document($dir.'/a.php'), true)['files'][0];
check('a declared repository prints canonically', $result['printer'] === 'canonical', $result['printer']);
check('and carries no warning', !isset($result['warning']));

$forced = $editor->apply(['files' => [[
    'path' => $dir.'/a.php',
    'printer' => 'format-preserving',
    'edits' => [['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'Renamed']],
]]], true)['files'][0];
check('an explicit printer overrides the declaration', $forced['printer'] === 'format-preserving');

try {
    $editor->apply(['files' => [['path' => $dir.'/a.php', 'printer' => 'nonsense', 'edits' => [
        ['target' => ['ref' => 'stmts[0].name'], 'operation' => 'set_name', 'value' => 'X'],
    ]]]], true);
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
        ['target' => ['ref' => 'stmts[0]'], 'operation' => 'add_member', 'php' => 'public int $b = 2;'],
        2,
    ],
    'delete_node' => [
        "<?php\nfunction f()\n{\n    \$a = 1;\n    \$b = 2;\n    \$c = 3;\n}\n",
        ['target' => ['ref' => 'stmts[0].stmts[1]'], 'operation' => 'delete_node'],
        1,
    ],
    'set_doc_comment' => [
        "<?php\nclass Foo\n{\n    public function bar()\n    {\n        return 1;\n    }\n}\n",
        ['target' => ['ref' => 'stmts[0].stmts[0]'], 'operation' => 'set_doc_comment', 'value' => 'Docs.'],
        3,
    ],
    'replace_expression' => [
        "<?php\n\$a = 1;\n\$b = 2;\n\$c = 3;\n",
        ['target' => ['ref' => 'stmts[1].expr.expr'], 'operation' => 'replace_expression', 'php' => '99'],
        2,
    ],
];

foreach ($cases as $label => [$source, $edit, $budget]) {
    $dir = workspace();
    file_put_contents($dir.'/a.php', $source);
    $result = (new Editor())->apply(['files' => [[
        'path' => $dir.'/a.php',
        'printer' => 'format-preserving',
        'edits' => [$edit],
    ]]], true)['files'][0];
    check(
        "format-preserving keeps $label local",
        $result['changedLines'] <= $budget,
        $result['changedLines'].' changed lines, budget '.$budget,
    );
    removeTree($dir);
}

// ---- format and normalize ---------------------------------------------------------------
$dir = workspace();
file_put_contents($dir.'/a.php', "<?php\nclass  Foo{\npublic function bar(){return 1;}\n}\n");
$before = (string) file_get_contents($dir.'/a.php');

$dry = new Formatter()->format([$dir], 80, true);
check('format --dry-run reports the file', $dry['changed'] === [$dir.'/a.php'], implode(',', $dry['changed']));
check('format --dry-run writes nothing', file_get_contents($dir.'/a.php') === $before);

$run = new Formatter()->format([$dir], 80, false);
check('format rewrites the file', file_get_contents($dir.'/a.php') !== $before);
check('format reports no failures', $run['failed'] === []);

$again = new Formatter()->format([$dir], 80, false);
check('format is idempotent', $again['changed'] === [], implode(',', $again['changed']));

$path = RepositoryConfig::write($dir, 100);
$config = RepositoryConfig::discover($dir.'/a.php');
check('the declaration is found from a file', $config->canonical && $config->width === 100);
check('the marker names its own path', $config->path === $path);
check('the root is where composer.json is', RepositoryConfig::rootFor($dir.'/a.php') === realpath($dir));

// A broken declaration must be named, not ignored.
file_put_contents($dir.'/'.RepositoryConfig::FILE, "{ not json\n");
try {
    RepositoryConfig::discover($dir);
    check('invalid declaration JSON is refused', false, 'accepted');
} catch (Throwable $throwable) {
    check('invalid declaration JSON is refused', str_contains($throwable->getMessage(), 'not valid JSON'));
}
removeTree($dir);

// ---- doctor ------------------------------------------------------------------------------
$dir = workspace();
$report = new Doctor()->examine($dir);
check('a bare repository is not ready', $report['status'] === 'warn');
check('and the missing formatter is named', str_contains(implode(' ', $report['findings']), 'No formatter configuration'));

mkdir($dir.'/.github/workflows', 0700, true);
file_put_contents($dir.'/.php-cs-fixer.php', "<?php\n");
file_put_contents($dir.'/.github/workflows/ci.yml', "run: php-cs-fixer fix --dry-run\n");
RepositoryConfig::write($dir, 80);
$report = new Doctor()->examine($dir);
check('a repository meeting the contract is ready', $report['status'] === 'ready', implode(' | ', $report['findings']));
check('and the formatter is identified', ($report['formatters'][0]['tool'] ?? '') === 'php-cs-fixer');
removeTree($dir);

if ($problems !== []) {
    fwrite(STDERR, 'FAIL: '.count($problems)." formatting check(s)\n  - ".implode("\n  - ", $problems)."\n");
    exit(1);
}

printf("OK: %d formatting checks passed.\n", $passed);
