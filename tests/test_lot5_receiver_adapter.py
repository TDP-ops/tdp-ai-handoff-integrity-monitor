"""Receiver-boundary adapter integration: synthetic files, ephemeral keys."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from handoff_monitor.receiver_adapter import receive_and_sign
from handoff_monitor.receiver_registry import ReceiverTrustRegistry
from test_lot4_structural_abstentions import load


class ReceiverAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.file = self.dir / "delivered.bin"
        self.file.write_bytes(b"synthetic independently observed receiver file")
        self.plan, self.sent, self.received = (
            load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
        sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        for event in (self.sent, self.received):
            event["artifacts"][0]["content_sha256"] = sha
            event["artifacts"][0]["size_bytes"] = self.file.stat().st_size
        self.private = Ed25519PrivateKey.generate()
        self.registry = ReceiverTrustRegistry(self.dir / "receiver-trust.sqlite")
        pub = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.registry.enroll_key(receiver_id="B", key_id="KEY1", public_key=pub)

    def receipt(self, *, sent=None, received=None, file=None):
        return receive_and_sign(
            plan=self.plan, sent=sent or self.sent, received=received or self.received,
            artifact_id="ART-001", file_path=file or self.file,
            receiver_id="B", key_id="KEY1", private_key=self.private)

    def expected(self):
        return dict(
            run_id=self.plan["run_id"], handoff_id=self.sent["handoff_id"],
            contract_id=self.sent["contract_id"],
            contract_version=self.sent["contract_version"],
            from_step=self.sent["from_step"], to_step=self.sent["to_step"],
            sent_event_id=self.sent["event_id"], received_event_id=self.received["event_id"],
            artifact_id="ART-001", artifact_version_id="ART-001-V1", attempt_number=1)

    def test_boundary_receipt_has_actual_bytes_and_verified_signature(self):
        receipt = self.receipt()
        self.assertEqual(receipt["body"]["content_sha256"],
                         hashlib.sha256(self.file.read_bytes()).hexdigest())
        result = self.registry.verify_and_record(
            receipt, expected=self.expected(), observed_file=self.file)
        self.assertEqual("VERIFIED_SIGNATURE", result["status"])

    def test_distinct_receipts_same_boundary_cannot_both_be_accepted(self):
        one, two = self.receipt(), self.receipt()
        self.assertNotEqual(one["body"]["receipt_id"], two["body"]["receipt_id"])
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            one, expected=self.expected())["status"])
        self.assertEqual("receipt_replay_or_fork", self.registry.verify_and_record(
            two, expected=self.expected())["reason"])

    def test_receiver_file_mismatch_refuses_to_sign(self):
        self.file.write_bytes(b"changed after manifest")
        with self.assertRaises(ValueError):
            self.receipt()

    def test_invalid_contract_refuses_to_sign(self):
        modified = copy.deepcopy(self.received)
        modified["contract_id"] = "UNRELATED"
        with self.assertRaises(ValueError):
            self.receipt(received=modified)

    def test_unavailable_recipient_observation_refuses_to_sign(self):
        modified = copy.deepcopy(self.received)
        modified["artifacts"][0]["observation"]["access"] = "unavailable"
        with self.assertRaises(ValueError):
            self.receipt(received=modified)

    def test_missing_file_refuses_to_sign(self):
        with self.assertRaises(ValueError):
            self.receipt(file=self.dir / "nonexistent")


if __name__ == "__main__":
    unittest.main()
