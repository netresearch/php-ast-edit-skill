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
use Netresearch\PhpAstEdit\Doctor;
use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\EditorConfig;
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\Formatter;
use Netresearch\PhpAstEdit\RepositoryConfig;
use PhpParser\ParserFactory;
use PhpParser\PhpVersion;

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
check(
    'a parameter list over budget is broken',
    substr_count($narrowParams, "\n") > 4,
    trim($narrowParams),
);

// The width must actually be the lever, and printing must be a fixed point of itself.
foreach ([40, 80, 200] as $width) {
    $printer = new CanonicalPrinter(null, $width);
    $once = $printer->prettyPrintFile($parser->parse($long));
    $twice = $printer->prettyPrintFile($parser->parse($once));
    check("printing is idempotent at width {$width}", $once === $twice);
}
// ---- Paragraph breaks survive the print ------------------------------------------------
// A blank line an author put between two ordinary statements is the largest share of what a
// canonical print removes, and no formatter rule puts it back — Doctor names that share
// unrecoverable. The parser knows the gap from the line attributes, so the printer keeps it.
$paragraphs = <<<'PHP'
<?php

function f()
{
    $a = 1;
    $b = 2;

    $c = 3;


    $d = 4;
}
PHP;
$kept = (new CanonicalPrinter(null, 120))->prettyPrintFile($parser->parse($paragraphs));
check(
    'a paragraph break between statements survives',
    str_contains($kept, "\$b = 2;\n\n    \$c = 3;"),
    $kept,
);
check(
    'statements the author kept together stay together',
    str_contains($kept, "\$a = 1;\n    \$b = 2;"),
    $kept,
);
check('several blank lines collapse to one', !str_contains($kept, "\n\n\n    \$d"), $kept);
check(
    'preserving paragraphs is still idempotent',
    (new CanonicalPrinter(null, 120))->prettyPrintFile($parser->parse($kept)) === $kept,
    $kept,
);
$commented = <<<'PHP'
<?php

function f()
{
    $a = 1;

    // why
    $b = 2;
}
PHP;
$keptComment = (new CanonicalPrinter(null, 120))->prettyPrintFile($parser->parse($commented));
check(
    'the gap is measured to the comment, not the statement',
    str_contains($keptComment, "\$a = 1;\n\n    // why\n    \$b = 2;"),
    $keptComment,
);
check(
    'no blank line carries indentation',
    preg_match('/\n[ \t]+\n/', $keptComment) === 0,
    $keptComment,
);

// A node an edit brings in is parsed from a snippet and starts at line 1. Read as a source
// position, that is a gap, and the printer answers it with a blank line nobody typed.
$editDir = workspace();
$editPath = $editDir . '/r.php';
RepositoryConfig::write($editDir, 120);
$paragraphed = <<<'PHP'
<?php

function f()
{
    $a = 1;
    $b = 2;

    $c = 3;
}
PHP . "\n";
$firstStatement = ['ref' => 'stmts[0].stmts[0]'];
$applyOne = static function (array $edit) use ($editPath): array {
    return (new Editor())->apply(['files' => [['path' => $editPath, 'edits' => [$edit]]]], true)['files'][0];
};
// A replacement inherits the position of the node it replaces.
file_put_contents($editPath, $paragraphed);
$replaced = $applyOne(['target' => $firstStatement, 'operation' => 'replace_statement', 'php' => '$a = 99;']);
check(
    'replacing a statement inserts no blank line',
    $replaced['changedLines'] === 2,
    (string) $replaced['changedLines'],
);
check(
    'and leaves the paragraph break where it was',
    str_contains((string) $replaced['code'], "\$b = 2;\n\n    \$c = 3;"),
    (string) $replaced['code'],
);
// An insertion has no predecessor to inherit from, so it must carry no position at all.
file_put_contents($editPath, $paragraphed);
$inserted = $applyOne(['target' => $firstStatement, 'operation' => 'insert_before', 'php' => '$z = 0;']);
check(
    'inserting before the first statement adds one line, not two',
    $inserted['changedLines'] === 1,
    (string) $inserted['changedLines'],
);
check(
    'the insertion abuts the statement it precedes',
    str_contains((string) $inserted['code'], "\$z = 0;\n    \$a = 1;"),
    (string) $inserted['code'],
);
file_put_contents($editPath, $paragraphed);
$into = $applyOne(
    [
        'target' => ['ref' => 'stmts[0]'],
        'operation' => 'insert_into',
        'property' => 'stmts',
        'position' => 'start',
        'php' => '$z = 0;',
    ],
);
check(
    'insert_into at the start adds one line too',
    $into['changedLines'] === 1,
    (string) $into['changedLines'],
);
check(
    'and the paragraph further down is untouched',
    str_contains((string) $into['code'], "\$b = 2;\n\n    \$c = 3;"),
    (string) $into['code'],
);
removeTree($editDir);

