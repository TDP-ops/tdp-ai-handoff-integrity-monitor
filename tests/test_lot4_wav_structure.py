"""Real bounded PCM WAV duration and sample-rate checks on local evidence.

These checks do not establish intelligibility, semantic completeness or
independent receiver-side custody. Other audio encodings must abstain.
"""
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

WAV_CASES = (
    ("wav_valid_duration_and_rate", "clean", "PASS"),
    ("wav_insufficient_duration", "violation", "ALERT"),
    ("wav_insufficient_sample_rate", "violation", "ALERT"),
    ("wav_truncated_samples", "evidence_unavailable", "UNKNOWN"),
    ("wav_receiver_unavailable", "evidence_unavailable", "UNKNOWN"),
)


def run_wav_case(name):
    if name not in (entry[0] for entry in WAV_CASES):
        raise ValueError("Unknown WAV scenario: " + name)
    plan, sent, received = (
        load("run-plan.json"), load("pass-sent.json"), load("pass-received.json"))
    for event in (sent, received):
        artifact = event["artifacts"][0]
        artifact["kind"] = "audio"
        artifact["checks"] = {
            "exact_bytes": True,
            "required_structure": [
                {"check_type": "audio_min_duration_ms", "duration_ms": 1000}],
            "quality_invariants": [
                {"check_type": "audio_min_sample_rate_hz", "sample_rate_hz": 16000}],
        }
    rate = 8000 if name == "wav_insufficient_sample_rate" else 16000
    frames = rate // 2 if name == "wav_insufficient_duration" else rate
    with tempfile.TemporaryDirectory() as td:
        sender = Path(td) / "sender.wav"
        receiver = Path(td) / "receiver.wav"
        with wave.open(str(sender), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(b"\x00\x00" * frames)
        raw = sender.read_bytes()
        if name == "wav_truncated_samples":
            raw = raw[:-100]
            sender.write_bytes(raw)
        receiver.write_bytes(raw)
        for event in (sent, received):
            event["artifacts"][0]["content_sha256"] = hashlib.sha256(raw).hexdigest()
        receiver_files = {} if name == "wav_receiver_unavailable" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received, sender_files={"ART-001": sender},
            receiver_files=receiver_files)


class WavIntegrityTests(unittest.TestCase):
    def test_actual_wav_observations(self):
        for name, truth, expected in WAV_CASES:
            with self.subTest(case=name):
                result = run_wav_case(name)
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


if __name__ == "__main__":
    unittest.main()
