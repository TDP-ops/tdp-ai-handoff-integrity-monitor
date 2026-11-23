"""Synthetic multi-hop checks (A→B→C→D), not independent custody proof."""
import copy
import tempfile
import unittest
from pathlib import Path

from handoff_monitor.journey import compare_journey


def artifact(version="v1", digest=None, parents=None):
    result = {
        "artifact_id": "a", "artifact_version_id": version, "kind": "pdf",
        "required": True, "checks": {"exact_bytes": True},
        "observation": {"source": "receiver", "access": "verified"},
    }
    if digest is not None:
        result["content_sha256"] = digest
    if parents is not None:
        result["parent_version_ids"] = parents
    return result


def manifest(role, start, end, version="v1", idx=0):
    item = artifact(version)
    item["observation"]["source"] = "sender" if role == "sent" else "receiver"
    return {
        "run_id": "run", "handoff_id": f"h-{start}-{end}",
        "event_id": f"event-{idx}-{role}", "from_step": start, "to_step": end,
        "contract_id": f"c-{start}-{end}", "contract_version": "1",
        "manifest_role": role, "rule_ids": ["KEEP"],
        "artifacts": [item],
    }


def plan():
    return {"run_id": "run", "steps": ["A", "B", "C", "D"],
            "critical_rule_ids": ["KEEP"],
            "contracts": [
                {"contract_id": f"c-{start}-{end}", "version": "1",
                 "from_step": start, "to_step": end,
                 "required_artifact_ids": ["a"],
                 "accepted_versions": {"a": ["v1", "v2"]},
                 "required_rule_ids": ["KEEP"],
                 "allowed_transforms": [],
                 "allowed_lifecycle_events": ["modified", "received", "transmitted"]}
                for start, end in [("A", "B"), ("B", "C"), ("C", "D")]]}


