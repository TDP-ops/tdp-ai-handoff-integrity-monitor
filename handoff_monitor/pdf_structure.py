"""Strict bounded PDF classic-xref page tree observation.

Supported: simple PDF 1.x with one classic xref table, direct object offsets,
an unencrypted /Root -> /Pages tree, and page leaves using /Type /Page.
All other PDF layouts abstain; this is NOT a general PDF parser.
"""
import re
import hashlib
from pathlib import Path

MAX_PDF = 4 * 1024 * 1024
OBJ_RE = re.compile(rb"\A(\d+)\s+(\d+)\s+obj\b")
REF_RE = re.compile(rb"(\d+)\s+(\d+)\s+R")
XREF_RE = re.compile(rb"\A(\d+)\s+(\d+)\s*\n")
REF_FIELD = rb"/%s\s+(\d+)\s+(\d+)\s+R\b"


def _one_reference(data, name):
    items = re.findall(REF_FIELD % name, data)
    if len(items) != 1:
        raise ValueError("Missing or ambiguous PDF reference")
    return tuple(int(v) for v in items[0])


def _objects(raw, *, plain_streams=False):
    end = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*\Z", raw)
    if end is None:
        raise ValueError("PDF trailer or EOF missing")
    offset = int(end.group(1))
    if offset >= len(raw) or raw[offset:offset + 4] != b"xref":
        raise ValueError("Unsupported PDF xref style")
    cursor = offset + 4
    if raw[cursor:cursor + 2] == b"\r\n":
        cursor += 2
    elif raw[cursor:cursor + 1] in (b"\r", b"\n"):
        cursor += 1
    else:
        raise ValueError("Bad xref line ending")
    xrefs = {}
    while True:
        if raw[cursor:cursor + 7] == b"trailer":
            cursor += 7
            break
        line_end = raw.find(b"\n", cursor)
        if line_end < 0:
            raise ValueError("Unterminated xref subsection")
        match = XREF_RE.fullmatch(raw[cursor:line_end + 1])
        if not match:
            raise ValueError("Unsupported xref subsection")
        first, count = map(int, match.groups())
        cursor = line_end + 1
        if count > 1000 or first + count > 1000:
            raise ValueError("Excessive PDF object count")
        for index in range(first, first + count):
            row_end = raw.find(b"\n", cursor)
            if row_end < 0:
                raise ValueError("Unterminated xref entry")
            row = raw[cursor:row_end + 1]
            entry = re.fullmatch(rb"(\d{10}) (\d{5}) ([nf]) \r?\n", row)
            if not entry:
                raise ValueError("Malformed classic xref entry")
            cursor = row_end + 1
            if entry.group(3) == b"n":
                ref = (index, int(entry.group(2)))
                if ref in xrefs:
                    raise ValueError("Duplicate xref object")
                xrefs[ref] = int(entry.group(1))
    cursor += len(raw[cursor:].split(b"<<", 1)[0])
    trailer_end = raw.find(b">>", cursor)
    if trailer_end < 0 or raw[cursor:cursor + 2] != b"<<":
        raise ValueError("Invalid PDF trailer dictionary")
    trailer = raw[cursor:trailer_end + 2]
    if any(token in trailer for token in (b"/Encrypt", b"/Prev", b"/XRefStm")):
        raise ValueError("Unsupported encrypted or incremental PDF")
    root = _one_reference(trailer, b"Root")
    objects = {}
    for ref, pos in xrefs.items():
        if pos >= offset or pos < 0:
            raise ValueError("PDF object offset invalid")
        match = OBJ_RE.match(raw[pos:])
        if match is None or (int(match.group(1)), int(match.group(2))) != ref:
            raise ValueError("PDF xref points to wrong object")
        start = pos + match.end()
        endobj = raw.find(b"endobj", start, offset)
        if endobj < 0:
            raise ValueError("Unterminated PDF object")
        body = raw[start:endobj].strip()
        if plain_streams and b"stream" in body:
            # Minimal byte-exact streams: no filters, no indirect Length,
            # no support for keyword-like tokens inside raw stream bytes.
            match_stream = re.fullmatch(
                rb"(<<[^<>]*?/Length\s+(\d+)\s*>>)"
                rb"\s*stream\r?\n(.*?)\r?\nendstream",
                body, re.DOTALL)
            if not match_stream or b"/Filter" in match_stream.group(1):
                raise ValueError("Unsupported PDF content stream")
            payload = match_stream.group(3)
            if len(payload) != int(match_stream.group(2)):
                raise ValueError("PDF stream length mismatch")
            objects[ref] = (match_stream.group(1), payload)
            continue
        # Keep the page-count-only parser behavior unchanged.
        if (not body.startswith(b"<<") or not body.endswith(b">>")
                or b"stream" in body or body.count(b"<<") != 1):
            raise ValueError("Unsupported PDF object structure")
        objects[ref] = body
    return objects, root


