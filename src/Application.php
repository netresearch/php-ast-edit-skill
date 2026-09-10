<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use JsonException;
use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Error as ParserError;
use PhpParser\ParserFactory;

final class Application
{
    /**
     * The operation's own arguments, as the flag form spells them.
     *
     * @var list<string>
     */
    private const OPERATION_FLAGS = ['php', 'match', 'value', 'alias', 'from', 'to', 'property', 'position', 'index'];

    /**
     * Everything `apply --file` reads. Anything else is refused rather than dropped.
     *
     * @var list<string>
     */
    private const FLAG_FORM_FLAGS = [
        'file',
        'op',
        'select',
        'ref',
        'kind',
        'parse-as',
        'sha256',
        'report',
        'dry-run',
        ...self::OPERATION_FLAGS,
    ];

    /**
     * Everything `apply --input` reads.
     *
     * @var list<string>
     */
    private const INPUT_FORM_FLAGS = ['input', 'dry-run'];

    /**
     * Real per-file settings that no flag carries — the document is their only home.
     *
     * Named so a caller who reaches for `--mode` is told where it lives, rather than that it
     * does not exist. Kept in step with what `Editor::prepare()` reads from a file spec.
     *
     * @var list<string>
     */
    private const DOCUMENT_ONLY_KEYS = ['mode', 'expectAbsent', 'optional', 'requires', 'phpVersion', 'printer'];

    public function run(array $argv): int
    {
        try {
            $command = $argv[1] ?? 'help';
            $options = $this->options(array_slice($argv, 2));

            return match ($command) {
                'inspect' => $this->inspect($options),
                'apply' => $this->apply($options),
                'validate' => $this->validate($options),
                'contexts' => $this->contexts($options),
                'format' => $this->format($options, false),
                'normalize' => $this->format($options, true),
                'doctor' => $this->doctor($options),
                'help', '--help', '-h' => $this->help(),
                default => throw new EditException('Unknown command: ' . $command),
            };
        } catch (EditException|ParserError|JsonException $exception) {
            fwrite(
                STDERR,
                json_encode(
                    [
                        'ok' => false,
                        'error' => $exception->getMessage(),
                        'class' => $exception::class,
                    ],
                    JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
                ) . "\n",
            );

            return 2;
        } catch (\Throwable $exception) {
            fwrite(
                STDERR,
                json_encode(
                    [
                        'ok' => false,
                        'error' => $exception->getMessage(),
                        'class' => $exception::class,
                    ],
                    JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
                ) . "\n",
            );

            return 3;
        }
    }

    private function inspect(array $options): int
    {
        $file = $this->requiredOption($options, 'file');
        $target = $this->targetFromOptions($options);
        $editor = new Editor();
        $result = $editor->inspect($file, $target, $options['php-version'] ?? null);
        $this->json($result);

        return 0;
    }

    private function validate(array $options): int
    {
        $file = $this->requiredOption($options, 'file');
        $editor = new Editor();
        $this->json($editor->validate($file, $options['php-version'] ?? null));

        return 0;
    }

    private function apply(array $options): int
    {
        // One command written two ways, so one execution and one verdict. Reporting the
        // flag form's result and returning 0 over it made a failed check look like a clean
        // edit — the opposite of what help promises, and unrecoverable for a caller that
        // reads the exit code and stops there.
        $document = $this->inlineDocument($options) ?? $this->inputDocument($options);
        $result = (new Editor())->apply($document, isset($options['dry-run']));
        $this->json($result);

        return $result['checksPassed'] === false ? 1 : 0;
    }

