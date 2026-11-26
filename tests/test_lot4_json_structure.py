"""Real RFC 6901 JSON Pointer checks via the public strict handoff API.

These observations check local JSON structure, not semantic equivalence,
independently authenticated remote custody or the entire dataset.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load


JSON_CASES = (
    ("json_nested_pointer_present", "clean", "PASS"),
    ("json_escaped_pointer_present", "clean", "PASS"),
    ("json_missing_pointer", "violation", "ALERT"),
    ("json_duplicate_keys", "evidence_unavailable", "UNKNOWN"),
    ("json_invalid_utf8", "evidence_unavailable", "UNKNOWN"),
    ("json_receiver_missing", "evidence_unavailable", "UNKNOWN"),
)


def run_json_case(name):
    if name not in (entry[0] for entry in JSON_CASES):
        raise ValueError("Unknown JSON case: " + name)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    pointer = "/items/0/id"
    content = b'{"items":[{"id":1}]}'
    if name == "json_escaped_pointer_present":
        pointer = "/a~1b/~0name"
        content = b'{"a/b":{"~name":true}}'
    elif name == "json_missing_pointer":
        content = b'{"items":[{"other":1}]}'
    elif name == "json_duplicate_keys":
        content = b'{"items":[{"id":1}],"items":[{"id":2}]}'
    elif name == "json_invalid_utf8":
        content = b'{"items":[{"id":"\xff"}]}'
    for event in (sent, received):
        artifact = event["artifacts"][0]
        artifact["kind"] = "json"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [
                {"check_type": "json_required_pointer", "pointer": pointer}
            ],
        }
        artifact["content_sha256"] = hashlib.sha256(content).hexdigest()
    with tempfile.TemporaryDirectory() as td:
        sender = Path(td) / "sender.json"
        receiver = Path(td) / "receiver.json"
        sender.write_bytes(content)
        receiver.write_bytes(content)
        receiver_files = {} if name == "json_receiver_missing" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=receiver_files)


class JsonPointerTests(unittest.TestCase):
    def test_real_json_pointer_evaluation(self):
        for name, truth, expected in JSON_CASES:
            with self.subTest(case=name):
                result = run_json_case(name)
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

    def test_json_root_and_array_index_rules(self):
        from handoff_monitor.structure import _json_pointer_exists
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.json"
            path.write_text('{"items":[{"id":null}]}', encoding="utf-8")
            self.assertTrue(_json_pointer_exists(path, ""))
            self.assertTrue(_json_pointer_exists(path, "/items/0/id"))
            self.assertFalse(_json_pointer_exists(path, "/items/00/id"))
            self.assertFalse(_json_pointer_exists(path, "/items/-/id"))


if __name__ == "__main__":
    unittest.main()
