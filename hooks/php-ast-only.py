#!/usr/bin/env python3
"""PreToolUse gate: PHP syntax may only be written through php-ast-edit.

The skill and AGENTS.md already state the rule, but an instruction cannot be
verified after the fact — an identical result gives no clue whether it came from an
AST transaction or from sed. Enforcement therefore has to happen *before* the write.

Wire it into ~/.claude/settings.json (or a project .claude/settings.json):

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
            "hooks": [
              {"type": "command", "command": "python3 /path/to/hooks/php-ast-only.py"}
            ]
          }
        ]
      }
    }

Set PHP_AST_ONLY_OFF=1 for the rare deliberate exception (a fixture that must contain
deliberately broken PHP, a generated file, a merge-conflict resolution).
"""

from __future__ import annotations

import json
import os
import shlex
import sys

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

PHP_SUFFIXES = (".php", ".phtml")

# Programs whose in-place flag rewrites a file in the shell.
IN_PLACE_PROGRAMS = {"sed", "gsed", "perl"}
REDIRECTS = {">", ">>"}

FOOTER = (
    "\n\nUse php-ast-edit instead:\n"
    "  php-ast-edit inspect --file <path> --line <n> --column <n>\n"
    "  php-ast-edit apply --input edits.json\n"
    'A new file is a file entry with "mode": "create"; a removal is "mode": "delete".\n'
    "Run `php-ast-edit contexts` for the parseAs and operation catalog.\n"
    "PHP_AST_ONLY_OFF=1 for a deliberate exception."
)


def deny(reason: str) -> int:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason + FOOTER,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


def php_paths(tool_input: dict) -> list[str]:
    candidates = []
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            candidates.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
                candidates.append(edit["file_path"])
    return [p for p in candidates if p.endswith(PHP_SUFFIXES)]


def is_in_place_flag(token: str) -> bool:
    if token == "--in-place":
        return True
    return token.startswith("-") and not token.startswith("--") and "i" in token


def text_mutation_of_php(command: str) -> str | None:
    """Name the text mutation this command performs on a PHP file, if any.

    Deliberately token-based rather than one large regular expression: a hook runs before
    every Bash call, so it must be linear in the length of the command line.
    """
    if not any(suffix in command for suffix in PHP_SUFFIXES):
        return None

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    program = None
    for token in tokens:
        if token in IN_PLACE_PROGRAMS:
            program = token
            continue
        if token == "apply_patch":
            return "apply_patch"
        if program is not None and is_in_place_flag(token):
            return f"{program} in place"
        if token in REDIRECTS or token == "tee":
            return "a shell redirect into a .php file"
        if token.startswith(">") and token.lstrip(">").endswith(PHP_SUFFIXES):
            return "a shell redirect into a .php file"

    return None


def main() -> int:
    if os.environ.get("PHP_AST_ONLY_OFF") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except ValueError:  # json.JSONDecodeError is a ValueError
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    if tool in FILE_TOOLS:
        targets = php_paths(tool_input)
        if targets:
            return deny(
                f"{tool} would write PHP syntax as text: {', '.join(sorted(set(targets)))}. "
                "PHP is written through its AST in this project, so that a change is a typed "
                "mutation that is re-parsed before it lands, not a text range that happens to "
                "compile."
            )
        return 0

    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or "php-ast-edit" in command:
            return 0
        label = text_mutation_of_php(command)
        if label is not None:
            return deny(
                f"This command mutates PHP as text ({label}). PHP is written through its "
                "AST in this project."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
