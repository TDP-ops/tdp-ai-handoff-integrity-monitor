"""Lot 4 replacement-policy cases against the strict public V0 API.

All evidence is synthetic and caller-supplied. A syntactically permitted
replacement must remain UNKNOWN because grant and custody provenance are
not authenticated here.
"""
import copy
import json
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"
GRANTS = {("GRANT-REPLACE", "replaced", "ART-NEW")}
CASES = (
    ("replacement_not_permitted", "UNAUTHORIZED_REPLACEMENT"),
    ("replacement_wrong_step", "UNAUTHORIZED_REPLACEMENT"),
    ("replacement_link_mismatch", "BROKEN_REFERENCE"),
    ("replacement_version_not_accepted", "STALE_ARTIFACT_VERSION"),
    ("replacement_event_missing", "MISSING_REQUIRED_ARTIFACT"),
)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def replacement_baseline():
    plan = load("run-plan.json")
    sent = load("pass-sent.json")
    received = load("pass-received.json")
    contract = plan["contracts"][0]
    contract["allowed_replacements"] = ["ART-001"]
    contract["allowed_lifecycle_events"].append("replaced")
    contract["accepted_versions"]["ART-NEW"] = ["ART-NEW-V2"]
    new = copy.deepcopy(received["artifacts"][0])
    new["artifact_id"] = "ART-NEW"
    new["artifact_version_id"] = "ART-NEW-V2"
    new["replaces_artifact_id"] = "ART-001"
    new["observation"]["access"] = "not_checked"
    new.pop("content_sha256", None)
    received["artifacts"] = [new]
    received["lifecycle_events"] = [{
        "event_id": "E-REPLACE",
        "artifact_id": "ART-NEW",
        "event_type": "replaced",
        "step_id": "B",
        "authorized_by_policy": True,
        "policy_ref": "GRANT-REPLACE",
        "replaces_artifact_id": "ART-001",
    }]
    return plan, sent, received


def replacement_case(name):
    plan, sent, received = replacement_baseline()
    if name == "replacement_not_permitted":
        plan["contracts"][0]["allowed_replacements"] = []
    elif name == "replacement_wrong_step":
        received["lifecycle_events"][0]["step_id"] = "A"
    elif name == "replacement_link_mismatch":
        received["artifacts"][0]["replaces_artifact_id"] = "ART-OTHER"
    elif name == "replacement_version_not_accepted":
        received["artifacts"][0]["artifact_version_id"] = "ART-NEW-V3"
    elif name == "replacement_event_missing":
        received["lifecycle_events"] = []
    else:
        raise ValueError("Unknown replacement adversarial scenario: " + name)
    return plan, sent, received


def compare(plan, sent, received):
    return compare_handoff_validated(
        plan, sent, received, policy_grants=GRANTS)


class AdversarialReplacementTests(unittest.TestCase):
    def test_permitted_but_unauthenticated_replacement_abstains(self):
        result = compare(*replacement_baseline())
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertIn("UNVERIFIABLE", {f["code"] for f in result["findings"]})
        self.assertNotIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})
        self.assertNotIn("UNAUTHORIZED_REPLACEMENT",
                         {f["code"] for f in result["findings"]})

    def test_replacement_violations_alert(self):
        for name, code in CASES:
            with self.subTest(scenario=name):
                result = compare(*replacement_case(name))
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn(code, {f["code"] for f in result["findings"]})
                self.assertNotIn("INVALID_MANIFEST",
                                 {f["code"] for f in result["findings"]})

    def test_replacement_tests_do_not_change_canonical_files(self):
        original = load("pass-received.json")
        replacement_baseline()
        for name, _ in CASES:
            replacement_case(name)
        self.assertEqual(original, load("pass-received.json"))


if __name__ == "__main__":
    unittest.main()
