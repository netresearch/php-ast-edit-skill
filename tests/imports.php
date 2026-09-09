<?php

declare(strict_types=1);

/**
 * `add_use`: the file-level import operation.
 *
 * An import belongs to the file, not to a node, so this is the one operation that takes no
 * target. The cases below fix what "already there" means — an exact duplicate, a group use,
 * an import under a different alias — and what happens when the short name is already taken
 * by something else. Each answer is reported in the effect, because the point of the
 * operation is that the caller does not have to go and grep for it afterwards.
 */
require_once dirname(__DIR__) . '/vendor/autoload.php';

use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\RepositoryConfig;

$dir = sys_get_temp_dir() . '/php-ast-imports-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
file_put_contents($dir . '/composer.json', "{}\n");
file_put_contents($dir . '/.editorconfig', "root = true\n[*]\nmax_line_length = 120\n");
RepositoryConfig::write($dir, 120);
$failed = [];
$passed = 0;

function importCheck(string $name, bool $condition): void
{
    global $failed, $passed;

    if ($condition) {
        ++$passed;

        return;
    }
    $failed[] = $name;
}

/**
 * The fixture goes through the tool, so it starts on the canonical fixed point. Written as
 * text it would carry this repository's own spelling of `declare(strict_types=1)`, the
 * printer would rewrite that line on any edit, and every "unchanged" assertion below would
 * be measuring the fixture's formatting rather than the operation.
 */
function importFixture(string $code): string
{
    global $dir;
    $path = $dir . '/' . bin2hex(random_bytes(5)) . '.php';
    (new Editor())->apply(['files' => [['path' => $path, 'mode' => 'create', 'php' => $code]]]);

    return $path;
}

/**
 * @param  list<array<string, mixed>> $edits
 * @return array<string, mixed>
 */
function importApply(string $path, array $edits): array
{
    return (new Editor())->apply(
        ['files' => [['path' => $path, 'sha256' => hash_file('sha256', $path), 'edits' => $edits]]],
    )['files'][0];
}

/** @return array<string, mixed> */
function addUse(string $name, ?string $alias = null): array
{
    return array_filter(['operation' => 'add_use', 'value' => $name, 'alias' => $alias]);
}
// Sonar counts these; more to the point, a reader should not have to check by eye that the
// name asked for and the name asserted on are the same string.
const THING = 'Vendor\Other\Thing';
const THING_IMPORT = 'use Vendor\Other\Thing;';
const EXISTING = 'Vendor\Ext\Existing';

$namespaced = "<?php\n\ndeclare(strict_types=1);\n\nnamespace Vendor\\Ext;\n\nuse Vendor\\Ext\\Existing;\n\nclass Subject\n{\n}\n";
$plain = "<?php\n\ndeclare(strict_types=1);\n\nuse Vendor\\Ext\\Existing;\n\n\$GLOBALS['x'] = Existing::class;\n";

// ---- The ordinary case: the import lands in the file's import section ------------------
$path = importFixture($namespaced);
$result = importApply($path, [addUse('Vendor\Other\Thing')]);
$code = (string) file_get_contents($path);
importCheck(
    'the import is written into the namespace',
    str_contains($code, 'use Vendor\Other\Thing;'),
);
importCheck(
    'and it sits with the other imports, not after the class',
    strpos($code, 'use Vendor\Other\Thing;') < strpos($code, 'class Subject'),
);
importCheck(
    'the effect names what was imported, so nobody greps for it',
    ($result['effects'][0]['imported'] ?? null) === 'Vendor\Other\Thing' && ($result['effects'][0]['as'] ?? null) === 'Thing' && ($result['effects'][0]['alreadyPresent'] ?? null) === false,
);

// ---- Idempotence: the same import twice is one import ----------------------------------
$path = importFixture($namespaced);
$result = importApply($path, [addUse('Vendor\Ext\Existing')]);
$code = (string) file_get_contents($path);
importCheck(
    'an import that is already there is not written twice',
    substr_count($code, 'use Vendor\Ext\Existing;') === 1,
);
importCheck('and the file is reported unchanged', ($result['changed'] ?? true) === false);
importCheck(
    'while the effect still says the name is available',
    ($result['effects'][0]['alreadyPresent'] ?? null) === true && ($result['effects'][0]['as'] ?? null) === 'Existing',
);

// A leading backslash is the same class, and so is a different case in the namespace part.
$path = importFixture($namespaced);
importApply($path, [addUse('\Vendor\Ext\Existing')]);
importCheck(
    'a leading backslash names the same class',
    substr_count((string) file_get_contents($path), 'Existing;') === 1,
);