    /**
     * The whole transaction, read from --input or stdin.
     *
     * @param  array<string, mixed> $options
     * @return array<string, mixed>
     */
    private function inputDocument(array $options): array
    {
        $this->rejectUnsupported(
            $options,
            self::INPUT_FORM_FLAGS,
            self::FLAG_FORM_FLAGS,
            '--input carries the whole document, so say it there.',
        );
        $input = $options['input'] ?? '-';

        if (!is_string($input)) {
            throw new EditException('--input requires a path or -.');
        }
        // `/dev/stdin` is how a heredoc caller spells `-`, and some sandboxes give a process
        // no such path while its standard input is perfectly readable.
        $json = in_array($input, ['-', '/dev/stdin', 'php://stdin'], true) ? stream_get_contents(STDIN) : file_get_contents($input);

        if ($json === false || trim($json) === '') {
            throw new EditException('No apply JSON received.');
        }
        $document = json_decode($json, true, 512, JSON_THROW_ON_ERROR);

        if (!is_array($document)) {
            throw new EditException('Apply input must decode to a JSON object.');
        }

        return $document;
    }

    /**
     * Refuse any option the chosen form does not carry, and say which kind of wrong it is.
     *
     * The parser takes `--anything value`, so a flag nobody reads is accepted and dropped.
     * Dropping `--sha256` was the worst of them: the caller believes it edited the file it
     * read, and the guard it asked for never ran.
     *
     * Three kinds of wrong, and one message for all three helps none of them. `--select`
     * against `--input` is a real flag in the wrong form. `--mode` is a real setting that
     * simply has no flag, and belongs in the document. `--fil` is a typo, and telling its
     * author to write it into a document sends them somewhere it does not belong either.
     *
     * @param array<string, mixed> $options
     * @param list<string>         $supported the flags this form reads
     * @param list<string>         $otherForm the flags the other form reads
     */
    private function rejectUnsupported(
        array $options,
        array $supported,
        array $otherForm,
        string $advice,
    ): void {
        $unsupported = array_values(array_diff(array_keys($options), $supported));

        if ($unsupported === []) {
            return;
        }
        $misplaced = array_values(array_intersect($unsupported, $otherForm));
        $rest = array_diff($unsupported, $otherForm);
        $documentOnly = array_values(array_intersect($rest, self::DOCUMENT_ONLY_KEYS));
        $unknown = array_values(array_diff($rest, self::DOCUMENT_ONLY_KEYS));
        $parts = [];

        if ($misplaced !== []) {
            $parts[] = $this->flagList($misplaced) . $this->verb($misplaced, ' belongs', ' belong') . ' to the other form of apply. ' . $advice;
        }

        if ($documentOnly !== []) {
            $parts[] = $this->flagList($documentOnly) . $this->verb(
                $documentOnly,
                ' is a per-file setting with no flag: write it in the document and pass --input.',
                ' are per-file settings with no flag: write them in the document and pass --input.',
            );
        }

        if ($unknown !== []) {
            $parts[] = $this->flagList($unknown) . $this->verb($unknown, ' is not a flag', ' are not flags') . ' apply takes. Run `php-ast-edit help` for the two forms and what each carries.';
        }

        throw new EditException(implode(' ', $parts));
    }

    /**
     * @param list<string> $flags
     */
    private function flagList(array $flags): string
    {
        return '--' . implode(', --', $flags);
    }

    /**
     * @param list<string> $flags
     */
    private function verb(array $flags, string $singular, string $plural): string
    {
        return count($flags) === 1 ? $singular : $plural;
    }

