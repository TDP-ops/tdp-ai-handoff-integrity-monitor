"""Lot 5 local durable trust/replay store, not a remote identity provider.

A separately administered verifier enrolls pinned Ed25519 public keys and
expected contexts. Acceptance is an atomic SQLite transaction; the receipt
producer never enrolls keys or writes this registry. The SQLite file itself
must be protected by the verifier's host and access controls.
"""
import os
import sqlite3
from pathlib import Path

from .receiver_evidence import verify_receiver_receipt

SCHEMA = """
CREATE TABLE IF NOT EXISTS trusted_keys (
 receiver_id TEXT NOT NULL,
 key_id TEXT NOT NULL,
 public_key BLOB NOT NULL CHECK(length(public_key) = 32),
 revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
 PRIMARY KEY (receiver_id, key_id)
);
CREATE TABLE IF NOT EXISTS accepted_receipts (
 receipt_id TEXT PRIMARY KEY,
 receiver_id TEXT NOT NULL,
 key_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 handoff_id TEXT NOT NULL,
 artifact_id TEXT NOT NULL,
 attempt_number INTEGER NOT NULL,
 content_sha256 TEXT NOT NULL,
 UNIQUE(receiver_id, run_id, handoff_id, artifact_id, attempt_number)
);
"""


class ReceiverTrustRegistry:
    """Single-host verifier-controlled SQLite registry.

    Administration is explicit. Never enroll a key from an untrusted receipt.
    All read+verify+insert receipt operations use BEGIN IMMEDIATE so concurrent
    checkers sharing one registry cannot both accept the same receipt.
    """

    def __init__(self, path):
        path = Path(path)
        if path.is_symlink():
            raise ValueError("Registry path must not be a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Create new registries with private file permissions on POSIX.
        if not path.exists():
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(descriptor)
            except FileExistsError:
                pass
        self.path = path
        with self._connection() as conn:
            conn.executescript(SCHEMA)

    def _connection(self):
        connection = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @staticmethod
    def _key_identity(receiver_id, key_id, public_key):
        from .receiver_evidence import IDENTIFIER
        if (not isinstance(receiver_id, str) or not IDENTIFIER.fullmatch(receiver_id)
                or not isinstance(key_id, str) or not IDENTIFIER.fullmatch(key_id)
                or not isinstance(public_key, bytes) or len(public_key) != 32):
            raise ValueError("Invalid independently provisioned public key")

    def enroll_key(self, *, receiver_id, key_id, public_key):
        """Privileged administration only: explicit immutable key enrollment."""
        self._key_identity(receiver_id, key_id, public_key)
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "INSERT INTO trusted_keys(receiver_id,key_id,public_key) "
                    "VALUES(?,?,?)", (receiver_id, key_id, public_key))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def revoke_key(self, *, receiver_id, key_id):
        """Revoke a pinned key; never accept new receipts from it."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    "UPDATE trusted_keys SET revoked=1 WHERE receiver_id=? AND key_id=?",
                    (receiver_id, key_id))
                if cursor.rowcount != 1:
                    raise ValueError("Unknown key identity")
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def rotate_key(self, *, receiver_id, old_key_id, new_key_id, new_public_key):
        """Atomically enroll a replacement key and revoke its predecessor."""
        self._key_identity(receiver_id, new_key_id, new_public_key)
        if old_key_id == new_key_id:
            raise ValueError("Key rotation requires a new key identifier")
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    "UPDATE trusted_keys SET revoked=1 "
                    "WHERE receiver_id=? AND key_id=? AND revoked=0",
                    (receiver_id, old_key_id))
                if cursor.rowcount != 1:
                    raise ValueError("Old key unknown or revoked")
                conn.execute(
                    "INSERT INTO trusted_keys(receiver_id,key_id,public_key) "
                    "VALUES(?,?,?)", (receiver_id, new_key_id, new_public_key))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def verify_and_record(self, receipt, *, expected, observed_file=None):
        """Accept one new verified receipt, or return ALERT/UNKNOWN without insertion.

        A VERIFIED_SIGNATURE result says only that a pinned key signed the
        declared content, not that an external receiver was authenticated.
        """
        if not isinstance(receipt, dict) or not isinstance(receipt.get("body"), dict):
            return {"status": "ALERT", "reason": "malformed_receipt"}
        body = receipt["body"]
        # A registry-level custody claim requires independently pinned
        # recipient identity and expected sender digest, never inferred from
        # the signed receipt. Partial context remains UNKNOWN.
        if (not isinstance(expected, dict)
                or not {"receiver_id", "content_sha256"}.issubset(expected)):
            return {"status": "UNKNOWN", "reason": "unbound_receiver_or_digest"}
        try:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    row = conn.execute(
                        "SELECT public_key,revoked FROM trusted_keys "
                        "WHERE receiver_id=? AND key_id=?",
                        (body.get("receiver_id"), body.get("key_id"))).fetchone()
                    if row is None:
                        conn.rollback()
                        return {"status": "UNKNOWN", "reason": "untrusted_receiver_key"}
                    if row[1]:
                        conn.rollback()
                        return {"status": "ALERT", "reason": "revoked_receiver_key"}
                    result = verify_receiver_receipt(
                        receipt, expected=expected,
                        trusted_public_keys={(body["receiver_id"], body["key_id"]): row[0]},
                        observed_file=observed_file,
                    )
                    if result["status"] != "VERIFIED_SIGNATURE":
                        conn.rollback()
                        return result
                    try:
                        conn.execute(
                            "INSERT INTO accepted_receipts "
                            "(receipt_id,receiver_id,key_id,run_id,handoff_id,"
                            "artifact_id,attempt_number,content_sha256) "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (body["receipt_id"], body["receiver_id"], body["key_id"],
                             body["run_id"], body["handoff_id"], body["artifact_id"],
                             body["attempt_number"], body["content_sha256"]))
                    except sqlite3.IntegrityError:
                        conn.rollback()
                        return {"status": "ALERT", "reason": "receipt_replay_or_fork"}
                    conn.commit()
                    return result
                except BaseException:
                    conn.rollback()
                    raise
        except (sqlite3.DatabaseError, OSError, ValueError, TypeError):
            return {"status": "UNKNOWN", "reason": "registry_unavailable"}
