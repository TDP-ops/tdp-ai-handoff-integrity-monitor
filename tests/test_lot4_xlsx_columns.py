"""Real XLSX first-row column verification via the strict public API.

Only literal first-row string headers are interpreted. Other cell types
and untrusted/missing bytes yield UNKNOWN, not a false header PASS.
"""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load
from test_lot4_xlsx_sheets import build_xlsx

COLUMN_CASES = (
    ("xlsx_columns_present", "clean", "PASS"),
    ("xlsx_columns_shared_strings", "clean", "PASS"),
    ("xlsx_required_column_missing", "violation", "ALERT"),
    ("xlsx_required_column_sheet_missing", "violation", "ALERT"),
    ("xlsx_formula_header_unverified", "evidence_unavailable", "UNKNOWN"),
    ("xlsx_receiver_columns_unavailable", "evidence_unavailable", "UNKNOWN"),
)


def build_header_workbook(name):
    raw = build_xlsx(sheet_name="Archive" if name == "xlsx_required_column_sheet_missing" else "Data")
    if name == "xlsx_columns_shared_strings":
        cells = '<c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
    elif name == "xlsx_required_column_missing":
        cells = '<c r="A1" t="inlineStr"><is><t>record_id</t></is></c>'
    elif name == "xlsx_formula_header_unverified":
        cells = '<c r="A1" t="str"><f>CONCAT("record","_id")</f><v>record_id</v></c><c r="B1" t="inlineStr"><is><t>amount</t></is></c>'
    else:
        cells = '<c r="A1" t="inlineStr"><is><t>record_id</t></is></c><c r="B1" t="inlineStr"><is><t>amount</t></is></c>'
    worksheet = (
        '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1">' + cells + '</row></sheetData></worksheet>'
    )
    shared_strings = (
        '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<si><t>record_id</t></si><si><t>amount</t></si></sst>'
    )
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as source:
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as dest:
            for member in source.namelist():
                dest.writestr(
                    member, worksheet if member == "xl/worksheets/sheet1.xml"
                    else source.read(member))
            if name == "xlsx_columns_shared_strings":
                dest.writestr("xl/sharedStrings.xml", shared_strings)
    return result.getvalue()


def run_xlsx_column_case(name):
    if name not in (case[0] for case in COLUMN_CASES):
        raise ValueError("Unknown XLSX header test: " + name)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    content = build_header_workbook(name)
    for manifest in (sent, received):
        artifact = manifest["artifacts"][0]
        artifact["kind"] = "xlsx"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [{
                "check_type": "xlsx_required_columns",
                "sheet_name": "Data",
                "column_names": ["record_id", "amount"],
            }],
        }
        artifact["content_sha256"] = hashlib.sha256(content).hexdigest()
    with tempfile.TemporaryDirectory() as folder:
        sender = Path(folder) / "source.xlsx"
        receiver = Path(folder) / "receiver.xlsx"
        sender.write_bytes(content)
        receiver.write_bytes(content)
        receiver_files = {} if name == "xlsx_receiver_columns_unavailable" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=receiver_files)


class XlsxColumnTests(unittest.TestCase):
    def test_real_xlsx_header_checks(self):
        for name, truth, expected in COLUMN_CASES:
            with self.subTest(case=name):
                result = run_xlsx_column_case(name)
                codes = {finding["code"] for finding in result["findings"]}
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
