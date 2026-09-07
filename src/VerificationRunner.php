<?php

declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use Netresearch\PhpAstEdit\Exception\EditException;

/** Prepare repository checks before writes, then execute their captured scope after formatting. */
final class VerificationRunner
{
    private const OUTPUT_CAP = 4000;

    /**
     * Capture configuration and exclusions while deleted files still exist.
     * @param list<FileTransaction> $transactions
     * @return list<array{cwd: string, scope: string, command: list<string>, members: list<array{file: FileTransaction, path: string}>}>
     */
    public function prepare(array $transactions): array
    {
        $groups = [];

        foreach ($transactions as $transaction) {
            if (!$transaction->changed) {
                continue;
            }
            $config = RepositoryConfig::discover($transaction->path);

            if ($config->verify === null || $config->path === null || $config->excludes($transaction->path)) {
                continue;
            }
            $root = realpath(dirname($config->path));

            if ($root === false) {
                throw new EditException('Cannot resolve verification root: ' . $config->path);
            }
            $groups[$root] ??= ['verify' => $config->verify, 'members' => []];
            $groups[$root]['members'][] = ['file' => $transaction, 'path' => $this->absolutePath($transaction->path)];
        }
        $prepared = [];

        foreach ($groups as $root => $group) {
            foreach ($group['verify'] as $entry) {
                $scope = array_is_list($entry) ? 'changed_files' : $entry['scope'];
                $command = array_is_list($entry) ? $entry : $entry['command'];
                $members = $scope === 'project' ? $group['members'] : array_values(
                    array_filter(
                        $group['members'],
                        static fn (array $member): bool => $member['file']->mode !== 'delete',
                    ),
                );

                if ($members === []) {
                    continue;
                }
                $prepared[] = ['cwd' => $root, 'scope' => $scope, 'command' => $command, 'members' => $members];
            }
        }

        return $prepared;
    }

    public function run(array $prepared): array
    {
        $results = [];

        foreach ($prepared as $check) {
            // Preserve the prepared scope even if a previous check removes an input.
            // The checker must see and report missing files instead of silently skipping them.
            $members = $check['members'];
            $command = $this->expandCommand($check['command'], array_column($members, 'path'));
            $result = [
                'id' => 'verify-' . (count($results) + 1),
                'cwd' => $check['cwd'],
                'scope' => $check['scope'],
                ...$this->captureCommand($command, $check['cwd']),
            ];
            $results[] = $result;

            foreach ($members as $member) {
                $member['file']->verify[] = $result;
            }
        }

        return $results;
    }

    /** @param list<string> $command
     * @param list<string> $paths
     * @return list<string>
     */
    private function expandCommand(array $command, array $paths): array
    {
        $expanded = [];

        foreach ($command as $argument) {
            if ($argument === RepositoryConfig::FILES_PLACEHOLDER) {
                array_push($expanded, ...$paths);
            } else {
                $expanded[] = $argument;
            }
        }

        return $expanded;
    }

    /** Preserve the original working-directory interpretation for files created later. */
    private function absolutePath(string $path): string
    {
        $resolved = realpath($path);

        if ($resolved !== false) {
            return $resolved;
        }

        if (str_starts_with($path, DIRECTORY_SEPARATOR) || preg_match('/^[A-Za-z]:[\\\\\\/]/', $path) === 1) {
            return $path;
        }
        $cwd = getcwd();

        if ($cwd === false) {
            throw new EditException('Cannot determine verification working directory.');
        }

        return $cwd . DIRECTORY_SEPARATOR . $path;
    }

    /** @param list<string> $command
     * @return array{command: string, ok: bool, output?: string}
     */
    private function captureCommand(array $command, string $root): array
    {
        $out = tempnam(sys_get_temp_dir(), 'php-ast-edit-verify-');
        $err = tempnam(sys_get_temp_dir(), 'php-ast-edit-verify-');

        if ($out === false || $err === false) {
            if (is_string($out)) {
                @unlink($out);
            }

            if (is_string($err)) {
                @unlink($err);
            }

            throw new EditException('Cannot create a temporary file for the check output.');
        }

        try {
            $process = proc_open($command, [1 => ['file', $out, 'w'], 2 => ['file', $err, 'w']], $pipes, $root);

            if (!is_resource($process)) {
                return [
                    'command' => implode(' ', $command),
                    'ok' => false,
                    'output' => 'could not be started',
                ];
            }
            $status = proc_close($process);
            $result = ['command' => implode(' ', $command), 'ok' => $status === 0];

            if ($status !== 0) {
                $said = trim(
                    (string) file_get_contents($out, false, null, 0, self::OUTPUT_CAP) . "\n" . (string) file_get_contents($err, false, null, 0, self::OUTPUT_CAP),
                );
                $result['output'] = substr($said, 0, self::OUTPUT_CAP);
            }

            return $result;
        } finally {
            @unlink($out);
            @unlink($err);
        }
    }
}
