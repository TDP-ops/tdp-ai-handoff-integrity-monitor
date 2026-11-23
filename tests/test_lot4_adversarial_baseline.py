"""Lot 4 adversarial baseline: execute real local byte observations.

This suite deliberately separates local deterministic outcomes from remote
custody and unsupported multimodal/structural checks. No client content.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


CASES = (
    ("equal_local_bytes", "PASS", None),
    ("equal_empty_bytes", "PASS", None),
    ("equal_binary_bytes", "PASS", None),
    ("equal_multichunk_bytes", "PASS", None),
    ("changed_receiver_bytes", "ALERT", "HASH_MISMATCH"),
    ("missing_receiver_bytes", "UNKNOWN", "UNVERIFIABLE"),
    ("receiver_not_checked", "UNKNOWN", "UNVERIFIABLE"),
)


class AdversarialBaselineTests(unittest.TestCase):
    def setUp(self):
        self.plan = load("run-plan.json")
        self.sent = load("pass-sent.json")
        self.received = load("pass-received.json")

    def run_case(self, scenario):
        sent = copy.deepcopy(self.sent)
        received = copy.deepcopy(self.received)
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "original.bin"
            receiver_file = Path(folder) / "receiver.bin"
            payload = {
                "equal_empty_bytes": b"",
                "equal_binary_bytes": bytes(range(256)) * 3,
                "equal_multichunk_bytes": b"lot4" * 210000,
            }.get(scenario, b"lot4 synthetic artifact version one")
            original.write_bytes(payload)
            receiver_file.write_bytes(
                b"lot4 synthetic artifact version TWO"
                if scenario == "changed_receiver_bytes"
                else original.read_bytes()
            )
            sent["artifacts"][0]["content_sha256"] = hashlib.sha256(
                original.read_bytes()).hexdigest()
            received["artifacts"][0]["content_sha256"] = hashlib.sha256(
                receiver_file.read_bytes()).hexdigest()
            if scenario == "receiver_not_checked":
                received["artifacts"][0]["observation"]["access"] = "not_checked"
            receiver_paths = {} if scenario == "missing_receiver_bytes" else {
                "ART-001": receiver_file
            }
            return compare_handoff_validated(
                self.plan, sent, received,
                sender_files={"ART-001": original},
                receiver_files=receiver_paths,
            )

    def test_adversarial_matrix_expected_verdicts(self):
        # Each verdict is observed by executing the strict engine, not read
        # from the lot 1 list of unimplemented acceptance expectations.
        for name, expected, code in CASES:
            with self.subTest(scenario=name):
                output = self.run_case(name)
                self.assertEqual(expected, output["verdict"])
                if code is not None:
                    self.assertIn(code, {item["code"] for item in output["findings"]})

    def test_equal_bytes_only_yield_local_pass(self):
        output = self.run_case("equal_local_bytes")
        self.assertEqual("PASS", output["verdict"])
        self.assertIn("EXACT_BYTES_MATCH",
                      {item["code"] for item in output["findings"]})

    def test_clean_byte_controls_do_not_create_false_alerts(self):
        for name in ("equal_empty_bytes", "equal_binary_bytes",
                     "equal_multichunk_bytes"):
            with self.subTest(scenario=name):
                result = self.run_case(name)
                self.assertEqual("PASS", result["verdict"])
                self.assertIn("EXACT_BYTES_MATCH",
                              {item["code"] for item in result["findings"]})

    def test_no_false_pass_for_unverified_cases(self):
        for name in ("changed_receiver_bytes", "missing_receiver_bytes",
                     "receiver_not_checked"):
            with self.subTest(scenario=name):
                output = self.run_case(name)
                self.assertNotEqual("PASS", output["verdict"])
                self.assertNotIn("EXACT_BYTES_MATCH",
                                 {item["code"] for item in output["findings"]})


if __name__ == "__main__":
    unittest.main()
