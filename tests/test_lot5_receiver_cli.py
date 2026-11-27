"""End-to-end receiver/verifier CLI in separate subprocesses and directories.

All inputs synthetic. The harness separately prepares expected context and
the approved fingerprint, but does NOT authenticate an external human/host.
No private-key bytes are returned on stdout or included in signed evidence.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_lot4_structural_abstentions import load


class ReceiverVerifierCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receiver = self.root / "receiver_domain"
        self.verifier = self.root / "verifier_domain"
        self.receiver.mkdir()
        self.verifier.mkdir()
        self.private = self.receiver / "private.key"
        self.public = self.receiver / "public.key"
        self.receipt = self.receiver / "receipt.json"
        self.db = self.verifier / "trust.sqlite"
        self.artifact = self.receiver / "observed.bin"
        self.raw = b"synthetic receiver-owned bytes for cross-process CLI"
        self.artifact.write_bytes(self.raw)
        self.docs = {}
        self.plan, self.sent, self.received = (
            load("run-plan.json"), load("pass-sent.json"),
            load("pass-received.json"))
        for event in (self.sent, self.received):
            event["artifacts"][0]["content_sha256"] = hashlib.sha256(self.raw).hexdigest()
            event["artifacts"][0]["size_bytes"] = len(self.raw)
        for name, obj in (("plan", self.plan), ("sent", self.sent),
                          ("received", self.received)):
            path = self.receiver / (name + ".json")
            path.write_text(json.dumps(obj), encoding="utf-8")
            self.docs[name] = path
        expected = {
            "receiver_id": "B",
            "content_sha256": hashlib.sha256(self.raw).hexdigest(),
            "size_bytes": len(self.raw),
            "run_id": self.plan["run_id"],
            "handoff_id": self.sent["handoff_id"],
            "contract_id": self.sent["contract_id"],
            "contract_version": self.sent["contract_version"],
            "from_step": self.sent["from_step"],
            "to_step": self.sent["to_step"],
            "sent_event_id": self.sent["event_id"],
            "received_event_id": self.received["event_id"],
            "artifact_id": "ART-001",
            "artifact_version_id": self.received["artifacts"][0]["artifact_version_id"],
            "attempt_number": 1,
        }
        self.expected = self.verifier / "approved-context.json"
        self.expected.write_text(json.dumps(expected), encoding="utf-8")

    def cli(self, *args, success=True):
        completed = subprocess.run(
            [sys.executable, "-m", "handoff_monitor.receiver_cli", *map(str, args)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=15)
        if success:
            self.assertEqual(0, completed.returncode, completed.stderr)
            return json.loads(completed.stdout)
        self.assertNotEqual(0, completed.returncode)
        return json.loads(completed.stdout or completed.stderr)

    def initialize(self):
        return self.cli(
            "receiver-init", "--private-key", self.private,
            "--public-key", self.public)

    def enroll(self, pin):
        return self.cli(
            "verifier-enroll", "--registry", self.db,
            "--public-key", self.public,
            "--receiver-id", "B", "--key-id", "KEY1",
            "--approved-fingerprint", pin)

    def sign(self):
        return self.cli(
            "receiver-sign", "--private-key", self.private,
            "--plan", self.docs["plan"],
            "--sent", self.docs["sent"],
            "--received", self.docs["received"],
            "--artifact-id", "ART-001",
            "--file", self.artifact,
            "--receiver-id", "B", "--key-id", "KEY1",
            "--output", self.receipt)

    def verify(self, success=True):
        return self.cli(
            "verifier-verify", "--registry", self.db,
            "--receipt", self.receipt, "--expected", self.expected,
            success=success)

    def test_separate_commands_signed_context_and_durable_replay(self):
        initialized = self.initialize()
        self.assertEqual("RECEIVER_KEY_CREATED", initialized["status"])
        if os.name == "posix":
            self.assertEqual(0o600, self.private.stat().st_mode & 0o777)
        # Test-only independently staged verifier policy: NOT a real trust
        # onboarding channel. No pin is learned from a signed receipt.
        approved_pin = initialized["public_key_sha256"]
        self.assertEqual("PINNED_KEY_ENROLLED", self.enroll(approved_pin)["status"])
        self.assertEqual("RECEIPT_SIGNED", self.sign()["status"])
        signed = self.receipt.read_text(encoding="utf-8")
        self.assertNotIn(self.private.read_bytes().hex(), signed)
        self.assertEqual("VERIFIED_SIGNATURE", self.verify()["status"])
        replay = self.verify(success=False)
        self.assertEqual("ALERT", replay["status"])
        self.assertEqual("receipt_replay_or_fork", replay["reason"])

    def test_wrong_preapproved_pin_cannot_enroll(self):
        self.initialize()
        failure = self.enroll("0" * 64)
        # Invalid verifier enrollment must not be a success.
        self.assertNotEqual("PINNED_KEY_ENROLLED", failure["status"])

    def test_no_private_key_replacement_and_missing_context(self):
        self.initialize()
        self.cli("receiver-init", "--private-key", self.private,
                 "--public-key", self.public, success=False)
        pin = hashlib.sha256(self.public.read_bytes()).hexdigest()
        self.enroll(pin)
        self.sign()
        self.expected.write_text('{"receiver_id": "B"}', encoding="utf-8")
        outcome = self.verify(success=False)
        self.assertEqual("UNKNOWN", outcome["status"])


if __name__ == "__main__":
    unittest.main()
