<?php
declare(strict_types=1);

/**
 * Does the shipped source stay inside the PHP version composer.json requires?
 *
 * `php -l` answers for the interpreter that runs it, so on a PHP 8.5 host it says nothing
 * about the 8.2 floor — which is how `new Foo()->bar()` reached CI twice. Parsing does not
 * answer either: php-parser accepts that construct at every version, because its grammar is
 * not version-gated for it.
 *
 * Re-printing does not answer it either: the parenthesised and the bare form are the same
 * AST, so a printer comparison flags every dereferenced `new` regardless of how it was
 * written. The source position does answer it, and that is what this checks — scoped
 * deliberately to the one construct that reached CI twice rather than pretending to cover
 * every version difference. For that, run the floor interpreter.
 */

$root = dirname(__DIR__);
$autoload = $root.'/vendor/autoload.php';
if (!is_file($autoload)) {
    fwrite(STDERR, "SKIP: vendor/autoload.php missing; run composer install.\n");
    exit(0);
}
require_once $autoload;

use PhpParser\Error as ParserError;
use PhpParser\ParserFactory;
use PhpParser\PhpVersion;

$composer = json_decode((string) file_get_contents($root.'/composer.json'), true);
$constraint = $composer['require']['php'] ?? null;
if (!is_string($constraint) || preg_match('/(\d+)\.(\d+)/', $constraint, $m) !== 1) {
    fwrite(STDERR, "FAIL: composer.json does not state a PHP floor.\n");
    exit(1);
}
$floor = PhpVersion::fromString($m[1].'.'.$m[2]);
$newest = PhpVersion::getNewestSupported();

$paths = [$root.'/src', $root.'/bin/php-ast-edit', $root.'/scripts', $root.'/tests'];
$files = [];
foreach ($paths as $path) {
    if (is_file($path)) {
        $files[] = $path;
        continue;
    }
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($path, FilesystemIterator::SKIP_DOTS)) as $entry) {
        if ($entry->isFile() && $entry->getExtension() === 'php') {
            $files[] = $entry->getPathname();
        }
    }
}
sort($files);

$parser = (new ParserFactory())->createForHostVersion();

/**
 * `new Foo()->bar()` without the parentheses is PHP 8.4. It cannot be found by parsing —
 * php-parser accepts it at every version — nor by re-printing, because the parenthesised and
 * the bare form are the same AST. The source position answers it: after a parenthesised
 * `new`, the next character is the closing parenthesis; after the bare form it is the
 * dereference operator.
 */
final class NewDereferenceVisitor extends PhpParser\NodeVisitorAbstract
{
    /** @var list<array{line: int, code: string}> */
    public array $found = [];

    public function __construct(private readonly string $source)
    {
    }

    public function enterNode(PhpParser\Node $node): ?PhpParser\Node
    {
        $inner = match (true) {
            $node instanceof PhpParser\Node\Expr\MethodCall,
            $node instanceof PhpParser\Node\Expr\NullsafeMethodCall,
            $node instanceof PhpParser\Node\Expr\PropertyFetch,
            $node instanceof PhpParser\Node\Expr\NullsafePropertyFetch,
            $node instanceof PhpParser\Node\Expr\ArrayDimFetch => $node->var,
            $node instanceof PhpParser\Node\Expr\StaticCall,
            $node instanceof PhpParser\Node\Expr\ClassConstFetch => $node->class,
            default => null,
        };

        if (!$inner instanceof PhpParser\Node\Expr\New_) {
            return null;
        }

        $after = $inner->getEndFilePos() + 1;
        while ($after < strlen($this->source) && ctype_space($this->source[$after])) {
            ++$after;
        }
        if (($this->source[$after] ?? '') !== ')') {
            $this->found[] = [
                'line' => $node->getStartLine(),
                'code' => trim(substr($this->source, $inner->getStartFilePos(), 60)),
            ];
        }

        return null;
    }
}

$offenders = [];
foreach ($files as $file) {
    $source = (string) file_get_contents($file);
    try {
        $ast = $parser->parse($source) ?? [];
    } catch (ParserError $error) {
        $offenders[] = str_replace($root.'/', '', $file).': does not parse — '.$error->getRawMessage();
        continue;
    }

    if ($floor->supportsNewDereferenceWithoutParentheses()) {
        continue;
    }

    $visitor = new NewDereferenceVisitor($source);
    $traverser = new PhpParser\NodeTraverser($visitor);
    $traverser->traverse($ast);

    foreach ($visitor->found as $hit) {
        $offenders[] = sprintf(
            '%s:%d  %s…  — needs parentheses below PHP 8.4',
            str_replace($root.'/', '', $file),
            $hit['line'],
            $hit['code'],
        );
    }
}

if ($offenders !== []) {
    fwrite(STDERR, sprintf(
        "FAIL: %d use(s) of syntax newer than the composer floor (PHP %d.%d)\n  - %s\n",
        count($offenders),
        intdiv($floor->id, 10000),
        intdiv($floor->id, 100) % 100,
        implode("\n  - ", $offenders),
    ));
    exit(1);
}

printf(
    "OK: %d files stay within the PHP %d.%d floor composer.json requires.\n",
    count($files),
    intdiv($floor->id, 10000),
    intdiv($floor->id, 100) % 100,
);