// ---- Group use: the class is imported, just not on a line of its own -------------------
$path = importFixture(
    "<?php\n\nnamespace Vendor\\Ext;\n\nuse Vendor\\Ext\\{Alpha, Beta};\n\nclass Subject\n{\n}\n",
);
$result = importApply($path, [addUse('Vendor\Ext\Beta')]);
importCheck(
    'a class inside a group use counts as imported',
    ($result['effects'][0]['alreadyPresent'] ?? null) === true && ($result['changed'] ?? true) === false,
);

// ---- The two collisions ----------------------------------------------------------------
$path = importFixture(
    "<?php\n\nnamespace Vendor\\Ext;\n\nuse Vendor\\Other\\Thing as Widget;\n\nclass Subject\n{\n}\n",
);
$aliased = null;

try {
    importApply($path, [addUse('Vendor\Other\Thing')]);
} catch (EditException $failure) {
    $aliased = $failure->getMessage();
}
importCheck(
    'the class already imported under an alias is refused, not imported twice',
    $aliased !== null && str_contains($aliased, 'Widget'),
);
importCheck(
    'and asking for that alias is the no-op it should be',
    (importApply($path, [addUse('Vendor\Other\Thing', 'Widget')])['effects'][0]['alreadyPresent'] ?? null) === true,
);
$path = importFixture($namespaced);
$taken = null;

try {
    importApply($path, [addUse('Vendor\Somewhere\Existing')]);
} catch (EditException $failure) {
    $taken = $failure->getMessage();
}
importCheck(
    'a short name already bound to another class is a collision, not a second import',
    $taken !== null && str_contains($taken, 'Vendor\Ext\Existing'),
);
importApply($path, [addUse('Vendor\Somewhere\Existing', 'OtherExisting')]);
importCheck(
    'and the collision is avoidable with an alias',
    str_contains(
        (string) file_get_contents($path),
        'use Vendor\Somewhere\Existing as OtherExisting;',
    ),
);

// ---- A file without a namespace has an import section too ------------------------------
$path = importFixture($plain);
importApply($path, [addUse('Vendor\Other\Thing')]);
$code = (string) file_get_contents($path);
importCheck(
    'an unnamespaced file takes the import at file level',
    str_contains($code, 'use Vendor\Other\Thing;'),
);
importCheck(
    'and it goes after the declare, which must stay first',
    strpos($code, 'strict_types') < strpos($code, 'use Vendor\Other\Thing;'),
);

// A file whose only import section is the declare line still has somewhere to put one.
$path = importFixture(
    "<?php\n\ndeclare(strict_types=1);\n\nnamespace Vendor\\Ext;\n\nclass Subject\n{\n}\n",
);
importApply($path, [addUse('Vendor\Other\Thing')]);
$code = (string) file_get_contents($path);
importCheck(
    'the first import of a file goes before the class',
    strpos($code, 'use Vendor\Other\Thing;') < strpos($code, 'class Subject'),
);

// ---- Two imports in one transaction ----------------------------------------------------
$path = importFixture($namespaced);
$result = importApply($path, [addUse('Vendor\Other\Thing'), addUse('Vendor\Other\Gadget')]);
$code = (string) file_get_contents($path);
importCheck(
    'two imports in one call both land',
    str_contains($code, 'use Vendor\Other\Thing;') && str_contains($code, 'use Vendor\Other\Gadget;'),
);
importCheck('and both are reported', count($result['effects'] ?? []) === 2);

// The second edit must see what the first one wrote, or idempotence is only per-call.
$path = importFixture($namespaced);
$result = importApply($path, [addUse('Vendor\Other\Thing'), addUse('Vendor\Other\Thing')]);
importCheck(
    'the same import twice in one call is written once',
    substr_count((string) file_get_contents($path), 'use Vendor\Other\Thing;') === 1,
);

// ---- What add_use is not ---------------------------------------------------------------
$path = importFixture($namespaced);
$targeted = null;

try {
    importApply($path, [addUse('Vendor\Other\Thing') + ['target' => ['select' => 'class:Subject']]]);
} catch (EditException $failure) {
    $targeted = $failure->getMessage();
}
importCheck(
    'a target is refused, because `use` inside a class is a trait and this is not that',
    $targeted !== null && str_contains($targeted, 'add_member'),
);
$path = importFixture("<?php\n\nnamespace A;\n\nclass X\n{\n}\n\nnamespace B;\n\nclass Y\n{\n}\n");
$ambiguous = null;

try {
    importApply($path, [addUse('Vendor\Other\Thing')]);
} catch (EditException $failure) {
    $ambiguous = $failure->getMessage();
}
importCheck(
    'a file with two namespaces has no single import section, and says so',
    $ambiguous !== null && str_contains($ambiguous, 'namespace'),
);

foreach (glob($dir . '/*') ?: [] as $entry) {
    @unlink($entry);
}
@rmdir($dir);

if ($failed !== []) {
    fwrite(STDERR, "FAILED:\n - " . implode("\n - ", $failed) . "\n");

    exit(1);
}
echo 'OK: ', $passed, " import checks passed.\n";
