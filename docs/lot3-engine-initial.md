# Lot 3 — Deterministic engine, tranche 1

Status: **partial implementation; untrusted manifests plus locally provided paths are NOT authenticated handoff evidence**.

## Implementation

- `handoff_monitor/core.py`: `compare_handoff(plan, sent, received, *, sender_files=None, receiver_files=None)` and `digest_file(path)`.
- `tests/test_engine_core.py`: 17 synthetic tests checking identity, contract, required rules, version, byte integrity, missing evidence, and unsupported structure checks.
- Python standard library only for the engine. Contract JSON Schema tests remain a separate CI stage.

`digest_file` hashes the **actual bytes read** in bounded chunks; a hash declared in a manifest is not treated as evidence of receipt. A declared SHA-256 that disagrees with locally read bytes produces `DECLARED_HASH_MISMATCH` (`ALERT`). A difference between locally read sender and receiver bytes produces `HASH_MISMATCH` (`ALERT`).

A missing local file, absent receiver file path or unsupported content extractor yields `UNKNOWN` unless another proven violation produces `ALERT`. The code does **not** turn identical manifest hashes into `PASS`.

## Trust limitation

A caller can pass the same file for sender and receiver. This **does not independently prove that any remote agent received that file**. Therefore a `PASS` at this stage means only that the caller-supplied local files were both readable and matched the specified byte comparison. It is **not yet** an independently authenticated handoff verdict. Lot 5 must establish receiver-side evidence and prevent untrusted path or digest substitution before claims about actual transfer success.

## Tranche 2 — lineage and lifecycle (partial)

- `handoff_monitor/lineage.py` adds conservative checks for duplicate version identities, parent references, cyclic ancestry, rejected/retired events, replacement identity, and an explicit policy-grant match.
- `compare_handoff(..., history=..., policy_grants=...)` accepts optional caller-supplied historical records and grant tuples; these inputs are **not authenticated** by the engine.
- With missing history needed for lineage, the result is `UNKNOWN`. With a verified conflict in the supplied graph, the result is `ALERT`.
- A self-attested `authorized_by_policy=true` is **not** enough to pass authorization. No supplied grant yields `UNKNOWN`; a conflicting supplied grant yields `ALERT`.
- A matching caller-supplied grant allows the *declared lifecycle check* to proceed but **does not prove** a policy authority really granted it. A real provenance/authentication boundary remains necessary.
- **Tranche 3:** The engine now recognizes an explicit one-to-one replacement when the destination manifest declares a `replaced` lifecycle event, the new artifact links to the removed ID, both IDs and the new version are consistent, and the active contract plus caller-supplied grant agree. This prevents the *false missing-artifact alert* in that narrow case, but the aggregate verdict remains **`UNKNOWN`** until trusted independent origin, grant and receiver receipt can be established. Unapproved substitutions remain `ALERT`.
- The replacement's **actual receiver-side local bytes** can be hashed and checked against its declared digest; a mismatch is `ALERT`. Matching locally observed bytes alone do not turn a replacement into a proven delivery.

The new synthetic tests exercise the guards but cannot establish remote receiver authenticity or policy provenance. GitHub Actions still needs green verification on the latest main commit.

## Tranche 4 — Multi-hop chain A → B → C → D (partial)

- `handoff_monitor/journey.py` implements `compare_journey(plan, handoffs, *, file_evidence=None)` for an **explicit, linear ordered route**. It checks expected boundary order, handoff/event ID replay, step continuity, required artifact inventory, version transitions, stable IDs and conflicting digests.
- A same-ID move from V1 to V2 between boundaries requires an explicit parent link, a `modified` lifecycle event at the **correct source step**, and permission for that event in the active boundary contract. A wrong step, disallowed event, missing parent or absent declaration raises `VERSION_ROLLBACK` / `ALERT`; an explicitly denied modification raises `UNDECLARED_TRANSFORMATION` / `ALERT`. Otherwise the transition remains **`UNKNOWN`**, not authenticated or independently observed.
- A branch that intentionally retains V1 is **not automatically stale** when V1 remains authorized for that particular boundary. Forks, joins, arbitrary DAG routes, late retries and actual step-to-step policy authorization remain future work.
- `tests/test_engine_journey.py` defines 13 synthetic scenarios, including unapproved V2→V1 rollback and continuing a declared V2 transition.
- **Security constraint:** even when every local pair has matching actual bytes, the journey aggregate remains `UNKNOWN` without independent agent-side custody evidence (lot 5).
- No client artifacts or private infrastructure, no new dependencies.

