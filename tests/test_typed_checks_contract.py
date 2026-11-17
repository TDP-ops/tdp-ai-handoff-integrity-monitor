"""JSON Schema validation of typed declarations, not execution of file checks."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class TypedChecksContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas/handoff-v0.schema.json").read_text())
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)
        cls.base = json.loads(
            (ROOT / "examples/lot1/pass-received.json").read_text()
        )

    def with_checks(self, checks):
        manifest = copy.deepcopy(self.base)
        manifest["artifacts"][0]["checks"] = checks
        return manifest

    def test_known_structure_types_are_accepted(self):
        checks = [
            {"check_type": "image_min_dimensions", "width_px": 800, "height_px": 600},
            {"check_type": "pdf_min_pages", "min_pages": 3},
            {"check_type": "pdf_required_page_sha256", "page_index": 1, "extracted_page_sha256": "a" * 64, "extractor_id": "pdf-v1"},
            {"check_type": "docx_required_paragraph_sha256", "paragraph_index": 2, "extracted_paragraph_sha256": "b" * 64, "extractor_id": "docx-v1"},
            {"check_type": "csv_required_columns", "column_names": ["id", "status"]},
            {"check_type": "xlsx_required_sheets", "sheet_names": ["Raw", "Summary"]},
            {"check_type": "xlsx_required_columns", "sheet_name": "Raw", "column_names": ["id"]},
            {"check_type": "db_required_table", "table_name": "orders"},
            {"check_type": "db_required_column", "table_name": "orders", "column_name": "id", "data_type": "integer"},
            {"check_type": "db_required_foreign_key", "table_name": "orders", "column_name": "customer_id", "references_table": "customers", "references_column": "id"},
            {"check_type": "json_required_pointer", "pointer": "/items/0"},
            {"check_type": "audio_min_duration_ms", "duration_ms": 4000},
            {"check_type": "text_required_segment_sha256", "segment_locator": "section:summary", "extracted_segment_sha256": "c" * 64, "extractor_id": "text-v1"},
        ]
        for item in checks:
            with self.subTest(item=item["check_type"]):
                manifest = self.with_checks({"required_structure": [item]})
                self.assertFalse(list(self.validator.iter_errors(manifest)))

    def test_known_quality_types_are_accepted(self):
        checks = [
            {"check_type": "image_min_ssim", "reference_artifact_version_id": "IMG-V0", "minimum_ssim": 0.9, "algorithm_id": "ssim-skimage-v1"},
            {"check_type": "image_max_blur_score_ratio", "reference_artifact_version_id": "IMG-V0", "maximum_ratio": 1.5, "algorithm_id": "variance-of-laplacian-v1"},
            {"check_type": "audio_min_sample_rate_hz", "sample_rate_hz": 16000},
        ]
        for item in checks:
            with self.subTest(item=item["check_type"]):
                manifest = self.with_checks({"quality_invariants": [item]})
                self.assertFalse(list(self.validator.iter_errors(manifest)))

    def test_invalid_declarations_are_rejected(self):
        invalid = [
            {"required_structure": [{"check_type": "pdf_min_pages"}]},
            {"required_structure": [{"check_type": "pdf_min_pages", "min_pages": 0}]},
            {"required_structure": [{"check_type": "invented", "threshold": 1}]},
            {"required_structure": {"check_type": "image_min_dimensions", "width_px": 10, "height_px": 10}},
            {"required_structure": [{"check_type": "csv_required_columns", "column_names": []}]},
            {"required_structure": [{"check_type": "pdf_min_pages", "min_pages": 2, "unknown": True}]},
            {"quality_invariants": [{"check_type": "image_min_ssim", "reference_artifact_version_id": "V1", "minimum_ssim": 1.4, "algorithm_id": "ssim-skimage-v1"}]},
            {"quality_invariants": [{"check_type": "image_min_ssim", "reference_artifact_version_id": "V1", "minimum_ssim": 0.9, "algorithm_id": "unsupported"}]},
            {"quality_invariants": [{"check_type": "image_max_blur_score_ratio", "reference_artifact_version_id": "V1", "maximum_ratio": 0, "algorithm_id": "variance-of-laplacian-v1"}]},
            {"quality_invariants": {"audio_min_sample_rate_hz": 16000}},
        ]
        for checks in invalid:
            with self.subTest(checks=checks):
                manifest = self.with_checks(checks)
                self.assertTrue(list(self.validator.iter_errors(manifest)))

    def test_empty_optional_arrays_are_allowed(self):
        manifest = self.with_checks({"exact_bytes": True, "required_structure": [], "quality_invariants": []})
        self.assertFalse(list(self.validator.iter_errors(manifest)))


if __name__ == "__main__":
    unittest.main()
