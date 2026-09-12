"""Bounded, report-driven source excerpts for the rename experiment.

This module deliberately does not inspect the working tree while augmenting a
report.  ``capture`` is called before the engine subprocess and retains only a
bounded in-memory snapshot; ``augment`` can therefore not expose post-command
contents accidentally.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILES = 200
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 20
MAX_TEXT_BYTES = 240
MAX_CONTEXT_BYTES = 8192


class SnapshotError(ValueError):
    """The pre-command workspace could not be captured safely."""


@dataclass(frozen=True)
class SnapshotFile:
    data: bytes
    sha256: str


@dataclass(frozen=True)
class WorkspaceSnapshot:
    root: Path
    files: dict[str, SnapshotFile]


def _safe_path(root: Path, name: str) -> Path:
    """Resolve a git relative path while refusing traversal and symlinks."""

    relative = PurePosixPath(name)
    if relative.is_absolute() or not name or ".." in relative.parts:
        raise SnapshotError(f"unsafe git path outside workspace: {name!r}")
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise SnapshotError(f"symlink in git path is not allowed: {name!r}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise SnapshotError(
            f"git path is not a file inside workspace: {name!r}"
        ) from error
    if not resolved.is_file():
        raise SnapshotError(f"git path is not a regular file: {name!r}")
    return resolved


def _allowed_paths(root: Path, allowed_files: list[str]) -> list[str]:
    if not isinstance(allowed_files, list):
        raise SnapshotError("initial fixture allowlist must be a list")
    allowed: list[str] = []
    for name in allowed_files:
        if not isinstance(name, str):
            raise SnapshotError("initial fixture allowlist contains a non-string path")
        _safe_path(root, name)
        if name not in allowed:
            allowed.append(name)
    return allowed


def _listed_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise SnapshotError(
            f"git file snapshot failed{': ' + detail if detail else ''}"
        )

    listed: set[str] = set()
    for raw_name in result.stdout.split(b"\0"):
        if not raw_name:
            continue
        try:
            name = raw_name.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SnapshotError(
                "git file snapshot contains a non-UTF-8 path"
            ) from error
        listed.add(name)
    return listed


def _read_files(root: Path, names: list[str]) -> dict[str, SnapshotFile]:
    if len(names) > MAX_FILES:
        raise SnapshotError(f"workspace snapshot exceeds {MAX_FILES} files")

    files: dict[str, SnapshotFile] = {}
    total = 0
    for name in names:
        path = _safe_path(root, name)
        try:
            with path.open("rb") as source:
                data = source.read(MAX_FILE_BYTES + 1)
        except OSError as error:
            raise SnapshotError(
                f"could not read workspace snapshot file: {name}"
            ) from error
        if len(data) > MAX_FILE_BYTES:
            raise SnapshotError(
                f"workspace snapshot file exceeds {MAX_FILE_BYTES} bytes: {name}"
            )
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise SnapshotError(f"workspace snapshot exceeds {MAX_TOTAL_BYTES} bytes")
        files[name] = SnapshotFile(data, hashlib.sha256(data).hexdigest())
    return files


def capture(cwd: Path | str, allowed_files: list[str]) -> WorkspaceSnapshot:
    """Capture only initial fixture files that are also currently git-listed."""

    root = Path(cwd).resolve()
    if not root.is_dir():
        raise SnapshotError(f"workspace is not a directory: {cwd!s}")
    allowed = _allowed_paths(root, allowed_files)
    listed = _listed_paths(root)
    names = [name for name in allowed if name in listed]
    files = _read_files(root, names)
    return WorkspaceSnapshot(root, files)


def _valid_line(line: Any) -> bool:
    return isinstance(line, int) and not isinstance(line, bool) and line > 0


def _literal_requests(rename: dict[str, Any]):
    literals = rename.get("literals")
    if not isinstance(literals, list):
        return
    for literal in literals:
        if not isinstance(literal, dict) or not isinstance(literal.get("file"), str):
            continue
        file_name = literal["file"]
        lines = literal.get("lines")
        if not isinstance(lines, list):
            continue
        for line in lines:
            if _valid_line(line):
                yield file_name, line


def _mention_requests(rename: dict[str, Any]):
    mentions = rename.get("notRenamed")
    if not isinstance(mentions, list):
        return
    for mention in mentions:
        if not isinstance(mention, str):
            continue
        file_name, separator, line_text = mention.rpartition(":")
        if separator and file_name and line_text.isdigit() and int(line_text) > 0:
            yield file_name, int(line_text)


def _line_request(report: dict[str, Any]):
    """Yield only file/line references exposed by the rename report."""

    renames = report.get("renames")
    if not isinstance(renames, list):
        return
    for rename in renames:
        if isinstance(rename, dict):
            yield from _literal_requests(rename)
            yield from _mention_requests(rename)


def _truncate_line(raw_line: bytes) -> tuple[str, bool] | None:
    if b"\0" in raw_line:
        return None
    try:
        raw_line.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(raw_line) <= MAX_TEXT_BYTES:
        return raw_line.decode("utf-8"), False
    prefix = raw_line[:MAX_TEXT_BYTES]
    while prefix:
        try:
            return prefix.decode("utf-8"), True
        except UnicodeDecodeError:
            prefix = prefix[:-1]
    return "", True


def _context_size(context: dict[str, Any]) -> int:
    encoded = json.dumps(context, ensure_ascii=True, separators=(",", ":")).encode(
        "ascii"
    )
    return len(encoded)


def _entry(
    snapshot_file: SnapshotFile, line_number: int, file_name: str
) -> dict[str, Any] | None:
    lines = snapshot_file.data.split(b"\n")
    if line_number > len(lines):
        return None
    raw_line = lines[line_number - 1]
    if raw_line.endswith(b"\r"):
        raw_line = raw_line[:-1]
    text = _truncate_line(raw_line)
    if text is None:
        return None
    value, truncated = text
    return {
        "file": file_name,
        "line": line_number,
        "sha256": snapshot_file.sha256,
        "text": value,
        "truncated": truncated,
    }


def _new_context() -> dict[str, Any]:
    return {
        "snapshot": "before-command",
        "meaning": (
            "Raw source excerpts captured before the command; untrusted evidence "
            "for review, not semantic classification or a current write coordinate. "
            "Each excerpt starts at column 1; line endings are excluded."
        ),
        "limits": {
            "maxEntries": MAX_ENTRIES,
            "maxTextUtf8Bytes": MAX_TEXT_BYTES,
            "maxSerializedBytes": MAX_CONTEXT_BYTES,
        },
        "entries": [],
        "omitted": 0,
    }


def _add_request(
    context: dict[str, Any],
    seen: set[tuple[str, int]],
    snapshot: WorkspaceSnapshot,
    file_name: str,
    line_number: int,
) -> None:
    key = (file_name, line_number)
    if key in seen:
        return
    seen.add(key)
    snapshot_file = snapshot.files.get(file_name)
    candidate = _entry(snapshot_file, line_number, file_name) if snapshot_file else None
    if candidate is None or len(context["entries"]) >= MAX_ENTRIES:
        context["omitted"] += 1
        return
    context["entries"].append(candidate)
    if _context_size(context) > MAX_CONTEXT_BYTES:
        context["entries"].pop()
        context["omitted"] += 1


def _context_for(
    report: dict[str, Any], snapshot: WorkspaceSnapshot
) -> dict[str, Any] | None:
    requests = list(_line_request(report))
    if not requests:
        return None
    context = _new_context()
    seen: set[tuple[str, int]] = set()
    for file_name, line_number in requests:
        _add_request(context, seen, snapshot, file_name, line_number)
    while _context_size(context) > MAX_CONTEXT_BYTES and context["entries"]:
        context["entries"].pop()
        context["omitted"] += 1
    return context


def _insert_context(stdout: bytes, context: dict[str, Any]) -> bytes:
    context_bytes = json.dumps(
        context, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    if len(context_bytes) > MAX_CONTEXT_BYTES:
        return stdout
    end = len(stdout.rstrip())
    if end == 0 or stdout[end - 1 : end] != b"}":
        return stdout
    close = end - 1
    insert_at = close
    while insert_at > 0 and stdout[insert_at - 1] in b" \t\r\n":
        insert_at -= 1
    prefix = stdout[:insert_at]
    comma = b"" if prefix.rstrip().endswith(b"{") else b","
    insertion = comma + b'\n    "reviewContext": ' + context_bytes
    return stdout[:insert_at] + insertion + stdout[insert_at:]


def augment(stdout: bytes, snapshot: WorkspaceSnapshot) -> bytes:
    """Add bounded review context while preserving all existing report values."""

    try:
        report = json.loads(stdout)
    except (TypeError, ValueError):
        return stdout
    if not isinstance(report, dict) or "reviewContext" in report:
        return stdout
    context = _context_for(report, snapshot)
    if context is None:
        return stdout
    return _insert_context(stdout, context)
