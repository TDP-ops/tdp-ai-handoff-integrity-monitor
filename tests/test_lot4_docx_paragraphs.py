"""Actual DOCX simple paragraph digest checks via the public strict API."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from handoff_monitor.docx_structure import DOCX_EXTRACTOR_ID, docx_paragraph_hash
from test_lot4_structural_abstentions import load

DOCX_CASES = (
    ("docx_paragraph_matching", "clean", "PASS"),
    ("docx_paragraph_changed", "violation", "ALERT"),
    ("docx_paragraph_removed", "violation", "ALERT"),
    ("docx_unsupported_table", "evidence_unavailable", "UNKNOWN"),
    ("docx_unsupported_extractor", "evidence_unavailable", "UNKNOWN"),
    ("docx_receiver_unavailable", "evidence_unavailable", "UNKNOWN"),
)


def build_docx(paragraphs, *, table=False):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    inner = "".join(
        '<w:p><w:r><w:t>' + value + '</w:t></w:r></w:p>'
        for value in paragraphs)
    if table:
        inner += '<w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>'
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="' + ns + '"><w:body>' + inner +
        '</w:body></w:document>')
    types = (
        '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/word/document.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="word/document.xml"/></Relationships>')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return stream.getvalue()


def run_docx_case(name):
    if name not in (row[0] for row in DOCX_CASES):
        raise ValueError("Unknown DOCX case: " + name)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    paragraphs = {
        "docx_paragraph_matching": ["Start", "Protected middle", "End"],
        "docx_paragraph_changed": ["Start", "Altered middle", "End"],
        "docx_paragraph_removed": ["Start"],
        "docx_unsupported_table": ["Start", "Protected middle", "End"],
        "docx_unsupported_extractor": ["Start", "Protected middle", "End"],
        "docx_receiver_unavailable": ["Start", "Protected middle", "End"],
    }[name]
    raw = build_docx(paragraphs, table=(name == "docx_unsupported_table"))
    expected = hashlib.sha256(b"Protected middle").hexdigest()
    for manifest in (sent, received):
        artifact = manifest["artifacts"][0]
        artifact["kind"] = "docx"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [{
                "check_type": "docx_required_paragraph_sha256",
                "paragraph_index": 1,
                "extracted_paragraph_sha256": expected,
                "extractor_id": ("untrusted-extractor"
                                 if name == "docx_unsupported_extractor"
                                 else DOCX_EXTRACTOR_ID),
            }],
        }
        artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.docx"
        dest = Path(directory) / "dest.docx"
        source.write_bytes(raw)
        dest.write_bytes(raw)
        evidence = {} if name == "docx_receiver_unavailable" else {
            "ART-001": dest}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": source}, receiver_files=evidence)


class DocxParagraphTests(unittest.TestCase):
    def test_actual_docx_paragraphs(self):
        for name, truth, expected in DOCX_CASES:
            with self.subTest(case=name):
                result = run_docx_case(name)
                codes = {item["code"] for item in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                    self.assertNotIn("EXACT_BYTES_MATCH", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                    self.assertNotIn("EXACT_BYTES_MATCH", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)

    def test_hash_is_stable_for_simple_paragraph(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.docx"
            path.write_bytes(build_docx(["Start", "Protected middle", "End"]))
            self.assertEqual(
                hashlib.sha256(b"Protected middle").hexdigest(),
                docx_paragraph_hash(path, 1))


if __name__ == "__main__":
    unittest.main()
