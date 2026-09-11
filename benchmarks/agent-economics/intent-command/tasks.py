#!/usr/bin/env python3
"""Build the bounded intent-command economics manifest.

The two task bodies are existing fixtures.  This manifest only adds the same
protected check/configuration support to the one-file method rename so that both
tasks exercise the deployed transaction and verification path.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
CLARIFIED = ROOT / "benchmarks/agent-economics/v080-pilot/clarified_tasks.py"
BASE_TASKS = ROOT / "benchmarks/tasks.json"

METHOD_TASK = "method-and-literal"
CROSS_TASK = "cross-file-rename-clarified"
CHECK_CONFIG = '{"verify":[{"scope":"project","command":["php","check.php"]}]}\n'
CHECK_SOURCE = """<?php

declare(strict_types=1);

require __DIR__ . '/Product.php';

$product = new Product();
if ($product->run() !== [7, 'findByUid']
    || !method_exists($product, 'resolveByUid')
    || method_exists($product, 'findByUid')) {
    exit(1);
}

echo "OK: Product method rename\n";
"""
CHECK_PATH = "check.php"
CONFIG_PATH = ".php-ast-edit.json"
SUPPORT = {CHECK_PATH: CHECK_SOURCE, CONFIG_PATH: CHECK_CONFIG}


def load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("intent_clarified_tasks", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load task generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def support_guard(support: dict[str, str]) -> str:
    entries = ", ".join(
        f"'{path}'=>'{hashlib.sha256(source.encode('utf-8')).hexdigest()}'"
        for path, source in support.items()
    )
    return (
        f"$supportHashes = [{entries}]; "
        "foreach ($supportHashes as $supportFile => $supportHash) { "
        "if (!is_file($supportFile) || hash_file('sha256', $supportFile) !== $supportHash) { exit(1); } } "
    )


def method_row() -> dict[str, Any]:
    manifest = json.loads(BASE_TASKS.read_text())
    source = next(row for row in manifest["tasks"] if row["id"] == METHOD_TASK)
    row = copy.deepcopy(source)
    row["prompt"] = (
        row["prompt"]
        + " After the change, `php check.php` must pass."
        + " Preserve check.php and .php-ast-edit.json byte-for-byte."
        + " Do not start background processes. Leave no unrelated edits."
    )
    row["files"] += [
        {"path": path, "php": content} for path, content in SUPPORT.items()
    ]
    row["preserve_source"] = True
    row["oracle"] = support_guard(SUPPORT) + row["oracle"]
    return row


def cross_row() -> dict[str, Any]:
    module = load_module(CLARIFIED)
    return copy.deepcopy(module.manifest()["tasks"][0])


def manifest() -> dict[str, Any]:
    return {"schema_version": 1, "tasks": [method_row(), cross_row()]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--output", dest="output_option", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output_option is not None:
        parser.error("use either OUTPUT or --output, not both")
    data = json.dumps(manifest(), indent=2) + "\n"
    destination = args.output_option or args.output
    if destination is None:
        print(data, end="")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        data
    )  # NOSONAR(S8707): explicit operator-selected offline manifest output.


if __name__ == "__main__":
    main()
