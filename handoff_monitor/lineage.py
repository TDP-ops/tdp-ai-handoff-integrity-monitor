"""Deterministic, conservative lineage and lifecycle checks.

These checks do not authenticate a policy or a historical event's issuer.
A missing trusted grant produces UNKNOWN rather than false authorization.
"""
from .core import finding


def check_lineage(left, right, history=None):
    """Check local parent consistency and optional complete trusted history.

    history is an optional collection of historical artifact records, already
    vetted by the caller; its provenance is NOT established here.
    """
    issues = []
    records = {}
    if history is not None:
        for artifact in history:
            aid, version = artifact.get("artifact_id"), artifact.get("artifact_version_id")
            if not aid or not version:
                issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Invalid history identity"))
                continue
            key = (aid, version)
            if key in records and records[key] != artifact:
                issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid, "Conflicting history version"))
            records[key] = artifact
    for aid in sorted(set(left) & set(right)):
        a, b = left[aid], right[aid]
        parents_a, parents_b = a.get("parent_version_ids", []), b.get("parent_version_ids", [])
        if len(parents_a) != len(set(parents_a)) or len(parents_b) != len(set(parents_b)):
            issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Duplicate parents"))
        if any(p == a.get("artifact_version_id") for p in parents_a):
            issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Self-parent version"))
        if a.get("replaces_artifact_id") == aid or b.get("replaces_artifact_id") == aid:
            issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid, "Replacement identity reused"))
    if history is None:
        if any(a.get("parent_version_ids") or a.get("derived_from_artifact_ids")
               or a.get("replaces_artifact_id")
               for a in list(left.values()) + list(right.values())):
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", explanation="Lineage history unavailable"))
        return issues
    for aid, artifact in list(left.items()) + list(right.items()):
        key = (aid, artifact.get("artifact_version_id"))
        if key not in records:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                  "Current artifact version absent from supplied history"))
        else:
            record = records[key]
            if (artifact.get("parent_version_ids", []) != record.get("parent_version_ids", [])
                    or artifact.get("derived_from_artifact_ids", []) != record.get("derived_from_artifact_ids", [])
                    or artifact.get("replaces_artifact_id") != record.get("replaces_artifact_id")):
                issues.append(finding("BROKEN_REFERENCE", "ALERT", aid,
                                      "Current version lineage disagrees with history"))
            if artifact.get("kind") != record.get("kind"):
                issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid,
                                      "Current artifact kind conflicts with history"))
            if (artifact.get("content_sha256") is not None
                    and record.get("content_sha256") is not None
                    and artifact["content_sha256"] != record["content_sha256"]):
                issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid,
                                      "Current version digest conflicts with history"))
    # Parent references are scoped to the same logical artifact.
    for key, artifact in records.items():
        aid, version = key
        for parent in artifact.get("parent_version_ids", []):
            if (aid, parent) not in records:
                issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Unknown parent version"))
        for source_aid in artifact.get("derived_from_artifact_ids", []):
            if not any(x == source_aid for x, _ in records):
                issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Unknown derived-from artifact"))
        replaced = artifact.get("replaces_artifact_id")
        if replaced and (replaced == aid or not any(x == replaced for x, _ in records)):
            issues.append(finding("BROKEN_REFERENCE", "ALERT", aid, "Replacement parent missing or self"))
    states = {}
    def visit(key):
        state = states.get(key, 0)
        if state == 1:
            return True
        if state == 2:
            return False
        states[key] = 1
        obj = records.get(key, {})
        for parent in obj.get("parent_version_ids", []):
            ref = (key[0], parent)
            if ref in records and visit(ref):
                return True
        states[key] = 2
        return False
    if any(visit(key) for key in records if states.get(key) != 2):
        issues.append(finding("BROKEN_REFERENCE", "ALERT", explanation="Cyclic version ancestry"))
    if any(artifact.get("parent_version_ids") or artifact.get("derived_from_artifact_ids")
           or artifact.get("replaces_artifact_id")
           for artifact in list(left.values()) + list(right.values())):
        issues.append(finding("UNVERIFIABLE", "UNKNOWN",
                              explanation="Supplied lineage history is not independently authenticated"))
    return issues


