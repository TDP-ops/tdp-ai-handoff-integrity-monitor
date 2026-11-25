"""Lot 4: lifecycle policy checks using the public strict comparator.

These tests validate declared event rules only. They do not demonstrate
content transformation, actual deletion or authenticated policy approval.
"""
import json
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"

VIOLATIONS = (
    ("rejection_not_in_contract", "UNDECLARED_REJECTION"),
    ("rejection_without_reason", "UNDECLARED_REJECTION"),
    ("rejection_explicitly_unauthorized", "UNDECLARED_REJECTION"),
    ("modification_not_in_contract", "UNDECLARED_TRANSFORMATION"),
    ("rejection_wrong_step", "UNDECLARED_REJECTION"),
    ("modification_wrong_step", "UNDECLARED_TRANSFORMATION"),
    ("sender_rejection_wrong_step", "UNDECLARED_REJECTION"),
    ("retirement_wrong_step", "UNDECLARED_REJECTION"),
)

ABSTENTIONS = ("declared_rejection_untrusted", "declared_modification_untrusted",
               "declared_sender_rejection_untrusted")


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def lifecycle_case(name):
    plan, sent, received = (load("run-plan.json"),
                            load("pass-sent.json"),
                            load("pass-received.json"))
    contract = plan["contracts"][0]
    is_modification = name in (
        "modification_not_in_contract", "modification_wrong_step",
        "declared_modification_untrusted")
    is_retirement = name == "retirement_wrong_step"
    sender_owned = name in ("sender_rejection_wrong_step",
                            "declared_sender_rejection_untrusted")
    event_type = "modified" if is_modification else "retired" if is_retirement else "rejected"
    if name not in ("rejection_not_in_contract", "modification_not_in_contract"):
        contract["allowed_lifecycle_events"].append(event_type)
    event = {
        "event_id": "E-LOT4-LIFECYCLE",
        "artifact_id": "ART-001",
        "event_type": event_type,
        "step_id": "B",
        "authorized_by_policy": name != "rejection_explicitly_unauthorized",
        "policy_ref": "POLICY-UNTRUSTED",
    }
    if not is_modification and name != "rejection_without_reason":
        event["reason"] = "Synthetic rejection scenario"
    if name in ("rejection_wrong_step", "modification_wrong_step",
                "retirement_wrong_step"):
        event["step_id"] = "A"
    if sender_owned:
        if name == "declared_sender_rejection_untrusted":
            event["step_id"] = "A"
        sent["lifecycle_events"] = [event]
    else:
        received["lifecycle_events"] = [event]
    return plan, sent, received


def compare_lifecycle(name):
    return compare_handoff_validated(*lifecycle_case(name))


class AdversarialLifecycleTests(unittest.TestCase):
    def test_declared_violations_alert(self):
        for name, expected_code in VIOLATIONS:
            with self.subTest(scenario=name):
                result = compare_lifecycle(name)
                self.assertEqual("ALERT", result["verdict"])
                codes = {f["code"] for f in result["findings"]}
                self.assertIn(expected_code, codes)
                self.assertNotIn("INVALID_MANIFEST", codes)

    def test_declared_but_untrusted_events_abstain(self):
        for name in ABSTENTIONS:
            with self.subTest(scenario=name):
                result = compare_lifecycle(name)
                codes = {f["code"] for f in result["findings"]}
                self.assertEqual("UNKNOWN", result["verdict"])
                self.assertIn("UNVERIFIABLE", codes)
                self.assertNotIn("INVALID_MANIFEST", codes)
                self.assertNotIn("EXACT_BYTES_MATCH", codes)

    def test_original_fixtures_are_unchanged(self):
        original = load("pass-received.json")
        for name, _ in VIOLATIONS:
            lifecycle_case(name)
        for name in ABSTENTIONS:
            lifecycle_case(name)
        self.assertEqual(original, load("pass-received.json"))


if __name__ == "__main__":
    unittest.main()
