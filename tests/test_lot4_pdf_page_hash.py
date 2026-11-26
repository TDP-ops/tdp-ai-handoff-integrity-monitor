"""Pinned PDF raw page-stream fingerprint regression through strict API.

Only simple PDF classic-xref and unfiltered content stream bytes supported;
tests do not claim rendered image equivalence or independent custody.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from handoff_monitor.pdf_structure import PDF_PAGE_EXTRACTOR_ID, pdf_page_hash
from test_lot4_structural_abstentions import load

PDF_HASH_CASES = (
    ("pdf_stream_hash_matches", "clean", "PASS"),
    ("pdf_stream_content_modified", "violation", "ALERT"),
    ("pdf_stream_page_missing", "violation", "ALERT"),
    ("pdf_stream_filter_unsupported", "evidence_unavailable", "UNKNOWN"),
    ("pdf_stream_unknown_extractor", "evidence_unavailable", "UNKNOWN"),
    ("pdf_stream_receiver_missing", "evidence_unavailable", "UNKNOWN"),
)


def make_pdf_stream(contents, *, pages=2, filtered=False):
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (b"<< /Type /Pages /Kids [" +
         b" ".join(f"{i} 0 R".encode() for i in range(3, 3 + pages)) +
         b"] /Count " + str(pages).encode() + b" >>"),
    ]
    for i in range(pages):
        bodies.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents " +
            str(3 + pages + i).encode() + b" 0 R >>")
    for i in range(pages):
        data = contents[i]
        header = (b"<< /Length " + str(len(data)).encode() +
                  (b" /Filter /FlateDecode" if filtered else b"") +
                  b" >>")
        bodies.append(header + b"\nstream\n" + data + b"\nendstream")
    raw = bytearray(b"%PDF-1.4\n")
    positions = [0]
    for n, body in enumerate(bodies, 1):
        positions.append(len(raw))
        raw.extend(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = len(raw)
    raw.extend(f"xref\n0 {len(positions)}\n".encode())
    raw.extend(b"0000000000 65535 f \n")
    for pos in positions[1:]:
        raw.extend(f"{pos:010} 00000 n \n".encode())
    raw.extend(
        b"trailer\n<< /Size " + str(len(positions)).encode() +
        b" /Root 1 0 R >>\nstartxref\n" +
        str(xref_offset).encode() + b"\n%%EOF\n")
    return bytes(raw)


def run_pdf_hash_case(name):
    if name not in (row[0] for row in PDF_HASH_CASES):
        raise ValueError("Unknown page-stream case: " + name)
    clean_content = [b"0 0 m 1 1 l S", b"10 10 m 20 20 l S"]
    contents = list(clean_content)
    if name == "pdf_stream_content_modified":
        contents[1] = b"10 10 m 19 20 l S"
    n_pages = 1 if name == "pdf_stream_page_missing" else 2
    raw = make_pdf_stream(
        contents[:n_pages], pages=n_pages,
        filtered=(name == "pdf_stream_filter_unsupported"))
    reference = hashlib.sha256(
        b"TDP-PDF-PAGE-RAW-V1\n0 0 200 200\x00" + clean_content[1]).hexdigest()
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"),
        load("pass-received.json"))
    for manifest in (sent, received):
        artifact = manifest["artifacts"][0]
        artifact["kind"] = "pdf"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [{
                "check_type": "pdf_required_page_sha256",
                "page_index": 1,
                "extracted_page_sha256": reference,
                "extractor_id": ("not-pinned" if name == "pdf_stream_unknown_extractor"
                                 else PDF_PAGE_EXTRACTOR_ID),
            }],
        }
        artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as folder:
        sender = Path(folder) / "sender.pdf"
        receiver = Path(folder) / "receiver.pdf"
        sender.write_bytes(raw)
        receiver.write_bytes(raw)
        receiver_files = {} if name == "pdf_stream_receiver_missing" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=receiver_files)


class PdfPageFingerprintTests(unittest.TestCase):
    def test_pinned_page_content_cases(self):
        for name, truth, expected in PDF_HASH_CASES:
            with self.subTest(case=name):
                result = run_pdf_hash_case(name)
                codes = {entry["code"] for entry in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)

    def test_fingerprint_is_deterministic(self):
        content = [b"0 0 m 1 1 l S", b"10 10 m 20 20 l S"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.pdf"
            path.write_bytes(make_pdf_stream(content))
            expected = hashlib.sha256(
                b"TDP-PDF-PAGE-RAW-V1\n0 0 200 200\x00" +
                content[1]).hexdigest()
            self.assertEqual(expected, pdf_page_hash(path, 1))


if __name__ == "__main__":
    unittest.main()
