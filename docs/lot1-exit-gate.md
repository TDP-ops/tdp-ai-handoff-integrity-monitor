# Lot 1 — contract exit gate

Date: 2026-11-17

## Scope and evidence

**Review completed for the versioned public contract files, not for runtime detection or actual GitHub Actions execution.**

Source files:
- `schemas/handoff-v0.schema.json` — single JSON Schema Draft 2020-12 vocabulary
- `docs/contract-v0.md` — identity, artifact version and sender/receiver evidence boundaries
- `docs/coherence-rules-v0.md` — 12 independent normative cross-record invariants
- `docs/typed-checks-v0.md` — 13 structure-check declarations and 3 quality-check declarations
- `examples/lot1/*.json` — synthetic contract and expectation fixtures
- `tests/test_contract_fixtures.py`, `tests/test_acceptance_contract.py`, `tests/test_typed_checks_contract.py`

## Reviewed gates

| Gate | Assessment | Limit |
|---|---|---|
| Baseline document and manifest shapes | **Specified** | Schema validity is not proof that a transfer occurred |
| Stable identities, versions, replacement relationships | **Specified** | Uniqueness, ancestry, event ordering and authorization require cross-record runtime enforcement |
| Exact-byte assertions | **Specified** | Independent bytes and measured SHA-256 must be supplied by a real probe |
| Types of file checks | **Specified, kind-constrained** | Some checks require parsers/algorithms that are not implemented |
| Cross-record invariants | **Specified (CR-01…CR-12)** | Not a working integrity engine |
| Synthetic expectations | **Specified (17 cases)** | Expected outcomes are not evidence of detector success |
| Automated contract schema tests | **Committed to CI** | Latest workflow conclusion **not independently observed** in this review |

## No overclaiming

A sender's `verified` flag is not independent evidence of recipient receipt. A quality rule with no available extractor must produce `UNKNOWN`; it must not pass. An accepted transformation cannot silently override required content or artifact identity. Optional `BLOCK` requires an actual interception mechanism and should not be interpreted as additional detection certainty.

The conditional rules now reject declaring a file-specific check against the wrong `artifact.kind`. Runtime must still check trusted versions of tools/extractors, policy grants and reference artifacts.

## Exit status

**Contract design: ready to freeze as V0 draft, conditional on green CI on the latest commit.**

**Runtime: not implemented by design at lot 1.**

**Remaining verification:** confirm the latest `main` GitHub Actions run concludes successfully after the kind-compatibility fix. If red, do not close the lot. No mandatory PR/status-check settings are introduced at this stage; those remain scheduled before the first external contribution.

Upon green confirmation, mark **lot 1: COMPLETE (contract-only)** and advance to lot 2 for selective review of external open-source components. No TFE, SignalForge, client integration or private TDP materials belong in this repo.
