"""Real UTF-8 CSV header evaluation through the strict handoff API.

Checks only required headers; it does NOT validate the whole CSV or prove
authenticity of the receiver-side observation.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

CSV_CASES = (
    ("csv_columns_present", "clean", "PASS"),
    ("csv_required_column_absent", "violation", "ALERT"),
    ("csv_duplicate_header", "evidence_unavailable", "UNKNOWN"),
    ("csv_invalid_utf8", "evidence_unavailable", "UNKNOWN"),
    ("csv_receiver_missing", "evidence_unavailable", "UNKNOWN"),
)


def run_csv_case(name):
    if name not in (x[0] for x in CSV_CASES):
        raise ValueError("Unknown CSV case: " + name)
    plan, sent, received = (load("run-plan.json"),
                            load("pass-sent.json"),
                            load("pass-received.json"))
    for event in (sent, received):
        artifact = event["artifacts"][0]
        artifact["kind"] = "csv"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [
                {"check_type": "csv_required_columns",
                 "column_names": ["record_id", "amount"]}
            ]
        }
    content = {
        "csv_columns_present": b"record_id,amount\n1,25\n",
        "csv_required_column_absent": b"record_id,description\n1,hello\n",
        "csv_duplicate_header": b"record_id,record_id\n1,2\n",
        "csv_invalid_utf8": b"record_id,\xff\n",
        "csv_receiver_missing": b"record_id,amount\n1,25\n",
    }[name]
    with tempfile.TemporaryDirectory() as td:
        original = Path(td) / "source.csv"
        receiver = Path(td) / "receiver.csv"
        original.write_bytes(content)
        receiver.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        for event in (sent, received):
            event["artifacts"][0]["content_sha256"] = sha
        receiver_files = {} if name == "csv_receiver_missing" else {"ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": original}, receiver_files=receiver_files)


class CsvRequiredColumnsTests(unittest.TestCase):
    def test_real_header_evaluations(self):
        for name, truth, expected in CSV_CASES:
            with self.subTest(name=name):
                result = run_csv_case(name)
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


if __name__ == "__main__":
    unittest.main()
