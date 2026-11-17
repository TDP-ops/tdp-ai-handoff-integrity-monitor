"""Validate synthetic contract fixtures only. Not a runtime integrity engine."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "lot1"
SCHEMA_PATH = ROOT / "schemas" / "handoff-v0.schema.json"

VALID_FILES = [
    "run-plan.json",
    "pass-sent.json",
    "pass-received.json",
    "pass-finding.json",
    "alert-received.json",
    "alert-finding.json",
    "unknown-received.json",
    "unknown-finding.json",
]
INVALID_FILES = [
    "invalid-missing-artifact-id.json",
    "invalid-bad-sha256.json",
]


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class ContractFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = read_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def test_valid_fixtures(self):
        for name in VALID_FILES:
            with self.subTest(name=name):
                errors = list(self.validator.iter_errors(read_json(FIXTURES / name)))
                self.assertEqual([], errors, f"{name}: {errors}")

    def test_invalid_fixtures(self):
        for name in INVALID_FILES:
            with self.subTest(name=name):
                errors = list(self.validator.iter_errors(read_json(FIXTURES / name)))
                self.assertTrue(errors, f"{name} must be rejected")

    def test_manifest_example_identity(self):
        sent = read_json(FIXTURES / "pass-sent.json")
        received = read_json(FIXTURES / "pass-received.json")
        self.assertEqual(sent["handoff_id"], received["handoff_id"])
        self.assertEqual(sent["artifacts"][0]["artifact_id"], received["artifacts"][0]["artifact_id"])
        self.assertEqual(sent["artifacts"][0]["content_sha256"], received["artifacts"][0]["content_sha256"])

    def test_alert_example_has_different_bytes_digest(self):
        sent = read_json(FIXTURES / "pass-sent.json")
        altered = read_json(FIXTURES / "alert-received.json")
        self.assertNotEqual(sent["artifacts"][0]["content_sha256"], altered["artifacts"][0]["content_sha256"])
        finding = read_json(FIXTURES / "alert-finding.json")
        self.assertEqual(("HASH_MISMATCH", "ALERT"), (finding["code"], finding["verdict"]))

    def test_unknown_example_has_no_observed_bytes(self):
        unknown = read_json(FIXTURES / "unknown-received.json")["artifacts"][0]
        self.assertNotIn("content_sha256", unknown)
        self.assertFalse(unknown["observation"]["hash_computed_from_bytes"])
        finding = read_json(FIXTURES / "unknown-finding.json")
        self.assertEqual(("UNVERIFIABLE", "UNKNOWN"), (finding["code"], finding["verdict"]))


if __name__ == "__main__":
    unittest.main()