// A path the project excluded is not this tool's to re-print. `format` and `normalize`
// honour the list; `apply` did not, so an edit to an excluded file was printed canonically
// anyway — and once the project formatter runs as part of the write, that reaches a file
// the project took out of its reach on purpose.
$excludedDir = workspace();
RepositoryConfig::write($excludedDir, 120, ['keep-away.php']);
$untouchable = $excludedDir . '/keep-away.php';
file_put_contents(
    $untouchable,
    <<<'PHP'
    <?php
    
    // The blank line below is what a canonical print removes.
    
    $config = ['state' => 'beta'];
    PHP . "\n",
);
$excludedResult = (new Editor())->apply(
    [
        'files' => [
            [
                'path' => $untouchable,
                'edits' => [
                    [
                        'target' => ['ref' => 'stmts[0].expr.expr.items[0].value'],
                        'operation' => 'set_string',
                        'value' => 'stable',
                    ],
                ],
            ],
        ],
    ],
    true,
)['files'][0];
check(
    'an excluded file is not printed canonically',
    $excludedResult['printer'] === 'format-preserving',
    (string) $excludedResult['printer'],
);
check(
    'and the exclusion is named',
    str_contains((string) ($excludedResult['warning'] ?? ''), 'EXCLUDED'),
    (string) ($excludedResult['warning'] ?? ''),
);
check(
    'and only the edited line changes',
    $excludedResult['changedLines'] === 2,
    (string) $excludedResult['changedLines'],
);
check(
    'so the blank line the project kept survives',
    str_contains((string) $excludedResult['code'], "removes.\n\n\$config"),
    (string) $excludedResult['code'],
);
removeTree($excludedDir);

// The fixed point belongs to the printer and the project's formatter together, so an edit
// that stops after printing leaves a file in a shape nobody wants: on a canonical TYPO3
// extension, adding one 9-line method reported 34 changed lines, the remainder trailing
// commas and `declare` spacing that only the formatter puts back. The project declares its
// formatter and `apply` runs it, on the files it wrote and no others.
$formatterDir = workspace();
file_put_contents(
    $formatterDir . '/fmt.php',
    <<<'PHP'
    <?php
    // A stand-in for the project's formatter: it restores the trailing comma a canonical
    // print drops, on exactly the files it is handed.
    foreach (array_slice($argv, 1) as $file) {
        $text = str_replace("'stable']", "'stable',]", (string) file_get_contents($file));
        file_put_contents($file, $text . "// the formatter was here\n");
    }
    PHP . "\n",
);
file_put_contents(
    $formatterDir . '/' . RepositoryConfig::FILE,
    json_encode(
        ['canonical' => true, 'printWidth' => 120, 'formatter' => ['php', 'fmt.php', '{files}']],
        JSON_PRETTY_PRINT,
    ) . "\n",
);
$formatted = $formatterDir . '/f.php';
file_put_contents($formatted, "<?php\n\n\$config = ['state' => 'beta'];\n");
$formatterResult = (new Editor())->apply(
    [
        'files' => [
            [
                'path' => $formatted,
                'edits' => [
                    [
                        'target' => ['ref' => 'stmts[0].expr.expr.items[0].value'],
                        'operation' => 'set_string',
                        'value' => 'stable',
                    ],
                ],
            ],
        ],
    ],
)['files'][0];
check(
    'the declared formatter runs on what apply wrote',
    str_contains((string) file_get_contents($formatted), "'stable',]"),
    (string) file_get_contents($formatted),
);
check(
    'and the report says it ran',
    ($formatterResult['formatter'] ?? null) === 'ran',
    (string) ($formatterResult['formatter'] ?? 'absent'),
);
check(
    // Two for the line the edit rewrote, one for the line the formatter appended: without
    // the formatter run this would be two, so the number describes the file that survives.
    'changedLines counts the file the formatter left behind',
    $formatterResult['changedLines'] === 3,
    (string) $formatterResult['changedLines'],
);
removeTree($formatterDir);

