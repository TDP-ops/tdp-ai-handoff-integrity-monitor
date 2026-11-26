"""Real bounded PNG dimensions via the strict handoff API.

Fixtures are generated in memory and contain actual RGB pixels, CRCs and
zlib-compressed scanlines. No remote image provenance is authenticated.
"""
import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

PNG_CASES = (
    ("png_dimensions_present", "clean", "PASS"),
    ("png_dimensions_below_minimum", "violation", "ALERT"),
    ("png_invalid_chunk_crc", "evidence_unavailable", "UNKNOWN"),
    ("png_truncated_pixel_stream", "evidence_unavailable", "UNKNOWN"),
    ("png_receiver_unavailable", "evidence_unavailable", "UNKNOWN"),
)


def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data)))


def make_png(width, height):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # Filter 0, RGB pixels: actual raster data, not header-only spoofing.
    pixels = (b"\x00" + b"\x19\x27\x39" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(pixels)) + _chunk(b"IEND", b""))


def run_png_case(name):
    if name not in (case[0] for case in PNG_CASES):
        raise ValueError("Unknown PNG case: " + name)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    width = 1 if name == "png_dimensions_below_minimum" else 2
    raw = make_png(width, 2)
    if name == "png_invalid_chunk_crc":
        raw = raw[:29] + bytes([raw[29] ^ 1]) + raw[30:]
    elif name == "png_truncated_pixel_stream":
        # Keep a valid PNG envelope but shorten the actual decompressed pixels.
        ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
        raw = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
               + _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00"))
               + _chunk(b"IEND", b""))
    for event in (sent, received):
        artifact = event["artifacts"][0]
        artifact["kind"] = "image"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [
                {"check_type": "image_min_dimensions",
                 "width_px": 2, "height_px": 2}
            ]
        }
        artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as td:
        sender = Path(td) / "sender.png"
        receiver = Path(td) / "receiver.png"
        sender.write_bytes(raw)
        receiver.write_bytes(raw)
        receiver_files = {} if name == "png_receiver_unavailable" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=receiver_files)


class ImageDimensionsTests(unittest.TestCase):
    def test_real_png_structure(self):
        for name, truth, expected in PNG_CASES:
            with self.subTest(case=name):
                result = run_png_case(name)
                codes = {item["code"] for item in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                    self.assertNotIn("EXACT_BYTES_MATCH", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                    self.assertNotIn("EXACT_BYTES_MATCH", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)

    def test_unsupported_palette_png_abstains(self):
        from handoff_monitor.image_structure import png_dimensions
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "palette.png"
            unsupported_ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 3, 0, 0, 0)
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + _chunk(b"IHDR", unsupported_ihdr)
                + _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00"))
                + _chunk(b"IEND", b""))
            with self.assertRaises(ValueError):
                png_dimensions(path)


if __name__ == "__main__":
    unittest.main()
