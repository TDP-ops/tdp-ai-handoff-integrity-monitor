"""Tests for Lot 4 three-way synthetic scoring accounting."""
import unittest

from scripts.measure_lot4_adversarial import score_rows


class AdversarialScoringTests(unittest.TestCase):
    def test_all_categories_are_counted_without_conflating_unknown(self):
        rows = [
            {"case": "detected", "truth": "violation", "verdict": "ALERT"},
            {"case": "missed", "truth": "violation", "verdict": "PASS"},
            {"case": "unresolved_violation", "truth": "violation", "verdict": "UNKNOWN"},
            {"case": "false_alarm", "truth": "clean", "verdict": "ALERT"},
            {"case": "correct_clean", "truth": "clean", "verdict": "PASS"},
            {"case": "unresolved_clean", "truth": "clean", "verdict": "UNKNOWN"},
            {"case": "no_ground_truth", "truth": "evidence_unavailable", "verdict": "UNKNOWN"},
        ]
        report = score_rows(rows)
        self.assertEqual(
            {"TP": 1, "FP": 1, "FN": 1, "TN": 1,
             "unknown_violation": 1, "unknown_clean": 1,
             "abstentions_unscored": 1},
            report["counts"],
        )
        self.assertEqual(6, report["known_ground_truth_cases"])
        self.assertEqual(4, report["classified_known_truth_cases"])
        self.assertEqual(0.5, report["precision_alert_classified"])
        self.assertEqual(1 / 3, report["recall_alert_including_unknown_as_missed_detection"])
        self.assertEqual(1 / 3, report["clean_pass_rate_including_unknown_as_unresolved"])

    def test_without_positive_or_clean_denominator_metrics_are_null(self):
        report = score_rows([
            {"case": "missing_ground_truth", "truth": "evidence_unavailable",
             "verdict": "UNKNOWN"}
        ])
        self.assertIsNone(report["precision_alert_classified"])
        self.assertIsNone(report["recall_alert_including_unknown_as_missed_detection"])
        self.assertIsNone(report["clean_pass_rate_including_unknown_as_unresolved"])

    def test_unavailable_truth_cannot_be_turned_into_success_or_alert(self):
        for verdict in ("PASS", "ALERT"):
            with self.subTest(verdict=verdict):
                with self.assertRaises(AssertionError):
                    score_rows([{"case": "unknown_truth", "truth": "evidence_unavailable",
                                 "verdict": verdict}])

    def test_unknown_categories_are_not_silently_counted(self):
        with self.assertRaises(ValueError):
            score_rows([{"case": "invalid_truth", "truth": "ambiguous",
                         "verdict": "UNKNOWN"}])
        with self.assertRaises(ValueError):
            score_rows([{"case": "invalid_verdict", "truth": "clean",
                         "verdict": "MAYBE"}])


if __name__ == "__main__":
    unittest.main()
