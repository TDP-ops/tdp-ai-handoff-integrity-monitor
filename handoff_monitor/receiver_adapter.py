"""Receiver-domain adapter creating a contextual receipt from actual local bytes.

The receiver, not the sender, invokes this adapter with its privately held
signing key. Manifest assertions and paths alone do not authenticate identity.
"""
import secrets
from pathlib import Path

from .receiver_evidence import create_receiver_receipt, _observe
from .validation import validate_handoff_records


def receive_and_sign(*, plan, sent, received, artifact_id, file_path,
                     receiver_id, key_id, private_key):
    """Fail closed if the observed bytes contradict recipient declarations.

    The caller must run this inside the recipient's separately controlled
    process/host, with a private key never shared with the sender.
    """
    errors = validate_handoff_records(plan, sent, received)
    if errors:
        raise ValueError("Invalid plan or handoff manifest")
    if (sent["manifest_role"] != "sent" or received["manifest_role"] != "received"
            or sent["run_id"] != received["run_id"]
            or sent["run_id"] != plan["run_id"]
            or any(sent[key] != received[key] for key in (
                "handoff_id", "contract_id", "contract_version",
                "from_step", "to_step"))):
        raise ValueError("Handoff identity mismatch")
    matches = [c for c in plan["contracts"] if (
        c["contract_id"] == sent["contract_id"]
        and c["version"] == sent["contract_version"]
        and c["from_step"] == sent["from_step"]
        and c["to_step"] == sent["to_step"])]
    if len(matches) != 1:
        raise ValueError("No unique matching contract")
    if (sent.get("attempt_number", 1) != received.get("attempt_number", 1)
            or sent.get("retry_of_handoff_id") != received.get("retry_of_handoff_id")):
        raise ValueError("Inconsistent attempt metadata")
    attempt = received.get("attempt_number", 1)
    if attempt > matches[0].get("max_attempts", 1):
        raise ValueError("Retry exceeds declared contract")
    artifacts = [a for a in received["artifacts"] if a["artifact_id"] == artifact_id]
    if len(artifacts) != 1:
        raise ValueError("Recipient artifact missing or duplicated")
    artifact = artifacts[0]
    if artifact.get("observation", {}).get("access") != "verified":
        raise ValueError("Recipient did not declare available local observation")
    path = Path(file_path)
    if not path.is_file():
        raise ValueError("Receiver evidence path is not a regular file")
    observed_sha, size = _observe(path)
    if (artifact.get("content_sha256") != observed_sha
            or (artifact.get("size_bytes") is not None
                and artifact["size_bytes"] != size)):
        raise ValueError("Receiver-declared evidence differs from observed bytes")
    # Receipt identity is newly generated inside receiver domain.
    receipt_id = "RCPT-" + secrets.token_hex(16)
    return create_receiver_receipt(
        file_path=path, private_key=private_key,
        receiver_id=receiver_id, key_id=key_id, receipt_id=receipt_id,
        run_id=received["run_id"], handoff_id=received["handoff_id"],
        contract_id=received["contract_id"],
        contract_version=received["contract_version"],
        from_step=received["from_step"], to_step=received["to_step"],
        sent_event_id=sent["event_id"], received_event_id=received["event_id"],
        artifact_id=artifact_id,
        artifact_version_id=artifact["artifact_version_id"],
        attempt_number=attempt,
    )
