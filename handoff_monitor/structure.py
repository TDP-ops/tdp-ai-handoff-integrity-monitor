"""Deterministic local structure observations for supported typed checks.

The parser reads caller-supplied paths and does not authenticate remote custody.
Unsupported checks and unreadable files must abstain, not produce false PASS.
"""
import csv
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


def check_structure(kind, checks, sender_path, receiver_path, artifact_id):
    """Return findings only for actually evaluated structure declarations."""
    issues = []
    for check in checks:
        if kind != "csv" or check.get("check_type") != "csv_required_columns":
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                  "Structure extractor not implemented"))
            continue
        for role, path in (("sender", sender_path), ("receiver", receiver_path)):
            if path is None:
                issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                      role + " CSV bytes unavailable"))
                continue
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
    return issues