def pdf_page_count(path):
    raw = Path(path).read_bytes()
    if (len(raw) > MAX_PDF or not raw.startswith(b"%PDF-1.")
            or b"\x00" in raw):
        raise ValueError("Unsupported PDF header, size or binary syntax")
    objects, root_ref = _objects(raw)
    root = objects.get(root_ref)
    if root is None or re.search(rb"/Type\s*/Catalog\b", root) is None:
        raise ValueError("PDF catalog missing")
    pages_ref = _one_reference(root, b"Pages")
    visited = set()

    def walk(ref, parent=None):
        if ref in visited or ref not in objects:
            raise ValueError("Cyclic or absent PDF page object")
        visited.add(ref)
        body = objects[ref]
        if parent is not None and _one_reference(body, b"Parent") != parent:
            raise ValueError("Invalid PDF page parent")
        if re.search(rb"/Type\s*/Page\b", body):
            return 1
        if not re.search(rb"/Type\s*/Pages\b", body):
            raise ValueError("Unsupported PDF page tree node")
        count = re.search(rb"/Count\s+(\d+)\b", body)
        kids = re.search(rb"/Kids\s*\[([^\]]*)\]", body)
        if count is None or kids is None:
            raise ValueError("Incomplete PDF page tree")
        refs = REF_RE.findall(kids.group(1))
        if not refs or len(refs) > 1000 or REF_RE.sub(b"", kids.group(1)).strip():
            raise ValueError("Malformed PDF Kids array")
        actual = sum(walk(tuple(map(int, item)), ref) for item in refs)
        if actual != int(count.group(1)):
            raise ValueError("PDF page count declaration inconsistent")
        return actual

    return walk(pages_ref)


PDF_PAGE_EXTRACTOR_ID = "tdp-pdf-simple-page-stream-sha256-v1"


def pdf_page_hash(path, page_index):
    """Hash a narrowly defined page representation, not rendered appearance.

    Representation (in this order): ASCII prefix, MediaBox coordinates,
    a zero byte, then the full raw bytes of one directly referenced,
    unfiltered /Contents stream. Requires a direct page MediaBox and no
    /Resources or inherited graphics state, to avoid unsound equivalence.
    """
    raw = Path(path).read_bytes()
    if (len(raw) > MAX_PDF or not raw.startswith(b"%PDF-1.")
            or b"\x00" in raw):
        raise ValueError("Unsupported PDF syntax")
    objects, root_ref = _objects(raw, plain_streams=True)
    catalog = objects.get(root_ref)
    if not isinstance(catalog, bytes) or not re.search(rb"/Type\s*/Catalog\b", catalog):
        raise ValueError("Unsupported PDF catalog")
    pages_root = _one_reference(catalog, b"Pages")
    collected = []
    seen = set()

    def walk(ref, parent=None):
        if ref in seen or ref not in objects:
            raise ValueError("Missing or repeated page tree node")
        seen.add(ref)
        node = objects[ref]
        if not isinstance(node, bytes):
            raise ValueError("Stream cannot be a page tree node")
        if parent is not None and _one_reference(node, b"Parent") != parent:
            raise ValueError("Invalid PDF parent reference")
        if re.search(rb"/Type\s*/Page\b", node):
            collected.append(node)
            return 1
        if not re.search(rb"/Type\s*/Pages\b", node):
            raise ValueError("Non-page node in tree")
        count = re.search(rb"/Count\s+(\d+)\b", node)
        kids = re.search(rb"/Kids\s*\[([^\]]*)\]", node)
        if count is None or kids is None:
            raise ValueError("Incomplete page tree")
        children = REF_RE.findall(kids.group(1))
        if not children or REF_RE.sub(b"", kids.group(1)).strip():
            raise ValueError("Invalid page tree children")
        actual = sum(walk(tuple(map(int, child)), ref) for child in children)
        if actual != int(count.group(1)):
            raise ValueError("Page tree declared count mismatch")
        return actual

    walk(pages_root)
    if page_index >= len(collected):
        return None
    page = collected[page_index]
    # Strictly forbid content-affecting dependencies we do not resolve.
    if any(x in page for x in (b"/Resources", b"/Rotate", b"/CropBox",
                                b"/Annots", b"/Group", b"/UserUnit")):
        raise ValueError("Unsupported page dependencies")
    box = re.findall(
        rb"/MediaBox\s*\[\s*([+-]?\d+)\s+([+-]?\d+)\s+"
        rb"([+-]?\d+)\s+([+-]?\d+)\s*\]", page)
    if len(box) != 1:
        raise ValueError("Exactly one direct integer MediaBox required")
    stream_ref = _one_reference(page, b"Contents")
    stream_obj = objects.get(stream_ref)
    if not isinstance(stream_obj, tuple):
        raise ValueError("Page has no supported raw content stream")
    # No assumption that this fingerprint represents rendered pixels.
    geometry = b" ".join(box[0])
    representation = (b"TDP-PDF-PAGE-RAW-V1\n" + geometry +
                      b"\x00" + stream_obj[1])
    return hashlib.sha256(representation).hexdigest()
