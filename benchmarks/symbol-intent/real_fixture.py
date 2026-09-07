#!/usr/bin/env python3
"""Pinned public-source extraction, behavior checker, and separate hidden oracle.

Only disposable exports contain PHP. The candidate-facing ``check`` command never
consults the expected edit inventory. See REAL_FIXTURE.md for scope and limits.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE_URL = "https://github.com/netresearch/t3x-nr-llm"
SOURCE_COMMIT = "b505c936935b99baa3088ce62ad222d2ba61cee0"
PHPUNIT_VERSION = "12.5.31"
PHPUNIT_SHA256 = "194fcb6621866b542f1304e0da8dc7abcb15d6f9d1851893aec40896bcf5bb44"
TEST_COUNT = 17
DECLARATION = "Classes/Service/Tool/SchemaPropertyClassifier.php"
CALLER = "Classes/Service/Tool/SchemaInputCoercer.php"
DIRECT_TEST = "Tests/Unit/Service/Tool/SchemaPropertyClassifierTest.php"

# SHA-256 of exact public git blobs, followed by the independently specified
# result of changing ONLY the three identifier tokens named in REPLACEMENTS.
FILE_HASHES = {
    DECLARATION: (
        "ed3f0b8006c225ff04633b578e3845a4e1161c2a3b10cc3d16be5ae6ba5eca23",
        "e1d76a58cd6ab67c3f41e5cb61e692a80586dc9e3fd38e55480fb1cc92f35c93",
    ),
    CALLER: (
        "f11346b904ecca5d0f89ece258db52e265c38d47e6d55138e254ed20ecf6cadf",
        "21f11064994430495659b5c411ee79eac03bc7f5464c2c93a3745a8acc8948a3",
    ),
    "Classes/Service/Schema/JsonSchemaValidator.php": (
        "f3316827c1a321cfcf09876ddea7c0739777d2fe780b7d2e4dfc6c811f6bc25a",
        "f3316827c1a321cfcf09876ddea7c0739777d2fe780b7d2e4dfc6c811f6bc25a",
    ),
    "Classes/Service/Schema/StrictSchemaSubset.php": (
        "1d7d0ddd7fe1524b63862aa36e5b3a7688d41aa9da4601d414036d21d29a6407",
        "1d7d0ddd7fe1524b63862aa36e5b3a7688d41aa9da4601d414036d21d29a6407",
    ),
    DIRECT_TEST: (
        "3ee903ed68d70c35070ceece9e636bf132c760be8185139fb54c5be29ba7c431",
        "d4c01ce064e729f6e4457038e11b4eb0a821a7b289f87ddbf2f34eaf836d0e7a",
    ),
    "Tests/Unit/Service/Tool/SchemaInputCoercerTest.php": (
        "bd74a73c9f469c84a0ca9da41b7333b4099d949bcdc544c50bc3980713394a72",
        "bd74a73c9f469c84a0ca9da41b7333b4099d949bcdc544c50bc3980713394a72",
    ),
    "LICENSE": (
        "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6",
        "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6",
    ),
}
REPLACEMENTS = {
    DECLARATION: (b"function classify(", b"function controlType("),
    CALLER: (b"->classify($propSchema)", b"->controlType($propSchema)"),
    DIRECT_TEST: (b"->classify($propSchema)", b"->controlType($propSchema)"),
}


class FixtureError(ValueError):
    """The fixture or checker preconditions were not satisfied."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def provenance():
    """Deterministic source-only provenance; no answer or local machine paths."""
    return {
        "schema": 1,
        "repository": SOURCE_URL,
        "commit": SOURCE_COMMIT,
        "license": "GPL-2.0-or-later",
        "scope": "Extracted schema classifier and coercer with original unit tests",
        "excluded_production_caller": "Classes/Service/Agent/Inbox/WaitingRunViewFactory.php",
        "files": {name: hashes[0] for name, hashes in sorted(FILE_HASHES.items())},
    }


def expected_inventory(*, renamed=True):
    """Controller-only exact byte oracle, independent of mutable fixture metadata."""
    return {
        **{name: hashes[int(renamed)] for name, hashes in FILE_HASHES.items()},
        "PROVENANCE.json": digest(encode(provenance())),
    }


def _reject_symlinks(directory, names):
    for name in names:
        path = directory / name
        if path.is_symlink():
            raise FixtureError("Fixture symlinks are unsupported: " + str(path))


