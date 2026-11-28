"""Lot 6 protects the exported static data against unvalidated source content."""
import copy
import unittest

from scripts.build_lot6_demo import sanitize


def synthetic_report():
    rows = (
        [{"case": "violation_%03d" % i, "truth": "violation", "verdict": "ALERT"}
         for i in range(69)]
        + [{"case": "clean_%03d" % i, "truth": "clean", "verdict": "PASS"}
           for i in range(20)]
        + [{"case": "unknown_%03d" % i, "truth": "evidence_unavailable",
            "verdict": "UNKNOWN"} for i in range(66)]
    )
    return {
        "scope": "small_synthetic_V0_local_only", "rows": rows,
        "total_cases": 155,
        "counts": {
            "TP": 69, "FP": 0, "FN": 0, "TN": 20,
            "unknown_violation": 0, "unknown_clean": 0,
            "abstentions_unscored": 66,
        },
        "private_metadata": "NEVER_PUBLISH"
    }


class Lot6DemoExportTests(unittest.TestCase):
    def test_scoped_public_export_is_explicitly_allowlisted(self):
        projected = sanitize(synthetic_report(), commit="a" * 40)
        self.assertEqual(155, projected["total_cases"])
        self.assertEqual(89, projected["known_ground_truth_cases"])
        self.assertEqual(66, projected["counts"]["abstentions_unscored"])
        self.assertNotIn("private_metadata", repr(projected))
        self.assertEqual(
            {"case", "truth", "verdict"}, set(projected["cases"][0]))

    def test_unsafe_case_string_fails_closed(self):
        report = synthetic_report()
        report["rows"][0]["case"] = "secret/file/path"
        with self.assertRaises(ValueError):
            sanitize(report)

    def test_duplicate_or_modified_case_fails_closed(self):
        report = synthetic_report()
        report["rows"][0]["case"] = report["rows"][1]["case"]
        with self.assertRaises(ValueError):
            sanitize(report)
        report = synthetic_report()
        report["rows"][0]["verdict"] = "PASS"
        with self.assertRaises(ValueError):
            sanitize(report)

    def test_unexpected_baseline_or_source_fails_closed(self):
        report = synthetic_report()
        report["counts"]["TP"] = 68
        with self.assertRaises(ValueError):
            sanitize(report)
        report = synthetic_report()
        report["scope"] = "production"
        with self.assertRaises(ValueError):
            sanitize(report)
        with self.assertRaises(ValueError):
            sanitize(synthetic_report(), commit="unknown")

    def test_abstentions_cannot_be_published_as_negatives(self):
        report = synthetic_report()
        report["rows"][-1]["verdict"] = "PASS"
        with self.assertRaises(ValueError):
            sanitize(report)


if __name__ == "__main__":
    unittest.main()
