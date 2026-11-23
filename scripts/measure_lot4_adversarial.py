"""Lot 4 small synthetic confusion matrix, executed against the strict engine.

Ground truth is authored per scenario below, independently from engine output.
UNKNOWN cases with no observable ground truth are abstentions, not negatives.
Numbers are suite-specific, not production accuracy estimates.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_lot4_adversarial_baseline import AdversarialBaselineTests
from test_lot4_adversarial_rules import CASES, adversarial_case
from test_lot4_adversarial_journey import CASES as JOURNEY_CASES, adversarial_journey, two_hop_baseline
from test_lot4_adversarial_replacements import CASES as REPLACEMENT_CASES, replacement_baseline, replacement_case, compare as compare_replacement
from handoff_monitor import compare_handoff_validated, compare_journey_validated


# Category: violation, clean, or evidence_unavailable (not scored binary).
BASE_CASES = (
    ("equal_local_bytes", "clean"),
    ("changed_receiver_bytes", "violation"),
    ("missing_receiver_bytes", "evidence_unavailable"),
    ("receiver_not_checked", "evidence_unavailable"),
)


def run():
    rows = []
    runner = AdversarialBaselineTests()
    runner.setUp()
    for name, truth in BASE_CASES:
        verdict = runner.run_case(name)["verdict"]
        rows.append({"case": name, "truth": truth, "verdict": verdict})
    for name, _expected_code in CASES:
        plan, sent, received = adversarial_case(name)
        verdict = compare_handoff_validated(plan, sent, received)["verdict"]
        rows.append({"case": name, "truth": "violation", "verdict": verdict})

    plan, hops = two_hop_baseline()
    rows.append({"case": "valid_two_hop_no_remote_custody",
                 "truth": "evidence_unavailable",
                 "verdict": compare_journey_validated(plan, hops)["verdict"]})
    for name, _expected_code in JOURNEY_CASES:
        plan, hops = adversarial_journey(name)
        verdict = compare_journey_validated(plan, hops)["verdict"]
        rows.append({"case": name, "truth": "violation", "verdict": verdict})

    rows.append({"case": "permitted_replacement_untrusted_grant",
                 "truth": "evidence_unavailable",
                 "verdict": compare_replacement(*replacement_baseline())["verdict"]})
    for name, _expected_code in REPLACEMENT_CASES:
        plan, sent, received = replacement_case(name)
        rows.append({"case": name, "truth": "violation",
                     "verdict": compare_replacement(plan, sent, received)["verdict"]})

    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0,
              "unknown_with_known_truth": 0, "abstentions_unscored": 0}
    for row in rows:
        truth, verdict = row["truth"], row["verdict"]
        if truth == "evidence_unavailable":
            if verdict == "UNKNOWN":
                counts["abstentions_unscored"] += 1
            else:
                # Missing-ground-truth scenarios must not be promoted to evidence.
                raise AssertionError(f"{row['case']}: expected UNKNOWN, got {verdict}")
        elif verdict == "UNKNOWN":
            counts["unknown_with_known_truth"] += 1
        elif truth == "violation":
            counts["TP" if verdict == "ALERT" else "FN"] += 1
        else:
            counts["FP" if verdict == "ALERT" else "TN"] += 1

    known = sum(1 for row in rows if row["truth"] != "evidence_unavailable")
    classified = counts["TP"] + counts["TN"] + counts["FP"] + counts["FN"]
    precision_den = counts["TP"] + counts["FP"]
    recall_den = counts["TP"] + counts["FN"] + sum(
        1 for row in rows if row["truth"] == "violation" and row["verdict"] == "UNKNOWN")
    report = {
        "scope": "small_synthetic_V0_local_only",
        "total_cases": len(rows),
        "known_ground_truth_cases": known,
        "classified_known_truth_cases": classified,
        "counts": counts,
        "precision_alert_classified": (counts["TP"] / precision_den
                                       if precision_den else None),
        "recall_alert_including_unknown_as_missed_detection": (
            counts["TP"] / recall_den if recall_den else None),
        "rows": rows,
        "limitations": [
            "No authenticated remote receipt.",
            "UNKNOWN without ground truth excluded from binary confusion matrix.",
            "Not representative of real-world false-positive or false-negative rates.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    # Gate on the expected performance of this deliberately bounded synthetic
    # sample; do not turn the measured performance into a general claim.
    assert counts == {"TP": 17, "FP": 0, "FN": 0, "TN": 1,
                      "unknown_with_known_truth": 0, "abstentions_unscored": 4}, counts
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
