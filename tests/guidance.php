<?php

declare(strict_types=1);

/*
 * What a refusal says next.
 *
 * A rejected edit is read instead of the documentation, not alongside it — the caller is
 * mid-task and acts on whatever the message contains. A message that only names what was
 * wrong therefore costs a round trip to find out what is right, and in a measured run over
 * eight agent sessions that round trip was the single largest avoidable cost: 42 % of apply
 * calls failed, and the most frequent failure was `set_docblock` for `set_doc_comment`.
 *
 * These cases pin the two refusals that carried no way out: an operation name that is not
 * in the catalogue, and a selector that resolves to nothing.
 */
require_once dirname(__DIR__) . '/vendor/autoload.php';

use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;

$dir = sys_get_temp_dir() . '/php-ast-guidance-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
$failed = [];
$passed = 0;

function guidanceCheck(string $name, bool $condition): void
{
    global $failed, $passed;

    if ($condition) {
        ++$passed;
    } else {
        $failed[] = $name;
    }
}

/** The message an edit against this source is refused with. */
function guidanceRefusal(string $code, array $edit): string
{
    global $dir;
    $path = $dir . '/Subject' . bin2hex(random_bytes(4)) . '.php';
    file_put_contents($path, $code);

    try {
        (new Editor())->apply(['files' => [['path' => $path, 'edits' => [$edit]]]]);

        return '';
    } catch (EditException $e) {
        return $e->getMessage();
    } finally {
        @unlink($path);
    }
}

$subject = <<<'PHP'
<?php

class Order
{
    private const RATE = 1;

    private int $total = 0;

    private function sum(): int
    {
        return $this->total;
    }

    private function tax(): int
    {
        return 0;
    }
}
PHP;

// An operation name that is not in the catalogue. `set_docblock` was the measured case and is
// now taken as a synonym outright (tests/scoped-replace.php); `set_doc_block` is the next
// spelling of the same guess — seven edits from `set_doc_comment`, sharing only the verb.
$unknown = guidanceRefusal(
    $subject,
    [
        'target' => ['select' => 'method:Order::sum'],
        'operation' => 'set_doc_block',
        'value' => '/** x */',
    ],
);
guidanceCheck('an unknown operation is still named', str_contains($unknown, 'set_doc_block'));
guidanceCheck(
    'an unknown operation suggests the catalogue entry it meant',
    str_contains($unknown, 'set_doc_comment'),
);

$typo = guidanceRefusal(
    $subject,
    ['target' => ['select' => 'method:Order::sum'], 'operation' => 'rename_metod', 'to' => 'total'],
);
guidanceCheck('a typo reaches its operation', str_contains($typo, 'rename_method'));

// A name with nothing in common must not drag the alphabetically nearest entry in with it:
// a confident wrong suggestion is worse than none, because it will be tried.
$nonsense = guidanceRefusal(
    $subject,
    ['target' => ['select' => 'method:Order::sum'], 'operation' => 'zzzzzz', 'value' => 'x'],
);
guidanceCheck('an unrelated name suggests nothing', !str_contains($nonsense, 'Did you mean'));
guidanceCheck(
    'an unrelated name still points at the catalogue',
    str_contains($nonsense, 'contexts'),
);

// A selector that matched nothing is almost always a near miss. The file's own declarations
// of that kind answer the next question without an inspect round trip.
$missing = guidanceRefusal(
    $subject,
    [
        'target' => ['select' => 'method:Order::totl'],
        'operation' => 'rename_method',
        'to' => 'total',
    ],
);
guidanceCheck('a missed selector is still named', str_contains($missing, 'method:Order::totl'));
guidanceCheck(
    'a missed selector names the methods that are there',
    str_contains($missing, 'Order::sum'),
);
guidanceCheck('a missed selector lists every one of them', str_contains($missing, 'Order::tax'));

$absent = guidanceRefusal(
    $subject,
    ['target' => ['select' => 'interface:Missing'], 'operation' => 'set_name', 'value' => 'X'],
);
guidanceCheck(
    'a kind the file has none of says so rather than listing nothing',
    str_contains($absent, 'no interface at all'),
);

// Properties and constants are qualified the way the selector spells them, so the message
// can be copied back into the edit that failed.
$property = guidanceRefusal(
    $subject,
    [
        'target' => ['select' => 'property:Order::$missing'],
        'operation' => 'set_name',
        'value' => 'X',
    ],
);
guidanceCheck(
    'a missed property names the properties that are there',
    str_contains($property, 'Order::$total'),
);

$constant = guidanceRefusal(
    $subject,
    ['target' => ['select' => 'const:Order::MISSING'], 'operation' => 'set_name', 'value' => 'X'],
);
guidanceCheck(
    'a missed constant names the constants that are there',
    str_contains($constant, 'Order::RATE'),
);

