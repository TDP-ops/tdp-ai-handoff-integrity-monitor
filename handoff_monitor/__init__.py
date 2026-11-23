"""Standalone deterministic handoff integrity monitoring core.

Use the schema-first validated entrypoints for untrusted input. Legacy
comparators remain exported for callers that validate inputs separately.
Validated entrypoints load jsonschema only when called.
"""
from .core import compare_handoff, digest_file
from .journey import compare_journey


def compare_handoff_validated(plan, sent, received, **kwargs):
    """Schema-first single-handoff comparison (requires jsonschema)."""
    from .validation import compare_handoff_validated as validated
    return validated(plan, sent, received, **kwargs)


def compare_journey_validated(plan, handoffs, *, file_evidence=None):
    """Schema-first linear journey comparison (requires jsonschema)."""
    from .validation import compare_journey_validated as validated
    return validated(plan, handoffs, file_evidence=file_evidence)


__all__ = [
    "compare_handoff_validated", "compare_journey_validated",
    "compare_handoff", "compare_journey", "digest_file",
]
