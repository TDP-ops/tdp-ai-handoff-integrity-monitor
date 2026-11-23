# Lot 3 — Exit Gate review (provisional, NOT APPROVED)

Date: 2026-11-23  
Baseline SHA: `9b38c8f4379a9ddba2ed437afab36205908dedb9`  
CI: **green confirmed by project owner** on `8ade1efcaaec0f7424d583360f0bbfc0b7253b46`. The owner supplied the exact JSON and unittest output from the `Measure deterministic-engine line coverage` job. This is user-provided evidence, not an independently retrieved log.

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
| Reproducible measured coverage | **Measured and supplied by owner** | 166 tests passed; core 173/190 (91.1%); journey 119/131 (90.8%); lineage 158/178 (88.8%); validation 130/132 (98.5%). Source: reported Actions log for the coverage instrumentation; not a pass/fail threshold |
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

1. **Completed:** record the four measured line coverage values and the 166/166 passing tests from the owner's CI log. The latest reported green SHA at the time of receipt was `8ade1efcaaec0f7424d583360f0bbfc0b7253b46`.
2. **Open:** audit untested paths and critical verdict transitions; add focused counterexample regressions if necessary, without expanding scope.
3. **Open:** recheck the resulting final SHA's CI after any change.
4. **Open:** mark the gate APPROVED only when the bounded V0 evidence meets the gate, or keep OPEN with explicit blockers. Synchronize Notion before starting lot 4.

## Tranche 29 — Verdict precedence counterexamples (CI pending)

- Six synthetic regression methods were added to the strict entrypoints: missing required rules with otherwise valid byte observations; malformed manifests despite local matching bytes; unsupported structural verification not becoming `PASS`; `ALERT` precedence over unverified evidence in a journey; schema errors preventing comparison.
- Expected outcome: `ALERT` takes priority over `UNKNOWN` and local byte `PASS` when a critical contradiction exists; unsupported verifications remain `UNKNOWN`.
- These are targeted regression scenarios, **not a complete adversarial benchmark** or a proof that all possible false `PASS` paths are closed.
- New tests and the latest commit must pass GitHub Actions before their behavior is treated as verified. Exit Gate **NOT APPROVED**.
