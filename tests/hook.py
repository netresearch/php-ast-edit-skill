#!/usr/bin/env python3
"""The enforcement gate's behaviour table.

A gate is only worth what it lets through. Both directions matter here: a miss makes the
rule advisory, and a false positive makes the gate something people turn off. Each row is
a command shape an agent plausibly writes.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "php-ast-only.py"

# (tool, tool_input, expect_deny)
CASES: list[tuple[str, dict, bool]] = [
    # File-editing tools
    ("Edit", {"file_path": "src/A.php"}, True),
    ("Edit", {"file_path": "src/A.PHP"}, True),
    ("Edit", {"file_path": "tpl/a.phtml"}, True),
    ("Edit", {"file_path": "README.md"}, False),
    ("Edit", {"file_path": "src/A.php.tpl"}, False),
    ("Write", {"file_path": "/abs/src/A.php"}, True),
    ("MultiEdit", {"file_path": "src/A.php"}, True),
    ("NotebookEdit", {"notebook_path": "x.ipynb"}, False),
    ("Read", {"file_path": "src/A.php"}, False),
    # In-place stream editors, including path-qualified programs
    ("Bash", {"command": "sed -i s/x/y/ a.php"}, True),
    ("Bash", {"command": "sed -i.bak s/x/y/ a.php"}, True),
    ("Bash", {"command": "sed --in-place s/x/y/ a.php"}, True),
    ("Bash", {"command": "/usr/bin/sed -i s/x/y/ a.php"}, True),
    ("Bash", {"command": "perl -pi -e s/a/b/ x.php"}, True),
    ("Bash", {"command": "sed -i s/x/y/ README.md"}, False),
    ("Bash", {"command": "perl -e 'print' x.php"}, False),
    # A later command's flag must not incriminate an earlier read
    ("Bash", {"command": "sed -n 1p input.php | grep -i text"}, False),
    # Redirects, including descriptor and glued forms
    ("Bash", {"command": "cat x > a.php"}, True),
    ("Bash", {"command": "cat x >a.php"}, True),
    ("Bash", {"command": "printf x >> a.PHP"}, True),
    ("Bash", {"command": "cat x 1> a.php"}, True),
    ("Bash", {"command": "/bin/cat x > a.php"}, True),
    ("Bash", {"command": "cat <<'EOF' > a.php\nx\nEOF"}, True),
    ("Bash", {"command": "cat x 2> err.log"}, False),
    ("Bash", {"command": "echo hi > /tmp/a.txt"}, False),
    ("Bash", {"command": "cat a.php | tee b.php"}, True),
    ("Bash", {"command": "cat a.php | tee /dev/null"}, False),
    ("Bash", {"command": "apply_patch < p.diff a.php"}, True),
    # An AST invocation exempts its own command, not the rest of the line
    ("Bash", {"command": "php-ast-edit apply --input e.json"}, False),
    ("Bash", {"command": "php-ast-edit inspect --file a.php && echo done"}, False),
    (
        "Bash",
        {"command": "php-ast-edit inspect --file a.php; sed -i s/x/y/ a.php"},
        True,
    ),
    (
        "Bash",
        {"command": "php-ast-edit apply --input e.json && sed -i s/a/b/ c.php"},
        True,
    ),
    # Deleting a PHP file is part of the contract too: mode "delete" guards it with a hash.
    # Reads are none of the gate's business
    ("Bash", {"command": "grep -n foo a.php"}, False),
    ("Bash", {"command": "php -l a.php"}, False),
    ("Bash", {"command": "git diff a.php"}, False),
    ("Bash", {"command": "vim a.php"}, False),
    ("Bash", {"command": "cp a.php b.php"}, False),
    ("Bash", {"command": "rm a.php"}, True),
    ("Bash", {"command": "rm -rf build"}, False),
    ("Bash", {"command": "git rm a.php"}, True),
    # Known blind spot, asserted so a future change to it is a deliberate one: the PHP path
    # and the mutation live in different simple commands, which needs dataflow to connect.
    ("Bash", {"command": "for f in *.php; do sed -i s/a/b/ $f; done"}, False),
]


def denies(tool: str, tool_input: dict) -> bool:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"hook exited {result.returncode}: {result.stderr}")
    if not result.stdout.strip():
        return False
    payload = json.loads(result.stdout)
    return payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def footer() -> str:
    """The denial message, read from the gate rather than restated here."""
    specification = importlib.util.spec_from_file_location("php_ast_only", HOOK)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.FOOTER


def footer_claims(text: str) -> list[str]:
    """Every command shape the denial message offers, as a command line.

    A denial is read instead of the documentation, not alongside it, so a shape it names
    and the gate then refuses costs a round trip and teaches the caller that the message
    is unreliable. These are checked against the gate itself, so an edit to the message
    that names a denied shape fails here rather than in someone's session.
    """
    claims = []
    for line in text.splitlines():
        if line.strip().startswith("php-ast-edit "):
            claims.append(line.strip())
        if "Reading is not gated:" in line:
            named = line.split("Reading is not gated:", 1)[1]
            named = named.split(" run as they are")[0]
            for program in named.replace(" and ", ",").split(","):
                program = program.strip()
                if program:
                    claims.append(f"{program} a.php")
    return claims


def main() -> int:
    failures = []
    for claim in footer_claims(footer()):
        if denies("Bash", {"command": claim}):
            failures.append(f"the denial message offers a denied shape: {claim}")

    for tool, tool_input, expected in CASES:
        actual = denies(tool, tool_input)
        if actual != expected:
            failures.append(
                f"{tool} {tool_input!r}: expected {'deny' if expected else 'allow'}, "
                f"got {'deny' if actual else 'allow'}"
            )

    # A payload the gate cannot parse must not brick the session.
    for payload in ["", "not json", "{}", '{"tool_name": "Bash"}']:
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"hook exited {result.returncode} on payload {payload!r}")

    if failures:
        print("FAIL: " + str(len(failures)) + " hook case(s)", file=sys.stderr)
        for failure in failures:
            print("  - " + failure, file=sys.stderr)
        return 1

    print(
        f"OK: {len(CASES)} hook cases behave as documented, "
        f"and {len(footer_claims(footer()))} shape(s) the denial offers are allowed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