// The guarantees the formatter run must not weaken, each measured rather than assumed.
$hardDir = workspace();
file_put_contents(
    $hardDir . '/' . RepositoryConfig::FILE,
    json_encode(
        [
            'canonical' => true,
            'printWidth' => 120,
            'exclude' => ['Generated'],
            'formatter' => ['php', 'break.php', '{files}'],
        ],
        JSON_PRETTY_PRINT,
    ) . "\n",
);
// A formatter that exits zero having written something that is no longer PHP, and that
// says a great deal on stderr on the way — enough to fill a pipe nobody is draining.
file_put_contents(
    $hardDir . '/break.php',
    <<<'PHP'
    <?php
    fwrite(STDERR, str_repeat("the formatter is talkative\n", 4096));
    foreach (array_slice($argv, 1) as $file) {
        file_put_contents($file, "<?php this is not php(((\n");
    }
    PHP . "\n",
);
$hardPath = $hardDir . '/h.php';
file_put_contents($hardPath, "<?php\n\n\$config = ['state' => 'beta'];\n");
$before = (string) file_get_contents($hardPath);

try {
    (new Editor())->apply(
        [
            'files' => [
                [
                    'path' => $hardPath,
                    'edits' => [
                        [
                            'target' => ['ref' => 'stmts[0].expr.expr.items[0].value'],
                            'operation' => 'set_string',
                            'value' => 'stable',
                        ],
                    ],
                ],
            ],
        ],
    );
    check('a formatter that writes non-PHP is refused', false, 'accepted');
} catch (EditException $failure) {
    check(
        'a formatter that writes non-PHP is refused',
        str_contains($failure->getMessage(), 'unparseable'),
        $failure->getMessage(),
    );
}
check(
    'and the write is rolled back',
    (string) file_get_contents($hardPath) === $before,
    (string) file_get_contents($hardPath),
);
// The exclusion has to hold for a file that does not exist yet, or `create` walks around it.
mkdir($hardDir . '/Generated');
$created = $hardDir . '/Generated/New.php';
$createdResult = (new Editor())->apply(
    ['files' => [['path' => $created, 'mode' => 'create', 'php' => "<?php\n\nclass New_ {}\n"]]],
    true,
)['files'][0];
check(
    // A new file has nothing to preserve, so it is necessarily printed canonically; what
    // the exclusion has to stop is the formatter, which would add the very
    // `declare(strict_types=1)` the excluded file exists to keep out.
    'the formatter does not reach a file created inside an excluded directory',
    !isset($createdResult['formatter']),
    (string) ($createdResult['formatter'] ?? 'absent'),
);
removeTree($hardDir . '/Generated');
removeTree($hardDir);

try {
    RepositoryConfig::assertFormatter(['fix' => 'php-cs-fixer', 'files' => '{files}']);
    check('a formatter given as an object is refused', false, 'accepted');
} catch (EditException $failure) {
    check(
        'a formatter given as an object is refused',
        str_contains($failure->getMessage(), 'list of arguments'),
        $failure->getMessage(),
    );
}

// A target named by what it is, and a rename that is one edit rather than one per
// occurrence. Between them they remove the `inspect --line --column` hunt that cost two to
// four calls before any edit was written.
$selectDir = workspace();
RepositoryConfig::write($selectDir, 120);
$selectPath = $selectDir . '/s.php';
file_put_contents(
    $selectPath,
    <<<'PHP'
    <?php
    
    class Vault
    {
        private array $nonceCache = [];
    
        public function store(string $nonce): string
        {
            $key = $this->nonceKey($nonce);
            $this->nonceCache[$key] = $nonce;
    
            return 'nonce_' . $nonce;
        }
    
        private function nonceKey(string $nonce): string
        {
            return \hash('sha256', $nonce);
        }
    }
    PHP . "\n",
);
$renamed = (new Editor())->apply(
    [
        'files' => [
            [
                'path' => $selectPath,
                'edits' => [
                    [
                        'target' => ['select' => 'method:Vault::store'],
                        'operation' => 'rename_variable',
                        'from' => 'nonce',
                        'to' => 'nonceValue',
                    ],
                ],
            ],
        ],
    ],
    true,
)['files'][0];
$after = (string) $renamed['code'];
check(
    'a method is reachable by name',
    $renamed['editsApplied'] === 1,
    (string) $renamed['editsApplied'],
);
check('every occurrence of the variable moves', substr_count($after, '$nonceValue') === 4, $after);
check('the property it resembles is untouched', substr_count($after, 'nonceCache') === 2, $after);
check('so is the method', substr_count($after, 'nonceKey') === 2, $after);
check('so is the string literal', str_contains($after, "'nonce_'"), $after);
check(
    'a scope the rename was not asked for keeps its own',
    substr_count($after, 'string $nonce)') === 1,
    $after,
);

