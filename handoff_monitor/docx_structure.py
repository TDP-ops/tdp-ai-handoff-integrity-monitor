"""Bounded deterministic DOCX body-paragraph hashing.

Extractor ID fixes the algorithm: concatenate direct w:r/w:t text in each
direct w:body/w:p, UTF-8 encode without whitespace normalization, SHA-256.
Unsupported rich content abstains. No authenticity of custody is implied.
"""
import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

DOCX_EXTRACTOR_ID = "tdp-docx-body-paragraph-utf8-v1"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_ZIP_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
MAX_MEMBERS = 128


def _paragraph_text(paragraph):
    fragments = []
    for run in paragraph:
        if run.tag != W + "r":
            raise ValueError("Unsupported DOCX paragraph node")
        for node in run:
            if node.tag == W + "t":
                fragments.append(node.text or "")
            elif node.tag == W + "rPr":
                continue  # Formatting changes do not modify plain text.
            else:
                raise ValueError("Unsupported DOCX run child")
    return "".join(fragments)


def docx_paragraph_hash(path, paragraph_index):
    path = Path(path)
    if path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("DOCX archive exceeds parser limit")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (not names or len(names) > MAX_MEMBERS
                    or len(set(names)) != len(names)
                    or sum(entry.file_size for entry in entries) > MAX_TOTAL_BYTES):
                raise ValueError("Unsafe DOCX archive structure")
            for entry in entries:
                if (entry.filename.startswith("/") or "\\" in entry.filename
                        or ".." in entry.filename.split("/") or entry.flag_bits & 1):
                    raise ValueError("Unsupported DOCX archive entry")
            if not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}.issubset(names):
                raise ValueError("DOCX required parts missing")
            if archive.testzip() is not None:
                raise ValueError("DOCX ZIP member CRC failure")
            root = ET.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, ET.ParseError, EOFError) as error:
        raise ValueError("Unreadable DOCX") from error
    if root.tag != W + "document":
        raise ValueError("Unsupported DOCX document namespace")
    body = root.find(W + "body")
    if body is None:
        raise ValueError("Missing DOCX body")
    paragraphs = []
    for item in body:
        if item.tag == W + "p":
            paragraphs.append(_paragraph_text(item))
        elif item.tag == W + "sectPr":
            continue
        else:
            raise ValueError("Unsupported body content; cannot assert paragraph order")
    if paragraph_index >= len(paragraphs):
        return None
    return hashlib.sha256(paragraphs[paragraph_index].encode("utf-8")).hexdigest()
