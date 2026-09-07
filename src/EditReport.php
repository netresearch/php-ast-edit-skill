<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

/** Reports observed outcomes without equating parsing with semantic correctness. */
final class EditReport
{
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
