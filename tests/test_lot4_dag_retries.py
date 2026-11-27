"""Bounded DAG retry policy: positive and negative strict-API scenarios.

Authorization is a caller-declared contract bound, not authenticated custody.
Approved local retries therefore remain UNKNOWN, never PASS.
"""
import copy
import unittest

from handoff_monitor import compare_journey_validated
from test_lot4_dag_journey import diamond

RETRY_CASES = (
    ("retry_bounded_legitimate", "evidence_unavailable", "UNKNOWN"),
    ("retry_out_of_order_presentation", "evidence_unavailable", "UNKNOWN"),
    ("retry_exceeds_policy_max", "violation", "ALERT"),
    ("retry_wrong_predecessor", "violation", "ALERT"),
    ("retry_duplicate_attempt_index", "violation", "ALERT"),
    ("retry_missing_attempt_index", "violation", "ALERT"),
    ("retry_payload_changed", "violation", "ALERT"),
    ("retry_roles_disagree", "violation", "ALERT"),
)


def run_retry_case(name):
    if name not in (row[0] for row in RETRY_CASES):
        raise ValueError("Unknown retry scenario")
    plan, hops = diamond()
    plan["contracts"][0]["max_attempts"] = 2
    prior = hops[0]
    for role in ("sent", "received"):
        prior[role]["attempt_number"] = 1
    retry = copy.deepcopy(prior)
    for role in ("sent", "received"):
        retry[role]["handoff_id"] = "H-ATTEMPT-2"
        retry[role]["event_id"] = "E-ATTEMPT-2-" + role.upper()
        retry[role]["attempt_number"] = 2
        retry[role]["retry_of_handoff_id"] = prior[role]["handoff_id"]
    hops.append(retry)
    if name == "retry_exceeds_policy_max":
        plan["contracts"][0]["max_attempts"] = 1
    elif name == "retry_wrong_predecessor":
        for role in ("sent", "received"):
            retry[role]["retry_of_handoff_id"] = "H-WRONG-PREDECESSOR"
    elif name == "retry_duplicate_attempt_index":
        for role in ("sent", "received"):
            retry[role]["attempt_number"] = 1
            retry[role].pop("retry_of_handoff_id")
    elif name == "retry_missing_attempt_index":
        for role in ("sent", "received"):
            retry[role].pop("attempt_number")
    elif name == "retry_payload_changed":
        for role in ("sent", "received"):
            retry[role]["artifacts"][0]["content_sha256"] = "b" * 64
    elif name == "retry_roles_disagree":
        retry["received"]["attempt_number"] = 1
    elif name == "retry_out_of_order_presentation":
        hops.reverse()
    return compare_journey_validated(plan, hops)


class DagRetryTests(unittest.TestCase):
    def test_all_bounded_retries(self):
        for name, truth, expected in RETRY_CASES:
            with self.subTest(name=name):
                result = run_retry_case(name)
                codes = {item["code"] for item in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertTrue(any(x["verdict"] == "ALERT"
                                        for x in result["findings"]))
                else:
                    self.assertIn("UNVERIFIABLE", codes)

    def test_original_dag_without_retry_fields_remains_supported(self):
        plan, hops = diamond()
        result = compare_journey_validated(plan, hops)
        self.assertEqual("UNKNOWN", result["verdict"])


if __name__ == "__main__":
    unittest.main()
