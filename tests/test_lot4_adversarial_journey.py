"""Lot 4: adversarial linear multi-hop continuity through the strict API.

Only the canonical synthetic fixtures are used. A coherent journey remains
UNKNOWN without authenticated receiver custody; violations must be ALERT.
"""
import copy
import json
import unittest
from pathlib import Path

from handoff_monitor import compare_journey_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


CASES = (
    ("missing_second_handoff", "CONTRACT_MISMATCH"),
    ("replayed_event_across_hops", "DUPLICATE_OR_UNEXPECTED"),
    ("artifact_dropped_between_hops", "MISSING_REQUIRED_ARTIFACT"),
)


def two_hop_baseline():
    plan = load("run-plan.json")
    first = {"sent": load("pass-sent.json"),
             "received": load("pass-received.json")}
    second = copy.deepcopy(first)
    plan["steps"] = ["A", "B", "C"]
    contract = copy.deepcopy(plan["contracts"][0])
    contract.update({"contract_id": "C-B-C", "from_step": "B", "to_step": "C"})
    plan["contracts"].append(contract)
    for role in ("sent", "received"):
        event = second[role]
        event.update({
            "handoff_id": "H-B-C", "contract_id": "C-B-C",
            "from_step": "B", "to_step": "C",
            "event_id": "E-SECOND-" + role.upper(),
        })
    return plan, [first, second]


def adversarial_journey(name):
    plan, hops = two_hop_baseline()
    if name == "missing_second_handoff":
        hops.pop()
    elif name == "replayed_event_across_hops":
        hops[1]["sent"]["event_id"] = hops[0]["received"]["event_id"]
    elif name == "artifact_dropped_between_hops":
        hops[1]["sent"]["artifacts"] = []
        hops[1]["received"]["artifacts"] = []
    else:
        raise ValueError(f"Unknown scenario: {name}")
    return plan, hops


class AdversarialJourneyTests(unittest.TestCase):
    def test_valid_synthetic_journey_abstains_without_custody(self):
        plan, hops = two_hop_baseline()
        result = compare_journey_validated(plan, hops)
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertEqual(2, len(result["handoffs"]))
        self.assertNotIn("INVALID_MANIFEST", {x["code"] for x in result["findings"]})

    def test_known_continuity_violations_alert(self):
        for name, expected_code in CASES:
            with self.subTest(scenario=name):
                plan, hops = adversarial_journey(name)
                result = compare_journey_validated(plan, hops)
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn(expected_code, {x["code"] for x in result["findings"]})
                self.assertNotIn("INVALID_MANIFEST", {x["code"] for x in result["findings"]})

    def test_cases_do_not_mutate_canonical_fixture(self):
        original = load("pass-sent.json")
        for name, _ in CASES:
            adversarial_journey(name)
        self.assertEqual(original, load("pass-sent.json"))


if __name__ == "__main__":
    unittest.main()
