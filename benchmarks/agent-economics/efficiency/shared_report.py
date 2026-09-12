"""Losslessly factor metadata shared by every file in an engine report."""

from __future__ import annotations

import copy
import json
import math
from decimal import Decimal, InvalidOperation
from typing import Any


class ReportError(ValueError):
    """Invalid report data that cannot be safely presented."""


FILE_DEFAULTS = "fileDefaults"
FILE_DEFAULTS_MEANING = "fileDefaultsMeaning"
FILE_DEFAULTS_TEXT = (
    "Every file entry inherits fileDefaults; explicit file fields override them. "
    "This is presentation metadata only: it does not merge actual check executions "
    "or create global validation."
)
FACTORED_KEYS = (
    "changed",
    "dryRun",
    "printer",
    "warnings",
    "warning",
    "parsed",
    "valid",
    "validation",
    "checkIds",
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _parse_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number: {token}")
    try:
        if Decimal(token) != Decimal(str(value)):
            raise ValueError(f"JSON number loses precision: {token}")
    except InvalidOperation as error:
        raise ValueError(f"invalid JSON number: {token}") from error
    return value


def _parse(stdout: bytes) -> Any:
    return json.loads(
        stdout.decode("utf-8"),
        object_pairs_hook=_strict_object,
        parse_float=_parse_float,
        parse_constant=_reject_constant,
    )


def _same_json(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_json(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_json(item, other) for item, other in zip(left, right)
        )
    return left == right


def _files(document: Any) -> list[dict[str, Any]] | None:
    if not isinstance(document, dict):
        return None
    files = document.get("files")
    if not isinstance(files, list) or len(files) < 2:
        return None
    if any(not isinstance(entry, dict) for entry in files):
        raise ValueError("report files must contain objects")
    return files


def factor(stdout: bytes) -> bytes:
    """Factor whitelisted metadata while retaining all original report values."""

    document = _parse(stdout)
    if not isinstance(document, dict):
        return stdout
    if FILE_DEFAULTS in document or FILE_DEFAULTS_MEANING in document:
        raise ValueError("report reserves fileDefaults and fileDefaultsMeaning")
    files = _files(document)
    if files is None:
        return stdout

    defaults: dict[str, Any] = {}
    for key in FACTORED_KEYS:
        if all(key in entry for entry in files):
            candidate = files[0][key]
            if all(_same_json(candidate, entry[key]) for entry in files[1:]):
                defaults[key] = copy.deepcopy(candidate)
    if not defaults:
        return stdout

    projected = copy.deepcopy(document)
    projected[FILE_DEFAULTS] = defaults
    projected[FILE_DEFAULTS_MEANING] = FILE_DEFAULTS_TEXT
    projected["files"] = [
        {key: value for key, value in entry.items() if key not in defaults}
        for entry in files
    ]
    return (json.dumps(projected, ensure_ascii=False, indent=4) + "\n").encode("utf-8")


def restore(document: dict[str, Any]) -> dict[str, Any]:
    """Expand a factored report, rejecting ambiguous explicit overrides."""

    if not isinstance(document, dict):
        raise ReportError("report must be an object")
    has_defaults = FILE_DEFAULTS in document
    has_meaning = FILE_DEFAULTS_MEANING in document
    if not has_defaults and not has_meaning:
        return copy.deepcopy(document)
    defaults = document.get(FILE_DEFAULTS)
    meaning = document.get(FILE_DEFAULTS_MEANING)
    if (
        not isinstance(defaults, dict)
        or meaning != FILE_DEFAULTS_TEXT
        or any(key not in FACTORED_KEYS for key in defaults)
    ):
        raise ReportError("invalid fileDefaults envelope")
    files = document.get("files")
    if not isinstance(files, list):
        raise ReportError("factored report files must be an array")
    restored = copy.deepcopy(document)
    restored.pop(FILE_DEFAULTS)
    restored.pop(FILE_DEFAULTS_MEANING)
    restored["files"] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ReportError("factored report files must contain objects")
        overlap = defaults.keys() & entry.keys()
        if overlap:
            raise ReportError(f"file overrides shared metadata: {sorted(overlap)}")
        restored["files"].append({**copy.deepcopy(defaults), **copy.deepcopy(entry)})
    return restored


SHARED_MODES = ("shared_report_control", "shared_report_factored")


def _presentation_values(entry: dict[str, Any], mode: str) -> tuple[Any, ...] | None:
    if (
        mode not in SHARED_MODES
        or entry.get("shared_report_mode") != mode
        or type(entry.get("shared_report_eligible")) is not bool
        or not isinstance(entry.get("stdout"), str)
        or not isinstance(entry.get("presented_stdout"), str)
        or type(entry.get("exit_code")) is not int
    ):
        return None
    return (
        entry["stdout"],
        entry["presented_stdout"],
        entry["shared_report_eligible"],
        entry["exit_code"],
    )


def _argv_is_eligible(entry: dict[str, Any], kwargs: dict[str, Any]) -> bool:
    if "argv" not in kwargs:
        return True
    argv = kwargs["argv"]
    if not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv):
        return False
    expected = entry["exit_code"] == 0 and bool(argv) and argv[0] in ("rename", "apply")
    return entry["shared_report_eligible"] == expected


def _eligible_presentation_valid(mode: str, original: bytes, presented: bytes) -> bool:
    original_document = _parse(original)
    presented_document = _parse(presented)
    projected = factor(original)
    if not _same_json(restore(_parse(projected)), original_document):
        return False
    if mode == "shared_report_control":
        return original == presented
    return presented == projected and _same_json(
        restore(presented_document), original_document
    )


def presentation_valid(entry: dict[str, Any], mode: str, **_kwargs: Any) -> bool:
    """Validate an engine result's original and arm-specific presented output."""

    values = _presentation_values(entry, mode)
    if values is None:
        return False
    try:
        stdout, presented_stdout, eligible, exit_code = values
        original = stdout.encode("utf-8")
        presented = presented_stdout.encode("utf-8")
        if not _argv_is_eligible(entry, _kwargs):
            return False
        if eligible and exit_code != 0:
            return False
        if not eligible:
            return original == presented
        return _eligible_presentation_valid(mode, original, presented)
    except (ValueError, TypeError):
        return False
