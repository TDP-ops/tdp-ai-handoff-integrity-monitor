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
