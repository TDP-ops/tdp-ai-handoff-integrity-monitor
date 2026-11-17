"""Conservative multi-hop coherence checks.

A journey is an ordered list of {"sent": manifest, "received": manifest}.
All data is caller-supplied; it is NOT authenticated receipt evidence.
"""
from .core import compare_handoff, finding


def _items(manifest):
    result = {}
    for obj in manifest.get("artifacts", []):
        key = obj.get("artifact_id")
        if key in result:
            return None
        result[key] = obj
    return result


def _boundary_key(event):
    return (event.get("run_id"), event.get("handoff_id"),
            event.get("from_step"), event.get("to_step"),
            event.get("contract_id"), event.get("contract_version"))


def compare_journey(plan, handoffs, *, file_evidence=None):
    """Check ordered, adjacent boundaries and continuity of artifact identity.

    Does not authenticate caller-supplied path evidence or history. Version
    changes *between* hops can be legitimate but need independent version and
    policy evidence; otherwise UNKNOWN, never unqualified PASS.
    """
    issues = []
    per_handoff = []
    evidence = file_evidence or {}
    steps = plan.get("steps", [])
    if len(steps) != len(set(steps)) or not steps:
        issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                              explanation="Run plan steps invalid or duplicated"))
    if not handoffs:
        issues.append(finding("UNVERIFIABLE", "UNKNOWN", explanation="No handoffs supplied"))
    seen_events, seen_handoffs = set(), set()
    previous = None
    for idx, hop in enumerate(handoffs):
        sent, received = hop["sent"], hop["received"]
        key = _boundary_key(sent)
        if sent.get("run_id") != plan.get("run_id"):
            issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                  explanation="Cross-run manifest"))
        if key[1] in seen_handoffs:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                  explanation="Handoff ID reused"))
        seen_handoffs.add(key[1])
        for ev in (sent, received):
            eid = ev.get("event_id")
            if not eid or eid in seen_events:
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Missing or duplicate run event ID"))
            seen_events.add(eid)
        if idx >= len(steps) - 1 or (sent.get("from_step"), sent.get("to_step")) != (
                steps[idx], steps[idx+1]):
            issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                  explanation="Handoff not in declared linear step order"))
        supplied = evidence.get(key[1], {})
        result = compare_handoff(
            plan, sent, received,
            sender_files=supplied.get("sender_files"),
            receiver_files=supplied.get("receiver_files"))
        per_handoff.append(result)
        if previous is not None:
            earlier, now = previous, sent
            if earlier.get("to_step") != now.get("from_step"):
                issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                      explanation="Disconnected agent boundary"))
            left, right = _items(earlier), _items(now)
            if left is None or right is None:
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Duplicate artifact in inter-hop inventory"))
            else:
                for aid in sorted(set(left) - set(right)):
                    issues.append(finding("MISSING_REQUIRED_ARTIFACT", "ALERT", aid,
                                          "Received artifact not carried forward"))
                for aid in sorted(set(right) - set(left)):
                    issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT", aid,
                                          "New artifact requires explicit source and policy"))
                for aid in sorted(set(left) & set(right)):
                    earlier_art, now_art = left[aid], right[aid]
                    old_v, new_v = earlier_art.get("artifact_version_id"), now_art.get("artifact_version_id")
                    if old_v != new_v:
                        parents = now_art.get("parent_version_ids", [])
                        contracts = [c for c in plan.get("contracts", [])
                                     if c.get("contract_id") == now.get("contract_id")
                                     and c.get("version") == now.get("contract_version")
                                     and c.get("from_step") == now.get("from_step")
                                     and c.get("to_step") == now.get("to_step")]
                        modification_permitted = (
                            len(contracts) == 1
                            and "modified" in contracts[0].get("allowed_lifecycle_events", [])
                        )
                        events = [e for e in now.get("lifecycle_events", [])
                                  if e.get("event_type") == "modified"
                                  and e.get("artifact_id") == aid
                                  and e.get("artifact_version_id") == new_v
                                  and e.get("step_id") == now.get("from_step")]
                        if old_v not in parents or not events or not modification_permitted:
                            issues.append(finding("VERSION_ROLLBACK", "ALERT", aid,
                                                  "Version transition lacks applicable parent, event or policy"))
                        elif any(e.get("authorized_by_policy") is False for e in events):
                            issues.append(finding("UNDECLARED_TRANSFORMATION", "ALERT", aid,
                                                  "Modification expressly unauthorized"))
                        else:
                            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                                  "Version transition declared but not authenticated"))
                    if old_v == new_v and (earlier_art.get("content_sha256") and now_art.get("content_sha256")
                            and earlier_art["content_sha256"] != now_art["content_sha256"]):
                        issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid,
                                              "Same version has conflicting declared digests"))
                    if earlier_art.get("kind") != now_art.get("kind"):
                        issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid,
                                              "Artifact kind changed across hops"))
                    # A later sender must not silently weaken the exact
                    # obligations received by the preceding agent. The
                    # receiver-to-next-sender edge is a separate trust boundary.
                    if earlier_art.get("checks", {}) != now_art.get("checks", {}):
                        issues.append(finding("MISSING_REQUIRED_RULE", "ALERT", aid,
                                              "Artifact checks changed between hops"))
                    # An unchanged version cannot silently shed its known
                    # digest; absence may be observation loss, not tampering.
                    if (old_v == new_v
                            and earlier_art.get("content_sha256")
                            and not now_art.get("content_sha256")):
                        issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                              "Known version digest absent at next sender"))
        previous = received
    if len(handoffs) != max(len(steps) - 1, 0):
        issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                              explanation="Run has missing or unexpected handoffs"))
    verdicts = [x["verdict"] for x in per_handoff] + [x["verdict"] for x in issues]
    verdict = ("ALERT" if "ALERT" in verdicts else "UNKNOWN")
    # A locally consistent journey is not proof of remote receipt.
    if verdict == "UNKNOWN" and not issues and per_handoff and all(
            x["verdict"] == "PASS" for x in per_handoff):
        issues.append(finding("UNVERIFIABLE", "UNKNOWN",
                              explanation="Independent agent custody not established"))
    return {"run_id": plan.get("run_id"), "verdict": verdict,
            "handoffs": per_handoff, "findings": issues}
