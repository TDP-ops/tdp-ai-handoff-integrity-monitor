"""Regression tests for schema-first multi-hop input validation."""
import copy
import json
import unittest
from pathlib import Path

from handoff_monitor.validation import compare_journey_validated

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "lot1"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StrictJourneyValidationTests(unittest.TestCase):
    def setUp(self):
        self.plan = load("run-plan.json")
        self.hops = [{"sent": load("pass-sent.json"),
                      "received": load("pass-received.json")}]

    def result(self):
        return compare_journey_validated(self.plan, self.hops)

    def assert_invalid(self):
        result = self.result()
        self.assertEqual("ALERT", result["verdict"])
        self.assertEqual([], result["handoffs"])
        self.assertIn("INVALID_MANIFEST", {item["code"] for item in result["findings"]})

    def test_valid_single_hop_is_not_remote_proof(self):
        self.assertEqual("UNKNOWN", self.result()["verdict"])

    def test_plan_must_satisfy_canonical_schema(self):
        self.plan.pop("plan_version")
        self.assert_invalid()

    def test_later_hop_cannot_bypass_validation(self):
        second = copy.deepcopy(self.hops[0])
        second["received"]["artifacts"][0]["observation"]["source"] = "invented"
        self.hops.append(second)
        self.assert_invalid()

    def test_non_object_hop_is_rejected(self):
        self.hops.append(None)
        self.assert_invalid()

    def test_missing_receiver_is_rejected(self):
        self.hops[0].pop("received")
        self.assert_invalid()

    def test_non_array_handoffs_are_rejected(self):
        self.hops = {"sent": self.hops[0]["sent"]}
        self.assert_invalid()

    def test_empty_handoffs_still_validates_plan(self):
        self.hops = []
        self.plan["untrusted"] = True
        self.assert_invalid()


if __name__ == "__main__":
    unittest.main()
