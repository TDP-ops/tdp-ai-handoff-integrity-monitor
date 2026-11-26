"""Bounded, standard-library OOXML XLSX sheet-name observation.

No formula evaluation, workbook repair, or external relationship resolution.
Files with unsupported layouts abstain. A locally present sheet is not proof
of authentic receiver custody.
"""
import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_FILE = 8 * 1024 * 1024
MAX_UNCOMPRESSED = 24 * 1024 * 1024
MAX_MEMBERS = 128


def xlsx_sheet_names(path, *, include_parts=False):
    if Path(path).stat().st_size > MAX_FILE:
        raise ValueError("XLSX exceeds bounded file size")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_MEMBERS:
                raise ValueError("Unsupported XLSX archive size")
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                raise ValueError("Duplicate OOXML ZIP members")
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED:
                raise ValueError("Uncompressed XLSX too large")
            for entry in entries:
                name = entry.filename
                if (name.startswith("/") or "\\" in name
                        or ".." in name.split("/") or entry.flag_bits & 1):
                    raise ValueError("Unsafe XLSX ZIP member")
            if not {"[Content_Types].xml", "xl/workbook.xml",
                    "xl/_rels/workbook.xml.rels"}.issubset(names):
                raise ValueError("Incomplete XLSX package")
            if archive.testzip() is not None:
                raise ValueError("Corrupt XLSX member")
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            relationships = ET.fromstring(
                archive.read("xl/_rels/workbook.xml.rels"))
            if workbook.tag != SS + "workbook" or relationships.tag != PKG + "Relationships":
                raise ValueError("Unsupported XLSX XML namespace")
            targets = {}
            for rel in relationships:
                if rel.tag != PKG + "Relationship":
                    raise ValueError("Unexpected workbook relationship")
                if rel.get("TargetMode", "Internal") != "Internal":
                    continue
                rel_id = rel.get("Id")
                target = rel.get("Target", "")
                if not rel_id or not target or rel_id in targets:
                    raise ValueError("Invalid workbook relationship")
                targets[rel_id] = (target, rel.get("Type", ""))
            sheets_node = workbook.find(SS + "sheets")
            if sheets_node is None or not len(sheets_node):
                raise ValueError("Workbook has no sheets")
            found = set()
            parts = {}
            for sheet in sheets_node:
                if sheet.tag != SS + "sheet":
                    raise ValueError("Unsupported sheets entry")
                title = sheet.get("name")
                rel_id = sheet.get(REL + "id")
                if not title or title in found or rel_id not in targets:
                    raise ValueError("Invalid or duplicate sheet")
                target, rel_type = targets[rel_id]
                if not rel_type.endswith("/worksheet"):
                    raise ValueError("Non-worksheet relation")
                member = (posixpath.normpath(target.lstrip("/"))
                          if target.startswith("/") else
                          posixpath.normpath(posixpath.join("xl", target)))
                if target.startswith("/"):
                    member = member.lstrip("/")
                if member not in names or not member.startswith("xl/"):
                    raise ValueError("Worksheet part missing")
                found.add(title)
                parts[title] = member
            return parts if include_parts else found
    except (zipfile.BadZipFile, ET.ParseError, EOFError) as error:
        raise ValueError("Unreadable XLSX archive or XML") from error


def _column_number(reference):
    letters = reference.rstrip("0123456789")
    row = reference[len(letters):]
    if not letters or row != "1" or not letters.isascii() or not letters.isalpha() or not letters.isupper():
        raise ValueError("Unsupported XLSX header cell reference")
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
        if number > 16384:
            raise ValueError("XLSX column index out of bounds")
    return number


def xlsx_first_row_columns(path, sheet_name):
    """Read first-row text headers, not arbitrary cells or computed formulas.

    Supports inline strings, shared strings, and direct string cells. Anything
    ambiguous is UNKNOWN to the calling engine, not a fabricated successful check.
    """
    parts = xlsx_sheet_names(path, include_parts=True)
    if sheet_name not in parts:
        return None
    with zipfile.ZipFile(path, "r") as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            if root.tag != SS + "sst":
                raise ValueError("Unexpected shared string namespace")
            for item in root:
                if item.tag != SS + "si":
                    raise ValueError("Unknown shared string child")
                shared.append("".join(t.text or "" for t in item.iter(SS + "t")))
        root = ET.fromstring(archive.read(parts[sheet_name]))
        if root.tag != SS + "worksheet":
            raise ValueError("Unexpected worksheet namespace")
        data = root.find(SS + "sheetData")
        if data is None:
            raise ValueError("Missing worksheet data")
        header = next((r for r in data if r.tag == SS + "row" and r.get("r") == "1"), None)
        if header is None:
            raise ValueError("No supported header row")
        used = set()
        observed = set()
        for cell in header:
            if cell.tag != SS + "c":
                raise ValueError("Unsupported header row element")
            reference = cell.get("r", "")
            column = _column_number(reference)
            if column in used:
                raise ValueError("Duplicate header cell column")
            used.add(column)
            if cell.find(SS + "f") is not None:
                raise ValueError("Formula header is not an observed label")
            kind = cell.get("t")
            if kind == "inlineStr":
                inline = cell.find(SS + "is")
                if inline is None:
                    raise ValueError("Missing inline string")
                value = "".join(t.text or "" for t in inline.iter(SS + "t"))
            elif kind == "s":
                element = cell.find(SS + "v")
                if element is None or element.text is None or not element.text.isascii() or not element.text.isdecimal():
                    raise ValueError("Invalid shared string reference")
                index = int(element.text)
                if index >= len(shared):
                    raise ValueError("Shared string reference out of range")
                value = shared[index]
            elif kind == "str":
                element = cell.find(SS + "v")
                if element is None:
                    raise ValueError("Missing string cell content")
                value = element.text or ""
            else:
                raise ValueError("Unsupported header cell type")
            if not value or value in observed:
                raise ValueError("Blank or duplicate header label")
            observed.add(value)
        if not observed:
            raise ValueError("No text headers")
        return observed