def check_lifecycle(sent, received, contract, policy_grants=None):
    """Validate declared lifecycle events against a separately supplied grant set.

    policy_grants consists of (policy_ref, event_type, artifact_id) tuples.
    The caller must independently validate grants and their version/scope.
    This function does not authenticate them.
    """
    issues = []
    allowed = set(contract.get("allowed_lifecycle_events", []))
    # Lifecycle claims must belong to the manifest's own boundary step.
    all_events = (
        [(event, sent.get("from_step")) for event in sent.get("lifecycle_events", [])]
        + [(event, received.get("to_step")) for event in received.get("lifecycle_events", [])]
    )
    for event, expected_step in all_events:
        aid = event.get("artifact_id")
        typ = event.get("event_type")
        if (typ in ("rejected", "retired", "modified")
                and event.get("step_id") != expected_step):
            code = ("UNDECLARED_REJECTION" if typ in ("rejected", "retired")
                    else "UNDECLARED_TRANSFORMATION")
            issues.append(finding(code, "ALERT", aid,
                                  "Lifecycle event step differs from manifest owner"))
        if typ not in allowed:
            issues.append(finding("UNDECLARED_REJECTION" if typ in ("rejected","retired") else "UNDECLARED_TRANSFORMATION",
                                  "ALERT", aid, "Event not in active contract"))
        if typ not in ("rejected", "retired", "replaced", "modified"):
            continue
        if typ in ("rejected", "retired") and not event.get("reason"):
            issues.append(finding("UNDECLARED_REJECTION", "ALERT", aid, "Missing reason"))
        if event.get("authorized_by_policy") is False:
            issues.append(finding("UNAUTHORIZED_REPLACEMENT" if typ == "replaced" else "UNDECLARED_REJECTION",
                                  "ALERT", aid, "Explicitly unauthorized event"))
        elif policy_grants is None:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid, "Policy grant not independently supplied"))
        elif (event.get("policy_ref"), typ, aid) not in policy_grants:
            issues.append(finding("UNAUTHORIZED_REPLACEMENT" if typ == "replaced" else "UNDECLARED_REJECTION",
                                  "ALERT", aid, "No matching approved grant"))
        else:
            # The grant set is supplied by the caller; a matching tuple is not
            # an authenticated issuer assertion, nor proof of its policy scope.
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                  "Matching policy grant has unverified provenance"))
        if typ == "replaced":
            old = event.get("replaces_artifact_id")
            if not old or old == aid:
                issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid, "Replacement requires distinct prior ID"))
            if old and old not in contract.get("allowed_replacements", []):
                issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", aid, "Old ID not permitted for replacement"))
    return issues


def check_replacements(left, right, received, contract, policy_grants=None):
    """Return (recognized_old_ids, recognized_new_ids, findings).

    This accepts only explicit one-to-one old->new declarations, with a
    matching active contract, replacement event and explicit new version.
    Even a matching caller-supplied grant is NOT independently authenticated:
    a valid substitution therefore remains UNKNOWN at this trust boundary.
    """
    issues = []
    recognized_old = set()
    recognized_new = set()
    added = set(right) - set(left)
    removed = set(left) - set(right)
    declared = [e for e in received.get("lifecycle_events", [])
                if e.get("event_type") == "replaced"]
    used_old = set()
    seen_new = set()
    for event in declared:
        new = event.get("artifact_id")
        old = event.get("replaces_artifact_id")
        if new in seen_new or old in used_old:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT", new,
                                  "Replacement not one-to-one"))
            continue
        seen_new.add(new)
        if old:
            used_old.add(old)
        if not new or not old or new == old:
            issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", new,
                                  "Replacement IDs must be distinct"))
            continue
        if old not in removed or new not in added:
            issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", new,
                                  "Replacement must match removed source and added destination"))
            continue
        if right[new].get("replaces_artifact_id") != old:
            issues.append(finding("BROKEN_REFERENCE", "ALERT", new,
                                  "Destination artifact does not identify replaced source"))
            continue
        if event.get("step_id") != received.get("to_step"):
            issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", new,
                                  "Replacement event does not belong to receiving step"))
            continue
        if (old not in contract.get("allowed_replacements", [])
                or "replaced" not in contract.get("allowed_lifecycle_events", [])):
            issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", new,
                                  "Replacement not permitted by active contract"))
            continue
        if right[new].get("artifact_version_id") not in contract.get("accepted_versions", {}).get(new, []):
            issues.append(finding("STALE_ARTIFACT_VERSION", "ALERT", new,
                                  "Replacement version not explicitly accepted"))
            continue
        if event.get("authorized_by_policy") is not True:
            issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", new,
                                  "No declared authorization"))
            continue
        if policy_grants is None:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN", new,
                                  "Missing independent replacement policy grant"))
            continue
        if (event.get("policy_ref"), "replaced", new) not in policy_grants:
            issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", new,
                                  "Replacement policy grant does not match"))
            continue
        recognized_old.add(old)
        recognized_new.add(new)
        issues.append(finding("UNVERIFIABLE", "UNKNOWN", new,
                              "Policy and receiver bytes have not been independently authenticated"))
    return recognized_old, recognized_new, issues
