#!/usr/bin/env python3
"""Generate the one clarified cross-file follow-up fixture.

This module loads the original generator without changing its source or manifest.
It reuses the original PHP fixture, edit payload, and oracle body, changing only
the YAML support fixture and the task wording that explains its decoy role.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ORIGINAL_PATH = HERE / "tasks.py"
TASK_ID = "cross-file-rename-clarified"
YAML_PATH = "config/services.yaml"
YAML_SOURCE = "label: fetch\n"


def load_original() -> Any:
    spec = importlib.util.spec_from_file_location(
        "v080_original_tasks_for_clarified", ORIGINAL_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load original task generator: {ORIGINAL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def original_row_without_guard(original: Any) -> dict[str, Any]:
    """Recover the original task body while suppressing its generated support guard."""

    saved_support = original.SUPPORT
    original.SUPPORT = {**saved_support, "cross-file-rename": {}}
    try:
        return next(
            row for row in original.build_tasks() if row["id"] == "cross-file-rename"
        )
    finally:
        original.SUPPORT = saved_support


def clarified_row() -> dict[str, Any]:
    original = load_original()
    source_row = original_row_without_guard(original)
    core_files = {entry["path"]: entry["php"] for entry in source_row["files"]}
    support = {
        **original.SUPPORT["cross-file-rename"],
        YAML_PATH: YAML_SOURCE,
    }
    saved_support = original.SUPPORT
    original.SUPPORT = {**saved_support, "cross-file-rename": support}
    try:
        row = original.task(
            "cross-file-rename",
            source_row["prompt"]
            + " Preserve check.php, .php-ast-edit.json, composer.json, and "
            + "config/services.yaml byte-for-byte; the YAML label is metadata "
            + "and is not a method call site.",
            core_files,
            source_row["edits"],
            source_row["oracle"],
        )
    finally:
        original.SUPPORT = saved_support
    row["id"] = TASK_ID
    return row


_ORIGINAL_FOR_SUPPORT = load_original()
SUPPORT = {
    "cross-file-rename-clarified": {
        **_ORIGINAL_FOR_SUPPORT.SUPPORT["cross-file-rename"],
        YAML_PATH: YAML_SOURCE,
    }
}


def manifest() -> dict[str, Any]:
    return {"schema_version": 1, "tasks": [clarified_row()]}


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
    destination.write_text(data)


if __name__ == "__main__":
    main()
