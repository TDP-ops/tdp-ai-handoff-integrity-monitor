"""V0 deterministic handoff checks (partial implementation).

Manifest assertions are not independent evidence. Only caller-supplied file
paths are opened and hashed; independent receiver provenance is a later lot.
"""
from __future__ import annotations
import hashlib
from pathlib import Path


def observe_file(path):
    """Measure digest and byte count from the same stream of file contents.

    This is one read, not an atomic filesystem snapshot; concurrent mutation
    and path provenance remain outside the trust guarantees of lot 3.
    """
    h = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            h.update(chunk)
    return h.hexdigest(), size


def digest_file(path):
    """Return the SHA-256 computed over bytes actually read."""
    return observe_file(path)[0]


def finding(code, verdict, artifact_id=None, explanation=""):
    item = {"code": code, "verdict": verdict,
            "evidence_status": "observed" if verdict == "ALERT" else "unavailable",
            "explanation": explanation}
    if artifact_id is not None:
        item["artifact_id"] = artifact_id
    return item


def index_artifacts(items, issues, role):
    result = {}
    if not isinstance(items, list):
        issues.append(finding("INVALID_MANIFEST", "ALERT",
                              explanation=role + ": artifact inventory must be a list"))
        return result
    for a in items:
        if not isinstance(a, dict):
            issues.append(finding("INVALID_MANIFEST", "ALERT",
                                  explanation=role + ": artifact entry must be an object"))
            continue
        aid = a.get("artifact_id")
        if not isinstance(aid, str) or not aid:
            issues.append(finding("INVALID_MANIFEST", "ALERT",
                                  explanation=role + ": invalid artifact ID"))
            continue
        if aid in result:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT", aid, role + ": duplicate ID"))
            continue
        if (not isinstance(a.get("artifact_version_id"), str)
                or not a["artifact_version_id"]
                or not isinstance(a.get("kind"), str)
                or not a["kind"]
                or type(a.get("required")) is not bool
                or not isinstance(a.get("observation"), dict)
                or not a["observation"].get("source")
                or not a["observation"].get("access")
                or not isinstance(a.get("checks", {}), dict)):
            issues.append(finding("INVALID_MANIFEST", "ALERT", aid,
                                  role + ": missing or malformed artifact identity/observation"))
            if not isinstance(a.get("checks", {}), dict):
                # Invalid checks cannot safely be evaluated downstream.
                continue
        result[aid] = a
    return result


