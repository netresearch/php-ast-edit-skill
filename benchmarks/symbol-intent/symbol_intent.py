#!/usr/bin/env python3
"""Experimental method-rename planning for trusted, self-contained PHP workspaces.

Phpactor resolves references. A batched AST helper validates every returned name and
converts it to guarded engine operations. No text-edit fallback or completeness claim.
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lsp import PHAR_SHA256, RELEASE, IntentError, rename, require

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1]
PLAN_ID = re.compile(r"[0-9a-f]{64}")
JSON_SUFFIX = ".json"
LIMIT_WARNING = "Experimental PHP-only method rename. Phpactor may omit unresolved references; run relevant behavior checks."


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def snapshot(root):
    inventory = {}
    total = 0

    def unreadable(error):
        raise error

    # Explicit local workspace root; no remote file-existence service. See TRUST.md.
    for directory, names, files in os.walk(  # NOSONAR(S6549)
        root, followlinks=False, onerror=unreadable
    ):
        current = Path(directory)
        if current == root and ".git" in names:
            names.remove(".git")
        for name in sorted(names + files):
            path = current / name
            require(
                not path.is_symlink(), "Symlinks are unsupported in the analysis scope"
            )
        for name in sorted(files):
            path = current / name
            if path == root / ".git":
                continue
            require(path.is_file(), "Only regular workspace files are supported")
            total += path.stat().st_size
            require(
                len(inventory) < 2000 and total <= 64_000_000,
                "Experimental workspace limit exceeded",
            )
            data = path.read_bytes()
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".php":
                require(
                    len(data) < 1_000_000, "PHP source exceeds resolver indexing limit"
                )
                data.decode("utf-8")
            require(
                name not in (".phpactor.json", ".phpactor.yml", ".phpactor.yaml"),
                "Custom Phpactor configuration is outside this experimental scope",
            )
            inventory[relative] = digest(data)
    require(
        any(name.endswith(".php") for name in inventory), "Workspace has no PHP files"
    )
    return dict(sorted(inventory.items()))


def runtime_identity():
    files = [
        HERE / "ast.php",
        HERE / "lsp.py",
        HERE / "symbol_intent.py",
        RUNTIME / "bin/php-ast-edit",
        RUNTIME / "composer.json",
    ]
    files += sorted((RUNTIME / "src").rglob("*.php"))
    files += sorted((RUNTIME / "vendor").rglob("*.php"))
    return digest(
        encode({str(p.relative_to(RUNTIME)): digest(p.read_bytes()) for p in files})
    )


def invoke(argv, request, cwd):
    env = os.environ.copy()
    env["PHP_AST_INTENT_AUTOLOAD"] = str(RUNTIME / "vendor/autoload.php")
    process = subprocess.run(
        argv,
        input=encode(request),
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=90,
        check=False,
    )
    data = json.loads(process.stdout or process.stderr)
    require(isinstance(data, dict), "Tool returned no object report")
    return process.returncode, data


def ast(request, root):
    status, result = invoke(
        ["php", str(HERE / "ast.php")], {"root": str(root), **request}, root
    )
    require(status == 0, "AST analysis refused: " + str(result.get("error")))
    return result


def byte_to_position(source, offset):
    prefix = source[:offset].decode("utf-8")
    line = prefix.count("\n")
    tail = prefix.rsplit("\n", 1)[-1]
    return {"line": line, "character": len(tail.encode("utf-16-le")) // 2}


def position_to_byte(source, position):
    require(
        isinstance(position, dict) and set(position) == {"line", "character"},
        "Invalid LSP position",
    )
    line, character = position["line"], position["character"]
    require(
        type(line) is int and type(character) is int and line >= 0 and character >= 0,
        "Invalid LSP position values",
    )
    lines = source.split(b"\n")
    require(line < len(lines), "LSP line is outside the source")
    content = lines[line].removesuffix(b"\r").decode("utf-8").encode("utf-16-le")
    require(character * 2 <= len(content), "LSP character is outside the line")
    try:
        prefix = content[: character * 2].decode("utf-16-le").encode("utf-8")
    except UnicodeError as error:
        raise IntentError("LSP position splits a Unicode code point") from error
    return sum(len(part) + 1 for part in lines[:line]) + len(prefix)


def validated_ranges(edits, source, anchor, is_anchor, new_name):
    anchor_found = False
    require(isinstance(edits, list) and edits, "Empty edit list")
    ranges = []
    for edit in edits:
        require(
            isinstance(edit, dict)
            and set(edit) == {"range", "newText"}
            and edit["newText"] == new_name,
            "Unsupported rename replacement",
        )
        interval = edit["range"]
        require(
            isinstance(interval, dict) and set(interval) == {"start", "end"},
            "Invalid rename range",
        )
        start = position_to_byte(source, interval["start"])
        end = position_to_byte(source, interval["end"])
        require(start < end, "Empty or reversed rename range")
        ranges.append({"start": start, "end": end})
        if is_anchor and start == anchor["start"] and end == anchor["end"]:
            anchor_found = True
    ranges.sort(key=lambda item: item["start"])
    require(
        all(first["end"] <= second["start"] for first, second in pairwise(ranges)),
        "Overlapping rename ranges",
    )
    return ranges, anchor_found


def translate(workspace_edit, root, inventory, anchor_path, anchor, new_name):
    require(
        isinstance(workspace_edit, dict) and set(workspace_edit) == {"documentChanges"},
        "Unsupported or empty WorkspaceEdit",
    )
    documents = workspace_edit["documentChanges"]
    require(isinstance(documents, list) and documents, "Rename returned no edits")
    files = []
    expected_inventory = dict(inventory)
    seen = set()
    anchor_found = False
    for document in documents:
        require(
            isinstance(document, dict) and set(document) == {"textDocument", "edits"},
            "Resource operations and annotations are unsupported",
        )
        descriptor = document["textDocument"]
        require(
            isinstance(descriptor, dict) and set(descriptor) == {"uri", "version"},
            "Invalid text document descriptor",
        )
        require(
            descriptor["version"] is None
            or type(descriptor["version"]) is int
            and descriptor["version"] == 0,
            "Unexpected document version",
        )
        require(isinstance(descriptor["uri"], str), "Invalid document URI")
        uri = urlsplit(descriptor["uri"])
        require(
            uri.scheme == "file"
            and not uri.netloc
            and not uri.query
            and not uri.fragment,
            "Only local file URIs are supported",
        )
        path = Path(unquote(uri.path)).resolve(strict=True)
        require(path.is_relative_to(root), "LSP edit is outside the workspace")
        relative = path.relative_to(root).as_posix()
        require(
            relative in inventory
            and relative.endswith(".php")
            and relative not in seen,
            "Unknown or duplicate LSP edit file",
        )
        seen.add(relative)
        source = path.read_bytes()
        require(digest(source) == inventory[relative], "Source changed during planning")
        ranges, matched = validated_ranges(
            document["edits"], source, anchor, path == anchor_path, new_name
        )
        anchor_found = anchor_found or matched
        files.append(
            {"path": str(path), "sha256": inventory[relative], "ranges": ranges}
        )
        # Read-only expected result: the engine remains the only source writer.
        expected = source
        for interval in reversed(ranges):
            expected = (
                expected[: interval["start"]]
                + new_name.encode("utf-8")
                + expected[interval["end"] :]
            )
        expected_inventory[relative] = digest(expected)
    require(anchor_found, "Rename did not include its selected declaration")
    document = ast(
        {
            "mode": "translate",
            "to": new_name,
            "old_name": anchor["name"],
            "files": files,
        },
        root,
    )
    sites = Counter({"declarations": 0, "references": 0})
    for file in document["files"]:
        sites.update(file.pop("resolved_sites"))
    return document, expected_inventory, dict(sites)


def plan(args, state):
    started = time.monotonic()
    root = args.root.resolve(strict=True)
    require(
        root.is_dir() and not state.is_relative_to(root),
        "State must be outside the workspace",
    )
    phar = args.phpactor.resolve(strict=True)
    require(
        digest(phar.read_bytes()) == PHAR_SHA256,
        "Phpactor PHAR does not match the pinned release digest",
    )
    inventory = snapshot(root)
    file = (root / args.file).resolve(strict=True)
    require(file.is_relative_to(root), "Anchor file is outside the workspace")
    relative = file.relative_to(root).as_posix()
    require(
        relative in inventory and relative.endswith(".php"),
        "Anchor must be a snapshotted PHP file",
    )
    anchor = ast(
        {
            "mode": "anchor",
            "file": {"path": str(file), "sha256": inventory[relative]},
            "select": args.select,
            "to": args.to,
        },
        root,
    )
    source = file.read_bytes()
    interval = {key: byte_to_position(source, anchor[key]) for key in ("start", "end")}
    run_dir = state / ("resolver-" + os.urandom(12).hex())
    run_dir.mkdir(mode=0o700)
    resolved = rename(
        phar,
        root,
        run_dir,
        file,
        interval["start"],
        interval,
        args.to,
        sum(name.endswith(".php") for name in inventory),
    )
    document, expected_inventory, sites = translate(
        resolved["workspace_edit"], root, inventory, file, anchor, args.to
    )
    require(snapshot(root) == inventory, "Workspace changed during planning")
    record = {
        "schema": 1,
        "root": str(root),
        "inventory": inventory,
        "runtime": runtime_identity(),
        "resolver": {"release": RELEASE, "sha256": PHAR_SHA256},
        "request": {"file": relative, "select": args.select, "to": args.to},
        "document": document,
        "expected_inventory": expected_inventory,
        "resolved_sites": sites,
        "resolver_result": resolved,
        "elapsed_ms": (time.monotonic() - started) * 1000,
    }
    raw = encode(record)
    identifier = digest(raw)
    with (state / (identifier + JSON_SUFFIX)).open("xb") as output:
        output.write(raw)
    return {
        "ok": True,
        "plan": identifier,
        "files": len(document["files"]),
        "edits": sum(len(file["edits"]) for file in document["files"]),
        "completeness": "unknown",
        "warnings": [LIMIT_WARNING],
        "elapsed_ms": record["elapsed_ms"],
    }, 0


def load_plan(args, state):
    require(PLAN_ID.fullmatch(args.plan) is not None, "Invalid plan ID")
    path = state / (args.plan + JSON_SUFFIX)
    require(not path.is_symlink(), "Symlink plans are unsupported")
    raw = path.read_bytes()
    require(digest(raw) == args.plan, "Plan content hash differs")
    record = json.loads(raw)
    require(
        isinstance(record, dict)
        and type(record.get("schema")) is int
        and record["schema"] == 1,
        "Unknown plan schema",
    )
    required = {
        "root",
        "inventory",
        "runtime",
        "resolver",
        "request",
        "document",
        "resolver_result",
        "elapsed_ms",
    }
    require(required <= record.keys(), "Plan is missing required fields")
    require(
        isinstance(record["root"], str) and Path(record["root"]).is_absolute(),
        "Invalid plan root",
    )
    require(
        isinstance(record["runtime"], str)
        and PLAN_ID.fullmatch(record["runtime"]) is not None,
        "Invalid plan runtime identity",
    )
    for field in ("inventory", "resolver", "request", "document", "resolver_result"):
        require(isinstance(record[field], dict), "Invalid plan field: " + field)
    require(
        isinstance(record["document"].get("files"), list)
        and record["document"]["files"],
        "Plan has no file operations",
    )
    expected = record.get("expected_inventory")
    if expected is not None:
        require(
            isinstance(expected, dict)
            and expected.keys() == record["inventory"].keys()
            and all(
                isinstance(value, str) and PLAN_ID.fullmatch(value) is not None
                for value in expected.values()
            ),
            "Invalid expected byte inventory",
        )
    sites = record.get("resolved_sites")
    if sites is not None:
        require(
            isinstance(sites, dict)
            and set(sites) == {"declarations", "references"}
            and all(type(count) is int and count >= 0 for count in sites.values())
            and sites["declarations"] >= 1
            and sum(sites.values())
            == sum(len(file["edits"]) for file in record["document"]["files"]),
            "Invalid resolved site counts",
        )
    return record


def apply_plan(args, state):
    record = load_plan(args, state)
    consumed = state / (args.plan + ".consumed")
    require(not consumed.exists(), "Plan was already consumed")
    require(
        runtime_identity() == record["runtime"],
        "Engine or planner changed since planning",
    )
    root = Path(record["root"])
    require(
        snapshot(root) == record["inventory"],
        "STALE_PLAN: workspace files changed, appeared or disappeared",
    )
    status, report = invoke(
        [str(RUNTIME / "bin/php-ast-edit"), "apply"],
        {**record["document"], "report": "compact"},
        root,
    )
    result_path = state / (args.plan + ".attempt-" + os.urandom(8).hex() + JSON_SUFFIX)
    with result_path.open("xb") as output:
        output.write(encode(report))
    if status in (0, 1) or snapshot(root) != record["inventory"]:
        with consumed.open("x") as marker:
            marker.write(str(status))
    if status not in (0, 1):
        return {
            "ok": False,
            "error": report.get("error", "Engine rejected plan"),
            "plan": args.plan,
        }, status
    files = report["files"]
    validation = {
        "parser": dict(Counter(file["validation"]["parser"] for file in files)),
        "lint": dict(Counter(file["validation"]["lint"]["status"] for file in files)),
        "checks": dict(Counter(file["validation"]["checks"] for file in files)),
    }
    issues = [
        {
            "path": Path(file["path"]).relative_to(root).as_posix(),
            "validation": file["validation"],
            "warnings": file.get("warnings", []),
        }
        for file in files
        if file.get("warnings")
        or file["validation"]["parser"] != "passed"
        or file["validation"]["lint"]["status"] != "passed"
        or file["validation"]["checks"] == "failed"
    ]
    result = {
        "ok": status == 0,
        "plan": args.plan,
        "changed_files": [
            Path(file["path"]).relative_to(root).as_posix()
            for file in files
            if file["changed"]
        ],
        "edits_applied": sum(file["editsApplied"] for file in files),
        "validation": validation,
        "file_issues": issues,
        "checksPassed": report["checksPassed"],
        "verify": report.get("verify", []),
        "completeness": "unknown",
        "warnings": [LIMIT_WARNING],
        "full_report": str(result_path),
    }
    if getattr(args, "evidence", False) or getattr(args, "guidance", False):
        add_result_evidence(result, record, root, result_path)
    if getattr(args, "guidance", False):
        add_result_guidance(result, record)
    return result, status


def add_result_evidence(result, record, root, result_path):
    """Report observed disk bytes, independently of the engine's in-memory output."""
    groups = {}
    for issue in result.pop("file_issues"):
        detail = {key: value for key, value in issue.items() if key != "path"}
        lint = dict(detail["validation"]["lint"])
        if "runtime" in lint:
            lint["php_version"] = lint.pop("runtime")
        detail["validation"] = {**detail["validation"], "lint": lint}
        key = encode(detail)
        groups.setdefault(key, {**detail, "paths": []})["paths"].append(issue["path"])
    result["issue_groups"] = list(groups.values())
    result["request"] = record["request"]
    result["planned_edits"] = sum(
        len(file["edits"]) for file in record["document"]["files"]
    )
    evidence = {
        "status": "not_established",
        "scope": "non-Git workspace bytes equal only the resolved, AST-validated name replacements",
    }
    observed = None
    expected = record.get("expected_inventory")
    try:
        if expected is None:
            evidence["reason"] = "Plan has no expected byte inventory"
        else:
            observed = snapshot(root)
            mismatches = sorted(
                name
                for name in expected.keys() | observed.keys()
                if expected.get(name) != observed.get(name)
            )
            evidence.update(
                status="not_established" if mismatches else "passed",
                checked_files=len(observed),
                mismatched_files=mismatches,
            )
            if mismatches:
                evidence["reason"] = (
                    "Disk bytes differ; formatting or other changes require inspection"
                )
    except (OSError, ValueError) as error:
        evidence["reason"] = "Cannot establish disk inventory: " + str(error)
    result["exact_edit_match"] = evidence
    # Separate immutable readback artifact; the original engine report stays intact.
    try:
        with result_path.with_suffix(".readback.json").open("x") as output:
            json.dump({"evidence": evidence, "observed_inventory": observed}, output)
    except OSError as error:
        result["warnings"].append("READBACK_NOT_SAVED: " + str(error))


