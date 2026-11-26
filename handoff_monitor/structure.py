"""Deterministic local structure observations for supported typed checks.

The parser reads caller-supplied paths and does not authenticate remote custody.
Unsupported checks and unreadable files must abstain, not produce false PASS.
"""
import csv
import json
import wave
import zlib
import zipfile
from xml.etree import ElementTree as ET
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



def _wav_metadata(path):
    """Read bounded WAV PCM metadata and verify complete declared frame data."""
    file_path = Path(path)
    with wave.open(str(file_path), "rb") as stream:
        if stream.getcomptype() != "NONE":
            raise ValueError("Compressed WAV unsupported")
        rate = stream.getframerate()
        count = stream.getnframes()
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        if rate <= 0 or channels <= 0 or width <= 0:
            raise ValueError("Invalid WAV parameters")
        # Verify the data chunk is complete, not just the declared header.
        if file_path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("WAV exceeds bounded parser size")
        frames = stream.readframes(count)
        if len(frames) != count * channels * width:
            raise ValueError("Truncated WAV sample data")
    return count, rate


def check_audio_quality(checks, sender_path, receiver_path, artifact_id):
    """Evaluate sample-rate minima on actual local WAV; others abstain."""
    issues = []
    for check in checks:
        if check.get("check_type") != "audio_min_sample_rate_hz":
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                  "Quality metric not implemented"))
            continue
        for role, path in (("sender", sender_path), ("receiver", receiver_path)):
            if path is None:
                issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                      role + " WAV observation unavailable"))
                continue
            try:
                _count, rate = _wav_metadata(path)
            except (OSError, EOFError, ValueError, wave.Error):
                issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                      role + " WAV metadata unreadable"))
                continue
            if rate < check["sample_rate_hz"]:
                issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                      role + " WAV sample rate below minimum"))
    return issues


def check_structure(kind, checks, sender_path, receiver_path, artifact_id):
    """Return findings only for actually evaluated structure declarations."""
    issues = []
    for check in checks:
        typ = check.get("check_type")
        if (kind, typ) not in (("csv", "csv_required_columns"),
                               ("json", "json_required_pointer"),
                               ("audio", "audio_min_duration_ms"),
                               ("image", "image_min_dimensions"),
                               ("xlsx", "xlsx_required_sheets"),
                               ("xlsx", "xlsx_required_columns"),
                               ("docx", "docx_required_paragraph_sha256"),
                               ("pdf", "pdf_min_pages"),
                               ("pdf", "pdf_required_page_sha256"),
                               ("db_schema", "db_required_table"),
                               ("db_schema", "db_required_column"),
                               ("db_schema", "db_required_foreign_key")):
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
            elif typ == "image_min_dimensions":
                from .image_structure import png_dimensions
                try:
                    width, height = png_dimensions(path)
                except (OSError, ValueError, OverflowError, MemoryError, zlib.error):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " PNG structure unreadable or unsupported"))
                    continue
                if width < check["width_px"] or height < check["height_px"]:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " PNG dimensions below minima"))
            elif typ == "xlsx_required_sheets":
                from .xlsx_structure import xlsx_sheet_names
                try:
                    observed = xlsx_sheet_names(path)
                except (OSError, ValueError, OverflowError, MemoryError, RuntimeError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " XLSX workbook unreadable or unsupported"))
                    continue
                missing = set(check["sheet_names"]) - observed
                if missing:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " XLSX missing sheets: " +
                                          ", ".join(sorted(missing))))
            elif typ == "xlsx_required_columns":
                from .xlsx_structure import xlsx_first_row_columns
                try:
                    observed = xlsx_first_row_columns(path, check["sheet_name"])
                except (OSError, ValueError, OverflowError, MemoryError, RuntimeError,
                        zipfile.BadZipFile, ET.ParseError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " XLSX header unavailable or unsupported"))
                    continue
                if observed is None:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " XLSX required sheet missing"))
                    continue
                missing = set(check["column_names"]) - observed
                if missing:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " XLSX missing columns: " +
                                          ", ".join(sorted(missing))))
            elif typ == "docx_required_paragraph_sha256":
                from .docx_structure import DOCX_EXTRACTOR_ID, docx_paragraph_hash
                if check["extractor_id"] != DOCX_EXTRACTOR_ID:
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          "DOCX extractor ID not supported"))
                    continue
                try:
                    observed = docx_paragraph_hash(path, check["paragraph_index"])
                except (OSError, ValueError, OverflowError, MemoryError, RuntimeError,
                        zipfile.BadZipFile, ET.ParseError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " DOCX paragraph cannot be extracted safely"))
                    continue
                if observed != check["extracted_paragraph_sha256"]:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " required DOCX paragraph missing or changed"))
            elif typ.startswith("db_required_"):
                from .db_structure import sqlite_schema, sqlite_schema_check
                try:
                    tables = sqlite_schema(path)
                    satisfied = sqlite_schema_check(tables, check)
                except (OSError, ValueError, OverflowError, MemoryError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " SQLite schema unreadable or unsupported"))
                    continue
                if not satisfied:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " SQLite required schema rule not satisfied"))
            elif typ == "pdf_required_page_sha256":
                from .pdf_structure import PDF_PAGE_EXTRACTOR_ID, pdf_page_hash
                if check["extractor_id"] != PDF_PAGE_EXTRACTOR_ID:
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          "PDF page extractor ID not supported"))
                    continue
                try:
                    observed = pdf_page_hash(path, check["page_index"])
                except (OSError, ValueError, OverflowError, MemoryError, RecursionError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " PDF page stream cannot be extracted safely"))
                    continue
                if observed != check["extracted_page_sha256"]:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " required PDF page absent or modified"))
            elif typ == "pdf_min_pages":
                from .pdf_structure import pdf_page_count
                try:
                    pages = pdf_page_count(path)
                except (OSError, ValueError, OverflowError, MemoryError, RecursionError):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " PDF page tree unreadable or unsupported"))
                    continue
                if pages < check["min_pages"]:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " PDF page count below minimum"))
            elif typ == "audio_min_duration_ms":
                try:
                    frames, rate = _wav_metadata(path)
                except (OSError, EOFError, ValueError, wave.Error):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", artifact_id,
                                          role + " WAV duration unreadable"))
                    continue
                if frames * 1000 < check["duration_ms"] * rate:
                    issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", artifact_id,
                                          role + " WAV duration below minimum"))
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
