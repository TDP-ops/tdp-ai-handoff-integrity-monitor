# V0 cross-record coherence rules — Lot 1 contract specification

**Status:** Normative design rules, not implemented by the JSON Schema. Enforcement belongs to lot 3; actual receiver probes belong to lot 5. All scenarios use synthetic evidence.

## Trust and scope

A valid JSON object is not sufficient evidence of a successful handoff. An issuer's statement that a recipient has the file is not an independent receipt. The verifier must bind a run plan, the active contract for a specific boundary, a sender's **sent** manifest, and a receiver-side **received** observation.

### 1. Pairing and contract binding

| ID | Invariant | If violated | Evidence-limited outcome |
|---|---|---|---|
| CR-01 | `run_id`, `handoff_id`, `from_step`, `to_step`, `contract_id`, and `contract_version` must identify **the same boundary** in both manifests and the run plan | `CONTRACT_MISMATCH` → ALERT | Missing run plan/contract → UNKNOWN |
| CR-02 | `event_id` unique within run, `handoff_id` identifies a transfer; a retry must not overwrite the earlier observation | `DUPLICATE_OR_UNEXPECTED` → ALERT | No complete event history → UNKNOWN for replay assessment |
| CR-03 | Every `required_rule_id` of active contract survives in `rule_ids`; no implicit downgrading of `critical_rule_ids` | `MISSING_REQUIRED_RULE` → ALERT | Unavailable original baseline → UNKNOWN for baseline completeness |

### 2. Artifact and version identity

| ID | Invariant | If violated | Evidence-limited outcome |
|---|---|---|---|
| CR-04 | Check required artifact IDs **as a set**, not only filenames or count. Duplicates in a single manifest are invalid. | `MISSING_REQUIRED_ARTIFACT` or `DUPLICATE_OR_UNEXPECTED` → ALERT | Receiver inventory not observed → UNKNOWN |
| CR-05 | Each `artifact_version_id` has a single immutable identity for the same logical `artifact_id` and observed byte digest (when available). Modifying the same artifact produces a **new** version ID | `ARTIFACT_ID_COLLISION` → ALERT | Missing trusted registry/baseline → UNKNOWN |
| CR-06 | A boundary must accept the version explicitly in `accepted_versions`. Older versions can be allowed **only when explicitly listed**; no global latest heuristic | `STALE_ARTIFACT_VERSION` or `VERSION_ROLLBACK` → ALERT | Version metadata unavailable → UNKNOWN |
| CR-07 | Parents and `derived_from_artifact_ids` must refer to known upstream records and form an acyclic lineage graph; branch/fork/join require explicit edges | `BROKEN_REFERENCE` → ALERT | Ancestry cannot be inspected → UNKNOWN |

### 3. Lifecycle and authorization

| ID | Invariant | If violated | Evidence-limited outcome |
|---|---|---|---|
| CR-08 | A replacement **creates** a new `artifact_id` with `replaces_artifact_id`; neither filename nor preserved count permits identity reuse | `UNAUTHORIZED_REPLACEMENT` or `ARTIFACT_ID_COLLISION` → ALERT | Replacement intent missing → UNKNOWN or ALERT based on observed substitution |
| CR-09 | Rejections/retirements require a lifecycle event, reason, and a boundary-applicable policy authorization. A rejection may legitimately remove an item from later requirements **only when the active contract/plan explicitly permits it** | `UNDECLARED_REJECTION` → ALERT | Policy missing → UNKNOWN; do not silently assume rejection is allowed |
| CR-10 | `allowed_transforms` and lifecycle events constrain what sender and receiver may change. A listed transformation type is **necessary but not sufficient**: its source and result must be linked | `UNDECLARED_TRANSFORMATION` → ALERT | Transformation proof not inspectable → UNKNOWN |

### 4. Evidence and quality

| ID | Invariant | If violated | Evidence-limited outcome |
|---|---|---|---|
| CR-11 | With `exact_bytes=true`, compare SHA-256 computed over real, observed sender/recipient bytes. A declared hash or asserted `verified` flag alone is not independent proof. | `HASH_MISMATCH` → ALERT | Missing independent receiver bytes → UNKNOWN |
| CR-12 | If exact bytes can legitimately change, check only explicitly configured and supported structure/quality invariants; never infer semantic equivalence from filename, size, generic score or equal dimensions | `MISSING_REQUIRED_CONTENT` or `QUALITY_INVARIANT_FAILED` → ALERT | No eligible extractor/threshold → UNKNOWN for the specific invariant |

## Outcomes and precedence

- Each **individual check** returns `PASS` (proved), `ALERT` (confirmed violation), or `UNKNOWN` (insufficient independent evidence). `BLOCK` is a policy action, only if the runtime actually intercepts the boundary; it is **not** an additional level of certainty.
- Aggregation: any confirmed `ALERT` dominates `UNKNOWN`; otherwise any required `UNKNOWN` makes the aggregate `UNKNOWN`; only all required `PASS` permits aggregate `PASS`.
- The `finding.verdict` field records the result or optional enforced block. It is not itself proof the monitor computed that result; the engine must derive it from evidence.
- Even if a rejected artifact is no longer required at a later step, the event and its earlier IDs/versions remain in immutable history.
- Trust boundaries: `sender` and `receiver` claims are both untrusted assertions until bound to an independent observation. No self-attested `hash_computed_from_bytes=true` can force `PASS`.

## Schema limitations to resolve before lot 1 exit

1. The schema currently allows free-form `checks.required_structure` and `quality_invariants`. These are **not executable checks** and their detailed type-specific representations need explicit, versioned definitions before an engine consumes them.
2. `authorized_by_policy` is a boolean **claim**, not proof of an actual policy grant. Cross-record policy evidence and version matching are mandatory.
3. `content_sha256`, `artifact_version_id`, and `observation` can be syntactically valid yet misleading. The schema cannot prove received bytes are independently observed.
4. A `sent` manifest and `received` manifest may share the same `handoff_id`; their `event_id` must be distinct. `event_id` uniqueness and cross-record duplication cannot be enforced by JSON Schema alone.
5. The current `finding` includes status but does not encode the full finding-to-evidence relation yet. The engine must not assume confidence from presence of an explanation string.

## Test contract / fixtures

`examples/lot1/acceptance-cases.json` is the **normative scenario expectation matrix** for the eventual deterministic engine; it does not mean detection is implemented. `tests/test_acceptance_contract.py` checks coverage and matrix consistency, not actual detection.

See also `docs/contract-v0.md` and `schemas/handoff-v0.schema.json`.
