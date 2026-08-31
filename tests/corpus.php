<?php

declare (strict_types=1);
/**
 * The promise is that only the AST writes PHP. That is worth exactly as much as the
 * print-and-reparse round trip is faithful, and a hand-picked fixture cannot show it: the
 * constructs that lose something are the ones nobody thought to write down.
 *
 * So run against a real corpus — the parser's own source, which is present in every
 * install and covers most of the grammar — and require the AST to come back identical,
 * attributes stripped. Also drive inspect across each file, because a position that lands
 * anywhere must never raise anything but a typed failure.
 */
$root = dirname(__DIR__);
$autoload = $root . '/vendor/autoload.php';
if (!is_file($autoload)) {
    fwrite(STDERR, "SKIP: vendor/autoload.php missing; the corpus check needs the parser.\n");
    exit(0);
}
require_once $autoload;
use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Node;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\ParserFactory;
use PhpParser\PrettyPrinter\Standard;
$corpus = $root . '/vendor/nikic/php-parser/lib';
if (!is_dir($corpus)) {
    fwrite(STDERR, "SKIP: corpus directory missing.\n");
    exit(0);
}
$files = [];
foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($corpus, FilesystemIterator::SKIP_DOTS)) as $file) {
    if ($file->isFile() && $file->getExtension() === 'php') {
        $files[] = $file->getPathname();
    }
}
sort($files);
if ($files === []) {
    fwrite(STDERR, "SKIP: corpus is empty.\n");
    exit(0);
}
$parser = (new ParserFactory())->createForHostVersion();
$printer = new Standard();
$traverser = new NodeTraverser();
$traverser->addVisitor(new class extends NodeVisitorAbstract
{
    public function enterNode(Node $node): ?Node
    {
        $node->setAttributes([]);
        return null;
    }
});
$problems = [];
$inspections = 0;
$editor = new Editor();
$work = sys_get_temp_dir() . '/php-ast-edit-corpus-' . bin2hex(random_bytes(6));
mkdir($work, 0700, true);
$scratch = $work . '/f.php';
foreach ($files as $source) {
    // Print from the AST as the Editor does — attributes intact, so comments and literal
    // kinds survive — and strip only for the comparison.
    $original = $parser->parse((string) file_get_contents($source));
    $printed = $printer->prettyPrintFile($original);
    $before = $traverser->traverse($original);
    $after = $traverser->traverse($parser->parse($printed));
    if (print_r($before, true) !== print_r($after, true)) {
        $problems[] = 'round trip changed the AST of ' . basename($source);
    }
    copy($source, $scratch);
    $length = max(1, (int) filesize($scratch));
    for ($step = 1; $step <= 8; ++$step) {
        try {
            $editor->inspect($scratch, ['offset' => intdiv($length * $step, 9)]);
            ++$inspections;
        } catch (EditException) {
            ++$inspections;
            // A typed refusal is a result, not a failure.
        } catch (Throwable $throwable) {
            $problems[] = sprintf('inspect raised %s on %s: %s', $throwable::class, basename($source), $throwable->getMessage());
        }
    }
}
@unlink($scratch);
@rmdir($work);
if ($problems !== []) {
    fwrite(STDERR, 'FAIL: ' . count($problems) . " corpus problem(s)\n  - " . implode("\n  - ", array_slice($problems, 0, 20)) . "\n");
    exit(1);
}
printf("OK: %d corpus files round-tripped unchanged, %d inspections raised nothing untyped.\n", count($files), $inspections);
