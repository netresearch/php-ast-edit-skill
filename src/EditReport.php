<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

/** Reports observed outcomes without equating parsing with semantic correctness. */
final class EditReport
{
    /**
     * The `agent` report's schema version.
     *
     * A bump means a field was removed or its meaning changed; a field added alongside the
     * existing ones does not bump it. `full` and `compact` are unversioned and stay that way
     * — they are the compatibility surface, and stamping a version on them now would claim a
     * guarantee they never gave.
     */
    public const AGENT_VERSION = 1;

    /**
     * What one file's write is known to have done, and what it left open.
     *
     * The `full` report answers "what happened"; this one answers "what does the next
     * decision need". Measured on controlled runs, the expensive half was never the edit —
     * it was the reading, re-reading and re-checking around it, and a report that carries the
     * diff, the generated file and two spellings of every field invites exactly that.
     *
     * Three separate claims, never collapsed into one boolean: the write landed, the syntax
     * parsed, the declared checks ran and said something. `checks` is a tri-state because
     * "no checks are declared" is not "the checks passed" — an agent that reads a nullable
     * boolean here cannot tell an unverified edit from a verified one.
     *
     * What is deliberately absent: `diff` and `code`. `beforeSha256` identifies the input
     * bytes but stores no retrievable snapshot. `git diff -- <path>` compares the working
     * tree with the index: earlier, staged or subsequent edits can differ from this
     * transaction, and untracked files are omitted. Request `full` or `compact` before
     * writing when the transaction's diff is needed, subject to existing output limits.
     * Do not rerun an edit merely to obtain its diff.
     *
     * @return array<string, mixed>
     */
    public static function agentFile(FileTransaction $file, bool $dryRun): array
    {
        $result = [
            'path' => $file->path,
            'mode' => $file->mode,
            'changed' => $file->changed,
            'editsApplied' => count($file->resolved),
            'beforeSha256' => $file->beforeSha(),
            'afterSha256' => $file->output === null ? null : hash('sha256', $file->output),
            'changedLines' => $file->changedLines,
            'syntax' => self::syntax($file),
            'checks' => self::checkState($file->verify),
            'checkIds' => array_column($file->verify, 'id'),
        ];

        if ($file->effects !== []) {
            ksort($file->effects);
            $result['effects'] = $file->effects;
        }
        $warnings = self::warnings($file);

        if ($warnings !== []) {
            // The list only. `warning` is the same text joined by newlines, and carrying both
            // spends the larger of the two fields on a value the caller already holds.
            $result['warnings'] = $warnings;
        }
        $result['open'] = self::open($file, $dryRun);

        return $result;
    }

    /**
     * Whether the parser was asked, and whether the host could confirm it on the target.
     *
     * `passed` is the parser plus a host lint that ran. `skipped` means the target PHP is
     * newer than this interpreter, so nothing checked the syntax the file will actually meet
     * — a weaker claim that must not read as the stronger one.
     */
    private static function syntax(FileTransaction $file): string
    {
        if ($file->mode === 'delete') {
            return 'not_run';
        }
        $status = $file->lint['status'] ?? null;

        if ($status === null) {
            // `render()` lints every transaction it prints, so nothing reaches this today.
            // It is here because the alternative default is `passed`: a path that stopped
            // linting would report the strongest claim this field can make, silently, and
            // an agent would stop on it. An absent check is not a passed one.
            return 'not_run';
        }

        return $status === 'skipped' ? 'skipped' : 'passed';
    }

    /**
     * The declared checks' verdict for one scope.
     *
     * @param list<array<string, mixed>> $verify
     */
    private static function checkState(array $verify): string
    {
        if ($verify === []) {
            return 'none_declared';
        }

        return in_array(false, array_column($verify, 'ok'), true) ? 'failed' : 'passed';
    }

