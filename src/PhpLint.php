<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;

/** PHP's compile-only check complements the parser without executing the edited source. */
final class PhpLint
{
    /** @return array{status: string, runtime: string, reason?: string} */
    public function check(string $source, string $path, ?string $targetVersion): array
    {
        $runtime = PHP_MAJOR_VERSION . '.' . PHP_MINOR_VERSION;

        if ($targetVersion !== null && \PhpParser\PhpVersion::getHostVersion()->older(
            \PhpParser\PhpVersion::fromString($targetVersion),
        )) {
            return ['status' => 'skipped', 'runtime' => $runtime, 'reason' => 'target_newer_than_runtime'];
        }
        $input = tempnam(sys_get_temp_dir(), 'php-ast-lint-');
        $output = tempnam(sys_get_temp_dir(), 'php-ast-lint-out-');

        if ($input === false || $output === false) {
            if (is_string($input)) {
                @unlink($input);
            }

            if (is_string($output)) {
                @unlink($output);
            }

            throw new EditException('PHP_LINT_FAILED: cannot create lint scratch files.');
        }

        try {
            if (file_put_contents($input, $source) === false) {
                throw new EditException('PHP_LINT_FAILED: cannot write lint input.');
            }
            $process = proc_open(
                [PHP_BINARY, '-n', '-l', $input],
                [
                    0 => ['file', $input, 'r'],
                    1 => ['file', $output, 'w'],
                    2 => ['file', $output, 'a'],
                ],
                $pipes,
            );

            if (!is_resource($process)) {
                throw new EditException('PHP_LINT_FAILED: cannot start the PHP interpreter.');
            }
            $exit = proc_close($process);

            if ($exit !== 0) {
                $message = str_replace($input, $path, trim((string) file_get_contents($output)));

                throw new EditException('PHP_LINT_FAILED: ' . substr($message, 0, 4000));
            }

            return ['status' => 'passed', 'runtime' => $runtime];
        } finally {
            @unlink($input);
            @unlink($output);
        }
    }
}