def verification_follow_up(result):
    checks = result["verify"]
    if result["checksPassed"] is False or any(
        check.get("ok") is False for check in checks
    ):
        return "Repair the failed commands in verify; edits may be retained. Re-run affected checks after repair."
    if not checks:
        return "No configured verification commands ran. Run the relevant behavior checks required by the task on the final files."
    if result["checksPassed"] is True and all(
        check.get("ok") is True for check in checks
    ):
        return "Named commands in verify already passed. Repeat after relevant input changes; run any other required checks."
    return "Configured verification success is not established. Inspect verify and run the relevant outstanding checks."


def add_result_guidance(result, record):
    """Scope next actions to observations; never declare the user's task complete."""
    exact = result["exact_edit_match"]["status"] == "passed"
    counts_match = result["planned_edits"] == result["edits_applied"]
    sites = record.get("resolved_sites")
    result["resolved_sites"] = (
        {**sites, "status": "applied" if exact and counts_match else "planned"}
        if sites is not None
        else {"declarations": None, "references": None, "status": "unknown"}
    )
    if not exact:
        review = "Inspect the mismatched files or reason in exact_edit_match; byte preservation is not established. Recheck affected final files."
    elif not counts_match:
        review = "Inspect the planned/applied edit-count discrepancy before relying on the reported site counts."
    else:
        review = "No additional source readback is needed solely to reconfirm the exact, reported name replacements."
    follow_up = [review, verification_follow_up(result)]
    validation = result["validation"]
    if any(set(validation.get(kind, {})) != {"passed"} for kind in ("parser", "lint")):
        follow_up.append(
            "Address failed, skipped or unperformed parser/lint validation shown in validation and issue_groups."
        )
    result["follow_up"] = follow_up
    result["warnings"] = [
        "Experimental PHP-only rename; reference completeness unknown. Report resolved sites and named checks, not complete coverage."
        if warning == LIMIT_WARNING
        else warning
        for warning in result["warnings"]
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("plan", "rename_method", "apply_plan", "show_plan"):
        command = commands.add_parser(name)
        command.add_argument("--state", type=Path, required=True)
        if name in ("plan", "rename_method"):
            command.add_argument("--root", type=Path, required=True)
            command.add_argument("--phpactor", type=Path, required=True)
            command.add_argument("--file", required=True)
            command.add_argument("--select", required=True)
            command.add_argument("--to", required=True)
        else:
            command.add_argument("--plan", required=True)
        if name in ("rename_method", "apply_plan"):
            command.add_argument("--evidence", action="store_true")
            command.add_argument("--guidance", action="store_true")
    args = parser.parse_args()
    try:
        require(
            not args.state.is_symlink(), "Symlink state directories are unsupported"
        )
        args.state.mkdir(mode=0o700, exist_ok=True)
        state = args.state.resolve(strict=True)
        lock = state / ".lock"
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            if args.action in ("plan", "rename_method"):
                result, status = plan(args, state)
                if args.action == "rename_method":
                    args.plan = result["plan"]
                    planning_ms = result["elapsed_ms"]
                    result, status = apply_plan(args, state)
                    result["planning_ms"] = planning_ms
            elif args.action == "apply_plan":
                result, status = apply_plan(args, state)
            else:
                result, status = load_plan(args, state), 0
        print(json.dumps(result, ensure_ascii=False))
        return status
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
