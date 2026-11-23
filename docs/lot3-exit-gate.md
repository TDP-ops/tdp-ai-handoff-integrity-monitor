# Lot 3 — Exit Gate review (provisional, NOT APPROVED)

Date: 2026-11-23  
Baseline SHA: `9b38c8f4379a9ddba2ed437afab36205908dedb9`  
CI: **green reported by project owner**. The connector did not expose the job's coverage log or a machine-verifiable percentage.

## Scope of the V0 gate

Deterministic, schema-first single-handoff and linear multi-hop verification with synthetic local evidence. A local `PASS` is **not** independently authenticated delivery, and the multi-hop aggregate remains `UNKNOWN` without agent-side custody proof.

## Evidence / decisions

| Criterion | Status | Evidence or blocker |
| --- | --- | --- |
| Canonical JSON schema is enforced before trusted application comparison | Implemented | `compare_handoff_validated`, `compare_journey_validated`; prior schema regression tests |
| Local SHA-256 and size are measured from opened file bytes | Implemented | `core.py`, synthetic file tests |
| Invalid records fail closed and cannot create a false `PASS` | Tested for covered cases; broader adversarial review pending | Schema-first/auxiliary-input regression tests |
| Contract, identity, versions, lineage, lifecycle, replacement and obligation continuity | Partial V0 implementation | `core.py`, `lineage.py`, `journey.py`; not universal policy enforcement |
| Backward-compatible public strict APIs and documented semantics | Implemented | Package exports, README, tests |
| Reproducible measured coverage | Instrumentation implemented; **actual measurement pending review** | `scripts/measure_engine_coverage.py` prints JSON in GitHub Actions `Measure deterministic-engine line coverage`; collect per-module percentages |
| Explicit anti-false-PASS / priority audit | **Open** | Record tested counterexamples, residual false-PASS risks, and `ALERT`/`UNKNOWN` precedence |
| Declared limitations and V0 exclusions | Documented below | Must be acknowledged in final decision |
| Last changes confirmed green | Owner confirmed baseline `9b38c8f`; any future commit needs new verification | GitHub Actions |
| Final gate approval | **NOT APPROVED** | Do not begin lot 4 on this basis |

## Deliberately out of scope — NOT functionality claims

- Authenticated receiver-side observation, identity of observing agent, cryptographic trust, policy issuer authority, file provenance or immutable custody: **lot 5**.
- Advanced PDF/DOCX/image/audio/structured-file extraction and adversarial precision/recall benchmark: **lot 4** and subsequent appropriate lots.
- Arbitrary DAGs, forks/joins, asynchronous retries, out-of-order events, dynamic discoveries and fully policy-authorized transformations are **not supported by the current linear V0 model**. Their assignment and acceptance criteria must be explicitly decided before advertising wider support.
- Operational `BLOCK` enforcement is not implemented. No production safety/security guarantee is asserted.

## Next exact gate actions

1. Read the **four measured line-coverage numbers** for `core.py`, `journey.py`, `lineage.py`, `validation.py` from the baseline GitHub Actions job. Record source SHA and measured values; do not infer an arbitrary pass threshold.
2. Audit untested paths and critical verdict transitions; add focused counterexample regressions as necessary, without expanding scope.
3. Recheck the resulting final SHA's CI.
4. Mark the gate APPROVED only if evidence satisfies the agreed bounded V0 scope, or keep it OPEN with explicit blockers. Synchronize Notion before starting lot 4.