    private function format(array $options, bool $normalize): int
    {
        $paths = isset($options['path']) ? [(string) $options['path']] : ['.'];
        $root = RepositoryConfig::rootFor($paths[0]);
        $config = RepositoryConfig::discover($root);
        // The width is the project's to declare, not this tool's to carry. `.editorconfig` is
        // where a project states it without handing the decision to one formatter.
        $declared = RepositoryConfig::widthFor($root);
        $width = $declared['width'] ?? $declared['recorded'];

        if (isset($options['width'])) {
            throw new EditException(
                '--width is gone: line width is a project rule and belongs in .editorconfig, under ' . '[*] or [*.php] as max_line_length. This tool reads it and holds the repository ' . 'to it; it does not bring one.',
            );
        }
        $exclude = $config->exclude;

        if (isset($options['exclude'])) {
            if (!$normalize) {
                throw new EditException(
                    '--exclude belongs to normalize, which records it in ' . RepositoryConfig::FILE . '. ' . 'Formatting a different set than the repository was normalised with leaves the ' . 'excluded files off the fixed point without anything saying so.',
                );
            }
            $exclude = array_values(
                array_filter(array_map('trim', explode(',', (string) $options['exclude']))),
            );
        }
        $dryRun = isset($options['dry-run']);

        // Refuse before the formatter writes anything. Rewriting the files at a width nobody
        // declared and only then refusing the marker would leave the repository half
        // normalised, which is worse than not starting.
        if ($normalize && !$dryRun && $declared['width'] === null) {
            $this->json(
                [
                    'scanned' => 0,
                    'changed' => [],
                    'printWidth' => null,
                    'widthSource' => null,
                    'exclude' => $exclude,
                    'dryRun' => $dryRun,
                    'declared' => null,
                    'next' => 'Not declared and nothing written: no max_line_length in .editorconfig. ' . 'Add it under [*] or [*.php] — line width is a project rule — then run ' . 'normalize again.',
                ],
            );

            return 1;
        }
        $result = (new Formatter($options['php-version'] ?? null))->format(
            $paths,
            $width,
            $dryRun,
            $exclude,
            $root,
        );
        $payload = [
            'scanned' => $result['scanned'],
            'changed' => array_values($result['changed']),
            'printWidth' => $width,
            'widthSource' => $declared['source'],
            'exclude' => $exclude,
            'dryRun' => $dryRun,
        ];

        if ($result['failed'] !== []) {
            $payload['failed'] = $result['failed'];
        }

        if ($normalize && !$dryRun) {
            // The marker describes the whole repository, so only a run that covered the whole
            // repository may write it. A partial normalise that declared the root would leave
            // everything beside it printed canonically against a source that never was.
            $scanned = realpath($paths[0]);

            if ($scanned !== realpath($root)) {
                $payload['declared'] = null;
                $payload['next'] = sprintf(
                    'Not declared: --path covered %s, and the declaration speaks for the whole ' . 'repository at %s. Re-run normalize without --path, or against the root.',
                    $paths[0],
                    $root,
                );
            } elseif ($result['failed'] !== []) {
                // A file that could not be parsed or written is not canonical, and a marker
                // saying otherwise is worse than none.
                $payload['declared'] = null;
                $payload['next'] = 'Not declared: ' . count($result['failed']) . ' file(s) could not be formatted. Fix those, then run normalize again.';
            } else {
                $payload['declared'] = RepositoryConfig::write($root, $width, $exclude);
                $payload['next'] = 'Run the project formatter now and commit both in one change ' . 'of their own — normalisation is not a feature commit.';
            }
        }
        $this->json($payload);

        return $result['failed'] === [] ? 0 : 1;
    }

    private function doctor(array $options): int
    {
        $report = (new Doctor())->examine((string) ($options['path'] ?? '.'));
        $this->json($report);

        return $report['status'] === 'ready' ? 0 : 1;
    }

