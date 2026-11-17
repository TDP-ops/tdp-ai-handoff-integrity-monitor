"""Validate the lot 1 normative scenario matrix; does NOT run a detection engine."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "examples" / "lot1" / "acceptance-cases.json"

REQUIRED_RULE_IDS = {f"CR-{i:02d}" for i in range(1, 13)}
REQUIRED_SCENARIOS = {
    "COMPLETE_HANDOFF",
    "IMAGE_ALTERED",
    "IMAGE_COMPRESSED_ALLOWED_UNCHECKED",
    "PDF_MIDDLE_REMOVED",
    "DOCX_CONVERSION_NO_EXTRACTION",
    "CSV_MISSING_REQUIRED_COLUMNS",
    "DB_SCHEMA_MISSING_FK",
    "VERSION_REVERSION",
    "AUTHORIZED_REJECTION_REPLACEMENT",
    "UNDECLARED_REPLACEMENT",
    "SAME_FILENAME_DIFFERENT_ID",
    "ID_REUSE_DIFFERENT_LINEAGE",
    "MISSING_RECEIVER_OBSERVATION",
    "REQUIRED_RULE_DROPPED",
    "STALE_CONTRACT",
    "VALID_FORK_WITH_OLDER_VERSION",
    "REPLAYED_EVENT_ID",
}
ACCEPTED_OUTCOMES = {"PASS", "ALERT", "UNKNOWN"}
ACCEPTED_CODES = {
    "HANDOFF_INTEGRITY_VERIFIED",
    "HASH_MISMATCH",
    "UNVERIFIABLE",
    "MISSING_REQUIRED_CONTENT",
    "VERSION_ROLLBACK",
    "UNAUTHORIZED_REPLACEMENT",
    "ARTIFACT_ID_COLLISION",
    "MISSING_REQUIRED_RULE",
    "CONTRACT_MISMATCH",
    "DUPLICATE_OR_UNEXPECTED",
}


class AcceptanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.cases = cls.matrix["cases"]

    def test_explicitly_not_engine_results(self):
        self.assertEqual(
            "EXPECTED_RESULTS_ONLY_NOT_ENGINE_TESTS", self.matrix["status"]
        )
        self.assertTrue(all(c["engine_implemented"] is False for c in self.cases))
        self.assertTrue(all(c["synthetic"] is True for c in self.cases))

    def test_required_scenarios_complete_without_duplicates(self):
        actual = [c["id"] for c in self.cases]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(REQUIRED_SCENARIOS, set(actual))

    def test_rule_references_and_expected_outputs(self):
        covered = set()
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["description"].strip())
                self.assertTrue(case["rules"])
                self.assertTrue(set(case["rules"]) <= REQUIRED_RULE_IDS)
                self.assertIn(case["expected_verdict"], ACCEPTED_OUTCOMES)
                self.assertIn(case["expected_code"], ACCEPTED_CODES)
                covered.update(case["rules"])
        self.assertEqual(REQUIRED_RULE_IDS, covered)


if __name__ == "__main__":
    unittest.main()
