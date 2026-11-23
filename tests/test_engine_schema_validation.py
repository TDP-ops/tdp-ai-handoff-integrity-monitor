"""Schema-first validation of full V0 records before any byte comparison."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from handoff_monitor.validation import compare_handoff_validated, validate_handoff_records

ROOT = Path(__file__).resolve().parents[1] / "examples" / "lot1"


def fixture(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class StrictValidationTests(unittest.TestCase):
    def setUp(self):
        self.plan = fixture("run-plan.json")
        self.sent = fixture("pass-sent.json")
        self.received = fixture("pass-received.json")

    def check_invalid(self):
        result = compare_handoff_validated(self.plan, self.sent, self.received)
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_canonical_examples_are_schema_valid(self):
        self.assertEqual([], validate_handoff_records(self.plan, self.sent, self.received))

    def test_unchanged_declared_digest_without_files_is_unknown(self):
        self.assertEqual("UNKNOWN", compare_handoff_validated(
            self.plan, self.sent, self.received)["verdict"])

    def test_local_bytes_can_pass_after_schema_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            sender = Path(folder) / "sender.bin"
            receiver = Path(folder) / "receiver.bin"
            sender.write_bytes(b"synthetic unchanged bytes")
            receiver.write_bytes(b"synthetic unchanged bytes")
            value = hashlib.sha256(sender.read_bytes()).hexdigest()
            self.sent["artifacts"][0]["content_sha256"] = value
            self.received["artifacts"][0]["content_sha256"] = value
            result = compare_handoff_validated(self.plan, self.sent, self.received,
                sender_files={"ART-001": sender}, receiver_files={"ART-001": receiver})
            self.assertEqual("PASS", result["verdict"])

    def test_invalid_sender_file_container_is_alert(self):
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, sender_files=[])
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {item["code"] for item in result["findings"]})

    def test_invalid_receiver_file_container_is_alert(self):
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, receiver_files="bad")
        self.assertEqual("ALERT", result["verdict"])

    def test_non_path_value_is_alert(self):
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, sender_files={"ART-001": 42})
        self.assertEqual("ALERT", result["verdict"])

    def test_blank_path_and_bad_artifact_key_are_alert(self):
        for paths in ({"ART-001": "  "}, {7: "example.bin"}, {"ART-001": None}):
            with self.subTest(paths=paths):
                result = compare_handoff_validated(
                    self.plan, self.sent, self.received, receiver_files=paths)
                self.assertEqual("ALERT", result["verdict"])

    def test_valid_missing_path_remains_unknown(self):
        result = compare_handoff_validated(
            self.plan, self.sent, self.received,
            sender_files={"ART-001": Path("/nonexistent-handoff-sender-file")},
            receiver_files={"ART-001": Path("/nonexistent-handoff-receiver-file")})
        self.assertEqual("UNKNOWN", result["verdict"])

    def test_non_collection_history_is_rejected(self):
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history={"artifact_id": "ART-001"})
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_malformed_historical_record_is_rejected(self):
        for history in ([None], [{"artifact_id": "ART-001"}],
                        [{"artifact_id": "ART-001", "artifact_version_id": "v1",
                          "parent_version_ids": "v0"}]):
            with self.subTest(history=history):
                result = compare_handoff_validated(
                    self.plan, self.sent, self.received, history=history)
                self.assertEqual("ALERT", result["verdict"])

    def test_missing_history_kind_is_rejected_as_invalid(self):
        record = {"artifact_id": "ART-001", "artifact_version_id": "ART-001-V1"}
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_non_string_history_kind_is_rejected(self):
        record = dict(self.sent["artifacts"][0])
        record["kind"] = ["image"]
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_unsupported_history_kind_is_rejected(self):
        record = dict(self.sent["artifacts"][0])
        record["kind"] = "not-supported"
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("ALERT", result["verdict"])

    def test_malformed_history_digest_is_rejected(self):
        for digest in ("not-a-hash", "A" * 64, 42, False):
            with self.subTest(digest=digest):
                record = dict(self.sent["artifacts"][0])
                record["content_sha256"] = digest
                result = compare_handoff_validated(
                    self.plan, self.sent, self.received, history=[record])
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_valid_historical_kind_and_digest_are_accepted_as_inputs(self):
        record = dict(self.sent["artifacts"][0])
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertNotIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})
        self.assertEqual("UNKNOWN", result["verdict"])

    def test_history_missing_required_observation_is_rejected(self):
        record = dict(self.sent["artifacts"][0])
        record.pop("observation")
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_history_invalid_size_and_observation_are_rejected(self):
        for change in (
                {"size_bytes": -1},
                {"observation": {"source": "invented", "access": "verified"}},
                {"extra_untrusted": True}):
            with self.subTest(change=change):
                record = dict(self.sent["artifacts"][0])
                record.update(change)
                result = compare_handoff_validated(
                    self.plan, self.sent, self.received, history=[record])
                self.assertEqual("ALERT", result["verdict"])
                self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_history_duplicate_parent_ids_are_rejected(self):
        record = dict(self.sent["artifacts"][0])
        record["parent_version_ids"] = ["v0", "v0"]
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("ALERT", result["verdict"])

    def test_history_invalid_nested_checks_are_rejected(self):
        record = dict(self.sent["artifacts"][0])
        record["checks"] = {"exact_bytes": "yes"}
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST", {f["code"] for f in result["findings"]})

    def test_non_collection_grants_are_rejected(self):
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, policy_grants={"policy": "invalid"})
        self.assertEqual("ALERT", result["verdict"])

    def test_malformed_grant_triples_are_rejected(self):
        for grants in ([None], [("policy", "modified")],
                       [("policy", "modified", 3)],
                       [("policy", "", "ART-001")]):
            with self.subTest(grants=grants):
                result = compare_handoff_validated(
                    self.plan, self.sent, self.received, policy_grants=grants)
                self.assertEqual("ALERT", result["verdict"])

    def test_well_formed_untrusted_history_does_not_authenticate_lineage(self):
        record = dict(self.sent["artifacts"][0])
        record["parent_version_ids"] = []
        result = compare_handoff_validated(
            self.plan, self.sent, self.received, history=[record])
        self.assertEqual("UNKNOWN", result["verdict"])

    def test_missing_plan_version_never_passes(self):
        self.plan.pop("plan_version")
        self.check_invalid()

    def test_unknown_plan_field_never_passes(self):
        self.plan["untrusted"] = True
        self.check_invalid()

    def test_missing_contract_transform_policy_never_passes(self):
        self.plan["contracts"][0].pop("allowed_transforms")
        self.check_invalid()

    def test_invalid_receiver_observation_never_passes(self):
        self.received["artifacts"][0]["observation"]["source"] = "invented"
        self.check_invalid()

    def test_mismatched_typed_check_never_passes(self):
        self.received["artifacts"][0]["checks"]["required_structure"] = [
            {"check_type": "pdf_min_pages", "min_pages": 2}]
        self.check_invalid()

    def test_invalid_sha256_never_passes(self):
        self.received["artifacts"][0]["content_sha256"] = "not-a-hash"
        self.check_invalid()

    def test_non_object_manifest_never_passes(self):
        self.received = None
        self.check_invalid()

    def test_root_finding_is_not_accepted_as_event(self):
        self.received = fixture("pass-finding.json")
        self.check_invalid()


if __name__ == "__main__":
    unittest.main()
