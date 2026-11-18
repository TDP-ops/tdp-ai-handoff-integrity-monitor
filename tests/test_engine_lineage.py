"""Synthetic unit tests for CR-07/08/09 partial checks, not policy authentication."""
import copy
import unittest

from handoff_monitor.lineage import check_lifecycle, check_lineage
PLAN = {"run_id": "r", "critical_rule_ids": ["KEEP"], "contracts": [
    {"contract_id": "c", "version": "1", "from_step": "A", "to_step": "B",
     "required_artifact_ids": ["a"], "accepted_versions": {"a": ["v1"]},
     "required_rule_ids": ["KEEP"]}]}


def manifest(role):
    artifact = {"artifact_id": "a", "artifact_version_id": "v1",
                "kind": "pdf", "required": True,
                "checks": {"exact_bytes": True},
                "observation": {"source": role, "access": "verified"}}
    return {"run_id": "r", "handoff_id": "h", "event_id": "e-" + role,
            "from_step": "A", "to_step": "B", "contract_id": "c",
            "contract_version": "1", "manifest_role": role,
            "rule_ids": ["KEEP"], "artifacts": [artifact]}

from handoff_monitor.core import compare_handoff


class LineageAndLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.sent = manifest("sent")
        self.received = manifest("received")
        self.contract = copy.deepcopy(PLAN["contracts"][0])

    def codes(self, findings):
        return {item["code"] for item in findings}

    def evaluate(self, **kwargs):
        return compare_handoff(PLAN, self.sent, self.received, **kwargs)

    def test_no_parent_links_is_not_a_lineage_failure(self):
        self.assertEqual([], check_lineage({"a": self.sent["artifacts"][0]},
                                           {"a": self.received["artifacts"][0]}))

    def test_parent_without_history_is_unknown(self):
        self.sent["artifacts"][0]["parent_version_ids"] = ["v0"]
        self.received["artifacts"][0]["parent_version_ids"] = ["v0"]
        self.assertIn("UNVERIFIABLE", self.codes(self.evaluate()["findings"]))

    def test_parent_reference_with_incomplete_history_is_alert(self):
        root = copy.deepcopy(self.sent["artifacts"][0])
        root["parent_version_ids"] = ["missing"]
        self.assertIn("BROKEN_REFERENCE", self.codes(check_lineage({}, {}, [root])))

    def test_cycle_in_history_is_alert(self):
        first = copy.deepcopy(self.sent["artifacts"][0])
        first["parent_version_ids"] = ["v2"]
        second = copy.deepcopy(first)
        second["artifact_version_id"] = "v2"
        second["parent_version_ids"] = ["v1"]
        self.assertIn("BROKEN_REFERENCE", self.codes(check_lineage({}, {}, [first, second])))

    def test_conflicting_version_history_is_alert(self):
        first = copy.deepcopy(self.sent["artifacts"][0])
        second = copy.deepcopy(first)
        second["content_sha256"] = "b" * 64
        self.assertIn("ARTIFACT_ID_COLLISION",
                      self.codes(check_lineage({}, {}, [first, second])))

    def test_current_version_missing_from_supplied_history_is_unknown(self):
        root = copy.deepcopy(self.sent["artifacts"][0])
        root["artifact_version_id"] = "v0"
        result = self.evaluate(history=[root])
        self.assertIn("UNVERIFIABLE", self.codes(result["findings"]))

    def test_current_version_parent_conflicts_with_history_is_alert(self):
        self.sent["artifacts"][0]["parent_version_ids"] = ["v0"]
        self.received["artifacts"][0]["parent_version_ids"] = ["v0"]
        old = copy.deepcopy(self.sent["artifacts"][0])
        old["artifact_version_id"] = "v0"
        old["parent_version_ids"] = []
        current = copy.deepcopy(self.sent["artifacts"][0])
        current["parent_version_ids"] = []
        result = self.evaluate(history=[old, current])
        self.assertIn("BROKEN_REFERENCE", self.codes(result["findings"]))

    def test_current_derived_from_conflicts_with_history(self):
        self.sent["artifacts"][0]["derived_from_artifact_ids"] = ["source-a"]
        self.received["artifacts"][0]["derived_from_artifact_ids"] = ["source-a"]
        root = copy.deepcopy(self.sent["artifacts"][0])
        root["derived_from_artifact_ids"] = ["source-b"]
        result = self.evaluate(history=[root])
        self.assertIn("BROKEN_REFERENCE", self.codes(result["findings"]))

    def test_current_replacement_link_conflicts_with_history(self):
        self.sent["artifacts"][0]["replaces_artifact_id"] = "old-a"
        self.received["artifacts"][0]["replaces_artifact_id"] = "old-a"
        root = copy.deepcopy(self.sent["artifacts"][0])
        root["replaces_artifact_id"] = "old-b"
        result = self.evaluate(history=[root])
        self.assertIn("BROKEN_REFERENCE", self.codes(result["findings"]))

    def test_current_kind_conflicts_with_history(self):
        root = copy.deepcopy(self.sent["artifacts"][0])
        root["kind"] = "docx"
        result = self.evaluate(history=[root])
        self.assertIn("ARTIFACT_ID_COLLISION", self.codes(result["findings"]))

    def test_current_hash_conflicts_with_history(self):
        self.sent["artifacts"][0]["content_sha256"] = "a" * 64
        self.received["artifacts"][0]["content_sha256"] = "a" * 64
        root = copy.deepcopy(self.sent["artifacts"][0])
        root["content_sha256"] = "b" * 64
        result = self.evaluate(history=[root])
        self.assertIn("ARTIFACT_ID_COLLISION", self.codes(result["findings"]))

    def test_matching_current_history_records_no_lineage_issue(self):
        root = copy.deepcopy(self.sent["artifacts"][0])
        findings = check_lineage(
            {"a": self.sent["artifacts"][0]},
            {"a": self.received["artifacts"][0]},
            history=[root],
        )
        self.assertEqual([], findings)

    def test_self_replacement_is_alert(self):
        self.sent["artifacts"][0]["replaces_artifact_id"] = "a"
        self.assertIn("ARTIFACT_ID_COLLISION", self.codes(self.evaluate()["findings"]))

    def test_disallowed_rejection_is_alert(self):
        self.sent["lifecycle_events"] = [{
            "event_id": "rej-1", "artifact_id": "a", "event_type": "rejected",
            "step_id": "A", "authorized_by_policy": True, "reason": "quality"
        }]
        self.assertIn("UNDECLARED_REJECTION", self.codes(self.evaluate()["findings"]))

    def test_self_attested_authorization_is_unknown(self):
        self.contract["allowed_lifecycle_events"] = ["rejected"]
        event = {"event_id": "rej-1", "artifact_id": "a", "event_type": "rejected",
                 "step_id": "A", "authorized_by_policy": True, "reason": "quality",
                 "policy_ref": "approval-1"}
        self.assertIn("UNVERIFIABLE",
                      self.codes(check_lifecycle({"lifecycle_events": [event]},
                                                 {}, self.contract)))

    def test_grant_must_match_event_and_artifact(self):
        self.contract["allowed_lifecycle_events"] = ["rejected"]
        event = {"event_id": "rej-1", "artifact_id": "a", "event_type": "rejected",
                 "step_id": "A", "authorized_by_policy": True, "reason": "quality",
                 "policy_ref": "approval-1"}
        findings = check_lifecycle({"lifecycle_events": [event]}, {},
                                   self.contract, policy_grants={("approval-other", "rejected", "a")})
        self.assertIn("UNDECLARED_REJECTION", self.codes(findings))

    def test_matching_grant_rejection_has_no_lifecycle_error(self):
        self.contract["allowed_lifecycle_events"] = ["rejected"]
        event = {"event_id": "rej-1", "artifact_id": "a", "event_type": "rejected",
                 "step_id": "A", "authorized_by_policy": True, "reason": "quality",
                 "policy_ref": "approval-1"}
        findings = check_lifecycle({"lifecycle_events": [event]}, {},
                                   self.contract, policy_grants={("approval-1", "rejected", "a")})
        self.assertEqual([], findings)

    def test_replacement_must_use_new_id(self):
        self.contract["allowed_lifecycle_events"] = ["replaced"]
        event = {"event_id": "rep-1", "artifact_id": "a", "event_type": "replaced",
                 "step_id": "A", "authorized_by_policy": True, "policy_ref": "grant-1",
                 "replaces_artifact_id": "a"}
        findings = check_lifecycle({"lifecycle_events": [event]}, {},
                                   self.contract, policy_grants={("grant-1", "replaced", "a")})
        self.assertIn("ARTIFACT_ID_COLLISION", self.codes(findings))

    def test_replacement_requires_allowed_old_id(self):
        self.contract["allowed_lifecycle_events"] = ["replaced"]
        event = {"event_id": "rep-1", "artifact_id": "new", "event_type": "replaced",
                 "step_id": "A", "authorized_by_policy": True, "policy_ref": "grant-1",
                 "replaces_artifact_id": "old"}
        findings = check_lifecycle({"lifecycle_events": [event]}, {},
                                   self.contract, policy_grants={("grant-1", "replaced", "new")})
        self.assertIn("UNAUTHORIZED_REPLACEMENT", self.codes(findings))

    def test_matching_grant_and_allowed_replacement(self):
        self.contract["allowed_lifecycle_events"] = ["replaced"]
        self.contract["allowed_replacements"] = ["old"]
        event = {"event_id": "rep-1", "artifact_id": "new", "event_type": "replaced",
                 "step_id": "A", "authorized_by_policy": True, "policy_ref": "grant-1",
                 "replaces_artifact_id": "old"}
        self.assertEqual([], check_lifecycle({"lifecycle_events": [event]}, {},
            self.contract, policy_grants={("grant-1", "replaced", "new")}))


if __name__ == "__main__":
    unittest.main()
