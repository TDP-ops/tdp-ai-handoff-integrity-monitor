"""Real local RGB PNG image blur metrics using explicitly provided references.

The score is a bounded local observation, not proof of remote custody.
SSIM must abstain when its versioned reference image is missing.
"""
import hashlib
import tempfile
import unittest
import zlib
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from handoff_monitor.image_quality import blur_score_ratio
from test_lot4_png_dimensions import _chunk
from test_lot4_structural_abstentions import load


BLUR_CASES = (
    ("blur_reference_matches", "clean", "PASS"),
    ("blur_candidate_flat", "violation", "ALERT"),
    ("blur_reference_missing", "evidence_unavailable", "UNKNOWN"),
    ("blur_dimensions_differ", "evidence_unavailable", "UNKNOWN"),
    ("blur_both_flat", "evidence_unavailable", "UNKNOWN"),
    ("blur_invalid_receiver", "evidence_unavailable", "UNKNOWN"),
    ("ssim_reference_missing", "evidence_unavailable", "UNKNOWN"),
)


def png_rgb(width, height, *, flat=False):
    import struct
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            value = 127 if flat else (255 if (x + y) % 2 else 0)
            raw.extend((value, value, value))
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(bytes(raw)))
            + _chunk(b"IEND", b""))


def run_blur_case(name):
    if name not in (case[0] for case in BLUR_CASES):
        raise ValueError("Unknown image-quality scenario: " + name)
    with tempfile.TemporaryDirectory() as folder:
        reference = Path(folder) / "baseline.png"
        sender = Path(folder) / "sender.png"
        receiver = Path(folder) / "receiver.png"
        reference.write_bytes(png_rgb(12, 12, flat=name == "blur_both_flat"))
        flat = name in ("blur_candidate_flat", "blur_both_flat")
        size = 10 if name == "blur_dimensions_differ" else 12
        candidate = png_rgb(size, 12, flat=flat)
        if name == "blur_invalid_receiver":
            candidate = b"not PNG image evidence"
        sender.write_bytes(candidate)
        receiver.write_bytes(candidate)

        plan, sent, received = (
            load("run-plan.json"), load("pass-sent.json"),
            load("pass-received.json"))
        quality = {
            "check_type": "image_max_blur_score_ratio",
            "reference_artifact_version_id": "ART-001-V1",
            "maximum_ratio": 1.25,
            "algorithm_id": "variance-of-laplacian-v1",
        }
        if name == "ssim_reference_missing":
            quality = {
                "check_type": "image_min_ssim",
                "reference_artifact_version_id": "ART-001-V1",
                "minimum_ssim": 0.95,
                "algorithm_id": "ssim-skimage-v1",
            }
        for manifest in (sent, received):
            artifact = manifest["artifacts"][0]
            artifact["kind"] = "image"
            artifact["checks"] = {
                "exact_bytes": True,
                "quality_invariants": [quality],
            }
            artifact["content_sha256"] = hashlib.sha256(candidate).hexdigest()
        ref_paths = {} if name in ("blur_reference_missing", "ssim_reference_missing") else {
            "ART-001-V1": reference}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender},
            receiver_files={"ART-001": receiver},
            reference_files=ref_paths)


class ImageBlurTests(unittest.TestCase):
    def test_strict_local_blur_cases(self):
        for name, truth, expected in BLUR_CASES:
            with self.subTest(case=name):
                result = run_blur_case(name)
                codes = {finding["code"] for finding in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                    self.assertNotIn("EXACT_BYTES_MATCH", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)

    def test_invalid_reference_path_container_fails_closed(self):
        plan, sent, received = (
            load("run-plan.json"), load("pass-sent.json"),
            load("pass-received.json"))
        result = compare_handoff_validated(
            plan, sent, received, reference_files={"ART-001-V1": 456})
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("INVALID_MANIFEST",
                      {f["code"] for f in result["findings"]})

    def test_same_raster_has_unit_laplacian_ratio(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.png"
            path.write_bytes(png_rgb(12, 12))
            ref_num, ref_den, cand_num, cand_den = blur_score_ratio(path, path)
            self.assertGreater(ref_num, 0)
            self.assertEqual(ref_num * cand_den, cand_num * ref_den)


if __name__ == "__main__":
    unittest.main()
