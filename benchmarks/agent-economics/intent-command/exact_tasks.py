#!/usr/bin/env python3
"""Attach identical operator-selected rename targets to existing intent tasks."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import tasks


def manifest():
    data = copy.deepcopy(tasks.manifest())
    targets = {
        tasks.METHOD_TASK: ("Product::findByUid", "Product.php", "resolveByUid"),
        tasks.CROSS_TASK: (
            "Pilot\\CrossFile\\Contract::fetch",
            "src/Contract.php",
            "load",
        ),
    }
    for row in data["tasks"]:
        method, file, destination = targets[row["id"]]
        row["intent"] = {"method": method, "file": file, "to": destination, "path": "."}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Explicit caller-selected destination, as in the base manifest generator.
    args.output.write_text(json.dumps(manifest(), indent=2) + "\n")  # NOSONAR(S8707)


if __name__ == "__main__":
    main()
