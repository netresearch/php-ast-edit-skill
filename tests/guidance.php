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

// An operation name that is not in the catalogue. `set_docblock` is the real case: six
// edits away from `set_doc_comment`, so edit distance alone does not reach it, but it
// shares the verb — which is the half the caller knew.
$unknown = guidanceRefusal(
    $subject,
    [
        'target' => ['select' => 'method:Order::sum'],
        'operation' => 'set_docblock',
        'value' => '/** x */',
    ],
);
guidanceCheck('an unknown operation is still named', str_contains($unknown, 'set_docblock'));
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

rmdir($dir);

if ($failed !== []) {
    fwrite(
        STDERR,
        "FAIL: " . count($failed) . " guidance case(s)\n  - " . implode("\n  - ", $failed) . "\n",
    );
    exit(1);
}
printf("OK: %d refusal messages name the way out.\n", $passed);
