"""Real UTF-8 line segment assertions via the validated public API."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from handoff_monitor.text_structure import TEXT_EXTRACTOR_ID, text_line_hash
from test_lot4_structural_abstentions import load

TEXT_CASES = (
    ("text_middle_line_preserved", "clean", "PASS"),
    ("text_middle_line_modified", "violation", "ALERT"),
    ("text_middle_line_removed", "violation", "ALERT"),
    ("text_invalid_encoding", "evidence_unavailable", "UNKNOWN"),
    ("text_unsupported_locator", "evidence_unavailable", "UNKNOWN"),
    ("text_extractor_mismatch", "evidence_unavailable", "UNKNOWN"),
    ("text_receiver_unavailable", "evidence_unavailable", "UNKNOWN"),
)


def run_text_case(name):
    if name not in (case[0] for case in TEXT_CASES):
        raise ValueError("Unknown text case " + name)
    raw = b"begin\nprotected middle\nend\n"
    if name == "text_middle_line_modified":
        raw = b"begin\nmodified middle\nend\n"
    elif name == "text_middle_line_removed":
        raw = b"begin\n"
    elif name == "text_invalid_encoding":
        raw = b"begin\n\xff\nend\n"
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    check = {
        "check_type": "text_required_segment_sha256",
        "segment_locator": ("line:0002" if name == "text_unsupported_locator"
                            else "line:2"),
        "extracted_segment_sha256": hashlib.sha256(b"protected middle").hexdigest(),
        "extractor_id": ("unsupported-extractor" if name == "text_extractor_mismatch"
                         else TEXT_EXTRACTOR_ID),
    }
    for manifest in (sent, received):
        artifact = manifest["artifacts"][0]
        artifact["kind"] = "text"
        artifact["checks"] = {"exact_bytes": True, "required_structure": [check]}
        artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as folder:
        sender = Path(folder) / "sender.txt"
        receiver = Path(folder) / "receiver.txt"
        sender.write_bytes(raw)
        receiver.write_bytes(raw)
        paths = {} if name == "text_receiver_unavailable" else {"ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=paths)


class TextSegmentTests(unittest.TestCase):
    def test_segment_outcomes(self):
        for name, truth, expected in TEXT_CASES:
            with self.subTest(name=name):
                result = run_text_case(name)
                codes = {item["code"] for item in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)

    def test_lf_line_digest_is_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "text.txt"
            path.write_bytes(b"first\nprotected middle\nlast\n")
            self.assertEqual(hashlib.sha256(b"protected middle").hexdigest(),
                             text_line_hash(path, "line:2"))


if __name__ == "__main__":
    unittest.main()
