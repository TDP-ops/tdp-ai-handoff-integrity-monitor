"""Lot 5 custody join: local byte integrity stays distinct from signed receipt.

All keys, files, and roles are synthetic, running on one test host. A valid
receipt never produces an authenticated remote-delivery PASS.
"""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from handoff_monitor.custody import compare_handoff_with_custody
from handoff_monitor.receiver_adapter import receive_and_sign
from handoff_monitor.receiver_registry import ReceiverTrustRegistry
from test_lot4_structural_abstentions import load


class CustodyVerdictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        self.sender = directory / "sender.bin"
        self.receiver = directory / "receiver.bin"
        raw = b"receiver independent local test bytes"
        self.sender.write_bytes(raw)
        self.receiver.write_bytes(raw)
        self.plan, self.sent, self.received = (
            load("run-plan.json"), load("pass-sent.json"),
            load("pass-received.json"))
        sha = hashlib.sha256(raw).hexdigest()
        for event in (self.sent, self.received):
            art = event["artifacts"][0]
            art["content_sha256"] = sha
            art["size_bytes"] = len(raw)
        self.private = Ed25519PrivateKey.generate()
        self.registry = ReceiverTrustRegistry(directory / "trusted.sqlite")
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.registry.enroll_key(receiver_id="B", key_id="K1", public_key=public)
        self.receipt = receive_and_sign(
            plan=self.plan, sent=self.sent, received=self.received,
            artifact_id="ART-001", file_path=self.receiver,
            receiver_id="B", key_id="K1", private_key=self.private,
        )

    def check(self, *, receipts=None, registry=None, receiver_id="B",
              sender_files=None, receiver_files=None, sent=None,
              received=None):
        return compare_handoff_with_custody(
            self.plan, sent or self.sent, received or self.received,
            sender_files=(sender_files if sender_files is not None
                          else {"ART-001": self.sender}),
            receiver_files=(receiver_files if receiver_files is not None
                            else {"ART-001": self.receiver}),
            registry=registry if registry is not None else self.registry,
            receipts=receipts if receipts is not None else {"ART-001": self.receipt},
            expected_receiver_id=receiver_id,
        )

    def test_signed_receipt_is_distinct_from_remote_delivery(self):
        result = self.check()
        self.assertEqual("VERIFIED_SIGNATURES", result["custody_status"])
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertIn(result["local_verdict"], ("PASS", "UNKNOWN"))
        self.assertEqual("VERIFIED_SIGNATURE",
                         result["receipt_results"]["ART-001"]["status"])

    def test_replayed_receipt_fails_durably(self):
        self.assertEqual("VERIFIED_SIGNATURES", self.check()["custody_status"])
        second = self.check()
        self.assertEqual("ALERT", second["verdict"])
        self.assertEqual("receipt_replay_or_fork",
                         second["receipt_results"]["ART-001"]["reason"])

    def test_receipt_wrong_receiver_alerts(self):
        result = self.check(receiver_id="WRONG")
        self.assertEqual("ALERT", result["verdict"])
        self.assertEqual("context_mismatch",
                         result["receipt_results"]["ART-001"]["reason"])

    def test_receipt_tamper_alerts(self):
        altered = copy.deepcopy(self.receipt)
        altered["body"]["content_sha256"] = "a" * 64
        result = self.check(receipts={"ART-001": altered})
        self.assertEqual("ALERT", result["verdict"])

    def test_missing_custody_configuration_abstains(self):
        result = self.check(receipts={})
        self.assertEqual("UNKNOWN", result["custody_status"])
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertEqual("required_evidence_missing",
                         result["receipt_results"]["ART-001"]["reason"])

    def test_missing_expected_receiver_abstains(self):
        result = self.check(receiver_id="")
        self.assertEqual("UNKNOWN", result["custody_status"])

    def test_local_integrity_alert_precedes_receipt(self):
        self.sender.write_bytes(b"tampered sender byte stream")
        result = self.check()
        self.assertEqual("ALERT", result["local_verdict"])
        self.assertEqual("ALERT", result["verdict"])
        self.assertEqual("NOT_EVALUATED", result["custody_status"])

    def test_no_sender_file_abstains(self):
        result = self.check(sender_files={})
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertEqual("sender_bytes_unavailable",
                         result["receipt_results"]["ART-001"]["reason"])

    def test_unexpected_receipt_artifact_alerts(self):
        result = self.check(receipts={"NOT-IN-MANIFEST": self.receipt})
        self.assertEqual("ALERT", result["custody_status"])

    def test_invalid_manifest_is_never_upgraded(self):
        received = copy.deepcopy(self.received)
        received["artifacts"][0]["artifact_version_id"] = "ALTERED-VERSION"
        result = self.check(received=received)
        self.assertEqual("ALERT", result["verdict"])
        self.assertEqual("NOT_EVALUATED", result["custody_status"])


if __name__ == "__main__":
    unittest.main()