    private function contexts(array $options = []): int
    {
        $arguments = Editor::operationArguments();

        if (isset($options['operation'])) {
            $operation = (string) $options['operation'];

            if (!isset($arguments[$operation])) {
                throw new EditException(
                    'Unknown operation: ' . $operation . '. Run contexts for the catalog.',
                );
            }
            $spec = $arguments[$operation];
            $values = array_intersect_key(
                Editor::argumentValues(),
                array_flip([...$spec['requires'], ...$spec['optional']]),
            );
            $this->json(
                $values === [] ? ['operation' => $operation, 'arguments' => $spec] : ['operation' => $operation, 'arguments' => $spec, 'argumentValues' => $values],
            );

            return 0;
        }
        $parser = (new ParserFactory())->createForHostVersion();
        $this->json(
            [
                'parseAs' => array_merge((new ContextParser($parser))->contexts(), ['stmts', 'file']),
                'operations' => [
                    'primitives' => [
                        'replace_node',
                        'delete_node',
                        'insert_into',
                        'replace_child',
                        'delete_child',
                        'move_node',
                    ],
                    'comments' => ['set_doc_comment', 'remove_doc_comment'],
                    'convenience' => [
                        'set_name',
                        'set_string',
                        'replace_expression',
                        'replace_statement',
                        'insert_before',
                        'insert_after',
                        'delete',
                        'replace_argument',
                        'add_argument',
                        'remove_argument',
                        'add_member',
                        'add_parameter',
                        'add_attribute',
                        'set_return_type',
                        'set_type',
                        'set_visibility',
                        'add_implements',
                        'set_extends',
                        'add_use',
                        'rename_variable',
                        'rename_method',
                    ],
                ],
                'fileModes' => ['edit', 'create', 'delete'],
                'operationArguments' => $arguments,
            ],
        );

        return 0;
    }

    private function help(): int
    {
        echo <<<'TEXT'
        php-ast-edit — AST-based PHP edits for coding agents
        
        Commands:
          php-ast-edit inspect --file FILE (--offset N | --line N --column N) [--kind TYPE] [--php-version 8.4]
          php-ast-edit apply [--input FILE|-] [--dry-run]
          php-ast-edit apply --file FILE (--select SEL|--ref REF) --op OPERATION [args]
              [--sha256 HASH] [--report full|compact] [--dry-run]
          php-ast-edit validate --file FILE [--php-version 8.4]
          php-ast-edit contexts [--operation OPERATION]
          php-ast-edit doctor [--path DIRECTORY]
          php-ast-edit normalize [--path DIRECTORY] [--exclude PATHS] [--dry-run]
          php-ast-edit format [--path FILE_OR_DIRECTORY] [--dry-run]
        
        Use a selector when the target has a name; inspect only when coordinates are needed:
          {"files":[{"path":"src/Foo.php","edits":[{"target":{"select":"method:Foo::bar"},
            "operation":"set_return_type","php":"string|int"}]}]}
        
        One edit against a named target is one call, with no payload file:
          php-ast-edit apply --file src/Foo.php --select method:Foo::bar \
              --op rename_variable --from nonce --to nonceValue
        The operation's own arguments become flags: --php, --match, --value, --alias,
        --from, --to, --property, --position, --index, --parse-as. A file-level operation takes
        no target: php-ast-edit apply --file src/Foo.php --op add_use --value
        'Vendor\Package\Thing'. Several edits, or several files, stay in one apply
        request through JSON on stdin.
        The flag form answers exactly as the JSON form does, guards included: --sha256
        carries the file guard, --report the response shape, and a failed check exits 1
        either way. A flag the chosen form cannot carry is refused rather than dropped,
        and the refusal says which kind it is: a real flag in the other form, a per-file
        setting that only the document carries (mode, expectAbsent, optional, requires,
        phpVersion, printer), or no such flag at all.
        
        Selectors: class:, interface:, trait:, enum:, method:Foo::bar, function:,
        property:Foo::$bar, const:Foo::BAR. Names are short names; ambiguity is refused.
        Coordinates are byte-based: offsets start at zero, lines and columns at one.
        Include inspect's sha256 when addressing its structural refs or coordinates.
        
        Operation arguments: contexts --operation rename_variable
        Full operation and parseAs catalog: contexts
        File modes: edit (default), create (requires php with an opening tag), delete.
        create refuses an existing file unless expectAbsent:false; a supplied sha256 is checked.
        Batch all edits and files belonging to one transaction in one apply request.
        
        Reports separate parsed, validation.lint and validation.checks.
        Use report:"compact" in the apply document for shared top-level verify results
        and per-file checkIds. The default report:"full" keeps per-file verify results.
        report:"agent" states what the write did and what it left open: outcome, a
        checks tri-state where none_declared is not passed, failing check output only,
        and a per-file open list. It carries no diff and no generated code — git diff
        has those, from the snapshot beforeSha256 names. It alone is versioned, by
        reportVersion.
        valid is a compatibility alias for parser success, not semantic correctness.
        Host PHP lint runs before writes; a newer explicit target reports lint skipped.
        Declared project verify checks run after writing. Failed checks keep the edit and
        make apply exit 1; read verify and fix the result. Errors before commit leave files
        unchanged; commit failures attempt rollback and report any restore failures.
        warnings contains every diagnostic; warning is the joined compatibility field.
        Rename operations refuse unsafe bindings; they are not project-wide refactoring.
        
        Format-preserving output is the default for an unconfigured repository.
        Inspect changedLines and diff. Canonical formatting is optional and reflows files.
        To adopt it, declare max_line_length in .editorconfig, run normalize, then the
        project formatter, review the whole change and commit it separately.
        normalize preserves declared formatter and verify commands.
        A formatter declaration is an argv list with a whole-element {files} placeholder:
          {"formatter":["php","vendor/bin/php-cs-fixer","fix","--config=.php-cs-fixer.php",
            "--path-mode=intersection","{files}"]}
        verify accepts argv lists with {files}, or {scope,command} objects.
        Use scope:"project" without {files} for stable project checks, including deletions;
        scope:"changed_files" requires {files} and omits intentional deletions.
        Never run project-wide format just to close a
        local edit. A clean-checkout CI gate may run format + formatter + git diff --exit-code.
        
        Exit codes: 0 command completed; 1 doctor/format/check result needs attention;
        2 invalid input, refused edit or transaction failure; 3 unexpected internal error;
        4 runtime dependency missing.
        TEXT;
        echo "\n";

        return 0;
    }

