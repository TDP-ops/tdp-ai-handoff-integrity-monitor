"""Local XLSX required-sheet checks using valid synthetic OOXML packages.

The checks prove only sheet names in a bounded observed workbook. They do not
parse cell data, formulas or authenticate a remote receiver.
"""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

XLSX_CASES = (
    ("xlsx_required_sheets_present", "clean", "PASS"),
    ("xlsx_required_sheet_missing", "violation", "ALERT"),
    ("xlsx_missing_worksheet_part", "evidence_unavailable", "UNKNOWN"),
    ("xlsx_corrupt_archive", "evidence_unavailable", "UNKNOWN"),
    ("xlsx_receiver_unavailable", "evidence_unavailable", "UNKNOWN"),
)


def build_xlsx(sheet_name="Data", *, missing_part=False):
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="' + sheet_name + '" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
        ' Target="worksheets/sheet1.xml"/></Relationships>'
    )
    types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '</Types>'
    )
    root_rel = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="root"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="xl/workbook.xml"/></Relationships>'
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("_rels/.rels", root_rel)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        if not missing_part:
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                '<?xml version="1.0"?><worksheet'
                ' xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData/></worksheet>')
    return stream.getvalue()


def run_xlsx_case(name):
    if name not in (case[0] for case in XLSX_CASES):
        raise ValueError("Unknown XLSX case: " + name)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    sheet = "Archive" if name == "xlsx_required_sheet_missing" else "Data"
    raw = build_xlsx(
        sheet, missing_part=(name == "xlsx_missing_worksheet_part"))
    if name == "xlsx_corrupt_archive":
        raw = b"not an xlsx package"
    for event in (sent, received):
        artifact = event["artifacts"][0]
        artifact["kind"] = "xlsx"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [
                {"check_type": "xlsx_required_sheets", "sheet_names": ["Data"]}],
        }
        artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        sender = Path(directory) / "sender.xlsx"
        receiver = Path(directory) / "receiver.xlsx"
        sender.write_bytes(raw)
        receiver.write_bytes(raw)
        receiver_files = {} if name == "xlsx_receiver_unavailable" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=receiver_files)


class XlsxSheetTests(unittest.TestCase):
    def test_local_ooxml_sheet_names(self):
        for name, truth, expected in XLSX_CASES:
            with self.subTest(case=name):
                result = run_xlsx_case(name)
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

    def test_duplicate_sheet_names_rejected(self):
        from handoff_monitor.xlsx_structure import xlsx_sheet_names
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.xlsx"
            raw = build_xlsx()
            with zipfile.ZipFile(io.BytesIO(raw)) as src:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
                    for member in src.namelist():
                        data = src.read(member)
                        if member == "xl/workbook.xml":
                            data = data.replace(
                                b"</sheets>",
                                b'<sheet name="Data" sheetId="2" r:id="rId1"/></sheets>')
                        dst.writestr(member, data)
                path.write_bytes(buf.getvalue())
            with self.assertRaises(ValueError):
                xlsx_sheet_names(path)


if __name__ == "__main__":
    unittest.main()
