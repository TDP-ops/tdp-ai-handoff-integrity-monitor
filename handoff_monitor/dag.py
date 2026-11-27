"""Opt-in DAG handoff comparison on explicit contract edges.

This is not a retry event store, graph scheduler, or remote custody system.
Each declared edge has one accepted outcome; bounded retries are permitted only
with explicit, consecutive attempt identities and immutable payload identity.
Input presentation order is not the causal attempt order.
"""
from collections import defaultdict, deque

from .core import compare_handoff, finding
from .journey import _boundary_key, _items


def compare_dag_journey(plan, handoffs, *, file_evidence=None):
    issues, results = [], []
    steps = plan.get("steps", [])
    valid_steps = set(steps)
    edges = defaultdict(list)
    indegrees = {step: 0 for step in steps}
    contracts = plan.get("contracts", [])
    by_edge = {}
    for contract in contracts:
        u, v = contract["from_step"], contract["to_step"]
        edge = (u, v)
        if u == v or u not in valid_steps or v not in valid_steps or edge in by_edge:
            issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                  explanation="DAG has repeated, self or unknown edge"))
            continue
        by_edge[edge] = contract
        edges[u].append(v)
        indegrees[v] += 1
    zero = deque(sorted(step for step, degree in indegrees.items() if degree == 0))
    visited = []
    while zero:
        u = zero.popleft()
        visited.append(u)
        for v in sorted(edges[u]):
            indegrees[v] -= 1
            if indegrees[v] == 0:
                zero.append(v)
    if len(visited) != len(steps):
        issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                              explanation="DAG cycle detected"))
    if len(steps) > 1 and len(by_edge) < len(steps) - 1:
        issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                              explanation="DAG missing connecting edges"))
    if len(steps) > 1:
        seen = set()
        undirected = defaultdict(set)
        for u, v in by_edge:
            undirected[u].add(v)
            undirected[v].add(u)
        stack = [steps[0]]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(undirected[node] - seen)
        if len(seen) != len(steps):
            issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                  explanation="DAG contains disconnected components"))

    attempts_by_edge = defaultdict(list)
    observed_edges, observed_events, observed_handoffs = {}, set(), set()
    evidence = file_evidence or {}
    for hop in handoffs:
        sent, received = hop["sent"], hop["received"]
        edge = (sent["from_step"], sent["to_step"])
        key = _boundary_key(sent)
        if (sent["run_id"] != plan["run_id"] or edge not in by_edge):
            issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                  explanation="Observed handoff not in declared DAG"))
        else:
            contract = by_edge[edge]
            if (sent["contract_id"], sent["contract_version"]) != (
                    contract["contract_id"], contract["version"]):
                issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                      explanation="DAG edge contract mismatch"))
        attempts_by_edge[edge].append(hop)
        if key[1] in observed_handoffs:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                  explanation="Reused DAG handoff ID"))
        observed_handoffs.add(key[1])
        for event in (sent, received):
            event_id = event["event_id"]
            if event_id in observed_events:
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Replayed DAG event ID"))
            observed_events.add(event_id)
        supplied = evidence.get(key[1], {})
        results.append(compare_handoff(
            plan, sent, received,
            sender_files=supplied.get("sender_files"),
            receiver_files=supplied.get("receiver_files")))

    # Explicitly declared retry policy is a caller claim, not authenticated
    # approval. For the bounded local gate it can remove duplicate-edge
    # alerts, but the overall DAG result still cannot be PASS.
    for edge, attempts in attempts_by_edge.items():
        if edge not in by_edge:
            continue
        contract = by_edge[edge]
        permitted = contract.get("max_attempts", 1)
        if len(attempts) > permitted:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                  explanation="DAG edge retry count exceeds declared limit"))
        indexed = {}
        for hop in attempts:
            sent, received = hop["sent"], hop["received"]
            number = sent.get("attempt_number")
            previous_id = sent.get("retry_of_handoff_id")
            if (number != received.get("attempt_number")
                    or previous_id != received.get("retry_of_handoff_id")):
                issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                                      explanation="Retry metadata differs across roles"))
            if number is None and len(attempts) == 1 and previous_id is None:
                number = 1  # Existing single-edge V0 DAG manifests remain valid.
            if (type(number) is not int or number < 1 or
                    number in indexed or (number > 1 and previous_id is None)
                    or (number == 1 and previous_id is not None)):
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Missing, repeated or invalid retry attempt"))
                continue
            indexed[number] = hop
        if set(indexed) != set(range(1, len(attempts) + 1)):
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                  explanation="Retry sequence missing attempt or ambiguous order"))
            continue
        for number in range(2, len(attempts) + 1):
            prior = indexed[number - 1]["sent"]["handoff_id"]
            if indexed[number]["sent"].get("retry_of_handoff_id") != prior:
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Retry predecessor handoff mismatch"))
        # Replay must not silently alter the original payload or obligations.
        first = indexed[1]["sent"]
        baseline = _items(first)
        if baseline is None:
            issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                  explanation="Invalid original retry payload"))
        else:
            baseline_view = {aid: (
                a.get("artifact_version_id"), a.get("content_sha256"),
                a.get("required"), a.get("kind"), a.get("checks"),
                a.get("parent_version_ids"), a.get("derived_from_artifact_ids"),
                a.get("replaces_artifact_id"))
                for aid, a in baseline.items()}
            for number in range(2, len(attempts) + 1):
                for role in ("sent", "received"):
                    current = _items(indexed[number][role])
                    view = None if current is None else {aid: (
                        a.get("artifact_version_id"), a.get("content_sha256"),
                        a.get("required"), a.get("kind"), a.get("checks"),
                        a.get("parent_version_ids"), a.get("derived_from_artifact_ids"),
                        a.get("replaces_artifact_id"))
                        for aid, a in current.items()}
                    if view != baseline_view:
                        issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT",
                                              explanation="Retry changed artifact identity or obligations"))
        # Only final declared attempt supplies downstream fork/join inventory.
        observed_edges[edge] = indexed[len(attempts)]

    for edge in by_edge.keys() - observed_edges.keys():
        issues.append(finding("CONTRACT_MISMATCH", "ALERT",
                              explanation="Missing declared DAG boundary"))

    # Every outgoing handoff from a fork must preserve all known required
    # artifacts received on incoming edges. At a join, contradictory
    # artifact versions or digests across parents are not silently merged.
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for (u, v), hop in observed_edges.items():
        if (u, v) not in by_edge:
            continue
        incoming[v].append(hop["received"])
        outgoing[u].append(hop["sent"])
    for node in steps:
        arrivals = incoming[node]
        departures = outgoing[node]
        baseline = {}
        for received in arrivals:
            artifacts = _items(received)
            if artifacts is None:
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Duplicate arriving DAG artifact"))
                continue
            for aid, artifact in artifacts.items():
                prior = baseline.get(aid)
                if prior is not None and (
                        prior.get("artifact_version_id") != artifact.get("artifact_version_id")
                        or (prior.get("content_sha256") and artifact.get("content_sha256")
                            and prior["content_sha256"] != artifact["content_sha256"])
                        or prior.get("kind") != artifact.get("kind")
                        or prior.get("checks") != artifact.get("checks")):
                    issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid,
                                          "Conflicting incoming versions at DAG join"))
                baseline[aid] = artifact
        for sent in departures:
            artifacts = _items(sent)
            if artifacts is None:
                issues.append(finding("DUPLICATE_OR_UNEXPECTED", "ALERT",
                                      explanation="Duplicate outgoing DAG artifact"))
                continue
            for aid, prior in baseline.items():
                if not prior.get("required"):
                    continue
                current = artifacts.get(aid)
                if current is None:
                    issues.append(finding("MISSING_REQUIRED_ARTIFACT", "ALERT", aid,
                                          "Required DAG artifact not propagated"))
                elif current.get("artifact_version_id") != prior.get("artifact_version_id"):
                    issues.append(finding("UNVERIFIABLE", "UNKNOWN", aid,
                                          "DAG transformation needs trusted lineage proof"))
                elif (current.get("kind") != prior.get("kind")
                      or current.get("checks") != prior.get("checks")
                      or (prior.get("content_sha256") and current.get("content_sha256")
                          and prior["content_sha256"] != current["content_sha256"])):
                    issues.append(finding("ARTIFACT_ID_COLLISION", "ALERT", aid,
                                          "Unchanged DAG artifact lost integrity"))

    verdicts = [r["verdict"] for r in results] + [f["verdict"] for f in issues]
    if "ALERT" in verdicts:
        verdict = "ALERT"
    else:
        verdict = "UNKNOWN"  # no authenticated independent receiver custody
        if not issues:
            issues.append(finding("UNVERIFIABLE", "UNKNOWN",
                                  explanation="DAG custody evidence not authenticated"))
    return {"run_id": plan["run_id"], "verdict": verdict,
            "handoffs": results, "findings": issues}
