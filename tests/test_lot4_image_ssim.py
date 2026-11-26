"""Pinned scikit-image SSIM with actual aligned RGB8 PNG reference evidence."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from handoff_monitor import compare_handoff_validated
from handoff_monitor.image_quality import local_ssim
from test_lot4_image_blur import png_rgb
from test_lot4_structural_abstentions import load

SSIM_CASES = (
    ("ssim_identical", "clean", "PASS"),
    ("ssim_identical_constant", "clean", "PASS"),
    ("ssim_flattened", "violation", "ALERT"),
    ("ssim_contrast_changed", "violation", "ALERT"),
    ("ssim_reference_unavailable", "evidence_unavailable", "UNKNOWN"),
    ("ssim_misaligned", "evidence_unavailable", "UNKNOWN"),
    ("ssim_invalid_image", "evidence_unavailable", "UNKNOWN"),
)


def run_ssim_case(name):
    if name not in (item[0] for item in SSIM_CASES):
        raise ValueError("Unknown SSIM case")
    with tempfile.TemporaryDirectory() as folder:
        reference = Path(folder) / "reference.png"
        sender = Path(folder) / "sender.png"
        receiver = Path(folder) / "receiver.png"
        reference.write_bytes(png_rgb(12, 12, flat=(name == "ssim_identical_constant")))
        candidate = png_rgb(12, 12, flat=name in (
            "ssim_identical_constant", "ssim_flattened"))
        if name == "ssim_contrast_changed":
            # Invert alternating source pixels by offsetting the phase.
            candidate = _invert_rgb(candidate)
        elif name == "ssim_misaligned":
            candidate = png_rgb(9, 12)
        elif name == "ssim_invalid_image":
            candidate = b"invalid PNG image"
        sender.write_bytes(candidate)
        receiver.write_bytes(candidate)
        plan, sent, received = (
            load("run-plan.json"), load("pass-sent.json"),
            load("pass-received.json"))
        check = {
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
                "quality_invariants": [check],
            }
            artifact["content_sha256"] = hashlib.sha256(candidate).hexdigest()
        references = ({} if name == "ssim_reference_unavailable"
                      else {"ART-001-V1": reference})
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender},
            receiver_files={"ART-001": receiver},
            reference_files=references)


def _invert_rgb(png):
    import struct
    import zlib
    from test_lot4_png_dimensions import _chunk
    # The generator uses a single IDAT with filter 0 for each row.
    marker = png.index(b"IDAT")
    length = struct.unpack(">I", png[marker - 4:marker])[0]
    rows = bytearray(zlib.decompress(png[marker + 4:marker + 4 + length]))
    for i in range(0, len(rows), 37):
        for x in range(i + 1, min(i + 37, len(rows))):
            rows[x] = 255 - rows[x]
    return png[:marker - 4] + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b"")


class SsimLocalTests(unittest.TestCase):
    def test_strict_ssim_cases(self):
        for name, truth, expected in SSIM_CASES:
            with self.subTest(name=name):
                result = run_ssim_case(name)
                codes = {item["code"] for item in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)

    def test_pinned_runtime_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "image.png"
            path.write_bytes(png_rgb(12, 12))
            with patch("skimage.__version__", "0.0.0"):
                with self.assertRaisesRegex(ValueError, "Unverified SSIM"):
                    local_ssim(path, path)

    def test_ssim_identical_is_unity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "image.png"
            path.write_bytes(png_rgb(12, 12))
            self.assertAlmostEqual(local_ssim(path, path), 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