## Tranche 5 — Anti-downgrade audit

- The receiver must carry the same `artifact.checks` declaration as the sender. A removed `exact_bytes`, `required_structure` or `quality_invariants` check is now `MISSING_REQUIRED_RULE` / `ALERT`. This is a **comparison of declarations only**; trusted original policy enforcement still requires authenticated inputs.
- Three targeted regression tests were added. The existing unsupported-structure case was updated so both sender and receiver declare the same unavailable check, still yielding `UNKNOWN`.
- Publishing GitHub files and reviewing source content does **not** independently prove that GitHub Actions tests passed. CI verification remains open.

## Tranche 6 — inter-hop check preservation

- At an adjacent boundary, the next sender must preserve the prior receiver's `artifact.checks` declarations for the same logical artifact ID, rather than only agreeing with its own destination.
- A changed or removed exact-byte, structure or quality declaration across hops raises `MISSING_REQUIRED_RULE` / `ALERT`. Explicitly authorized changes to verification policy are **not yet implemented**, so this deliberately rejects both silent weakening and unrecognized legitimate policy revisions.
- A previously declared digest that disappears at the next sender yields `UNVERIFIABLE` / `UNKNOWN` for that observation, not an unproven tampering accusation; conflicting digests for the same version still raise `ARTIFACT_ID_COLLISION`.
- Four synthetic regression tests were added. CI execution and independently authenticated custody are still outstanding.

## Tranche 7 — required status and size declaration

- A required artifact cannot silently flip `required: true` to `false` between sender and receiver; inconsistent declarations raise `MISSING_REQUIRED_RULE` / `ALERT`.
- When file paths are supplied and opened for byte hashing, any `size_bytes` declarations are compared with observed local file sizes. Mismatches raise `DECLARED_SIZE_MISMATCH` / `ALERT`.
- Without opened bytes, a declared size is not evidence of a real file and cannot produce `PASS`. Hash and size are now computed from the same byte stream; a concurrent writer can still mutate that stream, so atomic snapshot guarantees and authenticated receiver custody are not yet implemented.
- Five synthetic regression tests were added. Green CI on the latest commit remains a separate verification requirement.

## Tranche 8 — Single-read file measurements

- `observe_file(path)` returns SHA-256 and the measured byte count from **the same stream**. `digest_file` delegates to it for compatibility.
- Manifest `size_bytes` comparisons no longer use a separate filesystem `stat()` after reading the digest. This closes the inconsistent two-observation measurement path.
- This is **not an atomic snapshot**: a concurrent writer can still change bytes while the stream is open, and the caller controls the path. Authenticated immutable receipt and safe custody remain for lot 5.
- Two regression tests cover nonempty and empty files. Their publication does not imply the latest GitHub Actions run is green.

## Tranche 9 — immutable version derivation links

- Within a handoff, the receiving artifact must preserve the sender's `derived_from_artifact_ids` (in addition to parent versions and replacement link). An inconsistent declaration raises `BROKEN_REFERENCE`.
- Across adjacent handoffs, an unchanged `artifact_version_id` cannot change `parent_version_ids`, `derived_from_artifact_ids` or `replaces_artifact_id`. Contradictions raise `BROKEN_REFERENCE`.
- Both matching derivation claims still require an independently trustworthy history; missing history returns `UNKNOWN`, not a verified lineage.
- Four synthetic regression tests added. GitHub Actions result for the latest commit is not independently available in the current integration.

## Tranche 10 — Cross-boundary required-flag continuity

- A received required artifact cannot become optional in the next sender manifest without an explicitly versioned policy change. For now, any mismatch raises `MISSING_REQUIRED_RULE` / `ALERT`.
- Two regression tests cover both a downgrade and unchanged behavior.
- The GitHub Actions conclusion must be checked **after** this commit; a prior green run does not validate later modifications.

## Tranche 11 — Run-plan boundary consistency

