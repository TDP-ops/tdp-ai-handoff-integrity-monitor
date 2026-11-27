"""Lot 5: synthetic receiver and verifier execute in distinct OS processes.

Receiver private key exists only in receiver subprocess memory. The test
harness independently pins the ephemeral public key before verifying a
receipt across a process boundary. This DOES NOT authenticate remote hosts.
"""
import hashlib
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from handoff_monitor.custody import compare_handoff_with_custody
from handoff_monitor.receiver_registry import ReceiverTrustRegistry
from test_lot4_structural_abstentions import load


def _recipient_process(pipe, plan, sent, received, file_path):
    """Isolated process owns private key; sends only public key + receipt."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from handoff_monitor.receiver_adapter import receive_and_sign

        key = Ed25519PrivateKey.generate()
        pub = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        signed = receive_and_sign(
            plan=plan, sent=sent, received=received, artifact_id="ART-001",
            file_path=file_path, receiver_id="B", key_id="K-SYNTH",
            private_key=key)
        pipe.send(("ok", pub, signed))
    except Exception as error:
        pipe.send(("error", type(error).__name__, str(error)))
    finally:
        pipe.close()


class SeparateProcessEvidenceTests(unittest.TestCase):
    def test_two_processes_transfer_only_public_key_and_signed_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            sender = directory / "sender.bin"
            receiver = directory / "receiver.bin"
            raw = b"two-process synthetic recipient evidence"
            sender.write_bytes(raw)
            receiver.write_bytes(raw)
            plan, sent, received = (
                load("run-plan.json"), load("pass-sent.json"),
                load("pass-received.json"))
            for event in (sent, received):
                artifact = event["artifacts"][0]
                artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
                artifact["size_bytes"] = len(raw)
            ctx = multiprocessing.get_context("spawn")
            parent, child = ctx.Pipe(duplex=False)
            process = ctx.Process(
                target=_recipient_process,
                args=(child, plan, sent, received, str(receiver)))
            process.start()
            child.close()
            try:
                self.assertTrue(parent.poll(20), "Receiver process failed to answer")
                result = parent.recv()
            finally:
                parent.close()
                process.join(5)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            self.assertEqual(0, process.exitcode)
            self.assertEqual("ok", result[0], result)
            _, public_key, receipt = result
            self.assertEqual(32, len(public_key))
            self.assertEqual({"body", "signature"}, set(receipt))
            self.assertNotIn("private_key", repr(receipt))
            registry = ReceiverTrustRegistry(directory / "verifier.sqlite")
            # Test harness pins key in verifier domain: production onboarding
            # must authenticate this independently, not from the receipt.
            # In this synthetic fixture, the verifier-side pin is a separately
            # recorded expected fingerprint. Actual independent enrollment is
            # an operational precondition, NOT proven by this test harness.
            verifier_policy_pin = hashlib.sha256(public_key).hexdigest()
            registry.enroll_pinned_key(
                receiver_id="B", key_id="K-SYNTH", public_key=public_key,
                independently_expected_sha256=verifier_policy_pin)
            outcome = compare_handoff_with_custody(
                plan, sent, received,
                sender_files={"ART-001": sender},
                receiver_files={"ART-001": receiver},
                registry=registry,
                receipts={"ART-001": receipt},
                expected_receiver_id="B")
            self.assertEqual("VERIFIED_SIGNATURES", outcome["custody_status"])
            self.assertEqual("UNKNOWN", outcome["verdict"])
            self.assertEqual("ALERT", compare_handoff_with_custody(
                plan, sent, received,
                sender_files={"ART-001": sender},
                receiver_files={"ART-001": receiver},
                registry=registry,
                receipts={"ART-001": receipt},
                expected_receiver_id="B")["verdict"])


if __name__ == "__main__":
    unittest.main()
