"""Lot 5: combine V0 local evaluation with receiver-signed evidence safely.

Never upgrade a local PASS or a valid key signature to a claim of authenticated
remote delivery. The independent verifier context must be caller-provisioned.
"""
from .core import observe_file
from .validation import compare_handoff_validated


def compare_handoff_with_custody(
        plan, sent, received, *, sender_files=None, receiver_files=None,
        registry=None, receipts=None, expected_receiver_id=None,
        reference_files=None, history=None, policy_grants=None):
    """Report local integrity and independently checked signed receipts.

    The registry is verifier-owned; never pass a registry controlled by the
    sender/recipient. Only an independently observed sender file provides the
    digest to which the receiver receipt is bound. This local demonstration
    cannot authenticate physical separation of hosts or operators.
    """
    local = compare_handoff_validated(
        plan, sent, received, sender_files=sender_files,
        receiver_files=receiver_files, reference_files=reference_files,
        history=history, policy_grants=policy_grants)
    results = {}
    if local["verdict"] == "ALERT":
        return {
            "verdict": "ALERT", "local_verdict": "ALERT",
            "custody_status": "NOT_EVALUATED",
            "receipt_results": results, "local_result": local,
        }

    # Treat absent or invalid custody configuration as lack of evidence;
    # never let receipt validation accept unsigned/manifest-only claims.
    if (registry is None or not callable(getattr(registry, "verify_and_record", None))
            or not isinstance(receipts, dict)
            or not isinstance(sender_files, dict)
            or not isinstance(expected_receiver_id, str)
            or not expected_receiver_id):
        return {
            "verdict": "UNKNOWN", "local_verdict": local["verdict"],
            "custody_status": "UNKNOWN", "receipt_results": results,
            "local_result": local,
        }

    inventory = received.get("artifacts", [])
    if not isinstance(inventory, list):
        return {
            "verdict": "ALERT", "local_verdict": local["verdict"],
            "custody_status": "ALERT", "receipt_results": results,
            "local_result": local,
        }
    required_ids = set()
    for contract in plan.get("contracts", []):
        if (contract.get("contract_id") == sent.get("contract_id")
                and contract.get("version") == sent.get("contract_version")
                and contract.get("from_step") == sent.get("from_step")
                and contract.get("to_step") == sent.get("to_step")):
            required_ids.update(contract.get("required_artifact_ids", []))
    required_ids.update(a.get("artifact_id") for a in inventory if a.get("required") is True)
    # A receipt may only assert a uniquely identified recipient artifact.
    by_id = {a["artifact_id"]: a for a in inventory if isinstance(a, dict) and "artifact_id" in a}
    if not required_ids or set(receipts) - set(by_id):
        return {
            "verdict": "ALERT" if set(receipts) - set(by_id) else "UNKNOWN",
            "local_verdict": local["verdict"],
            "custody_status": "ALERT" if set(receipts) - set(by_id) else "UNKNOWN",
            "receipt_results": results, "local_result": local,
        }

    for aid in sorted(required_ids):
        artifact = by_id.get(aid)
        receipt = receipts.get(aid)
        sender_path = sender_files.get(aid)
        if artifact is None or receipt is None:
            results[aid] = {"status": "UNKNOWN", "reason": "required_evidence_missing"}
            continue
        if sender_path is None:
            results[aid] = {"status": "UNKNOWN", "reason": "sender_bytes_unavailable"}
            continue
        try:
            sha, size = observe_file(sender_path)
        except (OSError, ValueError, TypeError):
            results[aid] = {"status": "UNKNOWN", "reason": "sender_bytes_unavailable"}
            continue
        if (artifact.get("content_sha256") != sha
                or artifact.get("size_bytes") not in (None, size)):
            results[aid] = {"status": "ALERT", "reason": "sender_manifest_mismatch"}
            continue
        expected = {
            "receiver_id": expected_receiver_id,
            "content_sha256": sha,
            "size_bytes": size,
            "run_id": plan["run_id"],
            "handoff_id": sent["handoff_id"],
            "contract_id": sent["contract_id"],
            "contract_version": sent["contract_version"],
            "from_step": sent["from_step"],
            "to_step": sent["to_step"],
            "sent_event_id": sent["event_id"],
            "received_event_id": received["event_id"],
            "artifact_id": aid,
            "artifact_version_id": artifact["artifact_version_id"],
            "attempt_number": received.get("attempt_number", 1),
        }
        results[aid] = registry.verify_and_record(receipt, expected=expected)

    statuses = [result["status"] for result in results.values()]
    if "ALERT" in statuses:
        custody_status = "ALERT"
        verdict = "ALERT"
    elif len(statuses) == len(required_ids) and all(
            x == "VERIFIED_SIGNATURE" for x in statuses):
        custody_status = "VERIFIED_SIGNATURES"
        # The independent remote deployment / key-provisioning boundary has
        # not been demonstrated, and the local comparator may be UNKNOWN.
        verdict = "UNKNOWN"
    else:
        custody_status = "UNKNOWN"
        verdict = "UNKNOWN"
    return {
        "verdict": verdict, "local_verdict": local["verdict"],
        "custody_status": custody_status, "receipt_results": results,
        "local_result": local,
    }