- Where the run plan declares `steps`, a handoff boundary must match an adjacent directed pair from that route, and duplicate step IDs are rejected. Merely including a matching `contract_id` in the plan is not sufficient.
- Three synthetic regression tests cover off-route boundaries, legal adjacency, and duplicated route steps.
- Full schema validation is still a separate prerequisite. Older internal test fixtures that omit `steps` are temporarily handled for backward compatibility; production callers must validate a complete run plan against the canonical schema.
- GitHub Actions must be confirmed on **this** commit, not inferred from the prior successful CI.

## Tranche 12 — Historical identity binding

- When a caller supplies a version-history record for an artifact, the engine now cross-checks not only `parent_version_ids` but also `derived_from_artifact_ids`, `replaces_artifact_id`, artifact kind, and any simultaneously declared SHA-256 digests.
- A contradiction with the supplied history raises `BROKEN_REFERENCE` or `ARTIFACT_ID_COLLISION`. Five synthetic regression cases include an unchanged control.
- This is **not historical authentication**: caller-supplied records are untrusted unless separately verified (lot 5). Missing proof must not become an end-to-end `PASS`.
- Latest GitHub Actions outcome must be checked after this commit.

## Tranche 12 — Current-version vs history integrity

- When a current artifact/version also appears in supplied historical records, its `parent_version_ids`, `derived_from_artifact_ids`, `replaces_artifact_id`, `kind` and any mutually declared `content_sha256` must be consistent with that history.
- A contradictory lineage link triggers `BROKEN_REFERENCE` / `ALERT`; a contradictory kind or declared digest triggers `ARTIFACT_ID_COLLISION` / `ALERT`.
- Historical records remain **caller-supplied and unauthenticated** at this stage; matching values do not establish their independent truth. The proof boundary belongs to lot 5.
- Four targeted synthetic regression tests added. CI confirmation must match the most recent commit.

## Tranche 13 — Replacement event step binding

- A declared `replaced` lifecycle event on a destination artifact must be bound to the receiving step `received.to_step`. An event with another `step_id` is `UNAUTHORIZED_REPLACEMENT` / `ALERT`, even if the IDs and a caller-provided policy grant appear to match.
- Two targeted synthetic regression tests exercise a wrong step and the valid step. This check still does **not** authenticate the grant or prove actual receiver custody.
- CI must be verified on the latest commit before treating this tranche as tested.

## Tranche 14 — Handoff event identity hardening

- Both sender and receiver manifests must carry non-empty string `event_id` fields. Missing, empty or non-string IDs raise `INVALID_MANIFEST` / `ALERT`.
- Equal sender/receiver event IDs remain `DUPLICATE_OR_UNEXPECTED` / `ALERT`.
- Three targeted synthetic regression tests cover missing sender, missing receiver and empty receiver IDs. This is a runtime guard, not a replacement for canonical schema validation.
- CI of the latest published commit is not yet confirmed.

## Tranche 15 — Untrusted lifecycle grant evidence

- A caller-supplied matching `policy_grants` tuple is **not** authenticated policy evidence. `check_lifecycle` now returns `UNVERIFIABLE` / `UNKNOWN` even when the tuple matches the event, while a mismatched grant is still `ALERT`.
- Existing tests for matching rejection and replacement grants now expect `UNKNOWN`, and reject a false `UNAUTHORIZED_REPLACEMENT` finding in the matching case.
- This prevents an unverified caller authorization from contributing to an unqualified `PASS` for a lifecycle change. Independent policy provenance belongs to lot 5.
- Latest GitHub Actions run needs a separate confirmation; publishing tests does not establish that they pass.

## Tranche 16 — Unauthenticated lineage history

- Historical artifact records supplied to `check_lineage` remain controlled by the caller, even if parent and derived-from links match. Matching records with lineage claims therefore produce `UNVERIFIABLE` / `UNKNOWN`, not proven lineage authenticity.
- Contradictory history still produces `BROKEN_REFERENCE` / `ALERT` or `ARTIFACT_ID_COLLISION` / `ALERT` as applicable.
- Two synthetic regression tests cover matching parent and derived-from history, each deliberately returning `UNKNOWN`. History-free root versions without a declared lineage do not need this particular historical proof.
- Independent history and custody authentication belongs to lot 5. GitHub Actions must be checked on the latest published commit.

## Tranche 17 — Minimal runtime artifact input guard

