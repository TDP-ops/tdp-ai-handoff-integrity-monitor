# Lot 4 — Transformation authorization gap and executable acceptance gate

**Status: OPEN — design prerequisite, not an implemented detector.**  
Audit date: 2026-11-25. Last owner-confirmed green commit: `65a080ad1dea23e89ab3be88d9d87c71075d631d`.

## Verified from the code

- `schemas/handoff-v0.schema.json` requires each contract to have `allowed_transforms` (array of strings), but the lifecycle event schema has **no `transform_id` or equivalent field** identifying a particular transformation.
- `handoff_monitor/lineage.py:check_lifecycle` verifies `modified` against `allowed_lifecycle_events`, checks owner step, declared authorization and supplied grant tuple, but does **not** compare an actual transformation identity with `allowed_transforms`.
- `handoff_monitor/journey.py:compare_journey` checks a cross-hop version transition for an accepted version, parent linkage, an applicable `modified` event and authorization flag; it does **not** check whether a named transformation is allowed. A coherent, declared transition returns **UNKNOWN**, not authenticated `PASS`.
- The V0 engine has **no content transformation analyzer**. Inferring the applied operation from bytes, hashes or a version bump is impossible with the presently captured evidence.

**Consequence:** a declaration that a version was `modified` is not evidence that an approved transformation occurred. Green adversarial tests of version transitions do not validate `allowed_transforms`.

## Required contract decision before implementation

An enforceable transformation policy needs a stable identifier for the **declared requested operation**, for example `transform_id` on the `modified` lifecycle event, plus a precise binding to the active contract's `allowed_transforms`. This requires a deliberate schema/API compatibility decision. **Do not silently add mandatory fields to existing V0 inputs** or reinterpret an absent field as trusted.

Acceptance behavior for a prospective supported contract revision:

| Case | Expected outcome | Scope |
| --- | --- | --- |
| Declared transformation identifier absent when policy demands it | `ALERT` or explicit rejected input, as fixed by the new schema contract | Declaration completeness |
| Identifier not in active contract's allowlist | `ALERT` | Policy mismatch |
| Allowed identifier but no authenticated approval / remote custody | `UNKNOWN` | No false authorization |
| Allowed identifier + matching declaration, but actual file operation cannot be observed | `UNKNOWN` for semantic transformation correctness | No fake parser/semantic assurance |
| Changed content, yet same-version / digest contradiction | `ALERT` when observable, independent of policy declaration | Existing deterministic integrity |
| Legacy V0 event lacking the new identifier | Documented backward-compatibility outcome, **never assume authorized** | Migration boundary |

## Next actionable step

1. Decide whether this is a **contract V1 extension** or a separate `transform-policy` envelope. Maintain V0 behavior until contract compatibility and trust boundary are specified.
2. Define the transform identifier namespace and exact ownership: which step, version transition, artifact ID and policy grant it binds. Prevent reusing a grant across a different transformation.
3. Implement only the *declaration-policy match*, add strict tests for mismatch, absence, wrong step, stale version and matching-but-untrusted declarations. No new library or paid service is required for that deterministic stage.
4. Keep **actual transformation correctness** and format-specific extraction as separate unimplemented capabilities requiring real format fixtures and measurable positive/negative tests.
5. Update the original Lot 4 Exit Gate and Notion only with independently demonstrated outcomes. This assessment **does not authorize reducing** the original format/graph scope.

No engine change is justified until the contract can encode which transformation is being authorized.

## Implementation update — 2026-11-25 (CI pending)

The V0 lifecycle schema now permits **optional** `transform_id`. The deterministic engine compares a declared `modified.transform_id` with the active contract's `allowed_transforms` in both a single handoff and a linear journey's cross-hop version transition.

- **Declared ID absent from the allowlist:** `UNDECLARED_TRANSFORMATION` / `ALERT`.
- **Matching ID:** no transform-allowlist alert, but the verdict remains `UNKNOWN` without independently authenticated evidence.
- **Legacy `modified` event without `transform_id`:** explicit `UNVERIFIABLE` / `UNKNOWN`, never implicit authorization.
- **Events not of type `modified`:** continue under their existing lifecycle rules.

Implementation and strict tests: `schemas/handoff-v0.schema.json`, `handoff_monitor/lineage.py`, `handoff_monitor/journey.py`, `tests/test_lot4_transform_policy.py`, plus the synthetic score script. New expected corpus: **63** scenarios (35 known violations, 4 clean local cases, 24 unscored abstentions). **Do not mark as validated until the newest GitHub Actions SHA is green.**

Still not implemented: proof of the **actual file transformation**, independently authenticated policy and scoped grants, or comprehensive extraction of media/document structure. The original full Lot 4 Exit Gate remains **OPEN**.
