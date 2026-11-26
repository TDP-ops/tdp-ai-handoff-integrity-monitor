"""Opt-in DAG adversarial handoff scenarios on synthetic manifests.

DAG handoffs may be supplied in any list order; graph shape comes from the
contracts. Retries are currently rejected as ambiguous observations.
"""
import copy
import unittest

from handoff_monitor import compare_journey_validated
from test_lot4_adversarial_journey import load

DAG_CASES = (
    ("dag_diamond_in_any_order", "evidence_unavailable", "UNKNOWN"),
    ("dag_missing_branch", "violation", "ALERT"),
    ("dag_duplicate_retry", "violation", "ALERT"),
    ("dag_replayed_event", "violation", "ALERT"),
    ("dag_join_conflicting_version", "violation", "ALERT"),
    ("dag_fork_artifact_lost", "violation", "ALERT"),
    ("dag_cycle", "violation", "ALERT"),
)


def diamond():
    plan = load("run-plan.json")
    template = plan["contracts"][0]
    plan["journey_mode"] = "dag"
    plan["steps"] = ["A", "B", "C", "D"]
    boundaries = (("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"))
    plan["contracts"] = []
    hops = []
    for i, (source, destination) in enumerate(boundaries):
        contract = copy.deepcopy(template)
        contract["contract_id"] = "C-" + source + "-" + destination
        contract["from_step"] = source
        contract["to_step"] = destination
        plan["contracts"].append(contract)
        sent = load("pass-sent.json")
        received = load("pass-received.json")
        for role, event in (("sent", sent), ("received", received)):
            event["event_id"] = "E-" + str(i) + "-" + role
            event["handoff_id"] = "H-" + str(i)
            event["contract_id"] = contract["contract_id"]
            event["from_step"] = source
            event["to_step"] = destination
        hops.append({"sent": sent, "received": received})
    return plan, hops


def run_dag_case(name):
    if name not in (row[0] for row in DAG_CASES):
        raise ValueError("Unknown DAG scenario")
    plan, hops = diamond()
    if name == "dag_missing_branch":
        hops.pop(1)
    elif name == "dag_duplicate_retry":
        retry = copy.deepcopy(hops[0])
        retry["sent"]["event_id"] = "E-RETRY-SENT"
        retry["received"]["event_id"] = "E-RETRY-RECEIVED"
        retry["sent"]["handoff_id"] = "H-RETRY"
        retry["received"]["handoff_id"] = "H-RETRY"
        hops.append(retry)
    elif name == "dag_replayed_event":
        hops[1]["sent"]["event_id"] = hops[0]["sent"]["event_id"]
    elif name == "dag_join_conflicting_version":
        for role in ("sent", "received"):
            hops[3][role]["artifacts"][0]["artifact_version_id"] = "V-DIVERGED"
            hops[3][role]["artifacts"][0].pop("content_sha256", None)
    elif name == "dag_fork_artifact_lost":
        for role in ("sent", "received"):
            hops[2][role]["artifacts"] = []
    elif name == "dag_cycle":
        # Rewire the C->D branch to D->A, forming a cycle A->B->D->A.
        plan["contracts"][3]["from_step"] = "D"
        plan["contracts"][3]["to_step"] = "A"
        for role in ("sent", "received"):
            hops[3][role]["from_step"] = "D"
            hops[3][role]["to_step"] = "A"
    else:
        # Deliberately reverse the observed event presentation order.
        hops.reverse()
    return compare_journey_validated(plan, hops)


class DagJourneyTests(unittest.TestCase):
    def test_dag_evidence_outcomes(self):
        for name, truth, verdict in DAG_CASES:
            with self.subTest(name=name):
                result = run_dag_case(name)
                codes = {entry["code"] for entry in result["findings"]}
                self.assertEqual(verdict, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertTrue(any(entry["verdict"] == "ALERT"
                                        for entry in result["findings"]))
                else:
                    self.assertIn("UNVERIFIABLE", codes)

    def test_legacy_linear_still_rejects_diamond(self):
        plan, hops = diamond()
        plan.pop("journey_mode")
        result = compare_journey_validated(plan, hops)
        self.assertEqual("ALERT", result["verdict"])

    def test_same_dag_in_different_input_order(self):
        plan, hops = diamond()
        result_a = compare_journey_validated(plan, hops)
        result_b = compare_journey_validated(plan, list(reversed(hops)))
        self.assertEqual("UNKNOWN", result_a["verdict"])
        self.assertEqual("UNKNOWN", result_b["verdict"])


if __name__ == "__main__":
    unittest.main()
