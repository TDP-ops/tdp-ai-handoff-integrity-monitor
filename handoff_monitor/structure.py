"""Deterministic local structure observations for supported typed checks.

The parser reads caller-supplied paths and does not authenticate remote custody.
Unsupported checks and unreadable files must abstain, not produce false PASS.
"""
import csv
import json
from pathlib import Path

from .core import finding


def _csv_header(path):
    """Read only the UTF-8 (optional BOM) CSV header with strict parsing."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        columns = next(reader)
    if not columns or any(not name for name in columns):
        raise ValueError("CSV header missing or contains empty column names")
    if len(set(columns)) != len(columns):
        raise ValueError("Duplicate CSV header columns")
    return set(columns)



def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _json_pointer_exists(path, pointer):
    # A bounded local observation: oversized documents are unverified.
    with Path(path).open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("JSON exceeds bounded parser size")
    document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_pairs,
                          parse_constant=lambda constant: (_ for _ in ()).throw(
                              ValueError("Non-standard JSON constant")))
    if pointer == "":
        return True
    current = document
    for component in pointer.split("/")[1:]:
        key = component.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if key not in current:
                return False
            current = current[key]
        elif isinstance(current, list):
            if not key.isascii() or not key.isdecimal() or (
                    len(key) > 1 and key[0] == "0"):
                return False
            index = int(key) if len(key) < 12 else len(current)
            if index >= len(current):
                return False
            current = current[index]
        else:
            return False
    return True


def check_structure(kind, checks, sender_path, receiver_path, artifact_id):
    """Return findings only for actually evaluated structure declarations."""
    issues = []
    for check in checks:
        typ = check.get("check_type")
        if (kind, typ) not in (("csv", "csv_required_columns"),
                               ("json", "json_required_pointer")):
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                  "Structure extractor not implemented"))
            continue
        for role, path in (("sender", sender_path), ("receiver", receiver_path)):
            if path is None:
                issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                      role + " local structure bytes unavailable"))
                continue
            if typ == "csv_required_columns":
                try:
                    header = _csv_header(path)
                except (OSError, UnicodeError, csv.Error, ValueError, StopIteration):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " CSV header cannot be parsed safely"))
                    continue
                missing = set(check["column_names"]) - header
                if missing:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " CSV missing required columns: " +
                                          ", ".join(sorted(missing))))
            else:
                try:
                    exists = _json_pointer_exists(path, check["pointer"])
                except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " JSON cannot be parsed safely"))
                    continue
                if not exists:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " JSON Pointer absent: " + check["pointer"]))
    return issues
