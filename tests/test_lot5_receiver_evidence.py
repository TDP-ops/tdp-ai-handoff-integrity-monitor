"""Lot 5 receiver receipt tests with ephemeral keys and synthetic bytes only."""
import base64
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from handoff_monitor.receiver_evidence import (
    create_receiver_receipt, verify_receiver_receipt,
)


class ReceiverEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "receiver.bin"
        self.file.write_bytes(b"synthetic receiver bytes, not customer data\n")
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trusted = {("RECEIVER-B", "KEY-B-01"): public}
        self.receipt = create_receiver_receipt(
            file_path=self.file, private_key=self.private,
            receiver_id="RECEIVER-B", key_id="KEY-B-01",
            receipt_id="RCPT-01", run_id="RUN-01", handoff_id="H-A-B",
            contract_id="C-A-B", contract_version="1", from_step="A",
            to_step="B", sent_event_id="EV-SENT-01",
            received_event_id="EV-RECV-01", artifact_id="ART-01",
            artifact_version_id="ART-01-V1", attempt_number=1,
        )
        # These fields must be independently obtained from the expected
        # sender/receiver workflow. The receipt itself is not the authority.
        self.expected = {
            key: self.receipt["body"][key] for key in (
                "run_id", "handoff_id", "contract_id", "contract_version",
                "from_step", "to_step", "sent_event_id",
                "received_event_id", "artifact_id",
                "artifact_version_id", "attempt_number",
            )
        }

    def verify(self, receipt=None, **kwargs):
        return verify_receiver_receipt(
            receipt if receipt is not None else self.receipt,
            trusted_public_keys=kwargs.pop("trusted_public_keys", self.trusted),
            expected=kwargs.pop("expected", self.expected),
            **kwargs,
        )

    def test_signed_observation_matches_independently_pinned_key_and_context(self):
        result = self.verify(observed_file=self.file)
        self.assertEqual("VERIFIED_SIGNATURE", result["status"])
        self.assertEqual(
            hashlib.sha256(self.file.read_bytes()).hexdigest(),
            self.receipt["body"]["content_sha256"],
        )
        self.assertEqual(self.file.stat().st_size, self.receipt["body"]["size_bytes"])
        self.assertEqual({"body", "signature"}, set(self.receipt))
        self.assertNotIn("private_key", json.dumps(self.receipt))

    def test_tampered_receipt_fields_cannot_verify(self):
        changed = copy.deepcopy(self.receipt)
        changed["body"]["size_bytes"] += 1
        self.assertEqual("ALERT", self.verify(changed)["status"])

    def test_tampered_signature_rejected(self):
        changed = copy.deepcopy(self.receipt)
        raw = bytearray(base64.b64decode(changed["signature"]))
        raw[2] ^= 1
        changed["signature"] = base64.b64encode(raw).decode("ascii")
        self.assertEqual("invalid_signature", self.verify(changed)["reason"])

    def test_wrong_public_key_cannot_verify(self):
        stranger = Ed25519PrivateKey.generate()
        alternate = stranger.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        result = self.verify(trusted_public_keys={("RECEIVER-B", "KEY-B-01"): alternate})
        self.assertEqual("invalid_signature", result["reason"])

    def test_missing_independent_trust_is_unknown(self):
        self.assertEqual("UNKNOWN", self.verify(trusted_public_keys={})["status"])

    def test_wrong_expected_handoff_is_alert(self):
        expected = dict(self.expected)
        expected["handoff_id"] = "H-OTHER"
        self.assertEqual("context_mismatch", self.verify(expected=expected)["reason"])

    def test_incomplete_expected_context_is_unknown(self):
        self.assertEqual(
            "UNKNOWN",
            self.verify(expected={"handoff_id": "H-A-B"})["status"],
        )

    def test_replayed_receipt_id_is_alert(self):
        result = self.verify(seen_receipt_ids={"RCPT-01"})
        self.assertEqual("receipt_replay", result["reason"])

    def test_file_drift_at_verifier_is_alert(self):
        self.file.write_bytes(b"different data")
        result = self.verify(observed_file=self.file)
        self.assertEqual("observed_bytes_mismatch", result["reason"])

    def test_missing_optional_verifier_bytes_is_unknown(self):
        result = self.verify(observed_file=Path(self.temp.name) / "missing.bin")
        self.assertEqual("verifier_file_unavailable", result["reason"])

    def test_malformed_receipt_rejected(self):
        changed = copy.deepcopy(self.receipt)
        changed["body"]["unexpected"] = "injected"
        self.assertEqual("malformed_receipt", self.verify(changed)["reason"])

    def test_private_key_not_persisted_in_fixture(self):
        # Receipts are serializable evidence; no key bytes are serialized.
        reloaded = json.loads(json.dumps(self.receipt))
        self.assertEqual("VERIFIED_SIGNATURE", self.verify(reloaded)["status"])


if __name__ == "__main__":
    unittest.main()