def snapshot(root):
    """Hash all regular fixture files, excluding only the root git metadata."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise FixtureError("Fixture root must be a regular directory")
    result = {}

    def unreadable(error):
        raise error

    for directory, names, files in os.walk(root, followlinks=False, onerror=unreadable):
        current = Path(directory)
        if current == root:
            names[:] = [name for name in names if name != ".git"]
            files = [name for name in files if name != ".git"]
        _reject_symlinks(current, names + files)
        for name in files:
            path = current / name
            if not path.is_file():
                raise FixtureError("Fixture contains a non-regular file: " + str(path))
            result[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return dict(sorted(result.items()))


def export(root, source_repo):
    """Export and hash-verify exact git objects without touching the source tree."""
    root, source_repo = Path(root), Path(source_repo).resolve()
    if root.is_symlink() or root.resolve().is_relative_to(source_repo):
        raise FixtureError("Export must be outside the source repository")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FixtureError("Export destination must be absent or empty")
    blobs = {}
    for name, (expected, _) in FILE_HASHES.items():
        process = subprocess.run(
            ["git", "-C", str(source_repo), "show", SOURCE_COMMIT + ":" + name],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if process.returncode != 0 or digest(process.stdout) != expected:
            raise FixtureError("Pinned source object missing or hash mismatch: " + name)
        blobs[name] = process.stdout
    # All source hashes are checked before writing the first output byte.
    # Explicit operator-selected export destination, not a restricted-root service.
    root.mkdir(parents=True, exist_ok=True)  # NOSONAR(S8707)
    for name, data in blobs.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    result = provenance()
    (root / "PROVENANCE.json").write_bytes(encode(result))
    return result


def task(root):
    """Controller task metadata; keep the expected edit inventory out of prompts."""
    return {
        "file": str(Path(root).resolve() / DECLARATION),
        "select": "method:SchemaPropertyClassifier::classify",
        "to": "controlType",
        "expected_changed_files": list(REPLACEMENTS),
        "expected_edit_count": 3,
        "source_commit": SOURCE_COMMIT,
    }


def oracle(root, *, renamed=True, allowed_extras=None):
    expected, actual = dict(expected_inventory(renamed=renamed)), snapshot(root)
    for name, sha256 in (allowed_extras or {}).items():
        path = Path(name)
        if (
            name in expected
            or path.is_absolute()
            or ".." in path.parts
            or ".git" in path.parts
            or path.as_posix() != name
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
        ):
            raise FixtureError("Invalid or overlapping frozen extra file: " + name)
        expected[name] = sha256
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    mismatched = sorted(
        name
        for name in expected.keys() & actual.keys()
        if expected[name] != actual[name]
    )
    return {
        "ok": not (missing or unexpected or mismatched),
        "state": "renamed" if renamed else "baseline",
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }


def _bootstrap(root):
    # This PHP is generated only in the disposable external checker directory.
    literal = "'" + str(root).replace("\\", "\\\\").replace("'", "\\'") + "'"
    prefix = "<?php\ndeclare(strict_types=1);\n$fixtureRoot = " + literal + ";\n"
    return (
        prefix
        + r"""spl_autoload_register(static function (string $class) use ($fixtureRoot): void {
    $prefix = 'Netresearch\\NrLlm\\';
    if (!str_starts_with($class, $prefix)) {
        return;
    }
    $relative = substr($class, strlen($prefix));
    $base = str_starts_with($relative, 'Tests\\') ? '/' : '/Classes/';
    $file = $fixtureRoot . $base . str_replace('\\', '/', $relative) . '.php';
    if (is_file($file)) {
        require $file;
    }
});
"""
    )


def _junit(path):
    keys = ("tests", "assertions", "errors", "failures", "skipped")
    unknown = dict.fromkeys(keys)
    try:
        document = ET.parse(path).getroot()
        suites = [
            node for node in document.iter("testsuite") if not node.findall("testsuite")
        ]
        counts = [{key: int(suite.attrib[key]) for key in keys} for suite in suites]
        if not counts or any(value < 0 for count in counts for value in count.values()):
            return unknown
        return {key: sum(count[key] for count in counts) for key in keys}
    except (OSError, ET.ParseError, KeyError, ValueError):
        return unknown


def check(root, phpunit, *, receipt_dir=None, php="php", timeout=60):
    """Run only the original behavior suite; never call the hidden rename oracle.

    Both baseline and correctly renamed code should pass. Full observations are
    returned to the controller; CLI stdout contains the concise summary only.
    """
    root, phpunit = Path(root).resolve(), Path(phpunit).resolve()
    if digest(phpunit.read_bytes()) != PHPUNIT_SHA256:
        raise FixtureError("PHPUnit checksum does not match pinned " + PHPUNIT_VERSION)
    if receipt_dir is not None:
        receipt_dir = Path(receipt_dir).resolve()
        if receipt_dir.is_relative_to(root):
            raise FixtureError("Receipt directory must be outside the fixture")
        receipt_dir.mkdir(parents=True, exist_ok=True)
    before = snapshot(root)
    started_at_ns, started = time.time_ns(), time.perf_counter_ns()
    with tempfile.TemporaryDirectory(prefix="php-ast-real-check-") as directory:
        state = Path(directory)
        bootstrap, junit = state / "bootstrap.php", state / "junit.xml"
        bootstrap.write_text(_bootstrap(root))
        argv = [
            php,
            "-d",
            "auto_prepend_file=",
            "-d",
            "auto_append_file=",
            str(phpunit),
            "--no-configuration",
            "--bootstrap",
            str(bootstrap),
            "--do-not-cache-result",
            "--cache-directory",
            str(state / "cache"),
            "--fail-on-warning",
            "--fail-on-risky",
            "--fail-on-skipped",
            "--fail-on-incomplete",
            "--fail-on-empty-test-suite",
            "--colors=never",
            "--log-junit",
            str(junit),
            str(root / "Tests/Unit/Service/Tool"),
        ]
        env = os.environ.copy()
        # Never inherit a project-selected Composer autoloader from another run.
        for name in ("PHPUNIT_COMPOSER_INSTALL", "PHP_AST_INTENT_AUTOLOAD"):
            env.pop(name, None)
        timed_out = False
        try:
            # Operator-selected PHP executes the digest-pinned checker; see TRUST.md.
            process = subprocess.run(  # NOSONAR(S8701)
                argv,
                cwd=state,
                env=env,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            returncode, stdout, stderr = (
                process.returncode,
                process.stdout,
                process.stderr,
            )
        except subprocess.TimeoutExpired as error:
            timed_out = True
            returncode, stdout, stderr = None, error.stdout or b"", error.stderr or b""
        counts = _junit(junit)
    after = snapshot(root)
    result = {
        "ok": returncode == 0 and counts["tests"] == TEST_COUNT and before == after,
        "tests": counts["tests"],
        "assertions": counts["assertions"],
        "returncode": returncode,
        "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 3),
        "started_at_ns": started_at_ns,
        "finished_at_ns": time.time_ns(),
        "timed_out": timed_out,
        "fixture_unchanged": before == after,
        "before": before,
        "after": after,
        "phpunit_version": PHPUNIT_VERSION,
        "phpunit_sha256": PHPUNIT_SHA256,
        "command": argv,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "junit": counts,
    }
    if receipt_dir is not None:
        receipt = receipt_dir / (str(uuid.uuid4()) + ".json")
        result["receipt"] = str(receipt)
        with receipt.open("xb") as stream:
            stream.write(encode(result))
    return result


def command(root, phpunit, *, receipt_dir=None, php="php"):
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "check",
        str(Path(root).resolve()),
        "--phpunit",
        str(Path(phpunit).resolve()),
        "--php",
        php,
    ]
    if receipt_dir is not None:
        argv += ["--receipt-dir", str(Path(receipt_dir).resolve())]
    return argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    exporting = commands.add_parser("export")
    exporting.add_argument("root", type=Path)
    exporting.add_argument("--source-repo", required=True, type=Path)
    checking = commands.add_parser("check")
    checking.add_argument("root", type=Path)
    checking.add_argument("--phpunit", required=True, type=Path)
    checking.add_argument("--receipt-dir", type=Path)
    checking.add_argument("--php", default="php")
    checking.add_argument("--timeout", type=float, default=60)
    checking_oracle = commands.add_parser("oracle")
    checking_oracle.add_argument("root", type=Path)
    checking_oracle.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "export":
            result = {"ok": True, "provenance": export(args.root, args.source_repo)}
        elif args.action == "oracle":
            result = oracle(args.root, renamed=not args.baseline)
        else:
            observation = check(
                args.root,
                args.phpunit,
                receipt_dir=args.receipt_dir,
                php=args.php,
                timeout=args.timeout,
            )
            result = {
                key: observation[key]
                for key in ("ok", "tests", "assertions", "returncode", "duration_ms")
            }
            if not observation["ok"]:
                diagnostics = observation["stdout"] + "\n" + observation["stderr"]
                if not observation["fixture_unchanged"]:
                    diagnostics += "\nFixture changed during test execution."
                result["diagnostics"] = diagnostics[-4000:]
            if "receipt" in observation:
                result["receipt"] = observation["receipt"]
    except (FixtureError, OSError, subprocess.SubprocessError) as error:
        result = {"ok": False, "error": str(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