def hops():
    return [
        {"sent": manifest("sent", start, end, idx=i),
         "received": manifest("received", start, end, idx=i)}
        for i, (start, end) in enumerate([("A", "B"), ("B", "C"), ("C", "D")])
    ]


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan()
        self.hops = hops()

    def result(self):
        return compare_journey(self.plan, self.hops)

    def codes(self, response):
        return {entry["code"] for entry in response["findings"]}

    def test_three_hops_are_not_remote_proof(self):
        self.assertEqual("UNKNOWN", self.result()["verdict"])

    def test_explicitly_expected_handoff_count(self):
        self.assertEqual(3, len(self.result()["handoffs"]))

    def test_v2_reverts_to_v1_at_d(self):
        self.hops[1]["sent"]["artifacts"][0]["artifact_version_id"] = "v2"
        self.hops[1]["received"]["artifacts"][0]["artifact_version_id"] = "v2"
        self.hops[1]["sent"]["artifacts"][0]["parent_version_ids"] = ["v1"]
        self.hops[1]["received"]["artifacts"][0]["parent_version_ids"] = ["v1"]
        self.hops[1]["sent"]["lifecycle_events"] = [{
            "event_id": "v2-change", "artifact_id": "a", "artifact_version_id": "v2",
            "event_type": "modified", "step_id": "B", "authorized_by_policy": True,
        }]
        response = self.result()
        self.assertEqual("ALERT", response["verdict"])
        self.assertIn("VERSION_ROLLBACK", self.codes(response))

    def test_declared_v2_transition_is_unknown_not_falsely_pass(self):
        for step in [1, 2]:
            for role in ("sent", "received"):
                self.hops[step][role]["artifacts"][0]["artifact_version_id"] = "v2"
                self.hops[step][role]["artifacts"][0]["parent_version_ids"] = ["v1"]
        self.hops[1]["sent"]["lifecycle_events"] = [{
            "event_id": "v2-change", "artifact_id": "a", "artifact_version_id": "v2",
            "event_type": "modified", "step_id": "B", "authorized_by_policy": True,
        }]
        self.assertEqual("UNKNOWN", self.result()["verdict"])
        self.assertNotIn("VERSION_ROLLBACK", self.codes(self.result()))

    def test_wrong_step_modification_is_alert(self):
        for role in ("sent", "received"):
            self.hops[1][role]["artifacts"][0]["artifact_version_id"] = "v2"
            self.hops[1][role]["artifacts"][0]["parent_version_ids"] = ["v1"]
        self.hops[1]["sent"]["lifecycle_events"] = [{
            "event_id": "change-wrong-step", "artifact_id": "a",
            "artifact_version_id": "v2", "event_type": "modified",
            "step_id": "C", "authorized_by_policy": True,
        }]
        result = self.result()
        self.assertIn("VERSION_ROLLBACK", self.codes(result))

    def test_modification_not_permitted_by_contract_is_alert(self):
        self.plan["contracts"][1]["allowed_lifecycle_events"].remove("modified")
        for role in ("sent", "received"):
            self.hops[1][role]["artifacts"][0]["artifact_version_id"] = "v2"
            self.hops[1][role]["artifacts"][0]["parent_version_ids"] = ["v1"]
        self.hops[1]["sent"]["lifecycle_events"] = [{
            "event_id": "change-forbidden", "artifact_id": "a",
            "artifact_version_id": "v2", "event_type": "modified",
            "step_id": "B", "authorized_by_policy": True,
        }]
        self.assertIn("VERSION_ROLLBACK", self.codes(self.result()))

    def test_explicitly_unauthorized_modification_is_alert(self):
        for role in ("sent", "received"):
            self.hops[1][role]["artifacts"][0]["artifact_version_id"] = "v2"
            self.hops[1][role]["artifacts"][0]["parent_version_ids"] = ["v1"]
        self.hops[1]["sent"]["lifecycle_events"] = [{
            "event_id": "change-denied", "artifact_id": "a",
            "artifact_version_id": "v2", "event_type": "modified",
            "step_id": "B", "authorized_by_policy": False,
        }]
        self.assertIn("UNDECLARED_TRANSFORMATION", self.codes(self.result()))

    def test_unchanged_version_cannot_erase_derivation_link_between_hops(self):
        self.hops[0]["sent"]["artifacts"][0]["derived_from_artifact_ids"] = ["source-01"]
        self.hops[0]["received"]["artifacts"][0]["derived_from_artifact_ids"] = ["source-01"]
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("BROKEN_REFERENCE", self.codes(result))

    def test_unchanged_version_cannot_change_parent_between_hops(self):
        for role in ("sent", "received"):
            self.hops[0][role]["artifacts"][0]["parent_version_ids"] = ["v0"]
        for role in ("sent", "received"):
            self.hops[1][role]["artifacts"][0]["parent_version_ids"] = ["other"]
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("BROKEN_REFERENCE", self.codes(result))

    def test_interhop_required_artifact_cannot_become_optional(self):
        self.hops[1]["sent"]["artifacts"][0]["required"] = False
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_RULE", self.codes(result))

    def test_interhop_unchanged_required_status(self):
        self.assertNotIn("MISSING_REQUIRED_RULE", self.codes(self.result()))

    def test_interhop_required_exact_bytes_cannot_be_dropped(self):
        # B receives exact byte obligation, but B sends no checks to C.
        self.hops[1]["sent"]["artifacts"][0]["checks"] = {}
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_RULE", self.codes(result))

    def test_interhop_structure_requirement_cannot_be_dropped(self):
        requirement = {"check_type": "pdf_min_pages", "min_pages": 3}
        self.hops[0]["received"]["artifacts"][0]["checks"]["required_structure"] = [requirement]
        self.hops[0]["sent"]["artifacts"][0]["checks"]["required_structure"] = [requirement]
        # B -> C does not carry the previous receiver's requirement.
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_RULE", self.codes(result))

    def test_interhop_equal_checks_do_not_trigger_weakening_alert(self):
        requirement = {"check_type": "pdf_min_pages", "min_pages": 3}
        for hop in self.hops:
            for role in ("sent", "received"):
                hop[role]["artifacts"][0]["checks"]["required_structure"] = [requirement]
        self.assertNotIn("MISSING_REQUIRED_RULE", self.codes(self.result()))

    def test_missing_digest_between_hops_is_unknown_not_proven_tampering(self):
        self.hops[0]["received"]["artifacts"][0]["content_sha256"] = "a" * 64
        result = self.result()
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertIn("UNVERIFIABLE", self.codes(result))

    def test_missing_middle_hop_is_alert(self):
        self.hops.pop(1)
        self.assertEqual("ALERT", self.result()["verdict"])

    def test_swapped_hops_are_alert(self):
        self.hops[0], self.hops[1] = self.hops[1], self.hops[0]
        self.assertIn("CONTRACT_MISMATCH", self.codes(self.result()))

    def test_duplicate_event_replay_is_alert(self):
        self.hops[2]["received"]["event_id"] = self.hops[0]["received"]["event_id"]
        self.assertIn("DUPLICATE_OR_UNEXPECTED", self.codes(self.result()))

    def test_duplicate_handoff_identity_is_alert(self):
        self.hops[2]["sent"]["handoff_id"] = self.hops[0]["sent"]["handoff_id"]
        self.hops[2]["received"]["handoff_id"] = self.hops[0]["received"]["handoff_id"]
        self.assertIn("DUPLICATE_OR_UNEXPECTED", self.codes(self.result()))

    def test_missing_interhop_artifact_is_alert(self):
        self.hops[2]["sent"]["artifacts"] = []
        self.hops[2]["received"]["artifacts"] = []
        self.assertIn("MISSING_REQUIRED_ARTIFACT", self.codes(self.result()))

    def test_changed_identity_with_same_count_is_alert(self):
        for role in ("sent", "received"):
            self.hops[2][role]["artifacts"][0]["artifact_id"] = "another"
        self.assertIn("DUPLICATE_OR_UNEXPECTED", self.codes(self.result()))

    def test_unchanged_version_conflicting_digest_is_alert(self):
        self.hops[1]["received"]["artifacts"][0]["content_sha256"] = "a" * 64
        self.hops[2]["sent"]["artifacts"][0]["content_sha256"] = "b" * 64
        self.assertIn("ARTIFACT_ID_COLLISION", self.codes(self.result()))

    def test_fork_older_version_explicitly_accepted_does_not_trigger_rollback(self):
        self.hops[1]["sent"]["artifacts"][0]["artifact_version_id"] = "v1"
        self.hops[1]["received"]["artifacts"][0]["artifact_version_id"] = "v1"
        self.assertNotIn("VERSION_ROLLBACK", self.codes(self.result()))

    def test_local_bytes_equal_does_not_authenticate_custody(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "content.pdf"
            f.write_bytes(b"example")
            evidence = {
                hop["sent"]["handoff_id"]:
                    {"sender_files": {"a": f}, "receiver_files": {"a": f}}
                for hop in self.hops
            }
            result = compare_journey(self.plan, self.hops, file_evidence=evidence)
            self.assertEqual("UNKNOWN", result["verdict"])
            self.assertTrue(all(h["verdict"] == "PASS" for h in result["handoffs"]))


if __name__ == "__main__":
    unittest.main()
