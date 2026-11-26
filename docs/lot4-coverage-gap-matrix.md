# Lot 4 — Coverage and remaining evidence matrix

Status: **gap inventory, not an Exit Gate approval**  
Date: 2026-11-25  
Last owner-confirmed green commit: `9c17511cb375f76336579b79f3177939a459fbcf`.

The original project plan calls for adversarial tests across image, PDF, DOCX, audio, CSV, XLSX, database schemas, transformations, rejection/replacement, rollback, and potentially forks/joins. This matrix distinguishes executed V0 logic from declarations that the current engine cannot evaluate. It does not silently shrink the agreed plan.

| Area | Executable evidence today | What is **not** established | Next acceptance evidence |
| --- | --- | --- | --- |
| Local integrity (any byte stream) | Matching bytes, mismatching bytes, empty/binary/multi-read samples | Independent receiver custody | Keep the local PASS boundary explicit; authenticated custody belongs to lot 5 |
| Contract, rules, event identity, versions | Selected adversarial strict-API tests | Exhaustive state space; semantic equivalence of content | Add narrowly scoped rejection/transformation and version-transition tests with explicit ground truth |
| Linear handoff A→B→C | Missing hop, replay, dropped artifact and coherent-journey UNKNOWN | Forks, joins, retry ordering, concurrent/out-of-order events | Define a separate graph model and acceptance criteria before testing or claiming support |
| Replacement | Five invalid replacement cases; valid declared replacement remains UNKNOWN | Independent authorization and source authenticity | Extend rejection/transform cases under current V0; authenticated grant checks remain lot 5 |
| Image | `image_min_dimensions` declaration causes UNKNOWN; SSIM/blur declarations cause UNKNOWN | Real decoding, dimensions, SSIM, blur detection | Valid synthetic images, deterministic extractor/metric implementation, true positive/negative tests |
| PDF | `pdf_min_pages` declaration causes UNKNOWN | Actual page count, page SHA-256 extraction | Controlled valid PDFs, parser reference, positive/negative cases |
| DOCX | Required paragraph SHA declaration causes UNKNOWN | Paragraph extraction and deterministic canonicalization | Valid DOCX fixtures, algorithm/extractor versions, counterexamples |
| CSV | Local UTF-8 header parsing implemented for `csv_required_columns`; valid, absent and malformed header tests (latest CI pending) | Does not establish row completeness, broad dialect support or remote custody | Confirm latest CI and extend supported formats |
| XLSX | Required sheets declaration causes UNKNOWN | Workbook/sheet/column parsing | Valid XLSX fixtures, deterministic parsing, edge cases |
| DB schema | Foreign-key requirement declaration causes UNKNOWN | Schema/catalog comparison and dialect differences | Canonical schema snapshots, supported dialect definition, positive/negative cases |
| Audio | Duration/sample-rate declarations cause UNKNOWN | Audio decoding, duration/rate determination | Valid synthetic audio fixtures and decoder implementation |
| JSON / YAML / text | JSON required-pointer check now runs against local valid, missing, malformed and absent-byte fixtures (latest CI pending); YAML and text extractors remain unavailable | No JSON value semantics, YAML parser or text-segment hashing; no authenticated custody | Verify JSON CI; implement remaining declared checks independently |

## Evidence accounting

- The existing **37 synthetic executions** comprise 19 known violations, 4 clean local byte observations and 14 unscored abstentions. Their expected distribution is asserted by CI; the owner has confirmed the exact latest workflow green.
- Abstention tests are **valuable fail-safe tests**, not evidence that the corresponding parser, semantic check, or quality metric detects anything.
- The denominator of `19 TP / 4 TN` applies only to this hand-constructed deterministic sample. Do not convert it into generalized real-world detection performance.

## Recommendation / sequencing

1. **Keep the full Lot 4 Exit Gate OPEN.** The local deterministic sub-stage is green, but the original multi-format adversarial scope is incomplete.
2. Next tranche: cover the **currently implemented** rejection/transformation event rules with positive, negative and UNKNOWN cases through the strict API. Do not invent support for content transformations.
3. Before introducing format-specific libraries/extractors, define the minimal supported formats and trust guarantees, including dependency, security and maintenance cost. Unsupported advertised checks remain UNKNOWN until that capability is implemented and measured.
4. Forks/joins and authenticated custody must stay explicitly excluded from the **linear V0** unless separately designed. No claim of production-grade integrity.
5. Approve the final Exit Gate only after either (a) evidence satisfies the original agreed scope or (b) a conscious, documented re-scope is authorized; a green CI alone is insufficient.

No vendor service, external data transfer, or paid dependency is introduced by this inventory.

## Implementation update — local CSV headers (latest CI pending)

The local CSV extractor checks required header names in caller-supplied sender and receiver files. The new fixtures cover correct headers, missing columns, duplicate names, invalid UTF-8 and missing receiver paths. Results concern observed local structure, not authenticated custody. The expanded benchmark expects **68 synthetic cases** (36 violations, 5 clean, 27 abstentions); final CI verification is pending. Other format-specific extractors remain unavailable.

## Implementation update — JSON Pointer (latest CI pending)

The `json_required_pointer` local checker now reads real JSON data with strict UTF-8 parsing, duplicate-key rejection, bounded 8 MiB input, JSON Pointer unescaping and canonical array-index handling. Six new synthetic execution cases are included. The expected matrix is **74 cases** (37 known violations, 7 clean local controls, 30 abstentions), pending CI for the final SHA. Actual content semantics, YAML/text checks, remote custody and other type-specific extractors remain unverified.
