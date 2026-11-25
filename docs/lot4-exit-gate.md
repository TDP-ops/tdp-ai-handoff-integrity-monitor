# Lot 4 — Adversarial evaluation Exit Gate review

**Decision: OPEN — review drafted; not approved.**  
Review date: 2026-11-25  
Last validated baseline: `10e13ec8870484a8978bf5ba0b2e1930b5f26f31`, GitHub Actions **green confirmed by the project owner**. The job's JSON output was not independently retrieved.

## Executed V0 synthetic scope

The CI invokes `scripts/measure_lot4_adversarial.py` after unittest and coverage. The evaluator calls the public strict single-handoff and linear journey APIs and checks a **37-case** synthetic matrix:

| Ground truth / status | Number | Expected result on baseline |
| --- | ---: | --- |
| Known violations | 19 | 19 `ALERT` |
| Known clean *local byte* controls | 4 | 4 `PASS` (local byte equality only) |
| Unavailable independent evidence or unsupported quality/structure | 14 | 14 `UNKNOWN`; **unscored**, not true negatives |
| Total | **37** | **19 TP, 0 FP, 0 FN, 4 TN, 14 unscored abstentions** |

These are **CI-asserted synthetic expectations consistent with the owner's green run**, not a separately inspected raw measurement or independent performance assessment. `score_rows` now distinguishes `unknown_violation`, `unknown_clean` and `abstentions_unscored`, and has dedicated unit tests.

## Gate audit

| Requirement | Status | Boundary |
| --- | --- | --- |
| Executable synthetic violations: contract/rules, identity/version/replay, multi-hop continuity, replacement | **Covered for selected cases** | No exhaustive attack-space coverage |
| Local observed byte equality, mismatch, empty/binary/multi-read clean controls | **Covered for selected cases** | A local `PASS` is not an independently authenticated delivery |
| Unsupported structure and quality metrics fail to `UNKNOWN` | **Covered by abstention tests** | No actual PDF/DOCX/image/audio/CSV/XLSX/DB extraction or perceptual scoring |
| Alert takes precedence over missing structural/quality checks | **Covered for selected cases** | No confidence about untested mixed contradictions |
| Metrics TP/FP/FN/TN, denominators, `UNKNOWN` buckets | **Implemented and unit-tested** | Corpus is small, constructed and nonrepresentative; no real-world accuracy rate |
| Reproducible CI on latest tested baseline | **Owner confirmed green** | Obtain exact raw job output before quoting observed metrics as independently audited |
| Adversarial validity of structured and multimodal checks | **Not demonstrated** | Current tests use deliberately synthetic nonmedia bytes to confirm abstention |
| Forks/joins, unordered events, retries, ambiguous lineage | **Outside linear V0** | Do not claim supported |
| Authenticated receiver-side custody or policy provenance | **Deferred to Lot 5** | Caller-supplied observations and grants are not independent evidence |

## Outstanding decision

**The full Lot 4 Exit Gate is not approved.** The present evidence supports closing a **bounded sub-stage of synthetic V0 deterministic regression**, but not the project's broader adversarial scenario goals. Avoid falsely claiming multimodal verification or validated detection quality.

Recommended next scoped activity: confirm whether actual structure extractors and semantic/quality algorithms belong in Lot 4 as implemented features, or whether Lot 4 should strictly benchmark supported controls and mark unsupported modalities as explicit deferrals. Then assign objective acceptance criteria and a case-by-case executable matrix before expanding.

Do not proceed to Lot 5 solely because 37 constructed scenarios pass. Keep GitHub and Notion gate status aligned with the decision.
