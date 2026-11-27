"""Lot 5 persistent registry and standalone receiver boundary smoke tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from handoff_monitor.receiver_evidence import create_receiver_receipt
from handoff_monitor.receiver_registry import ReceiverTrustRegistry


def raw_public(private):
    return private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


class DurableRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "trust.sqlite"
        self.payload = self.root / "received.bin"
        self.payload.write_bytes(b"receiver domain synthetic payload")
        self.private = Ed25519PrivateKey.generate()
        self.registry = ReceiverTrustRegistry(self.db)
        self.registry.enroll_key(receiver_id="B", key_id="K1",
                                 public_key=raw_public(self.private))
        self.params = dict(
            receiver_id="B", key_id="K1",
            receipt_id="R1", run_id="RUN1", handoff_id="H1",
            contract_id="C1", contract_version="1", from_step="A",
            to_step="B", sent_event_id="E1", received_event_id="E2",
            artifact_id="ART1", artifact_version_id="V1",
            attempt_number=1)
        self.expected = {"receiver_id": "B",
                         "content_sha256": __import__("hashlib").sha256(
                             self.payload.read_bytes()).hexdigest(),
                         **{k: self.params[k] for k in (
            "run_id", "handoff_id", "contract_id", "contract_version",
            "from_step", "to_step", "sent_event_id", "received_event_id",
            "artifact_id", "artifact_version_id", "attempt_number")}}

    def receipt(self, **overrides):
        params = dict(self.params)
        params.update(overrides)
        return create_receiver_receipt(file_path=self.payload,
                                       private_key=self.private, **params)

    def test_persistent_replay_is_rejected_across_reopen(self):
        receipt = self.receipt()
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            receipt, expected=self.expected)["status"])
        restarted = ReceiverTrustRegistry(self.db)
        result = restarted.verify_and_record(receipt, expected=self.expected)
        self.assertEqual(("ALERT", "receipt_replay_or_fork"),
                         (result["status"], result["reason"]))

    def test_distinct_id_cannot_reissue_same_attempt(self):
        self.registry.verify_and_record(self.receipt(), expected=self.expected)
        changed = self.receipt(receipt_id="R2")
        result = self.registry.verify_and_record(changed, expected=self.expected)
        self.assertEqual("receipt_replay_or_fork", result["reason"])

    def test_bad_context_does_not_consume_receipt(self):
        bad = dict(self.expected)
        bad["handoff_id"] = "WRONG"
        receipt = self.receipt()
        self.assertEqual("ALERT", self.registry.verify_and_record(
            receipt, expected=bad)["status"])
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            receipt, expected=self.expected)["status"])

    def test_bad_signature_does_not_consume_receipt(self):
        receipt = self.receipt()
        broken = copy.deepcopy(receipt)
        broken["signature"] = "AA=="
        self.assertEqual("ALERT", self.registry.verify_and_record(
            broken, expected=self.expected)["status"])
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            receipt, expected=self.expected)["status"])

    def test_revoked_key_rejects_receipt(self):
        receipt = self.receipt()
        self.registry.revoke_key(receiver_id="B", key_id="K1")
        result = self.registry.verify_and_record(receipt, expected=self.expected)
        self.assertEqual(("ALERT", "revoked_receiver_key"),
                         (result["status"], result["reason"]))

    def test_key_rotation_revokes_old_without_new_key_collision(self):
        new_private = Ed25519PrivateKey.generate()
        self.registry.rotate_key(receiver_id="B", old_key_id="K1",
                                 new_key_id="K2", new_public_key=raw_public(new_private))
        self.assertEqual("revoked_receiver_key", self.registry.verify_and_record(
            self.receipt(), expected=self.expected)["reason"])
        params = dict(self.params, key_id="K2")
        receipt = create_receiver_receipt(file_path=self.payload,
                                         private_key=new_private, **params)
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            receipt, expected=self.expected)["status"])

    def test_failed_rotation_preserves_active_key(self):
        with self.assertRaises(ValueError):
            self.registry.rotate_key(receiver_id="B", old_key_id="MISSING",
                                     new_key_id="K2", new_public_key=raw_public(
                                         Ed25519PrivateKey.generate()))
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            self.receipt(), expected=self.expected)["status"])

    def test_unknown_key_stays_unknown(self):
        receiver = ReceiverTrustRegistry(self.root / "empty.sqlite")
        result = receiver.verify_and_record(self.receipt(), expected=self.expected)
        self.assertEqual("UNKNOWN", result["status"])

    def test_verifier_file_mismatch_blocks_persistence(self):
        original = self.receipt()
        self.payload.write_bytes(b"tampered after receiver observation")
        result = self.registry.verify_and_record(original, expected=self.expected,
                                                 observed_file=self.payload)
        self.assertEqual("observed_bytes_mismatch", result["reason"])
        self.assertEqual("VERIFIED_SIGNATURE", self.registry.verify_and_record(
            original, expected=self.expected)["status"])

    def test_symlink_registry_path_rejected(self):
        alias = self.root / "alias.sqlite"
        alias.symlink_to(self.db)
        with self.assertRaises(ValueError):
            ReceiverTrustRegistry(alias)

    def test_out_of_band_pin_rejects_substituted_key(self):
        from hashlib import sha256
        valid = Ed25519PrivateKey.generate()
        attacker = Ed25519PrivateKey.generate()
        pin = sha256(raw_public(valid)).hexdigest()
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.registry.enroll_pinned_key(
                receiver_id="B", key_id="K2",
                public_key=raw_public(attacker),
                independently_expected_sha256=pin)
        self.registry.enroll_pinned_key(
            receiver_id="B", key_id="K2",
            public_key=raw_public(valid),
            independently_expected_sha256=pin)

    def test_receipt_cannot_supply_enrollment_authority(self):
        from hashlib import sha256
        attacker = Ed25519PrivateKey.generate()
        false_pin = sha256(raw_public(self.private)).hexdigest()
        with self.assertRaises(ValueError):
            self.registry.enroll_pinned_key(
                receiver_id="B", key_id="K-UNTRUSTED",
                public_key=raw_public(attacker),
                independently_expected_sha256=false_pin)
        with self.registry._connection() as connection:
            rows = connection.execute(
                "SELECT count(*) FROM trusted_keys WHERE key_id=?",
                ("K-UNTRUSTED",)).fetchone()[0]
        self.assertEqual(0, rows)

    def test_invalid_pinned_digest_fail_closed(self):
        public_key = raw_public(Ed25519PrivateKey.generate())
        for bad in ("", "0" * 63, "z" * 64, None):
            with self.subTest(pin=bad):
                with self.assertRaises(ValueError):
                    self.registry.enroll_pinned_key(
                        receiver_id="B", key_id="K-BAD",
                        public_key=public_key,
                        independently_expected_sha256=bad)

    def test_key_enrollment_identity_is_immutable(self):
        with self.assertRaises(Exception):
            self.registry.enroll_key(receiver_id="B", key_id="K1",
                                     public_key=raw_public(Ed25519PrivateKey.generate()))


if __name__ == "__main__":
    unittest.main()