def compare_handoff(plan, sent, received, *, sender_files=None, receiver_files=None, reference_files=None, history=None, policy_grants=None):
    """Return a deterministic verdict for one boundary and local file evidence.

    Does not authenticate caller-supplied evidence. Unsupported file extractors
    yield UNKNOWN; lineage and lifecycle checks are conservative and accept
    optional historical records / grants whose provenance is caller-owned.
    Schema validation remains a separate input prerequisite.
    """
    issues = []
    sender_files, receiver_files = sender_files or {}, receiver_files or {}
    reference_files = reference_files or {}
    if sent.get("manifest_role") != "sent" or received.get("manifest_role") != "received":
        issues.append(finding("INVALID_MANIFEST", "ALERT", explanation="Manifest roles are incorrect"))
    if (not isinstance(sent.get("event_id"), str) or not sent["event_id"]
            or not isinstance(received.get("event_id"), str) or not received["event_id"]):
        issues.append(finding("INVALID_MANIFEST", "ALERT",
                              explanation="Missing or invalid handoff event ID"))
    elif sent["event_id"] == received["event_id"]:
        issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT", explanation="Event ID reused"))
    for field in ("run_id", "handoff_id", "from_step", "to_step", "contract_id", "contract_version"):
        if not sent.get(field) or sent.get(field) != received.get(field):
            issues.append(finding("CONTRACT_MISMATCH", "ALERT", explanation=field + " mismatch"))
    if sent.get("run_id") != plan.get("run_id") or received.get("run_id") != plan.get("run_id"):
        issues.append(finding("CONTRACT_MISMATCH", "ALERT", explanation="Run plan differs"))
    matches = [c for c in plan.get("contracts", []) if
               c.get("contract_id") == sent.get("contract_id")
               and c.get("version") == sent.get("contract_version")
               and c.get("from_step") == sent.get("from_step")
               and c.get("to_step") == sent.get("to_step")]
    if len(matches) != 1:
        issues.append(finding("CONTRACT_MISMATCH", "ALERT", explanation="No unique contract"))
        return {"handoff_id": sent.get("handoff_id"), "verdict": "ALERT", "findings": issues}
    contract = matches[0]
    # A boundary must belong to the declared route, not merely to an
    # attacker-supplied contract with matching identifiers.
    # Full schema validation is an input prerequisite; older local test
    # fixtures without 'steps' retain their legacy semantics.
    if "steps" in plan:
        steps = plan["steps"]
        boundary = (sent.get("from_step"), sent.get("to_step"))
        allowed_boundaries = set(zip(steps, steps[1:]))
        if (len(steps) != len(set(steps))
                or boundary not in allowed_boundaries):
            issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                  explanation="Boundary is not adjacent in the declared run plan"))
    required_rules = set(contract.get("required_rule_ids", []))
    if not set(plan.get("critical_rule_ids", [])).issubset(required_rules):
        issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", explanation="Contract omits run-critical rules"))
    for role, manifest in (("sent", sent), ("received", received)):
        missing = required_rules - set(manifest.get("rule_ids", []))
        if missing:
            issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", explanation=role + ": " + str(sorted(missing))))
    left = index_artifacts(sent.get("artifacts", []), issues, "sent")
    right = index_artifacts(received.get("artifacts", []), issues, "received")
    from .lineage import check_lineage, check_lifecycle, check_replacements
    accepted_old, accepted_new, replacement_issues = check_replacements(
        left, right, received, contract, policy_grants=policy_grants)
    issues.extend(replacement_issues)
    required = set(contract.get("required_artifact_ids", []))
    for aid in sorted(required):
        if aid not in left or (aid not in right and aid not in accepted_old):
            issues.append(finding("MISSING_REQUIRED_ARTIFACT", "ALERT", aid))
    for aid in sorted(set(left) ^ set(right)):
        if aid not in accepted_old and aid not in accepted_new and aid not in required:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT", aid, "Inventory changed"))
    issues.extend(check_lineage(left, right, history=history))
    issues.extend(check_lifecycle(sent, received, contract, policy_grants=policy_grants))
    accepted = contract.get("accepted_versions", {})
    for aid in sorted(accepted_new):
        a = right[aid]
        if aid not in receiver_files:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                  "No actual replacement receiver bytes available"))
            continue
        try:
            received_digest = digest_file(receiver_files[aid])
        except (OSError, ValueError) as error:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid, type(error).__name__))
            continue
        if a.get("content_sha256") is not None and received_digest != a["content_sha256"]:
            issues.append(finding("DECLARED_HASH_MISMATCH", "ALERT", aid,
                                  "Replacement digest disagrees with locally observed bytes"))
        else:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                  "Replacement origin and authorization unverified"))
    for aid in sorted(set(left) & set(right)):
        a, b = left[aid], right[aid]
        av, bv = a.get("artifact_version_id"), b.get("artifact_version_id")
        if a.get("kind") != b.get("kind"):
            issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid, "Kind differs"))
        if a.get("required") != b.get("required") or (aid in required and a.get("required") is not True):
            issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", aid,
                                  "Required artifact status weakened or inconsistent"))
        if av != bv:
            issues.append(finding("VERSION_ROLLBACK", "ALERT", aid, "Version differs"))
        if av not in accepted.get(aid, []) or bv not in accepted.get(aid, []):
            issues.append(finding("STALE_ARTIFACT_VERSION", "ALERT", aid, "Version not accepted"))
        if (a.get("parent_version_ids", []) != b.get("parent_version_ids", [])
                or a.get("derived_from_artifact_ids", []) != b.get("derived_from_artifact_ids", [])
                or a.get("replaces_artifact_id") != b.get("replaces_artifact_id")):
            issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Lineage differs"))
        ac, bc = a.get("checks", {}), b.get("checks", {})
        # Locally available files cannot override an observation explicitly
        # marked inaccessible or unchecked in a manifest. This still does not
        # authenticate an access="verified" claim (lot 5).
        if (a.get("observation", {}).get("access") != "verified"
                or b.get("observation", {}).get("access") != "verified"):
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                  "Sender or receiver access not verified in manifest"))
        if (a.get("observation", {}).get("source") == "receiver"
                or b.get("observation", {}).get("source") == "sender"):
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                  "Observation source contradicts handoff role"))
        # The receiver cannot silently remove or weaken declared controls.
        # Equal declarations are still claims, not independently audited policy.
        if ac != bc:
            issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", aid,
                                  "Artifact check declarations differ across handoff"))
        # Structure checks inspect supported local sender/receiver formats.
        # Unsupported typed extractors must abstain instead of claiming PASS.
        if ac.get("required_structure") or bc.get("required_structure"):
            from .structure import check_structure
            declared = ac.get("required_structure", [])
            issues.extend(check_structure(
                a.get("kind"), declared,
                sender_files.get(aid), receiver_files.get(aid), aid))
        if ac.get("quality_invariants") or bc.get("quality_invariants"):
            if a.get("kind") == "audio":
                from .structure import check_audio_quality
                issues.extend(check_audio_quality(
                    ac.get("quality_invariants", []),
                    sender_files.get(aid), receiver_files.get(aid), aid))
            elif a.get("kind") == "image":
                from .structure import check_image_quality
                issues.extend(check_image_quality(
                    ac.get("quality_invariants", []),
                    sender_files.get(aid), receiver_files.get(aid),
                    reference_files, aid))
            else:
                issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                      "Quality metric not implemented"))
        unsupported = bool(ac.get("required_structure") or bc.get("required_structure")
                           or ac.get("quality_invariants") or bc.get("quality_invariants"))
        if ac.get("exact_bytes") is not True and bc.get("exact_bytes") is not True:
            if not unsupported:
                issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid, "No supported checks configured"))
            continue
        if aid not in sender_files or aid not in receiver_files:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid, "Both actual byte observations required"))
            continue
        try:
            sha_a, size_a = observe_file(sender_files[aid])
            sha_b, size_b = observe_file(receiver_files[aid])
        except (OSError, ValueError) as error:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid, type(error).__name__))
            continue
        for declaration, observed_size, role in ((a, size_a, "sender"),
                                                  (b, size_b, "receiver")):
            if declaration.get("size_bytes") is not None and declaration["size_bytes"] != observed_size:
                issues.append(finding("DECLARED_SIZE_MISMATCH", "ALERT", aid,
                                      role + " declared size differs from opened file"))
        if a.get("size_bytes") is not None and b.get("size_bytes") is not None and a["size_bytes"] != b["size_bytes"]:
            issues.append(finding("DECLARED_SIZE_MISMATCH", "ALERT", aid,
                                  "Declared sizes disagree across exact-byte handoff"))
        if a.get("content_sha256") is not None and a["content_sha256"] != sha_a:
            issues.append(finding("DECLARED_HASH_MISMATCH", "ALERT", aid, "Sent digest does not match bytes"))
        if b.get("content_sha256") is not None and b["content_sha256"] != sha_b:
            issues.append(finding("DECLARED_HASH_MISMATCH", "ALERT", aid, "Received digest does not match bytes"))
        if sha_a != sha_b:
            issues.append(finding("HASH_MISMATCH", "ALERT", aid, "Actual file bytes differ"))
        elif not any(
                f.get("artifact_id") == aid and f["verdict"] in ("ALERT", "UNKNOWN")
                for f in issues):
            issues.append({"code": "EXACT_BYTES_MATCH", "verdict": "PASS", "artifact_id": aid,
                           "evidence_status": "observed", "explanation": "Locally computed byte hashes match"})
    if not left and not right:
        issues.append(finding("UNVERIFIABLE", "UNKNOWN", explanation="Empty inventory"))
    verdict = ("ALERT" if any(i["verdict"] == "ALERT" for i in issues) else
               "UNKNOWN" if any(i["verdict"] == "UNKNOWN" for i in issues) else "PASS")
    if verdict == "PASS" and not any(i["code"] == "EXACT_BYTES_MATCH" for i in issues):
        issues.append(finding("UNVERIFIABLE", "UNKNOWN", explanation="No measured evidence"))
        verdict = "UNKNOWN"
    return {"handoff_id": sent.get("handoff_id"), "verdict": verdict, "findings": issues}
