# Lot 3 — Deterministic engine V0 Exit Gate

**Decision: V0 LOCAL ENGINE EXIT GATE APPROVED — CI confirmed by the project owner.**  
Date: 2026-11-23  
Last code-and-test baseline verified green by the project owner: `6c4ba74c31c8a2309b110a524d9d6e133dfe92d8`. The final documentation-only Exit Gate commit `f2f067fe3eed9c8dd5c59f1809cf90f7751ae1bb` was also confirmed green by the owner.  
This decision is restricted to **schema-first deterministic validation of synthetic/local single handoffs and linear multi-hop journeys**. It is **not** a certification of remote receipt, production security or real-world error-detection accuracy.

## Evidence

| Gate criterion | Result and evidence |
| --- | --- |
| Explicit schemas at the public trust boundary | `compare_handoff_validated` and `compare_journey_validated` enforce the canonical JSON schemas before processing manifests. The historical low-level APIs require caller prevalidation and remain for compatibility. |
| Local byte-integrity checking | SHA-256 and size computed from locally opened bytes; missing or inaccessible evidence is not an independent success claim. |
| Core deterministic checks | Contracts, required rules and inventory, artifact identity/version/lineage, basic lifecycle and replacement rules, linear inter-hop continuity and anti-downgrade checks exercised by synthetic tests. |
| False-PASS regression protection | Tested non-verified access, role-inconsistent observation sources, unsupported checks, invalid manifests, missing required rules, unchanged hashes without local bytes, byte mismatches, and verdict priority. Suppress contradictory per-artifact `EXACT_BYTES_MATCH / PASS` when the same artifact has `UNKNOWN` or `ALERT`. |
| Multi-hop trust boundary | A coherent locally compared journey returns `UNKNOWN` without independently proven receiver custody; a verified contradiction produces `ALERT`. |
| CI | Owner supplied GitHub Actions confirmation that commit `6c4ba74` is green. This is a user-verified check, not independently retrieved job logs. |
| Reproducible line-coverage baseline | Owner supplied the Actions JSON for the earlier instrumented run: **166 passing tests**, `core.py` 173/190 (91.1%), `journey.py` 119/131 (90.8%), `lineage.py` 158/178 (88.8%), `validation.py` 130/132 (98.5%). Later added tests/changed code mean **these percentages are a historical baseline, not asserted as current**. |
| Engineering quality boundary | The covered negative cases and green tests support the bounded V0 engineering gate; **they do not show zero false positives/negatives or comprehensive branch coverage**. Those require the adversarial lot 4 suite. |

## Boundaries and explicit deferrals

1. **Lot 4:** representative adversarial scenarios, real structured/multimodal extractors and measurement of false positives/false negatives. Current unsupported structure/quality checks remain `UNKNOWN`.
2. **Lot 5:** authenticated sender/receiver observations, immutable custody, remote receipt, trusted history/policy-grant provenance, snapshot safety and protection against caller-controlled evidence substitution.
3. **Unsupported by linear V0:** arbitrary graph routing, forks/joins, retries, out-of-order events, dynamic artifact discoveries, and fully authorized policy changes between steps. Do not advertise this functionality until designed and verified.
4. No operational `BLOCK` mode or production enforcement. The result labels `PASS`, `ALERT` and `UNKNOWN` are **bounded local diagnostic outputs**, not end-to-end transfer assurance.
5. Local `PASS` does **not** establish that an actual recipient received a file. Callers must not promote it to authenticated handoff success.

## Final release condition

**Satisfied.** The code-and-tests baseline `6c4ba74` and final gate documentation `f2f067f` were confirmed green by the project owner. Lot 3 is approved **only for the bounded deterministic local V0**. Lot 4 may start. The remaining limitations are explicitly deferred and must not be represented as completed capabilities.

No further optional feature work belongs to Lot 3 merely to increase line coverage.
