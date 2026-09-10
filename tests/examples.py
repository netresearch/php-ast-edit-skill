#!/usr/bin/env python3
"""Run the apply documents printed in README.md and SKILL.md, exactly as printed.

A documented example is a claim twice over: that it works, and that it shows what the
prose around it recommends. Both halves drifted unnoticed — the skill told agents to use
`report: "agent"` twenty lines above an example that used `compact`, and the README never
learned the mode existed. Nothing failed, because nothing ran them.
"""

import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "bin/php-ast-edit"
SKILL = ROOT / "skills/php-structured-edit/SKILL.md"

# Each entry: the document, and the file it needs to exist first.
SOURCES = [
    (
        ROOT / "README.md",
        r"Send this JSON to `php-ast-edit apply --input edits\.json`:\n\n```json\n(.*?)\n```",
        {"src/Clock.php": "<?php\nnamespace App;\nfinal class Clock {}\n"},
    ),
    (
        SKILL,
        r"Minimal transaction:\n\n```json\n(.*?)\n```",
        {"src/Registry.php": "<?php\nfinal class Registry {}\n"},
    ),
]

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
    return condition


def documents():
    for path, pattern, fixtures in SOURCES:
        text = path.read_text()
        match = re.search(pattern, text, re.DOTALL)
        if not check(match is not None, f"{path.name}: no apply document found"):
            continue
        try:
            document = json.loads(match.group(1))
        except ValueError as error:
            failures.append(f"{path.name}: the example is not valid JSON — {error}")
            continue
        yield path, document, fixtures


def conditional_mode():
    """The mode SKILL.md names, and the condition it names it for.

    The skill no longer prescribes a default. It points at `agent` for one case — a
    declared check whose verdict matters — because recommending it generally was measured
    and lost (benchmarks/agent-economics/results/2026-09-10-agent-report). An example that
    reaches for it outside that case contradicts the guidance again, in the direction the
    measurement already ruled out.
    """
    match = re.search(
        r'Use `"report":"([a-z]+)"` when a declared check', SKILL.read_text()
    )
    if not check(
        match is not None,
        'SKILL.md no longer names the case report:"agent" is for',
    ):
        return None
    return match.group(1)


def main():
    if not ENGINE.is_file():
        print("SKIP: engine not built.")
        return 0
    conditional = conditional_mode()

    for path, document, fixtures in documents():
        # Neither fixture declares a check, so neither is the case the skill names. An
        # example is what gets copied; the condition in the prose is not.
        if conditional is not None and document.get("report") == conditional:
            check(
                False,
                f"{path.name}: the example asks for report {conditional!r} on a fixture "
                "that declares no checks — the case SKILL.md does not name it for",
            )

        with tempfile.TemporaryDirectory(prefix="php-ast-examples-") as directory:
            root = pathlib.Path(directory)
            for relative, source in fixtures.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            payload = json.loads(json.dumps(document))
            for entry in payload["files"]:
                entry["path"] = str(root / entry["path"])

            run = subprocess.run(
                [str(ENGINE), "apply", "--input", "-"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
            )
            if not check(
                run.returncode == 0,
                f"{path.name}: the example exits {run.returncode} — "
                f"{(run.stdout or run.stderr).strip()[:200]}",
            ):
                continue
            report = json.loads(run.stdout)
            applied = sum(file["editsApplied"] for file in report["files"])
            check(
                applied == sum(len(f["edits"]) for f in payload["files"]),
                f"{path.name}: the example applied {applied} of its edits",
            )
            check(
                all(file["changed"] for file in report["files"]),
                f"{path.name}: the example changed nothing",
            )
            print(
                f"ok   {path.name}: the documented example runs and applies {applied} edit(s)"
            )

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print("OK: the documented apply examples run and stay inside the skill's guidance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