    /**
     * What this write did not establish, derived from what actually happened.
     *
     * Only real state produces an entry. A constant line on every response — "whether the
     * user's task is met does not follow from this" — is true, and belongs in the mode's
     * documentation rather than in every payload it returns.
     *
     * @return list<string>
     */
    private static function open(FileTransaction $file, bool $dryRun): array
    {
        $open = [];

        if ($dryRun) {
            $open[] = 'NOT_WRITTEN: this was a dry run; the working tree is unchanged.';
        }

        foreach ($file->effects as $effect) {
            $operation = (string) ($effect['operation'] ?? 'rename');
            $remaining = (int) ($effect['remainingInFile'] ?? 0);

            if ($remaining > 0) {
                $open[] = sprintf(
                    'REMAINING_IN_FILE: %s left %d occurrence(s) of the old name in this file.',
                    $operation,
                    $remaining,
                );
            }

            if ((int) ($effect['otherReceivers'] ?? 0) > 0) {
                $open[] = sprintf(
                    'UNRESOLVED_RECEIVERS: %s found %d call site(s) whose receiver type could not be resolved.',
                    $operation,
                    (int) $effect['otherReceivers'],
                );
            }

            if ($operation === 'rename_method') {
                // The rename is declaration-and-resolved-dispatch only, by design. Saying so
                // is the difference between an agent stopping here and an agent believing
                // the project is consistent.
                $open[] = 'CALLERS_OUTSIDE_FILE: rename_method does not resolve callers in other files; a project-aware tool has to confirm them.';
            }
        }

        if (self::syntax($file) === 'skipped') {
            $open[] = 'SYNTAX_UNCHECKED_ON_TARGET: the running interpreter is older than the target PHP; the syntax was not confirmed against it.';
        }

        if ($file->verify === []) {
            $open[] = 'NO_CHECKS_DECLARED: this repository declares no verify commands, so nothing tested the result.';
        }

        return $open;
    }

    /** @return list<string> */
    private static function warnings(FileTransaction $file): array
    {
        $warnings = [];

        if ($file->warning !== null) {
            $warnings[] = $file->warning;
        }

        return $warnings;
    }

    /** @return array<string, mixed> */
    public static function file(
        FileTransaction $file,
        bool $dryRun,
        ?string $diff,
        bool $compact = false,
    ): array {
        $result = [
            'path' => $file->path,
            'mode' => $file->mode,
            'beforeSha256' => $file->beforeSha(),
            'afterSha256' => $file->output === null ? null : hash('sha256', $file->output),
            'changed' => $file->changed,
            'changedLines' => $file->changedLines,
            'printer' => $file->printer,
            'editsApplied' => count($file->resolved),
            'dryRun' => $dryRun,
        ];
        $warnings = [];

        if ($file->effects !== []) {
            ksort($file->effects);
            $result['effects'] = $file->effects;
            $unfinished = [];

            foreach ($file->effects as $effect) {
                $left = (int) ($effect['remainingInFile'] ?? $effect['otherReceivers'] ?? 0);

                if ($left > 0) {
                    $unfinished[] = sprintf(
                        '%s: %d old-name occurrence(s) remain in this file',
                        (string) ($effect['operation'] ?? 'rename'),
                        $left,
                    );
                }
            }

            if ($unfinished !== []) {
                $warnings[] = 'INCOMPLETE_RENAME: ' . implode('; ', $unfinished) . '. Review whether those occurrences belong to the requested scope.';
            }
        }

        if ($file->warning !== null) {
            $warnings[] = $file->warning;
        }

        if (($file->lint['status'] ?? '') === 'skipped') {
            $warnings[] = 'PHP_LINT_SKIPPED: target PHP is newer than the running interpreter; validate with the target runtime.';
        }

        if ($warnings !== []) {
            $result['warnings'] = $warnings;
            $result['warning'] = implode("\n", $warnings);
        }

        if ($diff !== null) {
            $result['diff'] = $diff;
        }

        if ($file->formatter !== null) {
            $result['formatter'] = $file->formatter;
        }
        $checks = $file->verify === [] ? 'not_run' : (in_array(false, array_column($file->verify, 'ok'), true) ? 'failed' : 'passed');

        if ($compact) {
            $result['checkIds'] = array_column($file->verify, 'id');
        } elseif ($file->verify !== []) {
            $result['verify'] = array_map(
                static fn (
                    array $check,
                ): array => array_intersect_key($check, array_flip(['command', 'ok', 'output'])),
                $file->verify,
            );
        }

        if ($file->mode !== 'delete') {
            $result['parsed'] = true;
            $result['valid'] = true;
            // Compatibility alias of parser success, not an application verdict.
            $result['validation'] = ['parser' => 'passed', 'lint' => $file->lint, 'checks' => $checks];
        } else {
            $result['validation'] = ['parser' => 'not_run', 'lint' => ['status' => 'not_run'], 'checks' => $checks];
        }

        if ($dryRun && $file->output !== null) {
            $result['code'] = $file->output;
        }

        return $result;
    }
}
