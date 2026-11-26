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
| Image | Real PNG RGB/RGBA 8-bit dimension checks (signature, chunks/CRC, bounded raster) with positive/negative/abstention fixtures; latest CI pending | No other image formats, SSIM, blur, visual semantics or authenticated custody | Validate CI; implement remaining quality metrics and formats against real fixtures |
| PDF | `pdf_min_pages` declaration causes UNKNOWN | Actual page count, page SHA-256 extraction | Controlled valid PDFs, parser reference, positive/negative cases |
| DOCX | Required paragraph SHA declaration causes UNKNOWN | Paragraph extraction and deterministic canonicalization | Valid DOCX fixtures, algorithm/extractor versions, counterexamples |
| CSV | Local UTF-8 header parsing implemented for `csv_required_columns`; valid, absent and malformed header tests (latest CI pending) | Does not establish row completeness, broad dialect support or remote custody | Confirm latest CI and extend supported formats |
| XLSX | Local OOXML required-sheet names parser with valid, absent, corrupted and missing-path fixture tests (latest CI pending) | Column/cell contents, formulas, external links and remote authenticity are not checked | Complete `xlsx_required_columns` and verify CI |
| DB schema | Foreign-key requirement declaration causes UNKNOWN | Schema/catalog comparison and dialect differences | Canonical schema snapshots, supported dialect definition, positive/negative cases |
| Audio | PCM WAV duration and sample-rate checks implemented on local bytes with threshold, truncation and missing-path tests (latest CI pending) | No compressed audio decoder, transcript or intelligibility scoring; no authenticated remote custody | Confirm CI and expand to remaining modalities |
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

## Implementation update — PCM WAV measurements (latest CI pending)

Real locally generated uncompressed PCM WAV fixtures now exercise duration and sample-rate thresholds, incomplete samples and missing recipient observations. No audio decoding beyond PCM WAV or speech-quality assertion is claimed. Expected synthetic matrix: **79 cases** (39 violations, 8 clean local observations, 32 abstentions); these values are not confirmed until the newest GitHub Actions SHA is green.

## Implementation update — PNG dimensions (latest CI pending)

PNG structural checks are now executed on actual synthetic RGB/RGBA PNG raster bytes, with checks for dimensions, CRC integrity, missing pixel data, unsupported variants, and missing receiver observations. Expected score: **84 synthetic cases** (40 known violations, 9 clean local examples, 35 abstentions); the most recent SHA still requires CI confirmation. This does not constitute broader image verification or perceptual quality measurement.

## Implementation update — XLSX required sheets (latest CI pending)

Bounded ZIP/XML XLSX parsing now checks named worksheets using workbook relationships and ZIP CRCs. The five added synthetic scenarios increase the expected adversarial matrix to **89 cases** (41 violations, 10 clean local examples, 38 abstentions). CI on the final SHA is still pending; XLSX columns and spreadsheet semantics remain unimplemented.