    private function targetFromOptions(array $options): array
    {
        $target = [];

        if (isset($options['offset'])) {
            $target['offset'] = $this->integerOption($options, 'offset');
        } else {
            $target['line'] = $this->integerOption($options, 'line');
            $target['column'] = $this->integerOption($options, 'column');
        }

        if (isset($options['kind'])) {
            $target['kind'] = (string) $options['kind'];
        }

        return $target;
    }

    private function options(array $args): array
    {
        $options = [];

        for ($i = 0, $count = count($args); $i < $count; ++$i) {
            $arg = $args[$i];

            if (!str_starts_with($arg, '--')) {
                throw new EditException('Unexpected argument: ' . $arg);
            }
            $arg = substr($arg, 2);

            if (str_contains($arg, '=')) {
                [$name, $value] = explode('=', $arg, 2);
                $options[$name] = $value;

                continue;
            }

            if (in_array($arg, ['dry-run'], true)) {
                $options[$arg] = true;

                continue;
            }

            if ($i + 1 >= $count || str_starts_with($args[$i + 1], '--')) {
                throw new EditException('--' . $arg . ' requires a value.');
            }
            $options[$arg] = $args[++$i];
        }

        return $options;
    }

    private function integerOption(array $options, string $key): int
    {
        if (!isset($options[$key]) || filter_var($options[$key], FILTER_VALIDATE_INT) === false) {
            throw new EditException('--' . $key . ' requires an integer.');
        }

        return (int) $options[$key];
    }

    private function requiredOption(array $options, string $key): string
    {
        $value = $options[$key] ?? null;

        if (!is_string($value) || $value === '') {
            throw new EditException('--' . $key . ' is required.');
        }

        return $value;
    }

    private function json(array $data): void
    {
        // A source file need not be UTF-8. Substituting keeps `inspect` usable on a latin-1
        // file instead of failing the whole command over one byte in an excerpt.
        echo json_encode(
            $data,
            JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE | JSON_THROW_ON_ERROR,
        ) . "\n";
    }

