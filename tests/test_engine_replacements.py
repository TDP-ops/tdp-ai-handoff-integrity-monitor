"""Contract-aware replacement tests; authorization and receipt remain untrusted."""

import copy
import tempfile
import unittest
from pathlib import Path
from handoff_monitor.core import compare_handoff, digest_file

BASE_CONTRACT = {
    "contract_id": "c", "version": "1", "from_step": "A", "to_step": "B",
    "required_artifact_ids": ["old"], "accepted_versions": {"old": ["v1"], "new": ["v2"]},
    "required_rule_ids": ["KEEP"], "allowed_replacements": ["old"],
    "allowed_lifecycle_events": ["transmitted", "received", "replaced"],
}

def manifest(role, art):
    return {"run_id": "r", "handoff_id": "h", "event_id": "e-" + role,
            "from_step": "A", "to_step": "B", "contract_id": "c",
            "contract_version": "1", "manifest_role": role,
            "rule_ids": ["KEEP"], "artifacts": [art]}


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(BASE_CONTRACT)
        self.plan = {"run_id": "r", "critical_rule_ids": ["KEEP"],
                     "contracts": [self.contract]}
        self.old = {"artifact_id": "old", "artifact_version_id": "v1", "kind": "pdf",
                    "required": True, "checks": {"exact_bytes": True},
                    "observation": {"source": "sender", "access": "verified"}}
        self.new = {"artifact_id": "new", "artifact_version_id": "v2", "kind": "pdf",
                    "required": True, "replaces_artifact_id": "old",
                    "checks": {"exact_bytes": True},
                    "observation": {"source": "receiver", "access": "not_checked"}}
        self.sent = manifest("sent", self.old)
        self.received = manifest("received", self.new)
        self.event = {"event_id": "rep-1", "artifact_id": "new", "event_type": "replaced",
                      "step_id": "B", "authorized_by_policy": True,
                      "policy_ref": "grant-1", "replaces_artifact_id": "old"}
        self.received["lifecycle_events"] = [self.event]
        self.grants = {("grant-1", "replaced", "new")}

    def result(self, **kwargs):
        return compare_handoff(self.plan, self.sent, self.received,
                               policy_grants=self.grants, **kwargs)

    @staticmethod
    def codes(result):
        return {f["code"] for f in result["findings"]}

    def test_declared_replacement_is_not_missing_artifact(self):
        result = self.result()
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertNotIn("MISSING_REQUIRED_ARTIFACT", self.codes(result))
        self.assertNotIn("DUPLICATE_OR_UNEXPECTED", self.codes(result))

    def test_unauthorized_replacement_is_alert(self):
        self.contract["allowed_replacements"] = []
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("UNAUTHORIZED_REPLACEMENT", self.codes(result))

    def test_missing_declaration_is_alert(self):
        self.received.pop("lifecycle_events")
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_ARTIFACT", self.codes(result))

    def test_missing_policy_evidence_is_not_pass(self):
        result = compare_handoff(self.plan, self.sent, self.received)
        self.assertNotEqual("PASS", result["verdict"])
        self.assertIn("UNVERIFIABLE", self.codes(result))

    def test_reused_old_identity_is_alert(self):
        self.new["artifact_id"] = "old"
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])

    def test_replacement_event_at_wrong_step_is_alert(self):
        self.event["step_id"] = "A"
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("UNAUTHORIZED_REPLACEMENT", self.codes(result))

    def test_replacement_event_at_receiving_step_is_not_rejected(self):
        result = self.result()
        self.assertNotIn("UNAUTHORIZED_REPLACEMENT", self.codes(result))
        self.assertEqual("UNKNOWN", result["verdict"])

    def test_wrong_replacement_link_is_alert(self):
        self.new["replaces_artifact_id"] = "different"
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("BROKEN_REFERENCE", self.codes(result))

    def test_nonaccepted_replacement_version_is_alert(self):
        self.new["artifact_version_id"] = "v3"
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("STALE_ARTIFACT_VERSION", self.codes(result))

    def test_same_count_without_replacement_event_is_alert(self):
        self.received["lifecycle_events"] = []
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])

    def test_replacement_with_declared_hash_conflict_is_alert(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "replacement.pdf"
            path.write_bytes(b"replacement content")
            self.new["content_sha256"] = "a" * 64
            result = self.result(receiver_files={"new": path})
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("DECLARED_HASH_MISMATCH", self.codes(result))

    def test_matching_local_digest_still_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "replacement.pdf"
            path.write_bytes(b"replacement content")
            self.new["content_sha256"] = digest_file(path)
            result = self.result(receiver_files={"new": path})
        self.assertEqual("UNKNOWN", result["verdict"])


if __name__ == "__main__":
    unittest.main()
