"""Lot 4: independently supplied grant tuple mismatches must not be accepted.

The grant tuples are caller-provided synthetic data, NOT authenticated
policy signatures. Matching tuples must never yield independent trust.
"""
import unittest

from handoff_monitor import compare_handoff_validated
from test_lot4_adversarial_lifecycle import lifecycle_case

GRANT_VIOLATIONS = (
    ("rejection_wrong_grant_reference", "declared_rejection_untrusted",
     {("POLICY-OTHER", "rejected", "ART-001")}),
    ("modification_wrong_grant_type", "declared_modification_untrusted",
     {("POLICY-UNTRUSTED", "rejected", "ART-001")}),
)
GRANT_ABSTENTIONS = (
    ("rejection_matching_untrusted_grant", "declared_rejection_untrusted",
     {("POLICY-UNTRUSTED", "rejected", "ART-001")}),
    ("modification_matching_untrusted_grant", "declared_modification_untrusted",
     {("POLICY-UNTRUSTED", "modified", "ART-001")}),
)


def grant_case(name):
    for scenario, baseline, grants in GRANT_VIOLATIONS + GRANT_ABSTENTIONS:
        if name == scenario:
            return baseline, grants
    raise ValueError("Unknown grant scenario: " + name)


def compare_grant(name):
    baseline, grants = grant_case(name)
    plan, sent, received = lifecycle_case(baseline)
    return compare_handoff_validated(
        plan, sent, received, policy_grants=grants)


class PolicyGrantBoundaryTests(unittest.TestCase):
    def test_mismatched_grants_cause_alert(self):
        for name, _, _ in GRANT_VIOLATIONS:
            with self.subTest(name=name):
                result = compare_grant(name)
                codes = {f["code"] for f in result["findings"]}
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn("UNDECLARED_REJECTION", codes)
                self.assertNotIn("INVALID_MANIFEST", codes)

    def test_matching_caller_grants_still_abstain(self):
        for name, _, _ in GRANT_ABSTENTIONS:
            with self.subTest(name=name):
                result = compare_grant(name)
                codes = {f["code"] for f in result["findings"]}
                self.assertEqual("UNKNOWN", result["verdict"])
                self.assertIn("UNVERIFIABLE", codes)
                self.assertNotIn("INVALID_MANIFEST", codes)
                self.assertNotIn("EXACT_BYTES_MATCH", codes)


if __name__ == "__main__":
    unittest.main()
