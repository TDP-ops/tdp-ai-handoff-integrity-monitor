"""Minimal two-role command-line adapter for signed handoff evidence.

Receiver operations keep the Ed25519 private key on the receiver filesystem.
Verifier operations require an independently approved key fingerprint and an
independently assembled expected-context JSON file. A receipt must never be
used as the source of either trust input. This CLI does not provide transport.
"""
import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

from .receiver_adapter import receive_and_sign
from .receiver_registry import ReceiverTrustRegistry


def _json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def _raw_public(private):
    from cryptography.hazmat.primitives import serialization
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)


def _init_receiver(key_path, public_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_path = Path(key_path)
    public = Path(public_path)
    if private_path.resolve(strict=False) == public.resolve(strict=False):
        raise ValueError("Private and public key paths must differ")
    if private_path.is_symlink() or public.is_symlink():
        raise ValueError("Key paths cannot be symbolic links")
    key = Ed25519PrivateKey.generate()
    secret = key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption())
    # O_EXCL prevents replacing a key; 0600 prevents accidental group access.
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(secret)
    except BaseException:
        private_path.unlink(missing_ok=True)
        raise
    public_bytes = _raw_public(key)
    try:
        with public.open("xb") as handle:
            handle.write(public_bytes)
    except BaseException:
        # Do not leave a newly generated orphaned private key.
        private_path.unlink(missing_ok=True)
        raise
    return {"status": "RECEIVER_KEY_CREATED",
            "public_key_sha256": hashlib.sha256(public_bytes).hexdigest(),
            "public_key_path": str(public),
            "private_key_path": str(private_path)}


def _load_private(path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key_path = Path(path)
    info = key_path.lstat()
    if not stat.S_ISREG(info.st_mode) or key_path.is_symlink():
        raise ValueError("Private key must be a regular non-symlink file")
    if os.name == "posix" and info.st_mode & 0o077:
        raise ValueError("Private key permissions must be owner-only")
    secret = key_path.read_bytes()
    if len(secret) != 32:
        raise ValueError("Invalid receiver private key")
    return Ed25519PrivateKey.from_private_bytes(secret)


def _receiver_sign(args):
    key = _load_private(args.private_key)
    signed = receive_and_sign(
        plan=_json(args.plan), sent=_json(args.sent),
        received=_json(args.received), artifact_id=args.artifact_id,
        file_path=args.file, receiver_id=args.receiver_id,
        key_id=args.key_id, private_key=key)
    destination = Path(args.output)
    if destination.is_symlink():
        raise ValueError("Receipt destination may not be a symbolic link")
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(signed, handle, sort_keys=True, indent=2)
        handle.write("\n")
    return {"status": "RECEIPT_SIGNED", "receipt_path": str(destination),
            "receipt_id": signed["body"]["receipt_id"]}


def _verifier_enroll(args):
    key = Path(args.public_key).read_bytes()
    registry = ReceiverTrustRegistry(args.registry)
    registry.enroll_pinned_key(
        receiver_id=args.receiver_id,
        key_id=args.key_id,
        public_key=key,
        independently_expected_sha256=args.approved_fingerprint)
    return {"status": "PINNED_KEY_ENROLLED", "receiver_id": args.receiver_id,
            "key_id": args.key_id}


def _verifier_verify(args):
    registry = ReceiverTrustRegistry(args.registry)
    expected = _json(args.expected)
    return registry.verify_and_record(
        _json(args.receipt), expected=expected,
        observed_file=args.observed_file)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m handoff_monitor.receiver_cli",
        description="Separate receiver and verifier evidence operations")
    sub = parser.add_subparsers(dest="command", required=True)
    key = sub.add_parser("receiver-init", help="Generate receiver-local private/public key files")
    key.add_argument("--private-key", required=True)
    key.add_argument("--public-key", required=True)

    sign = sub.add_parser("receiver-sign", help="Sign recipient-observed bytes")
    for name in ("private-key", "plan", "sent", "received", "artifact-id",
                 "file", "receiver-id", "key-id", "output"):
        sign.add_argument("--" + name, required=True)

    enroll = sub.add_parser("verifier-enroll", help="Enroll against independently approved pin")
    for name in ("registry", "public-key", "receiver-id", "key-id",
                 "approved-fingerprint"):
        enroll.add_argument("--" + name, required=True)

    verify = sub.add_parser("verifier-verify", help="Verify and atomically register one receipt")
    for name in ("registry", "receipt", "expected"):
        verify.add_argument("--" + name, required=True)
    verify.add_argument("--observed-file")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "receiver-init":
            result = _init_receiver(args.private_key, args.public_key)
        elif args.command == "receiver-sign":
            result = _receiver_sign(args)
        elif args.command == "verifier-enroll":
            result = _verifier_enroll(args)
        else:
            result = _verifier_verify(args)
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "ERROR", "reason": type(error).__name__}),
              file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in (
        "RECEIVER_KEY_CREATED", "RECEIPT_SIGNED",
        "PINNED_KEY_ENROLLED", "VERIFIED_SIGNATURE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