try {
    (new Editor())->apply(
        [
            'files' => [
                [
                    'path' => $selectPath,
                    'edits' => [
                        [
                            'target' => ['select' => 'method:nonceKey', 'kind' => 'Stmt_Property'],
                            'operation' => 'rename_variable',
                            'from' => 'nonce',
                            'to' => 'x',
                        ],
                    ],
                ],
            ],
        ],
        true,
    );
    check('a selector held to the wrong kind is refused', false, 'accepted');
} catch (EditException $failure) {
    check(
        'a selector held to the wrong kind is refused',
        str_contains($failure->getMessage(), 'expected Stmt_Property'),
        $failure->getMessage(),
    );
}

try {
    $locator = new Netresearch\PhpAstEdit\NodeLocator();
    $parsed = (new ParserFactory())->createForHostVersion()->parse(
        "<?php\nclass A { public function f() {} }\nclass B { public function f() {} }\n",
    ) ?? [];
    $locator->resolveSelect($parsed, 'method:f');
    check('an ambiguous selector is refused', false, 'accepted');
} catch (EditException $failure) {
    check(
        'an ambiguous selector is refused',
        str_contains($failure->getMessage(), 'matched 2 nodes'),
        $failure->getMessage(),
    );
    check(
        'and naming the owner settles it',
        $locator->resolveSelect($parsed, 'method:B::f')->path !== '',
    );
}
removeTree($selectDir);

// Scope, which is what makes a rename by name safe rather than lucky.
$scopeDir = workspace();
RepositoryConfig::write($scopeDir, 200);
$scopePath = $scopeDir . '/scope.php';
file_put_contents(
    $scopePath,
    <<<'PHP'
    <?php
    
    class Outer
    {
        public function run(string $item): string
        {
            $shadow = static function (string $item): string {
                return $item;
            };
            $capture = function () use ($item): string {
                return $item;
            };
            $arrow = fn (): string => $item;
            $ownArrow = fn (string $item): string => $item;
            $anon = new class {
                public function run(string $item): string
                {
                    return $item;
                }
            };
    
            return $this->tag() . $item . $shadow('x') . $capture() . $arrow() . $ownArrow('y') . $anon->run('z');
        }
    
        private function tag(): string
        {
            return 'x';
        }
    }
    PHP . "\n",
);
$scoped = (new Editor())->apply(
    [
        'files' => [
            [
                'path' => $scopePath,
                'edits' => [
                    [
                        'target' => ['select' => 'method:Outer::run'],
                        'operation' => 'rename_variable',
                        'from' => 'item',
                        'to' => 'value',
                    ],
                ],
            ],
        ],
    ],
    true,
)['files'][0];
$scopedCode = (string) $scoped['code'];
check(
    'a closure that captures the name moves with it',
    str_contains($scopedCode, 'use ($value)'),
    $scopedCode,
);
check(
    'a closure with its own parameter of that name keeps it',
    str_contains($scopedCode, 'static function (string $item)'),
    $scopedCode,
);
check(
    'an arrow function captures, so it moves',
    str_contains($scopedCode, 'fn(): string => $value'),
    $scopedCode,
);
check(
    'an arrow function that shadows the name keeps it',
    str_contains($scopedCode, 'fn(string $item): string => $item'),
    $scopedCode,
);
check(
    'a method of an anonymous class is a scope of its own',
    substr_count($scopedCode, 'public function run(string $item)') === 1,
    $scopedCode,
);
// The same anonymous class must not answer a selector naming the class around it.
$selected = (new Editor())->apply(
    [
        'files' => [
            [
                'path' => $scopePath,
                'edits' => [
                    [
                        'target' => ['select' => 'method:Outer::run'],
                        'operation' => 'set_name',
                        'value' => 'execute',
                    ],
                ],
            ],
        ],
    ],
    true,
)['files'][0];
check(
    'and it does not answer a selector naming the class around it',
    $selected['editsApplied'] === 1,
    (string) $selected['editsApplied'],
);

