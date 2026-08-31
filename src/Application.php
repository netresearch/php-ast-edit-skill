<?php
declare(strict_types=1);

namespace Netresearch\PhpAstEdit;

use JsonException;
use Netresearch\PhpAstEdit\Exception\EditException;
use PhpParser\Error as ParserError;
use PhpParser\ParserFactory;

final class Application
{
    public function run(array $argv): int
    {
        try {
            $command = $argv[1] ?? 'help';
            $options = $this->options(array_slice($argv, 2));

            return match ($command) {
                'inspect' => $this->inspect($options),
                'apply' => $this->apply($options),
                'validate' => $this->validate($options),
                'contexts' => $this->contexts(),
                'help', '--help', '-h' => $this->help(),
                default => throw new EditException('Unknown command: '.$command),
            };
        } catch (EditException|ParserError|JsonException $exception) {
            fwrite(STDERR, json_encode([
                'ok' => false,
                'error' => $exception->getMessage(),
                'class' => $exception::class,
            ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE)."\n");
            return 2;
        } catch (\Throwable $exception) {
            fwrite(STDERR, json_encode([
                'ok' => false,
                'error' => $exception->getMessage(),
                'class' => $exception::class,
            ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE)."\n");
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
        $input = $options['input'] ?? '-';
        if (!is_string($input)) {
            throw new EditException('--input requires a path or -.');
        }
        $json = $input === '-' ? stream_get_contents(STDIN) : file_get_contents($input);
        if ($json === false || trim($json) === '') {
            throw new EditException('No apply JSON received.');
        }
        $document = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($document)) {
            throw new EditException('Apply input must decode to a JSON object.');
        }
        $editor = new Editor();
        $this->json($editor->apply($document, isset($options['dry-run'])));
        return 0;
    }

    private function contexts(): int
    {
        $parser = (new ParserFactory())->createForHostVersion();
        $this->json([
            'parseAs' => array_merge((new ContextParser($parser))->contexts(), ['stmts', 'file']),
            'operations' => [
                'primitives' => ['replace_node', 'delete_node', 'insert_into', 'replace_child', 'delete_child', 'move_node'],
                'comments' => ['set_doc_comment', 'remove_doc_comment'],
                'convenience' => [
                    'set_name', 'set_string', 'replace_expression', 'replace_statement',
                    'insert_before', 'insert_after', 'delete',
                    'replace_argument', 'add_argument', 'remove_argument',
                    'add_member', 'add_parameter', 'add_attribute',
                    'set_return_type', 'set_type', 'set_visibility',
                    'add_implements', 'set_extends',
                ],
            ],
            'fileModes' => ['edit', 'create', 'delete'],
        ]);
        return 0;
    }

    private function help(): int
    {
        echo <<<'TEXT'
php-ast-edit - AST-native PHP writer for coding agents

Every creation, modification, replacement, deletion and movement of PHP syntax goes
through this tool. PHP text is accepted as construction input only: it is parsed,
mutated as an AST, and written back exclusively from that AST.

Usage:
  php-ast-edit inspect --file FILE (--offset N | --line N --column N) [--php-version 8.4]
  php-ast-edit validate --file FILE [--php-version 8.4]
  php-ast-edit contexts
  php-ast-edit apply [--input FILE|-] [--dry-run]

Coordinates:
  offset   zero-based byte offset in the original source
  line     one-based line
  column   one-based byte column
  ref      structural AST path from inspect, e.g. stmts[1].stmts[0].params[0]

Apply JSON:
  {
    "files": [{
      "path": "src/Foo.php",
      "mode": "edit",            // edit (default) | create | delete
      "sha256": "hash from inspect",
      "phpVersion": "8.4",
      "edits": [{
        "target": {"ref": "stmts[0].stmts[0].name"},
        "expect": {"name": "oldMethod"},
        "operation": "set_name",
        "value": "newMethod"
      }]
    }]
  }

Primitives:
  replace_node, delete_node, insert_into, replace_child, delete_child, move_node

Convenience:
  set_name, set_string, replace_expression, replace_statement,
  insert_before, insert_after, delete,
  replace_argument, add_argument, remove_argument,
  add_member, add_parameter, add_attribute,
  set_return_type, set_type, set_visibility, add_implements, set_extends,
  set_doc_comment, remove_doc_comment

Run `php-ast-edit contexts` for the full parseAs and operation catalog.

PHP snippets are syntax, not formatting. Compact one-line snippets are preferred;
the AST is pretty-printed canonically after the transaction.
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
                throw new EditException('Unexpected argument: '.$arg);
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
                throw new EditException('--'.$arg.' requires a value.');
            }
            $options[$arg] = $args[++$i];
        }
        return $options;
    }

    private function integerOption(array $options, string $key): int
    {
        if (!isset($options[$key]) || filter_var($options[$key], FILTER_VALIDATE_INT) === false) {
            throw new EditException('--'.$key.' requires an integer.');
        }
        return (int) $options[$key];
    }

    private function requiredOption(array $options, string $key): string
    {
        $value = $options[$key] ?? null;
        if (!is_string($value) || $value === '') {
            throw new EditException('--'.$key.' is required.');
        }
        return $value;
    }

    private function json(array $data): void
    {
        echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)."\n";
    }
}
