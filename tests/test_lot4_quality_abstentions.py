"""Lot 4: declared perceptual/audio quality checks remain UNKNOWN without metrics.

These are synthetic byte observations, NOT an SSIM, blur or audio parser test.
"""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

QUALITY_CASES = (
    ("image", {
        "check_type": "image_min_ssim",
        "reference_artifact_version_id": "ART-001-V1",
        "minimum_ssim": 0.95,
        "algorithm_id": "ssim-skimage-v1",
    }),
    ("image", {
        "check_type": "image_max_blur_score_ratio",
        "reference_artifact_version_id": "ART-001-V1",
        "maximum_ratio": 1.5,
        "algorithm_id": "variance-of-laplacian-v1",
    }),
    ("audio", {
        "check_type": "audio_min_sample_rate_hz",
        "sample_rate_hz": 16000,
    }),
)


def quality_case(kind, quality, *, tamper=False):
    plan = load("run-plan.json")
    sent = load("pass-sent.json")
    received = load("pass-received.json")
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "source"
        dest = Path(folder) / "receiver"
        source.write_bytes(b"synthetic bytes, no quality algorithm")
        dest.write_bytes(b"synthetic altered bytes" if tamper else source.read_bytes())
        for record, path in ((sent, source), (received, dest)):
            artifact = record["artifacts"][0]
            artifact["kind"] = kind
            artifact["checks"] = {
                "exact_bytes": True,
                "quality_invariants": [copy.deepcopy(quality)],
            }
            artifact["content_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": source},
            receiver_files={"ART-001": dest},
        )


class QualityAbstentionTests(unittest.TestCase):
    def test_unimplemented_quality_checks_never_pass(self):
        for kind, quality in QUALITY_CASES:
            with self.subTest(check=quality["check_type"]):
                result = quality_case(kind, quality)
                codes = {item["code"] for item in result["findings"]}
                self.assertEqual("UNKNOWN", result["verdict"])
                self.assertIn("UNVERIFIABLE", codes)
                self.assertNotIn("INVALID_MANIFEST", codes)
                self.assertNotIn("EXACT_BYTES_MATCH", codes)

    def test_actual_byte_mismatch_remains_alert(self):
        kind, quality = QUALITY_CASES[0]
        result = quality_case(kind, quality, tamper=True)
        codes = {item["code"] for item in result["findings"]}
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("HASH_MISMATCH", codes)
        self.assertIn("UNVERIFIABLE", codes)
        self.assertNotIn("EXACT_BYTES_MATCH", codes)


if __name__ == "__main__":
    unittest.main()
