"""Bounded classic-xref PDF /Pages tree evaluation via strict public API.

This is intentionally not a general PDF parser or page-content verifier.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

PDF_CASES = (
    ("pdf_two_pages_present", "clean", "PASS"),
    ("pdf_only_one_page", "violation", "ALERT"),
    ("pdf_false_count_declaration", "evidence_unavailable", "UNKNOWN"),
    ("pdf_truncated_xref", "evidence_unavailable", "UNKNOWN"),
    ("pdf_receiver_missing", "evidence_unavailable", "UNKNOWN"),
)


def make_pdf(pages=2, *, false_count=False):
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (b"<< /Type /Pages /Kids [" +
         b" ".join(f"{i} 0 R".encode() for i in range(3, 3 + pages)) +
         b"] /Count " + str(pages + (1 if false_count else 0)).encode() +
         b" >>"),
    ]
    for _ in range(pages):
        bodies.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>")
    raw = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for num, body in enumerate(bodies, start=1):
        offsets.append(len(raw))
        raw.extend(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = len(raw)
    raw.extend(f"xref\n0 {len(offsets)}\n".encode())
    raw.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        raw.extend(f"{offset:010} 00000 n \n".encode())
    raw.extend(b"trailer\n<< /Size " + str(len(offsets)).encode() +
               b" /Root 1 0 R >>\nstartxref\n" +
               str(xref_offset).encode() + b"\n%%EOF\n")
    return bytes(raw)


def run_pdf_case(name):
    if name not in (row[0] for row in PDF_CASES):
        raise ValueError("Unknown PDF scenario: " + name)
    raw = make_pdf(
        1 if name == "pdf_only_one_page" else 2,
        false_count=name == "pdf_false_count_declaration")
    if name == "pdf_truncated_xref":
        raw = raw.replace(b"xref\n", b"xxxx\n", 1)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    for manifest in (sent, received):
        artifact = manifest["artifacts"][0]
        artifact["kind"] = "pdf"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [
                {"check_type": "pdf_min_pages", "min_pages": 2}],
        }
        artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "sender.pdf"
        receiver = Path(folder) / "receiver.pdf"
        source.write_bytes(raw)
        receiver.write_bytes(raw)
        receiver_files = {} if name == "pdf_receiver_missing" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": source}, receiver_files=receiver_files)


class PdfPageTests(unittest.TestCase):
    def test_real_pdf_page_tree(self):
        for name, truth, expected in PDF_CASES:
            with self.subTest(case=name):
                result = run_pdf_case(name)
                codes = {entry["code"] for entry in result["findings"]}
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

    def test_page_count_uses_tree_not_keyword_occurrences(self):
        from handoff_monitor.pdf_structure import pdf_page_count
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.pdf"
            path.write_bytes(make_pdf(2))
            self.assertEqual(2, pdf_page_count(path))


if __name__ == "__main__":
    unittest.main()
