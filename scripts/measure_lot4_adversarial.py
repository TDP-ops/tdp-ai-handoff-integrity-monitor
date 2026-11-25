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
from test_lot4_structural_abstentions import STRUCTURAL_CASES, structural_case
from test_lot4_quality_abstentions import QUALITY_CASES, quality_case
from test_lot4_adversarial_lifecycle import VIOLATIONS as LIFECYCLE_VIOLATIONS, ABSTENTIONS as LIFECYCLE_ABSTENTIONS, compare_lifecycle
from test_lot4_policy_grants import GRANT_VIOLATIONS, GRANT_ABSTENTIONS, compare_grant
from handoff_monitor import compare_handoff_validated, compare_journey_validated


# Category: violation, clean, or evidence_unavailable (not scored binary).
BASE_CASES = (
    ("equal_local_bytes", "clean"),
    ("equal_empty_bytes", "clean"),
    ("equal_binary_bytes", "clean"),
    ("equal_multichunk_bytes", "clean"),
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

    for kind, structure in STRUCTURAL_CASES:
        rows.append({"case": "unsupported_structure_" + kind,
                     "truth": "evidence_unavailable",
                     "verdict": structural_case(kind, structure)["verdict"]})
    kind, structure = STRUCTURAL_CASES[1]
    rows.append({"case": "byte_change_despite_unsupported_pdf_structure",
                 "truth": "violation",
                 "verdict": structural_case(kind, structure, tamper=True)["verdict"]})

    for kind, quality in QUALITY_CASES:
        rows.append({"case": "unsupported_quality_" + quality["check_type"],
                     "truth": "evidence_unavailable",
                     "verdict": quality_case(kind, quality)["verdict"]})
    kind, quality = QUALITY_CASES[0]
    rows.append({"case": "byte_change_despite_unavailable_image_ssim",
                 "truth": "violation",
                 "verdict": quality_case(kind, quality, tamper=True)["verdict"]})

    for name, _expected_code in LIFECYCLE_VIOLATIONS:
        rows.append({"case": name, "truth": "violation",
                     "verdict": compare_lifecycle(name)["verdict"]})
    for name in LIFECYCLE_ABSTENTIONS:
        rows.append({"case": name, "truth": "evidence_unavailable",
                     "verdict": compare_lifecycle(name)["verdict"]})

    for name, _, _ in GRANT_VIOLATIONS:
        rows.append({"case": name, "truth": "violation",
                     "verdict": compare_grant(name)["verdict"]})
    for name, _, _ in GRANT_ABSTENTIONS:
        rows.append({"case": name, "truth": "evidence_unavailable",
                     "verdict": compare_grant(name)["verdict"]})

    report = score_rows(rows)
    print(json.dumps(report, indent=2, sort_keys=True))
    expected = {"TP": 29, "FP": 0, "FN": 0, "TN": 4,
                "unknown_violation": 0, "unknown_clean": 0,
                "abstentions_unscored": 19}
    assert report["counts"] == expected, report["counts"]
    return 0


def score_rows(rows):
    """Score synthetic ground truth without hiding UNKNOWN among negative cases."""
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0,
              "unknown_violation": 0, "unknown_clean": 0,
              "abstentions_unscored": 0}
    for row in rows:
        truth, verdict = row["truth"], row["verdict"]
        if truth not in ("violation", "clean", "evidence_unavailable"):
            raise ValueError("Unsupported ground truth: " + str(truth))
        if verdict not in ("PASS", "ALERT", "UNKNOWN"):
            raise ValueError("Unsupported verdict: " + str(verdict))
        if truth == "evidence_unavailable":
            if verdict != "UNKNOWN":
                raise AssertionError(
                    f"{row['case']}: expected UNKNOWN without ground truth, got {verdict}")
            counts["abstentions_unscored"] += 1
        elif truth == "violation":
            if verdict == "ALERT":
                counts["TP"] += 1
            elif verdict == "PASS":
                counts["FN"] += 1
            else:
                counts["unknown_violation"] += 1
        else:
            if verdict == "ALERT":
                counts["FP"] += 1
            elif verdict == "PASS":
                counts["TN"] += 1
            else:
                counts["unknown_clean"] += 1

    known = sum(1 for row in rows if row["truth"] != "evidence_unavailable")
    classified = sum(counts[k] for k in ("TP", "FP", "FN", "TN"))
    precision_den = counts["TP"] + counts["FP"]
    recall_den = counts["TP"] + counts["FN"] + counts["unknown_violation"]
    clean_den = counts["TN"] + counts["FP"] + counts["unknown_clean"]
    assert known == classified + counts["unknown_violation"] + counts["unknown_clean"]
    return {
        "scope": "small_synthetic_V0_local_only",
        "total_cases": len(rows),
        "known_ground_truth_cases": known,
        "classified_known_truth_cases": classified,
        "counts": counts,
        "precision_alert_classified": counts["TP"] / precision_den if precision_den else None,
        "recall_alert_including_unknown_as_missed_detection": (
            counts["TP"] / recall_den if recall_den else None),
        "clean_pass_rate_including_unknown_as_unresolved": (
            counts["TN"] / clean_den if clean_den else None),
        "rows": rows,
        "limitations": [
            "No authenticated remote receipt.",
            "UNKNOWN on known violations or known clean cases is counted explicitly.",
            "UNKNOWN without ground truth is excluded from the binary matrix.",
            "Not representative of real-world false-positive or false-negative rates.",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(run())
