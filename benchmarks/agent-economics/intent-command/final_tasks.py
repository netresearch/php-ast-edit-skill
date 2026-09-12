#!/usr/bin/env python3
"""Generate held-out method-rename fixtures for offline and paid evaluation."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import tasks as current_tasks

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
V080_TASKS = ROOT / "benchmarks/agent-economics/v080-pilot/tasks.py"
SINGLE_TASK = "ledger-method-rename"
CROSS_TASK = "transport-contract-rename"
CHECK_CONFIG = current_tasks.CHECK_CONFIG
CATALOG_PATH = "Catalog.php"
TRANSPORT_PATH = "src/Transport.php"


SINGLE_SOURCE = r"""<?php

declare(strict_types=1);

namespace Evidence\Solo;

final class Catalog
{
    public function findSku(): int
    {
        return 23;
    }

    public function report(): array
    {
        return [$this->findSku(), 'findSku', ['findSku' => 'literal']];
    }
}
"""

SINGLE_CHECK = r"""<?php

declare(strict_types=1);

require __DIR__ . '/Catalog.php';

$catalog = new Evidence\Solo\Catalog();
$source = file_get_contents(__DIR__ . '/Catalog.php');
if ($source === false
    || $catalog->report() !== [23, 'findSku', ['findSku' => 'literal']]
    || !method_exists($catalog, 'resolveSku')
    || method_exists($catalog, 'findSku')
    || substr_count($source, 'function resolveSku') !== 1
    || substr_count($source, 'function findSku') !== 0
    || !str_contains($source, "'findSku',")
    || !str_contains($source, "'findSku' =>")) {
    exit(1);
}

echo "OK: Catalog method rename\n";
"""

CROSS_FILES = {
    TRANSPORT_PATH: r"""<?php

declare(strict_types=1);

namespace Evidence\Network;

interface Transport
{
    public function deliver(): string;
}
""",
    "src/EmailTransport.php": r"""<?php

declare(strict_types=1);

namespace Evidence\Network;

final class EmailTransport implements Transport
{
    public function deliver(): string
    {
        return 'email';
    }
}
""",
    "src/QueueTransport.php": r"""<?php

declare(strict_types=1);

namespace Evidence\Network;

final class QueueTransport implements Transport
{
    public function deliver(): string
    {
        return 'queue';
    }
}
""",
    "src/Sender.php": r"""<?php

declare(strict_types=1);

namespace Evidence\Network;

final class Sender
{
    public function dispatch(Transport $transport): string
    {
        return $transport->deliver();
    }
}
""",
    "src/LegacyTransport.php": r"""<?php

declare(strict_types=1);

namespace Evidence\Network;

final class LegacyTransport
{
    public function deliver(): string
    {
        return 'legacy';
    }
}
""",
    "src/LegacySender.php": r"""<?php

declare(strict_types=1);

namespace Evidence\Network;

final class LegacySender
{
    public function dispatch(LegacyTransport $transport): string
    {
        return $transport->deliver();
    }
}
""",
}

CROSS_CHECK = r"""<?php

declare(strict_types=1);

require __DIR__ . '/src/Transport.php';
require __DIR__ . '/src/EmailTransport.php';
require __DIR__ . '/src/QueueTransport.php';
require __DIR__ . '/src/Sender.php';
require __DIR__ . '/src/LegacyTransport.php';
require __DIR__ . '/src/LegacySender.php';

use Evidence\Network\EmailTransport;
use Evidence\Network\LegacySender;
use Evidence\Network\LegacyTransport;
use Evidence\Network\QueueTransport;
use Evidence\Network\Sender;

$sender = new Sender();
$legacySender = new LegacySender();
$transport = file_get_contents(__DIR__ . '/src/Transport.php');
$senderSource = file_get_contents(__DIR__ . '/src/Sender.php');
$config = file_get_contents(__DIR__ . '/config/channels.yaml');
if ($transport === false
    || $senderSource === false
    || $config === false
    || $sender->dispatch(new EmailTransport()) !== 'email'
    || $sender->dispatch(new QueueTransport()) !== 'queue'
    || !method_exists(new EmailTransport(), 'transmit')
    || method_exists(new EmailTransport(), 'deliver')
    || !method_exists(new QueueTransport(), 'transmit')
    || method_exists(new QueueTransport(), 'deliver')
    || $legacySender->dispatch(new LegacyTransport()) !== 'legacy'
    || !str_contains($transport, 'function transmit')
    || str_contains($transport, 'function deliver')
    || !str_contains($senderSource, '->transmit()')
    || str_contains($senderSource, '->deliver()')
    || !str_contains($config, "label: deliver\n")) {
    exit(1);
}

