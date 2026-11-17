# Canonical handoff contract — V0 / lot 1

Status: **schema baseline only; runtime validation and receiver-side verification not implemented**.

## Scope

The source of truth is `schemas/handoff-v0.schema.json` (JSON Schema draft 2020-12). This single contract covers a versioned run plan, sent/received handoff events, artifact versions, lifecycle events, and findings.

The schema is deliberately strict (`additionalProperties: false`). Field names in this independent public project are **V0 provisional**; any future SignalForge integration requires separate registry review and approval. No customer data, production IDs, or TDP private internals belong here.

## Identity rules

- `artifact_id` stays stable when the **same logical document is modified**.
- `artifact_version_id` is a new identity for each new version; use `parent_version_ids` to trace ancestry.
- A **replacement** must get a different `artifact_id` and link to the old one with `replaces_artifact_id`.
- Same filename and same total artifact count do **not** establish sameness.
- A rejected item is not silently deleted: it remains in lifecycle history.
- Allowed versions are **per handoff** (`contract.accepted_versions`), not “latest overall”; branch-specific legitimate older versions remain possible.
- Forks, joins, retries and late events require explicit `handoff_id`/`event_id`, and runtime event ordering checks.

## Evidence rules

- A manifest from the sender is an assertion, not proof that the receiver obtained the artifact.
- `observation.source` and `observation.access` record the observation channel and result. `hash_computed_from_bytes=true` is a **claim**, to be established by an authorized probe in lot 5.
- Hashes are SHA-256 of **observed exact bytes** only; a canonical JSON digest is not a file-byte digest.
- `content_sha256` is optional when bytes are not available; missing evidence must yield `UNKNOWN`, not `PASS` in the core.
- Policy `exact_bytes` permits a hash comparison; `required_structure` and `quality_invariants` are explicit checks for transformed files, not a general guarantee of semantic quality.

## Enforcement and validation gates

JSON Schema validates types and required fields only. The lot 3 engine must enforce **cross-record rules** (unique IDs, consistent version parents, valid replacements, contract revisions, allowed transitions), compare two independent observations, and compute `PASS / ALERT / UNKNOWN`. `BLOCK` is optional and requires an actual interceptable boundary.

Typed declaration shapes for `required_structure` and `quality_invariants` are specified in `docs/typed-checks-v0.md`; these cannot be treated as verified just because the object is syntactically accepted. Type-specific extractors and quality metrics are not implemented. No model judge or paid API is required.

## Acceptance scenarios inherited from the Perturbateur

1. Clear image compressed during transfer: identify mismatch vs allowed conversion, then check configured quality threshold or UNKNOWN.
2. PDF/DOCX with missing middle section; same name does not make it intact.
3. Spreadsheet / DB schema missing rows, columns, keys or constraints.
4. Modified V2 reverts to V1 at agent D when V2 was required.
5. Six artifacts → rejection of one → replacement by a different sixth; preserve lineage and authorization.
6. Attempt to re-use an existing `artifact_id` for a conflicting artifact.

## Boundaries

This repository is the **general standalone monitor**, not the TFE, SignalForge, website, or any private TDP integration. GitHub Actions and the future Hugging Face Static Space use synthetic examples only.
