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
        elif artifact.get("parent_version_ids", []) != records[key].get("parent_version_ids", []):
            issues.append(finding("BROKEN_REFERENCE", "ALERT", aid,
                                  "Current version parents disagree with history"))
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
    return issues


def check_lifecycle(sent, received, contract, policy_grants=None):
    """Validate declared lifecycle events against a separately supplied grant set.

    policy_grants consists of (policy_ref, event_type, artifact_id) tuples.
    The caller must independently validate grants and their version/scope.
    This function does not authenticate them.
    """
    issues = []
    allowed = set(contract.get("allowed_lifecycle_events", []))
    all_events = sent.get("lifecycle_events", []) + received.get("lifecycle_events", [])
    for event in all_events:
        aid = event.get("artifact_id")
        typ = event.get("event_type")
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
        if typ == "replaced":
            old = event.get("replaces_artifact_id")
            if not old or old == aid:
                issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid, "Replacement requires distinct prior ID"))
            if old and old not in contract.get("allowed_replacements", []):
                issues.append(finding("UNAUTHORIZED_REPLACEMENT", "ALERT", aid, "Old ID not permitted for replacement"))
    return issues