echo "OK: interface method rename\n";
"""

SINGLE_ORACLE = r"""require 'Catalog.php'; $catalog = new Evidence\Solo\Catalog(); $source = file_get_contents('Catalog.php'); if ($source === false || $catalog->report() !== [23, 'findSku', ['findSku' => 'literal']] || !method_exists($catalog, 'resolveSku') || method_exists($catalog, 'findSku') || substr_count($source, 'function resolveSku') !== 1 || substr_count($source, 'function findSku') !== 0 || !str_contains($source, "'findSku',") || !str_contains($source, "'findSku' =>")) { exit(1); }"""

CROSS_ORACLE = r"""require 'src/Transport.php'; require 'src/EmailTransport.php'; require 'src/QueueTransport.php'; require 'src/Sender.php'; require 'src/LegacyTransport.php'; require 'src/LegacySender.php'; $sender = new Evidence\Network\Sender(); $legacySender = new Evidence\Network\LegacySender(); $transport = file_get_contents('src/Transport.php'); $senderSource = file_get_contents('src/Sender.php'); $config = file_get_contents('config/channels.yaml'); if ($transport === false || $senderSource === false || $config === false || $sender->dispatch(new Evidence\Network\EmailTransport()) !== 'email' || $sender->dispatch(new Evidence\Network\QueueTransport()) !== 'queue' || !method_exists(new Evidence\Network\EmailTransport(), 'transmit') || method_exists(new Evidence\Network\EmailTransport(), 'deliver') || !method_exists(new Evidence\Network\QueueTransport(), 'transmit') || method_exists(new Evidence\Network\QueueTransport(), 'deliver') || $legacySender->dispatch(new Evidence\Network\LegacyTransport()) !== 'legacy' || !str_contains($transport, 'function transmit') || str_contains($transport, 'function deliver') || !str_contains($senderSource, '->transmit()') || str_contains($senderSource, '->deliver()') || !str_contains($config, "label: deliver\n")) { exit(1); }"""

SUPPORT = {
    SINGLE_TASK: {
        ".php-ast-edit.json": CHECK_CONFIG,
        "check.php": SINGLE_CHECK,
    },
    CROSS_TASK: {
        ".php-ast-edit.json": CHECK_CONFIG,
        "check.php": CROSS_CHECK,
        "config/channels.yaml": "label: deliver\n",
    },
}


def load_v080() -> Any:
    spec = importlib.util.spec_from_file_location("final_v080_tasks", V080_TASKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load task helper: {V080_TASKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _task_helper(
    identifier: str,
    prompt: str,
    files: dict[str, str],
    edits: list[dict[str, Any]],
    oracle: str,
) -> dict[str, Any]:
    helper = load_v080()
    helper.SUPPORT = {**helper.SUPPORT, identifier: SUPPORT[identifier]}
    return helper.task(identifier, prompt, files, edits, oracle)


def _single_row() -> dict[str, Any]:
    row = _task_helper(
        SINGLE_TASK,
        "Rename Catalog::findSku() to resolveSku(), including its internal call. Preserve the unrelated findSku data labels. Make sure `php check.php` passes. Do not start background processes. Leave no unrelated edits.",
        {CATALOG_PATH: SINGLE_SOURCE},
        [
            {
                "path": CATALOG_PATH,
                "edits": [
                    {
                        "target": {"select": "method:Evidence\\Solo\\Catalog::findSku"},
                        "operation": "rename_method",
                        "to": "resolveSku",
                    }
                ],
            }
        ],
        SINGLE_ORACLE,
    )
    row["intent"] = {
        "method": "Evidence\\Solo\\Catalog::findSku",
        "file": CATALOG_PATH,
        "to": "resolveSku",
        "path": ".",
    }
    return row


def _cross_row() -> dict[str, Any]:
    row = _task_helper(
        CROSS_TASK,
        "Rename the deliver() method declared by Transport and implemented by EmailTransport and QueueTransport to transmit(), updating the typed Sender caller. Preserve LegacyTransport::deliver(), its typed LegacySender caller, and the config label. Make sure `php check.php` passes. Do not start background processes. Leave no unrelated edits.",
        CROSS_FILES,
        [
            {
                "path": TRANSPORT_PATH,
                "edits": [
                    {
                        "target": {
                            "select": "method:Evidence\\Network\\Transport::deliver"
                        },
                        "operation": "rename_method",
                        "to": "transmit",
                    }
                ],
            }
        ],
        CROSS_ORACLE,
    )
    row["intent"] = {
        "method": "Evidence\\Network\\Transport::deliver",
        "file": TRANSPORT_PATH,
        "to": "transmit",
        "path": ".",
    }
    return row


def manifest() -> dict[str, Any]:
    return {"schema_version": 1, "tasks": [_single_row(), _cross_row()]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--output", dest="output_option", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output_option is not None:
        parser.error("use either OUTPUT or --output, not both")
    destination = args.output_option or args.output
    data = json.dumps(manifest(), indent=2) + "\n"
    if destination is None:
        print(data, end="")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)  # NOSONAR(S8707)
    destination.write_text(data)


if __name__ == "__main__":
    main()
