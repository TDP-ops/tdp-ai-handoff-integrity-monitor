"""Lot 5 receiver-side Ed25519 file receipt (scoped evidence primitive).

A receiver signs its own file observation with its private key. A separate
verifier accepts the signature only against an out-of-band pinned key registry.
No private key, network endpoint, or registry is supplied by a receipt.
A valid signature proves key possession and signed data integrity; it does
NOT by itself prove the real-world identity of a receiver or remote delivery.
"""
import base64
import hashlib
import json
import re
from pathlib import Path

DOMAIN = b"TDP-AI-HANDOFF-RECEIVER-RECEIPT-V1\x00"
FIELDS = frozenset((
    "receipt_version", "receipt_id", "receiver_id", "key_id",
    "run_id", "handoff_id", "contract_id", "contract_version",
    "from_step", "to_step", "sent_event_id", "received_event_id",
    "artifact_id", "artifact_version_id", "attempt_number",
    "content_sha256", "size_bytes",
))
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z", re.ASCII)
DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
MAX_BYTES = 32 * 1024 * 1024


def _crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey,
        )
    except ImportError as error:
        raise RuntimeError("Pinned cryptography runtime unavailable") from error
    return InvalidSignature, Ed25519PrivateKey, Ed25519PublicKey


def _validate_body(body):
    if not isinstance(body, dict) or set(body) != FIELDS:
        raise ValueError("Receiver receipt has missing or additional fields")
    if body["receipt_version"] != "tdp-receiver-ed25519-v1":
        raise ValueError("Unsupported signed receipt version")
    for name in FIELDS - {"receipt_version", "attempt_number", "size_bytes", "content_sha256"}:
        if not isinstance(body[name], str) or not IDENTIFIER.fullmatch(body[name]):
            raise ValueError("Invalid receipt identifier: " + name)
    if type(body["attempt_number"]) is not int or not 1 <= body["attempt_number"] <= 5:
        raise ValueError("Invalid attempt number")
    if type(body["size_bytes"]) is not int or not 0 <= body["size_bytes"] <= MAX_BYTES:
        raise ValueError("Invalid receipt byte size")
    if not isinstance(body["content_sha256"], str) or not DIGEST.fullmatch(body["content_sha256"]):
        raise ValueError("Invalid receipt content SHA-256")


def _payload(body):
    _validate_body(body)
    return DOMAIN + json.dumps(body, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")


def _observe(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            if size > MAX_BYTES:
                raise ValueError("Receiver observation exceeds 32 MiB")
            digest.update(block)
    return digest.hexdigest(), size


def create_receiver_receipt(*, file_path, private_key, receiver_id, key_id,
                            receipt_id, run_id, handoff_id, contract_id,
                            contract_version, from_step, to_step, sent_event_id,
                            received_event_id, artifact_id, artifact_version_id,
                            attempt_number=1):
    """Call only inside the receiver's separate trust domain.

    The private key must be provisioned locally by the receiver; do not read it
    from a manifest, generate/store it in GitHub, or include it in the receipt.
    """
    _, PrivateKey, _ = _crypto()
    if not isinstance(private_key, PrivateKey):
        raise TypeError("Private key must be an Ed25519 private key object")
    sha, size = _observe(file_path)
    body = {
        "receipt_version": "tdp-receiver-ed25519-v1",
        "receipt_id": receipt_id, "receiver_id": receiver_id, "key_id": key_id,
        "run_id": run_id, "handoff_id": handoff_id,
        "contract_id": contract_id, "contract_version": contract_version,
        "from_step": from_step, "to_step": to_step,
        "sent_event_id": sent_event_id,
        "received_event_id": received_event_id,
        "artifact_id": artifact_id, "artifact_version_id": artifact_version_id,
        "attempt_number": attempt_number,
        "content_sha256": sha, "size_bytes": size,
    }
    signature = private_key.sign(_payload(body))
    return {"body": body, "signature": base64.b64encode(signature).decode("ascii")}


def verify_receiver_receipt(receipt, *, trusted_public_keys, expected,
                            observed_file=None, seen_receipt_ids=None):
    """Return VERIFIED, ALERT or UNKNOWN, never the core comparator's PASS.

    trusted_public_keys is an independently provisioned mapping:
      (receiver_id, key_id) -> 32 raw Ed25519 public-key bytes
    expected must bind every other field except receiver identity, key ID,
    receipt ID and the measured digest/size; expected may also pin these.
    The trusted registry and expected context are owned by the verifier.
    """
    try:
        InvalidSignature, _, PublicKey = _crypto()
    except RuntimeError:
        return {"status": "UNKNOWN", "reason": "crypto_runtime_unavailable"}
    if not isinstance(receipt, dict) or set(receipt) != {"body", "signature"}:
        return {"status": "ALERT", "reason": "malformed_receipt"}
    body = receipt["body"]
    try:
        payload = _payload(body)
        signature = base64.b64decode(receipt["signature"], validate=True)
        if len(signature) != 64:
            raise ValueError("Wrong signature length")
    except (ValueError, TypeError, KeyError):
        return {"status": "ALERT", "reason": "malformed_receipt"}
    if not isinstance(expected, dict) or not expected:
        return {"status": "UNKNOWN", "reason": "expected_context_unavailable"}
    if not isinstance(trusted_public_keys, dict):
        return {"status": "UNKNOWN", "reason": "trust_registry_unavailable"}
    # A partially specified expected event context cannot establish binding.
    required_context = FIELDS - {
        "receipt_version", "receipt_id", "receiver_id", "key_id",
        "content_sha256", "size_bytes",
    }
    if not required_context.issubset(expected):
        return {"status": "UNKNOWN", "reason": "incomplete_expected_context"}
    for name, value in expected.items():
        if name not in FIELDS or body.get(name) != value:
            return {"status": "ALERT", "reason": "context_mismatch"}
    if seen_receipt_ids is not None:
        if not isinstance(seen_receipt_ids, (set, frozenset)):
            return {"status": "UNKNOWN", "reason": "replay_registry_unavailable"}
        if body["receipt_id"] in seen_receipt_ids:
            return {"status": "ALERT", "reason": "receipt_replay"}
    key = trusted_public_keys.get((body["receiver_id"], body["key_id"]))
    if key is None:
        return {"status": "UNKNOWN", "reason": "untrusted_receiver_key"}
    if not isinstance(key, bytes) or len(key) != 32:
        return {"status": "UNKNOWN", "reason": "invalid_pinned_key"}
    try:
        public_key = PublicKey.from_public_bytes(key)
        public_key.verify(signature, payload)
    except (InvalidSignature, ValueError, TypeError):
        # Includes cryptography InvalidSignature, but do not reveal key details.
        return {"status": "ALERT", "reason": "invalid_signature"}
    if observed_file is not None:
        try:
            sha, size = _observe(observed_file)
        except (OSError, ValueError):
            return {"status": "UNKNOWN", "reason": "verifier_file_unavailable"}
        if (sha, size) != (body["content_sha256"], body["size_bytes"]):
            return {"status": "ALERT", "reason": "observed_bytes_mismatch"}
    return {"status": "VERIFIED_SIGNATURE",
            "reason": "signed_measurement_matches_pinned_key_and_context"}
