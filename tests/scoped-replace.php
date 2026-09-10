<?php

declare(strict_types=1);

/*
 * Replace an expression or a statement inside a named declaration, by what it says.
 *
 * Measured over sixteen gated agent sessions on a three-change task, the change "inside
 * resetLockout(), replace $this->rateLimitCache->remove($key) with $this->clearAttempts($key)"
 * was attempted five ways — `match`/`replace` fields, replace_statement on the method's
 * selector, replace_node, replace_child with a guessed property path, insert_before — and
 * refused each time. The engine took that edit only through inspect and a line and column,
 * and that loop was where the gated arm's extra turns went: 54 of 98 apply calls refused,
 * turns following refusals at r = 0.74.
 *
 * These cases pin the form that edit now takes, the defect that turned one of those
 * attempts into an INVALID_RESULT, and the synonyms the engine already recognised in its
 * own refusals.
 */
require_once dirname(__DIR__) . '/vendor/autoload.php';

use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\Exception\EditException;

$dir = sys_get_temp_dir() . '/php-ast-scoped-' . bin2hex(random_bytes(6));
mkdir($dir, 0700, true);
$failed = [];
$passed = 0;

function scopedCheck(string $name, bool $condition): void
{
    global $failed, $passed;

    if ($condition) {
        ++$passed;
    } else {
        $failed[] = $name;
    }
}

/**
 * Apply one edit to a fresh copy of `$code`.
 *
 * @return array{code: string, result: ?array<string, mixed>, error: string}
 */
function scopedApply(string $code, array $edit): array
{
    global $dir;
    $path = $dir . '/Subject' . bin2hex(random_bytes(4)) . '.php';
    file_put_contents($path, $code);

    try {
        $result = (new Editor())->apply(['files' => [['path' => $path, 'edits' => [$edit]]]]);
        $error = '';
    } catch (EditException $e) {
        $result = null;
        $error = $e->getMessage();
    }
    $after = (string) file_get_contents($path);
    @unlink($path);

    return ['code' => $after, 'result' => $result, 'error' => $error];
}

/** The body of one method, as printed, so a check can be scoped to it. */
function scopedBody(string $code, string $method): string
{
    $start = strpos($code, 'function ' . $method . '(');

    if ($start === false) {
        return '';
    }
    $next = strpos($code, "\n    public function ", $start + 1);
    $next = $next === false ? strpos($code, "\n    private function ", $start + 1) : $next;

    return substr($code, $start, ($next === false ? strlen($code) : $next) - $start);
}

/** @return list<array<string, mixed>> */
function scopedEffects(?array $result): array
{
    return $result['files'][0]['effects'] ?? [];
}

// The measured subject, reduced: the same removal written in two methods, so a replacement
// that ignores its scope is visible as one.
$subject = <<<'PHP'
<?php

final class RateLimiter
{
    public function __construct(private readonly Cache $rateLimitCache)
    {
    }

    public function resetLockout(string $username, string $ip = ''): void
    {
        if ($ip !== '') {
            $key = $this->lockoutKeyFor($username, $ip);
            $this->rateLimitCache->remove($key);

            return;
        }
        $this->rateLimitCache->flushByTag('lockout_' . $username);
    }

    public function recordSuccess(string $username, string $key): void
    {
        $this->rateLimitCache->remove($key);
    }

    private function clearAttempts(string $key): void
    {
        $this->rateLimitCache->remove($key);
    }

    private function lockoutKeyFor(string $username, string $ip): string
    {
        return $username . $ip;
    }
}
PHP;

$reset = ['select' => 'method:RateLimiter::resetLockout'];

// --- The measured edit, in the form it takes now -----------------------------------------
$expression = scopedApply(
    $subject,
    [
        'target' => $reset,
        'operation' => 'replace_expression',
        'match' => '$this->rateLimitCache->remove($key)',
        'php' => '$this->clearAttempts($key)',
    ],
);
scopedCheck('a scoped expression replace is accepted', $expression['error'] === '');
scopedCheck(
    'it replaces the expression inside the named method',
    str_contains(scopedBody($expression['code'], 'resetLockout'), '$this->clearAttempts($key);'),
);
scopedCheck(
    'and leaves the same expression in another method alone',
    str_contains(
        scopedBody($expression['code'], 'recordSuccess'),
        '$this->rateLimitCache->remove($key);',
    ),
);
scopedCheck(
    'and inside the method it would otherwise recurse into',
    str_contains(
        scopedBody($expression['code'], 'clearAttempts'),
        '$this->rateLimitCache->remove($key);',
    ),
);
scopedCheck(
    'the report says how many it replaced',
    (scopedEffects($expression['result'])[0]['replaced'] ?? null) === 1,
);

// The match is structural. Spacing and quoting are the printer's business, not the caller's:
// a caller that copied the expression from a differently formatted file still hits it.
$loose = scopedApply(
    str_replace("'lockout_'", '"lockout_"', $subject),
    [
        'target' => $reset,
        'operation' => 'replace_expression',
        'match' => "\$this -> rateLimitCache -> flushByTag( 'lockout_' . \$username )",
        'php' => '$this->clearAll($username)',
    ],
);
scopedCheck('the match ignores spacing and quote style', $loose['error'] === '');
scopedCheck(
    'and replaces what it matched',
    str_contains(scopedBody($loose['code'], 'resetLockout'), '$this->clearAll($username);'),
);