try {
    (new Editor())->apply(
        [
            'files' => [
                [
                    'path' => $scopePath,
                    'edits' => [
                        [
                            'target' => ['select' => 'method:Outer::run'],
                            'operation' => 'rename_variable',
                            'from' => 'this',
                            'to' => 'self',
                        ],
                    ],
                ],
            ],
        ],
        true,
    );
    check('renaming $this is refused', false, 'accepted');
} catch (EditException $failure) {
    check(
        'renaming $this is refused',
        str_contains($failure->getMessage(), 'will not rename $this'),
        $failure->getMessage(),
    );
}
removeTree($scopeDir);

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
check(
    'a declared repository prints canonically',
    $result['printer'] === 'canonical',
    $result['printer'],
);
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
    check(
        'an unknown printer is refused',
        str_contains($throwable->getMessage(), 'printer must be'),
    );
}
removeTree($dir);
// ---- Format-preserving must hold for every operation class, not just renames ------------
// printFormatPreserving() falls back to full printing for a subtree it cannot map, silently.
// Each class is therefore measured, not assumed.
$cases = [
    'set_name' => [
        "<?php\nclass Foo\n{\n    public function bar()\n    {\n        return 1;\n    }\n}\n",
        [
            'target' => ['ref' => 'stmts[0].stmts[0].name'],
            'operation' => 'set_name',
            'value' => 'baz',
        ],
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
        ['target' => $firstStatement, 'operation' => 'set_doc_comment', 'value' => 'Docs.'],
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
check(
    'the root is where composer.json is',
    RepositoryConfig::rootFor($dir . '/a.php') === realpath($dir),
);
// A broken declaration must be named, not ignored.
file_put_contents($dir . '/' . RepositoryConfig::FILE, "{ not json\n");

try {
    RepositoryConfig::discover($dir);
    check('invalid declaration JSON is refused', false, 'accepted');
} catch (Throwable $throwable) {
    check(
        'invalid declaration JSON is refused',
        str_contains($throwable->getMessage(), 'not valid JSON'),
    );
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
    check(
        'a width below the minimum is refused',
        str_contains($throwable->getMessage(), 'at least'),
    );
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
check(
    'a php-specific section outranks the catch-all',
    EditorConfig::discover($dir)->maxLineLength === 120,
);
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
check(
    'a config without the key declares nothing',
    EditorConfig::discover($dir)->maxLineLength === null,
);
// The nearest file wins, and root = true stops the walk.
mkdir($dir . '/nested', 0700, true);
file_put_contents($dir . '/nested/.editorconfig', "[*]\nmax_line_length = 60\n");
check(
    'the nearest declaration wins',
    EditorConfig::discover($dir . '/nested')->maxLineLength === 60,
);
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
check(
    'the declaration outranks the recorded width',
    $width['width'] === 120 && $width['recorded'] === 40,
);
removeTree($dir);
// ---- exclusions: a fixture is input data, not source ------------------------------------
$dir = workspace();
mkdir($dir . '/fixtures', 0700, true);
file_put_contents($dir . '/a.php', "<?php\nclass  Foo{}\n");
file_put_contents($dir . '/fixtures/keep.php', "<?php\nclass  Untouched{}\n");
$fixture = (string) file_get_contents($dir . '/fixtures/keep.php');
$run = (new Formatter())->format([$dir], 80, false, ['fixtures'], $dir);
check('an excluded path is left alone', file_get_contents($dir . '/fixtures/keep.php') === $fixture);
check(
    'everything else is still formatted',
    file_get_contents($dir . '/a.php') !== "<?php\nclass  Foo{}\n",
);
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
check(
    'and the formatter is identified',
    ($report['formatters'][0]['tool'] ?? '') === 'php-cs-fixer',
);
removeTree($dir);
// The whole call is measured, not just its argument list. `pMaybeMultiline()`
// is handed the arguments alone, so a call whose arguments fit while the call
// does not used to come out on one long line — 203 of the 477 over-long lines
// in a 119-file corpus were exactly that.
$printer = new CanonicalPrinter(PhpVersion::fromString('8.2'), 60);
$parser = (new ParserFactory())->createForVersion(PhpVersion::fromString('8.2'));
// The argument list alone is 16 characters and fits a 60-column budget twice
// over; the call around it does not. What sits in front of the *expression* —
// the `return ` — is a level further up still and is not measured, so the case
// is built on the call alone.
$source = "<?php\nclass C { public function f(\$aaa, \$bbb, \$ccc) { new AnExtremelyLongClassNameForThisTest(\$aaa, \$bbb, \$ccc); } }\n";
$wide = $printer->prettyPrintFile($parser->parse($source) ?? []);
$longest = 0;

foreach (explode("\n", $wide) as $line) {
    $longest = max($longest, strlen($line));
}
check(
    'a call is broken when the call, not just its arguments, exceeds the width',
    $longest <= 60,
    'longest line is ' . $longest . ":\n" . $wide,
);
// A chain: the receiver is rendered before the call's own argument list, so a
// re-print keyed on a flag rather than on the list breaks the wrong one — the
// short inner list, leaving the long line long.
$chained = $printer->prettyPrintFile(
    $parser->parse(
        "<?php\nclass C { public function f(\$aaa, \$bbb) { \$q->firstMethodName(\$aaa)->secondMethodName(\$bbb, \$aaa); } }\n",
    ) ?? [],
);
check(
    'the outer list of a chain is the one that breaks',
    // Both halves are needed: the negative one alone is satisfied by a chain
    // that is not broken at all, whatever the receiver does.
    str_contains($chained, "secondMethodName(\n") && !str_contains($chained, "firstMethodName(\n"),
    $chained,
);
// Two empty argument lists are `===` to each other, so keying the re-print on
// the list itself broke the receiver's — `$q->one(` on one line, `)->two();` on
// the next. There is nothing to break in an empty list at all.
$empty = (new CanonicalPrinter(PhpVersion::fromString('8.2'), 40))->prettyPrintFile(
    $parser->parse(
        "<?php\nclass C { public function f() { \$q->veryLongMethodNameOne()->veryLongMethodNameTwo(); } }\n",
    ) ?? [],
);
check('an empty argument list is never broken', !str_contains($empty, "(\n"), $empty);
// A signature: the parameter list fits, the line that carries it does not. The
// rendering of a declaration always contains its body's line breaks, so this
// only works because the width is compared against the first line rather than
// the whole thing.
$signature = (new CanonicalPrinter(PhpVersion::fromString('8.2'), 80))->prettyPrintFile(
    $parser->parse(
        "<?php\nclass C {\n    private function verifyUsernameFirst(string \$username, string \$assertion, string \$challenge): int { return 1; }\n}\n",
    ) ?? [],
);
check(
    'a parameter list is broken when the signature exceeds the width',
    str_contains($signature, "verifyUsernameFirst(\n"),
    $signature,
);
// Attributes stand on their own lines in front of a declaration. Measuring the
// first line of the rendering would measure `#[Attr]` and let the signature
// behind it run past the budget.
$attributed = (new CanonicalPrinter(PhpVersion::fromString('8.4'), 80))->prettyPrintFile(
    $parser->parse(
        "<?php\nclass C {\n    #[Attr]\n    private function verifyUsernameFirst(string \$username, string \$assertion, string \$c): int { return 1; }\n}\n",
    ) ?? [],
);
check(
    'an attribute in front does not stand in for the signature',
    str_contains($attributed, "verifyUsernameFirst(\n"),
    $attributed,
);
// Property hooks carry a parameter list too, through a printer of their own.
$hook = (new CanonicalPrinter(PhpVersion::fromString('8.4'), 40))->prettyPrintFile(
    $parser->parse(
        "<?php\nclass C {\n    public int \$value { set(int \$aRatherLongParameterName) { \$this->value = \$aRatherLongParameterName; } }\n}\n",
    ) ?? [],
);
check('a property hook is measured like any other signature', str_contains($hook, "set(\n"), $hook);
// Attribute arguments. nikic prints those with `pCommaSeparated()`, which has
// no width at all, so a long `#[AsCommand(...)]` stayed on one line however far
// it ran.
$attributed = $printer->prettyPrintFile(
    $parser->parse(
        "<?php\n#[AsCommand(name: 'a:command', description: 'A description long enough to push the attribute past the budget.')]\nfinal class R {}\n",
    ) ?? [],
);
check(
    'attribute arguments are broken like call arguments',
    str_contains($attributed, "#[AsCommand(\n"),
    $attributed,
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