- The engine now rejects missing artifact version, kind, required Boolean or observation metadata; malformed artifact inventories and non-object entries also raise `INVALID_MANIFEST` / `ALERT`.
- Malformed `checks` are not passed into downstream comparison; they fail closed instead of raising a runtime exception or producing a false `PASS`.
- Six synthetic regression tests exercise missing fields and malformed inputs, with local matching byte files deliberately supplied to test false-PASS resistance.
- This is **minimal defensive validation**, not complete implementation of the canonical JSON Schema at the runtime API boundary. Full schema validation remains an explicit caller prerequisite, to be resolved in the lot 3 exit audit.
- The latest GitHub Actions run must be confirmed separately.

## Tranche 18 — Canonical schema-first verification API

- `handoff_monitor/validation.py` adds `validate_handoff_records(plan, sent, received)` and `compare_handoff_validated(...)`. These validate the `run_plan` and the two `event` records against their respective **canonical JSON Schema draft 2020-12 definitions**, before any byte observation. A valid `finding` object cannot be substituted for an event.
- Malformed required fields, unexpected properties, illegal SHA-256 digests, incompatible typed checks, non-object records and incomplete plan contracts return `INVALID_MANIFEST` / `ALERT`, not a false `PASS`.
- The strict path requires `jsonschema==4.23.0`, already installed for GitHub Actions. The existing `compare_handoff` implementation remains a lower-level legacy API whose callers must validate the schema first; the explicit validated function is now the recommended application entrypoint.
- The tests cover valid manifests, missing evidence `UNKNOWN`, local byte equality `PASS`, and malformed input `ALERT`. These synthetic tests do **not** authenticate remote receiver evidence or policy authority.
- **Not the lot 3 exit gate yet:** verify the new tests on GitHub Actions and decide whether every public consumption path, including `compare_journey`, must enforce strict validation by default.

## Not yet implemented

- Complete CR-01–CR-12 coverage, authenticated cross-hop event history and non-linear fork/join DAG routes
- Full lifecycle authorization, authenticated replacement approvals, multi-hop lineage and proof-backed replacement acceptance
- Transformations and type-specific parsers for PDF, DOCX, images, tables, audio and DB schemas
- Independent receiver-side observation and auditable provenance
- External integrations, CLI and `BLOCK` enforcement

## Verification and exit gate

Tests run as part of the existing `python3 -m unittest discover -s tests -p 'test_*.py' -v` CI command. Local development smoke tests succeeded for the initial 17 test scenarios before publication. **GitHub Actions conclusion for the published commit must still be observed**; do not claim CI green until actually confirmed.

The core must not be presented as production-ready or as a fully independently verified artifact transfer.

## Tranche 19 — Multi-hop schema-first entrypoint (CI pending)

- `compare_journey_validated(plan, handoffs, *, file_evidence=None)` in `handoff_monitor/validation.py` validates the full run plan and each sent/received event against the canonical Draft 2020-12 definitions before calling `compare_journey`.
- Malformed handoff arrays, missing event objects, schema-invalid records in later hops, and invalid plans return `INVALID_MANIFEST` / `ALERT` without executing the comparison or returning `PASS`.
- Seven synthetic regression tests added in `tests/test_engine_journey_schema_validation.py`. The lower-level `compare_journey` remains available for already schema-validated callers; it does not enforce the boundary itself.
- This change validates structure only. It does not authenticate custody, policy grants, historical lineage, or independent receiver observations. It does not establish a lot 3 Exit Gate.
- Verify the final published commit in GitHub Actions before declaring the tranche tested.

## Tranche 20 — Multi-hop evidence container defense (CI pending)

- `compare_journey_validated` now rejects a non-mapping `file_evidence`, non-mapping handoff entries, and non-mapping `sender_files` / `receiver_files` before calling the lower-level comparator.
- Invalid structures return `INVALID_MANIFEST` / `ALERT`, with no per-handoff results. Five synthetic regression tests cover malformed and valid empty evidence containers.
- These checks are **container-level**, not proof of actual filesystem paths, trustworthiness of caller-supplied evidence, independent custody, or complete runtime API hardening. Additional audit of path values and other auxiliary inputs remains necessary before lot 3 Exit Gate.
- Final GitHub Actions CI result must be confirmed for this exact commit.