    /**
     * Build a one-edit document from flags, so a simple change is one call.
     *
     * Measured on controlled runs: every edit cost two calls, one writing a JSON payload to a
     * temporary file and one applying it. The JSON form stays — several edits over several
     * files need it — but the common case is a single edit against a named target, and that
     * should not require a file.
     *
     *     php-ast-edit apply --file Foo.php --select method:Foo::bar \
     *         --op rename_variable --from nonce --to nonceValue
     *
     * @param  array<string, mixed> $options
     * @return array<string, mixed>|null the document, or null when no flag form was used
     */
    private function inlineDocument(array $options): ?array
    {
        if (!isset($options['file'])) {
            return null;
        }

        // The two forms are alternatives, and mixing them produced the least useful message
        // the CLI had: `--input e.json --file a.php` reported that the flag form requires
        // --op, which is true and answers nothing, because the caller had a whole document
        // and did not want the flag form at all.
        if (isset($options['input'])) {
            throw new EditException(
                '--input and --file are the two ways to say the same thing, and only one at a ' . 'time. --input carries a whole transaction as JSON; --file with --select or ' . '--ref and --op is one edit written out as flags. Drop whichever you did not mean.',
            );
        }
        $this->rejectUnsupported(
            $options,
            self::FLAG_FORM_FLAGS,
            self::INPUT_FORM_FLAGS,
            'Per-file settings with no flag — mode, expectAbsent, optional, requires, ' . 'phpVersion, printer — only a whole document can carry: write them as JSON and ' . 'pass --input.',
        );
        $operation = $this->flagString($options, 'op', true);
        $edit = ['operation' => $operation];
        $target = $this->flagTarget($options, $operation);

        if ($target !== null) {
            $edit['target'] = $target;
        }

        foreach (self::OPERATION_FLAGS as $key) {
            $value = $this->flagString($options, $key);

            if ($value !== null) {
                $edit[$key] = in_array($key, ['position', 'index'], true) && ctype_digit($value) ? (int) $value : $value;
            }
        }
        $parseAs = $this->flagString($options, 'parse-as');

        if ($parseAs !== null) {
            $edit['parseAs'] = $parseAs;
        }
        $file = ['path' => $this->flagString($options, 'file', true), 'edits' => [$edit]];

        // A guard the caller asked for and the document never carried is worse than no
        // guard: `--sha256` reads as "refuse if this file moved under me" and did nothing.
        $sha256 = $this->flagString($options, 'sha256');

        if ($sha256 !== null) {
            $file['sha256'] = $sha256;
        }
        $document = ['files' => [$file]];
        $report = $this->flagString($options, 'report');

        if ($report !== null) {
            // Passed through unvalidated: the response shape is the Editor's contract, and
            // one place deciding which values exist is one place to change when they do.
            $document['report'] = $report;
        }

        return $document;
    }

    /**
     * The target the flag form names, or null for an operation that has none.
     *
     * @param  array<string, mixed> $options
     * @return array<string, string>|null
     */
    private function flagTarget(array $options, string $operation): ?array
    {
        $target = [];

        foreach (['select', 'ref', 'kind'] as $key) {
            $value = $this->flagString($options, $key);

            if ($value !== null) {
                $target[$key] = $value;
            }
        }

        if (in_array($operation, Editor::FILE_SCOPED, true)) {
            if ($target !== []) {
                throw new EditException(
                    '--op ' . $operation . ' writes to the file, not to a node, and takes no target.',
                );
            }

            return null;
        }

        if (!isset($target['select']) && !isset($target['ref'])) {
            // --kind narrows a locator, it is not one: without --select or --ref it would name
            // every node of that kind in the file, which is not a target an edit can apply to.
            throw new EditException('The flag form needs --select or --ref to name the target.');
        }

        return $target;
    }

    /**
     * One string option, or null when it was not given.
     *
     * @param array<string, mixed> $options
     */
    private function flagString(array $options, string $name, bool $required = false): ?string
    {
        if (!isset($options[$name])) {
            if ($required) {
                throw new EditException('The flag form requires --' . $name . '.');
            }

            return null;
        }
        $value = $options[$name];

        if (!is_string($value)) {
            throw new EditException('--' . $name . ' requires a value.');
        }

        return $value;
    }
}