// set_name on a method declaration renames nothing that calls it. A gated run did that on a
// method with 29 callers and then renamed them one by one; the refusal carries the edit that
// renames both, ready to copy.
$declaration = guidanceRefusal(
    "<?php\nclass Order\n{\n    public function sum(): int\n    {\n        return 1;\n    }\n\n    public function twice(): int\n    {\n        return \$this->sum() * 2;\n    }\n}\n",
    ['target' => ['select' => 'method:Order::sum'], 'operation' => 'set_name', 'value' => 'total'],
);
guidanceCheck(
    'set_name on a method declaration counts the calls it would leave behind',
    str_contains($declaration, '1 call(s) in 1 file(s)'),
);
// A method nothing calls loses nothing by a declaration-only rename.
guidanceCheck(
    'set_name on a method nobody calls is not refused',
    guidanceRefusal(
        $subject,
        [
            'target' => ['select' => 'method:Order::tax'],
            'operation' => 'set_name',
            'value' => 'levy',
        ],
    ) === '',
);
// A comment or a string that reads like a call is not one.
guidanceCheck(
    'text that only looks like a call does not refuse the rename',
    guidanceRefusal(
        "<?php\nclass Order\n{\n    public function sum(): int\n    {\n        // \$this->sum() once lived here\n        return strlen('Order::sum()');\n    }\n}\n",
        [
            'target' => ['select' => 'method:Order::sum'],
            'operation' => 'set_name',
            'value' => 'total',
        ],
    ) === '',
);

guidanceCheck(
    'a mocks value that is not a boolean is refused, null included',
    str_contains(
        guidanceRefusal(
            $subject,
            [
                'target' => ['select' => 'method:Order::sum'],
                'operation' => 'rename_method',
                'to' => 'total',
                'mocks' => null,
            ],
        ),
        '"mocks" is true or false',
    ),
);
$mocksFlag = shell_exec(
    escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(dirname(__DIR__) . '/bin/php-ast-edit') . ' apply --file x.php --select method:A::b --op set_name --value x --mocks 2>&1',
) ?? '';
guidanceCheck(
    '--mocks is refused outside rename_method',
    str_contains($mocksFlag, '--mocks takes no value and belongs to --op rename_method'),
);

foreach (['--op set_string --value x --declaration-only', '--op set_name --value x --declaration-only=false'] as $flags) {
    $misplaced = shell_exec(
        escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(dirname(__DIR__) . '/bin/php-ast-edit') . ' apply --file x.php --select method:A::b ' . $flags . ' 2>&1',
    ) ?? '';
    guidanceCheck(
        '--declaration-only is refused outside a valueless set_name: ' . $flags,
        str_contains($misplaced, '--declaration-only takes no value and belongs to --op set_name'),
    );
}
guidanceCheck(
    'set_name on a method declaration hands over the rename_method edit',
    str_contains(
        $declaration,
        '{"target": {"select": "method:Order::sum"}, "operation": "rename_method", "to": "total"}',
    ),
);
guidanceCheck(
    'set_name on a method declaration names the declaration-only opt-in',
    str_contains($declaration, '"declarationOnly": true'),
);

// The two apply forms are alternatives. Mixing them used to report that the flag form
// requires --op, which is true and answers nothing: the caller had a whole document and
// did not want the flag form at all.
$engine = dirname(__DIR__) . '/bin/php-ast-edit';
$mixed = shell_exec(
    escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($engine) . ' apply --input /dev/null --file x.php 2>&1',
) ?? '';
guidanceCheck(
    'mixing --input and --file names both forms',
    str_contains($mixed, '--input and --file'),
);
guidanceCheck('mixing them does not ask for --op', !str_contains($mixed, 'requires --op'));

// An argument whose values are a closed set says so where it is listed, rather than only
// when it is got wrong.
$catalogue = json_decode(
    shell_exec(
        escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($engine) . ' contexts --operation insert_into',
    ) ?: '{}',
    true,
);
guidanceCheck(
    'the catalogue publishes the values position accepts',
    in_array('start', $catalogue['argumentValues']['position']['values'] ?? [], true),
);
guidanceCheck(
    'the catalogue publishes the default',
    ($catalogue['argumentValues']['position']['default'] ?? null) === 'end',
);
$plain = json_decode(
    shell_exec(
        escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($engine) . ' contexts --operation rename_method',
    ) ?: '{}',
    true,
);
guidanceCheck(
    'an operation with no enumerated argument carries no empty map',
    !array_key_exists('argumentValues', $plain),
);

// And the refusal itself now says what it got, so a wrong value is visible in the message.
$position = guidanceRefusal(
    $subject,
    [
        'target' => ['select' => 'class:Order'],
        'operation' => 'insert_into',
        'property' => 'stmts',
        'php' => 'public int $x = 1;',
        'position' => 'middle',
    ],
);
guidanceCheck(
    'a bad position names the values it accepts',
    str_contains($position, '"start", "end"'),
);
guidanceCheck('a bad position echoes what it got', str_contains($position, 'middle'));

rmdir($dir);

if ($failed !== []) {
    fwrite(
        STDERR,
        "FAIL: " . count($failed) . " guidance case(s)\n  - " . implode("\n  - ", $failed) . "\n",
    );
    exit(1);
}
printf("OK: %d refusal messages name the way out.\n", $passed);
