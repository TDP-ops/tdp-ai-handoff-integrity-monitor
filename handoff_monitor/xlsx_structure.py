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


def xlsx_sheet_names(path):
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
            return found
    except (zipfile.BadZipFile, ET.ParseError, EOFError) as error:
        raise ValueError("Unreadable XLSX archive or XML") from error
