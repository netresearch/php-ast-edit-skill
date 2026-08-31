<?php
declare(strict_types=1);

/**
 * `php-ast-edit contexts` is what an agent reads to learn what exists. It is a hand-written
 * list next to a hand-written dispatcher, so it can drift silently in either direction: an
 * operation the catalog omits is invisible, and one it invents fails only when someone tries
 * it. Both directions are checked here against the dispatcher's own case labels.
 */

$root = dirname(__DIR__);
$autoload = $root.'/vendor/autoload.php';
if (!is_file($autoload)) {
    fwrite(STDERR, "SKIP: vendor/autoload.php missing; run composer install to check the catalog.\n");
    exit(0);
}
require_once $autoload;

use Netresearch\PhpAstEdit\ContextParser;
use PhpParser\ParserFactory;

$problems = [];

// --- Operations ---------------------------------------------------------------------------
$editor = file_get_contents($root.'/src/Editor.php');
$dispatchers = [];
foreach (['applyPrimitive', 'applyComment', 'applyShorthand', 'applySemantic'] as $handler) {
    $start = strpos($editor, 'private function '.$handler.'(');
    if ($start === false) {
        $problems[] = 'Editor has no handler '.$handler.'; the catalog check is out of date.';
        continue;
    }
    // Bound the handler by the next method, not by a formatting detail inside it.
    $end = strpos($editor, "\n    private function ", $start + 1);
    $body = substr($editor, $start, ($end === false ? strlen($editor) : $end) - $start);
    preg_match_all("/^\s+case '([a-z0-9_]+)':/m", $body, $matches);
    $dispatchers = array_merge($dispatchers, $matches[1]);
}
sort($dispatchers);

$catalog = json_decode((string) shell_exec(escapeshellarg(PHP_BINARY).' '.escapeshellarg($root.'/bin/php-ast-edit').' contexts'), true);
if (!is_array($catalog)) {
    fwrite(STDERR, "FAIL: `php-ast-edit contexts` did not return JSON.\n");
    exit(1);
}

$advertised = array_merge(...array_values($catalog['operations']));
sort($advertised);

foreach (array_diff($dispatchers, $advertised) as $missing) {
    $problems[] = 'Editor handles "'.$missing.'" but `contexts` does not advertise it.';
}
foreach (array_diff($advertised, $dispatchers) as $invented) {
    $problems[] = '`contexts` advertises "'.$invented.'" but no handler implements it.';
}

// --- Parse contexts -----------------------------------------------------------------------
$parser = new ContextParser((new ParserFactory())->createForHostVersion());
$known = array_merge($parser->contexts(), ['stmts', 'file']);
sort($known);
$advertisedContexts = $catalog['parseAs'];
sort($advertisedContexts);
if ($known !== $advertisedContexts) {
    $problems[] = 'parseAs catalog drifted: '.implode(',', array_merge(
        array_diff($known, $advertisedContexts),
        array_diff($advertisedContexts, $known),
    ));
}

// Every advertised context must actually be reachable, `file` excepted: it needs an open tag.
foreach ($parser->contexts() as $context) {
    try {
        $parser->parse($context, 'x');
    } catch (Throwable $throwable) {
        if (str_contains($throwable->getMessage(), 'Unknown parseAs context')) {
            $problems[] = 'Context "'.$context.'" is advertised but not implemented.';
        }
    }
}

// --- Documentation ------------------------------------------------------------------------
$operationsDoc = file_get_contents($root.'/skills/php-structured-edit/references/operations.md');
foreach ($dispatchers as $operation) {
    if (!str_contains($operationsDoc, '`'.$operation.'`')) {
        $problems[] = 'operations.md does not document "'.$operation.'".';
    }
}
foreach ($parser->contexts() as $context) {
    if (!str_contains($operationsDoc, '`'.$context.'`')) {
        $problems[] = 'operations.md does not document the "'.$context.'" context.';
    }
}

if ($problems !== []) {
    fwrite(STDERR, "FAIL: catalog drift\n  - ".implode("\n  - ", $problems)."\n");
    exit(1);
}

printf("OK: %d operations and %d contexts agree across dispatcher, catalog and docs.\n", count($dispatchers), count($known));
