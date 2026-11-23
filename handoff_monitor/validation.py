"""Strict JSON Schema entrypoint for the deterministic V0 handoff comparator.

Unlike the historical core comparator, this entrypoint rejects invalid inputs
before evaluating any local byte evidence. Authenticity of the files, policies
and receiver observations is still outside the V0 trust boundary.
"""
import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from .core import compare_handoff, finding


@lru_cache(maxsize=1)
def _validators():
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "handoff-v0.schema.json"
    with schema_path.open(encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft202012Validator.check_schema(schema)
    return {
        definition: Draft202012Validator({
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": "#/$defs/" + definition,
        })
        for definition in ("run_plan", "event")
    }


def validate_handoff_records(plan, sent, received):
    """Return schema errors for one run plan and two manifests.

    This checks each record against its *specific* definition, not merely the
    root oneOf that would also admit a finding object.
    """
    validators = _validators()
    problems = []
    for label, record, definition in (
            ("plan", plan, "run_plan"),
            ("sent", sent, "event"),
            ("received", received, "event")):
        errors = sorted(validators[definition].iter_errors(record),
                        key=lambda error: (str(list(error.absolute_path)), error.message))
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            problems.append(finding(
                "INVALID_MANIFEST", "ALERT",
                explanation=f"{label}.{location}: {error.message}",
            ))
    return problems


def compare_handoff_validated(plan, sent, received, **kwargs):
    """Schema-first comparison; invalid records never produce PASS or UNKNOWN."""
    problems = validate_handoff_records(plan, sent, received)
    if problems:
        return {
            "handoff_id": sent.get("handoff_id") if isinstance(sent, dict) else None,
            "verdict": "ALERT",
            "findings": problems,
        }
    return compare_handoff(plan, sent, received, **kwargs)


def compare_journey_validated(plan, handoffs, *, file_evidence=None):
    """Validate every event and the plan before multi-hop comparison.

    This validates caller-supplied records, not remote receipt or provenance.
    The legacy compare_journey remains available for already-validated inputs.
    """
    from .journey import compare_journey

    if not isinstance(handoffs, list):
        return {
            "run_id": plan.get("run_id") if isinstance(plan, dict) else None,
            "verdict": "ALERT", "handoffs": [],
            "findings": [finding("INVALID_MANIFEST", "ALERT",
                                 explanation="handoffs: expected an array")],
        }

    problems = []
    # Validate the plan even when no handoffs were supplied.
    validators = _validators()
    for error in validators["run_plan"].iter_errors(plan):
        problems.append(finding("INVALID_MANIFEST", "ALERT",
                                explanation=f"plan: {error.message}"))
    for index, hop in enumerate(handoffs):
        if not isinstance(hop, dict) or not isinstance(hop.get("sent"), dict) or not isinstance(hop.get("received"), dict):
            problems.append(finding("INVALID_MANIFEST", "ALERT",
                                    explanation=f"handoffs[{index}]: expected sent and received event objects"))
            continue
        for label, record in (("sent", hop["sent"]), ("received", hop["received"])):
            for error in validators["event"].iter_errors(record):
                location = ".".join(str(part) for part in error.absolute_path) or "<root>"
                problems.append(finding("INVALID_MANIFEST", "ALERT",
                                        explanation=f"handoffs[{index}].{label}.{location}: {error.message}"))
    # File evidence is caller-supplied and outside the JSON manifest schema.
    # Reject malformed containers before the downstream comparator calls .get.
    if file_evidence is not None:
        if not isinstance(file_evidence, dict):
            problems.append(finding("INVALID_MANIFEST", "ALERT",
                                    explanation="file_evidence: expected an object"))
        else:
            for handoff_id, supplied in file_evidence.items():
                if not isinstance(handoff_id, str) or not isinstance(supplied, dict):
                    problems.append(finding("INVALID_MANIFEST", "ALERT",
                                            explanation="file_evidence: invalid handoff entry"))
                    continue
                for role in ("sender_files", "receiver_files"):
                    paths = supplied.get(role)
                    if paths is not None and not isinstance(paths, dict):
                        problems.append(finding("INVALID_MANIFEST", "ALERT",
                                                explanation=f"file_evidence[{handoff_id}].{role}: expected an object"))
                    elif isinstance(paths, dict):
                        for artifact_id, path in paths.items():
                            if (not isinstance(artifact_id, str) or not artifact_id
                                    or not isinstance(path, (str, Path))
                                    or (isinstance(path, str) and not path.strip())):
                                problems.append(finding(
                                    "INVALID_MANIFEST", "ALERT",
                                    explanation=f"file_evidence[{handoff_id}].{role}: invalid artifact ID or file path"))
    if problems:
        return {
            "run_id": plan.get("run_id") if isinstance(plan, dict) else None,
            "verdict": "ALERT", "handoffs": [], "findings": problems,
        }
    return compare_journey(plan, handoffs, file_evidence=file_evidence)