// Every occurrence in scope, each with its own node: a replacement shared between two
// places would be one object hanging in two parents.
$twice = str_replace(
    "        \$this->rateLimitCache->flushByTag('lockout_' . \$username);",
    "        \$this->rateLimitCache->remove(\$key);\n        \$this->rateLimitCache->remove(\$key);",
    $subject,
);
$both = scopedApply(
    $twice,
    [
        'target' => $reset,
        'operation' => 'replace_expression',
        'match' => '$this->rateLimitCache->remove($key)',
        'php' => '$this->clearAttempts($key)',
    ],
);
scopedCheck(
    'every occurrence in scope is replaced',
    substr_count(scopedBody($both['code'], 'resetLockout'), '$this->clearAttempts($key);') === 3,
);
scopedCheck('and counted', (scopedEffects($both['result'])[0]['replaced'] ?? null) === 3);

// Nothing matched is a refusal that says what it looked for and where, not a silent no-op
// that reports success.
$none = scopedApply(
    $subject,
    [
        'target' => $reset,
        'operation' => 'replace_expression',
        'match' => '$this->rateLimitCache->remove($other)',
        'php' => '$this->clearAttempts($other)',
    ],
);
scopedCheck('a match that finds nothing is refused', $none['error'] !== '');
scopedCheck('the refusal names the pattern', str_contains($none['error'], 'remove($other)'));
scopedCheck('and the scope it searched', str_contains($none['error'], 'resetLockout'));
scopedCheck('and nothing is written', $none['code'] === $subject);

// The statement form, for a caller who names the whole statement.
$statement = scopedApply(
    $subject,
    [
        'target' => $reset,
        'operation' => 'replace_statement',
        'match' => '$this->rateLimitCache->remove($key);',
        'php' => '$this->clearAttempts($key);',
    ],
);
scopedCheck('a scoped statement replace is accepted', $statement['error'] === '');
scopedCheck(
    'and replaces the statement in scope only',
    str_contains(scopedBody($statement['code'], 'resetLockout'), '$this->clearAttempts($key);') && str_contains(
        scopedBody($statement['code'], 'recordSuccess'),
        '$this->rateLimitCache->remove($key);',
    ),
);

// A measured caller wrote the replacement as `replace` beside `match`. With `match` there is
// no other reading of it.
$replaceField = scopedApply(
    $subject,
    [
        'target' => $reset,
        'operation' => 'replace_expression',
        'match' => '$this->rateLimitCache->remove($key)',
        'replace' => '$this->clearAttempts($key)',
    ],
);
scopedCheck('"replace" beside "match" is read as the replacement', $replaceField['error'] === '');

// --- The defect behind eight INVALID_RESULTs ---------------------------------------------
// ClassMethod extends Stmt, so replace_statement took a method as its target, swapped it for
// a statement, and the file failed only at the reparse gate — a message about a syntax error
// on a line the caller never touched.
$onMethod = scopedApply(
    $subject,
    ['target' => $reset, 'operation' => 'replace_statement', 'php' => '$this->clearAttempts($key);'],
);
scopedCheck('replace_statement on a method is refused', $onMethod['error'] !== '');
scopedCheck(
    'before mutation, not at the reparse gate',
    !str_contains($onMethod['error'], 'INVALID_RESULT'),
);
scopedCheck('the refusal shows the scoped form', str_contains($onMethod['error'], '"match"'));
scopedCheck('and nothing is written', $onMethod['code'] === $subject);

$exprOnMethod = scopedApply(
    $subject,
    ['target' => $reset, 'operation' => 'replace_expression', 'php' => '$this->clearAttempts($key)'],
);
scopedCheck(
    'replace_expression on a method names the scoped form too',
    str_contains($exprOnMethod['error'], '"match"'),
);

// --- Names the engine already recognised in its own refusals ------------------------------
$docTarget = ['select' => 'method:RateLimiter::recordSuccess'];

foreach (['set_docblock', 'update_docblock'] as $alias) {
    $doc = scopedApply(
        $subject,
        ['target' => $docTarget, 'operation' => $alias, 'value' => 'Forget the caller.'],
    );
    scopedCheck(
        $alias . ' sets the doc comment',
        $doc['error'] === '' && str_contains($doc['code'], 'Forget the caller.'),
    );
}

$docField = scopedApply(
    $subject,
    ['target' => $docTarget, 'operation' => 'set_doc_comment', 'docComment' => 'Forget the caller.'],
);
scopedCheck(
    'set_doc_comment reads "docComment" as its value',
    $docField['error'] === '' && str_contains($docField['code'], 'Forget the caller.'),
);

// The one-call flag form carries `match` like any other argument of the operation.
$flagPath = $dir . '/Flag.php';
file_put_contents($flagPath, $subject);
exec(
    implode(
        ' ',
        array_map(
            'escapeshellarg',
            [
                PHP_BINARY,
                dirname(__DIR__) . '/bin/php-ast-edit',
                'apply',
                '--file',
                $flagPath,
                '--select',
                'method:RateLimiter::resetLockout',
                '--op',
                'replace_expression',
                '--match',
                '$this->rateLimitCache->remove($key)',
                '--php',
                '$this->clearAttempts($key)',
            ],
        ),
    ) . ' 2>&1',
    $flagOutput,
    $flagStatus,
);
scopedCheck('the flag form takes --match', $flagStatus === 0);
scopedCheck(
    'and applies it in scope',
    str_contains(
        scopedBody((string) file_get_contents($flagPath), 'resetLockout'),
        '$this->clearAttempts($key);',
    ),
);
@unlink($flagPath);

rmdir($dir);

if ($failed !== []) {
    fwrite(
        STDERR,
        "FAIL: " . count($failed) . " scoped-replace case(s)\n  - " . implode("\n  - ", $failed) . "\n",
    );
    exit(1);
}
printf("OK: %d scoped-replace cases.\n", $passed);
