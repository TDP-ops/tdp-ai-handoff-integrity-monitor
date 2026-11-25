"""Strict V0 contract extension: declared transforms, not semantic file checks.

A matching transform identifier is an untrusted declaration, not evidence of
the operation itself or independent policy authorization.
"""
import unittest

from handoff_monitor import compare_handoff_validated, compare_journey_validated
from test_lot4_adversarial_lifecycle import lifecycle_case
from test_lot4_version_transitions import version_case

SINGLE_VIOLATIONS = (
    ("forbidden_transform", "UNDECLARED_TRANSFORMATION"),
    ("transform_with_empty_allowlist", "UNDECLARED_TRANSFORMATION"),
)
JOURNEY_VIOLATIONS = (
    ("forbidden_interhop_transform", "UNDECLARED_TRANSFORMATION"),
)
SINGLE_ABSTENTIONS = (
    "matching_transform_untrusted",
    "legacy_transform_without_identifier",
)
JOURNEY_ABSTENTIONS = (
    "matching_interhop_transform_untrusted",
    "legacy_interhop_transform_without_identifier",
)


def single_case(name):
    plan, sent, received = lifecycle_case("declared_modification_untrusted")
    contract = plan["contracts"][0]
    contract["allowed_transforms"] = ["TRANSFORM-APPROVED"]
    event = received["lifecycle_events"][0]
    if name == "forbidden_transform":
        event["transform_id"] = "TRANSFORM-NOT-APPROVED"
    elif name == "transform_with_empty_allowlist":
        contract["allowed_transforms"] = []
        event["transform_id"] = "TRANSFORM-APPROVED"
    elif name == "matching_transform_untrusted":
        event["transform_id"] = "TRANSFORM-APPROVED"
    elif name == "legacy_transform_without_identifier":
        pass
    else:
        raise ValueError(name)
    return plan, sent, received


def interhop_case(name):
    plan, hops = version_case("declared_version_change_untrusted")
    contract = plan["contracts"][1]
    contract["allowed_transforms"] = ["TRANSFORM-APPROVED"]
    event = hops[1]["sent"]["lifecycle_events"][0]
    if name == "forbidden_interhop_transform":
        event["transform_id"] = "TRANSFORM-NOT-APPROVED"
    elif name == "matching_interhop_transform_untrusted":
        event["transform_id"] = "TRANSFORM-APPROVED"
    elif name == "legacy_interhop_transform_without_identifier":
        pass
    else:
        raise ValueError(name)
    return plan, hops


def compare_transform(name):
    if name in SINGLE_ABSTENTIONS or name in (x[0] for x in SINGLE_VIOLATIONS):
        return compare_handoff_validated(*single_case(name))
    return compare_journey_validated(*interhop_case(name))


class TransformDeclarationTests(unittest.TestCase):
    def test_disallowed_declared_transform_is_alert(self):
        for name, code in SINGLE_VIOLATIONS + JOURNEY_VIOLATIONS:
            with self.subTest(case=name):
                result = compare_transform(name)
                codes = {finding["code"] for finding in result["findings"]}
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn(code, codes)
                self.assertNotIn("INVALID_MANIFEST", codes)

    def test_allowed_or_legacy_transform_remains_unknown(self):
        for name in SINGLE_ABSTENTIONS + JOURNEY_ABSTENTIONS:
            with self.subTest(case=name):
                result = compare_transform(name)
                codes = {finding["code"] for finding in result["findings"]}
                self.assertEqual("UNKNOWN", result["verdict"])
                self.assertIn("UNVERIFIABLE", codes)
                self.assertNotIn("UNDECLARED_TRANSFORMATION", codes)
                self.assertNotIn("INVALID_MANIFEST", codes)

    def test_legacy_manifest_with_no_modification_remains_valid(self):
        plan, sent, received = lifecycle_case("declared_rejection_untrusted")
        result = compare_handoff_validated(plan, sent, received)
        self.assertEqual("UNKNOWN", result["verdict"])
        self.assertNotIn("INVALID_MANIFEST", {x["code"] for x in result["findings"]})


if __name__ == "__main__":
    unittest.main()
