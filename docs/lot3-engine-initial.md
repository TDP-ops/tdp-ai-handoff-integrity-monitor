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

## Not yet implemented

- Complete CR-01–CR-12 coverage and plan-wide cross-hop event histories
- Full policy, rejected/retired objects, authorized replacements and lineage DAG
- Transformations and type-specific parsers for PDF, DOCX, images, tables, audio and DB schemas
- Independent receiver-side observation and auditable provenance
- External integrations, CLI and `BLOCK` enforcement

## Verification and exit gate

Tests run as part of the existing `python3 -m unittest discover -s tests -p 'test_*.py' -v` CI command. Local development smoke tests succeeded for the initial 17 test scenarios before publication. **GitHub Actions conclusion for the published commit must still be observed**; do not claim CI green until actually confirmed.

The core must not be presented as production-ready or as a fully independently verified artifact transfer.
