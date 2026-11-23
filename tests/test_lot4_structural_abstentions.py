"""Lot 4: declared structure checks must abstain without implemented extractors.

Synthetic bytes are deliberately not valid multimedia documents: the purpose
is to verify the control boundary, not to claim actual structure extraction.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"

STRUCTURAL_CASES = (
    ("image", {"check_type": "image_min_dimensions", "width_px": 640, "height_px": 480}),
    ("pdf", {"check_type": "pdf_min_pages", "min_pages": 2}),
    ("docx", {"check_type": "docx_required_paragraph_sha256",
              "paragraph_index": 0, "extracted_paragraph_sha256": "a" * 64,
              "extractor_id": "synthetic-unavailable"}),
    ("csv", {"check_type": "csv_required_columns", "column_names": ["record_id"]}),
    ("xlsx", {"check_type": "xlsx_required_sheets", "sheet_names": ["Data"]}),
    ("db_schema", {"check_type": "db_required_foreign_key",
                   "table_name": "items", "column_name": "owner_id",
                   "references_table": "owners", "references_column": "id"}),
    ("audio", {"check_type": "audio_min_duration_ms", "duration_ms": 1000}),
)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def structural_case(kind, structure, *, tamper=False):
    plan, sent, received = [load(n) for n in (
        "run-plan.json", "pass-sent.json", "pass-received.json")]
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "source"
        dest = Path(folder) / "receiver"
        source.write_bytes(b"synthetic source; no real media parser")
        dest.write_bytes(b"modified source" if tamper else source.read_bytes())
        for event, path in ((sent, source), (received, dest)):
            artifact = event["artifacts"][0]
            artifact["kind"] = kind
            artifact["checks"] = {
                "exact_bytes": True,
                "required_structure": [copy.deepcopy(structure)],
            }
            artifact["content_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": source},
            receiver_files={"ART-001": dest},
        )


class StructuralAbstentionTests(unittest.TestCase):
    def test_unsupported_structure_abstains_even_when_bytes_match(self):
        for kind, structure in STRUCTURAL_CASES:
            with self.subTest(kind=kind):
                result = structural_case(kind, structure)
                codes = {x["code"] for x in result["findings"]}
                self.assertEqual("UNKNOWN", result["verdict"])
                self.assertIn("UNVERIFIABLE", codes)
                self.assertNotIn("INVALID_MANIFEST", codes)
                self.assertNotIn("EXACT_BYTES_MATCH", codes)

    def test_observable_byte_tampering_overrides_unsupported_structure(self):
        kind, structure = STRUCTURAL_CASES[1]  # PDF metadata; byte comparator is generic
        result = structural_case(kind, structure, tamper=True)
        codes = {x["code"] for x in result["findings"]}
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("HASH_MISMATCH", codes)
        self.assertIn("UNVERIFIABLE", codes)
        self.assertNotIn("EXACT_BYTES_MATCH", codes)


if __name__ == "__main__":
    unittest.main()
