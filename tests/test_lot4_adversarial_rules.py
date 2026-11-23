"""Lot 4: deterministic adversarial rule, identity and version cases.

Each case runs the public schema-first comparator on the canonical synthetic
fixtures. Expected codes and verdicts are independently specified here, not
read from a pre-existing contract expectation matrix.
"""
import json
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


CASES = (
    ("required_rule_dropped", "MISSING_REQUIRED_RULE"),
    ("received_version_not_accepted", "VERSION_ROLLBACK"),
    ("reused_event_identity", "DUPLICATE_OR_UNEXPECTED"),
    ("stale_contract_version", "CONTRACT_MISMATCH"),
    ("required_artifact_removed", "MISSING_REQUIRED_ARTIFACT"),
)


def adversarial_case(name):
    plan = fixture("run-plan.json")
    sent = fixture("pass-sent.json")
    received = fixture("pass-received.json")
    if name == "required_rule_dropped":
        received["rule_ids"] = []
    elif name == "received_version_not_accepted":
        received["artifacts"][0]["artifact_version_id"] = "ART-001-V0"
    elif name == "reused_event_identity":
        received["event_id"] = sent["event_id"]
    elif name == "stale_contract_version":
        received["contract_version"] = "0"
    elif name == "required_artifact_removed":
        received["artifacts"] = []
    else:
        raise ValueError(f"Unknown scenario: {name}")
    return plan, sent, received


class AdversarialRuleIdentityTests(unittest.TestCase):
    def test_each_real_rule_violation_produces_alert(self):
        for name, code in CASES:
            with self.subTest(scenario=name):
                plan, sent, received = adversarial_case(name)
                result = compare_handoff_validated(plan, sent, received)
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn(code, {f["code"] for f in result["findings"]})

    def test_no_violation_case_can_pass_without_local_bytes(self):
        result = compare_handoff_validated(
            fixture("run-plan.json"),
            fixture("pass-sent.json"),
            fixture("pass-received.json"),
        )
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertNotIn("EXACT_BYTES_MATCH",
                         {f["code"] for f in result["findings"]})

    def test_each_scenario_is_isolated_from_original_fixtures(self):
        original = fixture("pass-received.json")
        for name, _ in CASES:
            with self.subTest(scenario=name):
                _, _, changed = adversarial_case(name)
                self.assertNotEqual(changed, original)
        self.assertEqual(original, fixture("pass-received.json"))


if __name__ == "__main__":
    unittest.main()
