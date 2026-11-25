"""Strict V0 multi-hop version transitions; no remote policy authentication."""
import unittest
from handoff_monitor import compare_journey_validated
from test_lot4_adversarial_journey import two_hop_baseline

VIOLATIONS = (
    ("missing_version_event", "VERSION_ROLLBACK"),
    ("wrong_version_parent", "VERSION_ROLLBACK"),
    ("denied_version_change", "UNDECLARED_TRANSFORMATION"),
)
ABSTENTIONS = ("declared_version_change_untrusted",)


def version_case(name):
    plan, hops = two_hop_baseline()
    contract = plan["contracts"][1]
    contract["accepted_versions"]["ART-001"].append("ART-001-V2")
    contract["allowed_lifecycle_events"].append("modified")
    for role in ("sent", "received"):
        artifact = hops[1][role]["artifacts"][0]
        artifact["artifact_version_id"] = "ART-001-V2"
        artifact["parent_version_ids"] = ["ART-001-V1"]
    change = {
        "event_id": "E-V2-MODIFIED",
        "artifact_id": "ART-001",
        "artifact_version_id": "ART-001-V2",
        "event_type": "modified",
        "step_id": "B",
        "authorized_by_policy": True,
        "policy_ref": "UNTRUSTED-POLICY",
    }
    if name == "missing_version_event":
        pass
    elif name == "wrong_version_parent":
        for role in ("sent", "received"):
            hops[1][role]["artifacts"][0]["parent_version_ids"] = ["ART-OTHER-V1"]
        hops[1]["sent"]["lifecycle_events"] = [change]
    elif name == "denied_version_change":
        change["authorized_by_policy"] = False
        hops[1]["sent"]["lifecycle_events"] = [change]
    elif name == "declared_version_change_untrusted":
        hops[1]["sent"]["lifecycle_events"] = [change]
    else:
        raise ValueError("Unknown scenario: " + name)
    return plan, hops


def compare_version(name):
    return compare_journey_validated(*version_case(name))


class AdversarialVersionTransitionTests(unittest.TestCase):
    def test_invalid_changes_alert(self):
        for name, diagnostic in VIOLATIONS:
            with self.subTest(case=name):
                result = compare_version(name)
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn(diagnostic, {f["code"] for f in result["findings"]})
                self.assertNotIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_declared_change_cannot_prove_remote_custody(self):
        result = compare_version("declared_version_change_untrusted")
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertIn("UNVERIFIABLE", {f["code"] for f in result["findings"]})
        self.assertNotIn("VERSION_ROLLBACK", {f["code"] for f in result["findings"]})


if __name__ == "__main__":
    unittest.main()
