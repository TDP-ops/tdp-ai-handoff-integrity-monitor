# Lot 4 — Coverage and remaining evidence matrix

## Update — V0 text segment hashes (latest CI pending)

`text_required_segment_sha256` now has a versioned executable extractor for bounded, BOM-free UTF-8 files using canonical 1-based `line:N` locators. Seven synthetic scenarios check intact/modified/removed protected lines and required `UNKNOWN` cases. Expected updated synthetic matrix: **140** (57 violations, 20 clean local controls, 63 abstentions). Full latest CI is pending; no broader text semantics are claimed. **Remaining Lot 4 blocker:** planned fork/join/out-of-order/retry acceptance, not remote custody (Lot 5).

## Exit Gate audit — 2026-11-26

- **Last complete evidence verified:** GitHub Actions `30009d2` succeeded. Raw job logs show 235 passing unit tests, 133 synthetic scenarios, TP=55, FP=0, FN=0, TN=19, and 59 excluded `UNKNOWN` abstentions; these are **not production statistics**.
- **Blocking contractual gap:** `text_required_segment_sha256` remains declared but unimplemented; no real-text extracted-segment fixture establishes its detection capability.
- **Blocking planned scenario gap:** forks/joins and out-of-order/retry semantics remain outside the linear journey engine, with no executable adversarial oracle or separate scope decision.
- **Format scope:** checks do exist on narrow PNG/PDF/DOCX/PCM WAV/CSV/XLSX/SQLite/JSON subsets. No proof of complete format, semantic, or production accuracy coverage.
- **Correct allocation:** independent custody, authenticated reference/policy provenance and remote receiver evidence are Lot 5, not a prerequisite to *local* Lot 4 validation. Hugging Face demonstration remains Lot 6.
- **Decision:** Lot 4 Exit Gate stays **OPEN**. Next: text-segment extractor and executable graph/ordering acceptance tests or explicitly authorized V0 deferral, followed by a final review.

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
| Image | Local PNG dimension, RGB8 PNG Laplacian blur, and pinned scikit-image grayscale SSIM with positive/negative/UNKNOWN fixtures (latest CI pending) | Other image formats, full-color/perceptual semantics, baseline authenticity and receiver custody | Confirm latest CI, then review scope and original Lot 4 Exit Gate |
| PDF | Classic-xref page-tree count and pinned unfiltered raw page-stream fingerprint with real synthetic positive/negative/abstention cases (latest CI pending) | Compressed/object-stream PDFs, rendered page equivalence, semantics, inherited graphics state and authenticated custody | Verify CI; test broader layouts only with explicit extractor definition |
| DOCX | Pinned local simple-body-paragraph UTF-8 SHA-256 extraction; matching, modified, removed and unsupported-structure fixtures (latest CI pending) | Tables, fields, tracked changes, text boxes, full fidelity and remote custody | Validate latest CI; build other format checks |
| CSV | Local UTF-8 header parsing implemented for `csv_required_columns`; valid, absent and malformed header tests (latest CI pending) | Does not establish row completeness, broad dialect support or remote custody | Confirm latest CI and extend supported formats |
| XLSX | Local OOXML worksheet names and first-row inline/shared string headers tested with present, absent and unsupported formula cases (latest CI pending) | No cell-row completeness, formula execution, non-standard sheets or independently authenticated custody | Validate CI; continue other missing formats and quality checks |
| DB schema | SQLite 3 local schema tables, declared column types and foreign keys observed using read-only sqlite3 with synthetic valid/missing/malformed fixtures (latest CI pending) | Other SQL dialects, row data, WAL consistency, authenticated remote custody | Confirm CI; decide breadth of DB dialect scope at Exit Gate |
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

## Implementation update — XLSX first-row required columns (latest CI pending)

`xlsx_required_columns` now reads actual local XLSX worksheet row 1, including inline strings and shared-string header references. Missing sheets/headers yield ALERT; formula-derived headers and inaccessible evidence abstain to UNKNOWN. Six new strict-API scenarios grow the expected matrix to **95 cases** (43 known violations, 12 clean local cases, 40 abstentions), pending latest CI. Spreadsheet formulas, row/data completeness and remote receipt remain unverified.

## Implementation update — DOCX paragraph hashes (CI pending)

The pinned extractor `tdp-docx-body-paragraph-utf8-v1` now parses bounded DOCX `word/document.xml`, preserves direct body paragraph ordering and computes SHA-256 for a supported simple-text paragraph. Six real synthetic fixtures cover intact, changed or absent protected middle paragraphs, unsupported body tables, wrong extractor ID and missing receiver evidence. The expected matrix becomes **101 synthetic cases** (45 known violations, 13 clean local cases, 43 abstentions); not validated until the final SHA CI is green. This does not verify rich DOCX semantics or remote provenance.

## Implementation update — classic PDF page count (CI pending)

A bounded PDF 1.x classic cross-reference parser now walks a supported page tree, rather than counting textual `/Page` occurrences. Five synthetic executable tests cover correct minimum, insufficient pages, inconsistent `/Count`, broken xref, and unavailable receiver bytes. Expected matrix: **106 scenarios** (46 violations, 14 clean local examples, 46 abstentions), pending final SHA CI. Compressed/encrypted/incremental PDFs and page-content hash checks remain unsupported.

## Implementation update — pinned PDF page stream (CI pending)

The pinned extractor `tdp-pdf-simple-page-stream-sha256-v1` hashes the locally extracted raw unfiltered page stream plus declared MediaBox for a narrowly bounded classic-xref PDF subset. Six real synthetic cases check matching and changed content, absent page, compressed/unsupported stream, unknown extractor and missing receiver evidence. Expected adversarial matrix: **112 cases** (48 known violations, 15 clean local cases, 49 abstentions). Latest SHA CI pending. This does not establish rendered, textual or semantic PDF integrity.

## Implementation update — SQLite structure (CI pending)

Actual bounded SQLite database files are inspected in read-only mode for `db_required_table`, `db_required_column` and `db_required_foreign_key`. Seven synthetic strict-API cases include real matching/missing structures, type changes, missing foreign keys, non-database bytes and missing receiver evidence. Expected matrix: **119 synthetic cases** (52 known violations, 16 clean local cases, 51 abstentions); latest CI not yet verified. This does not validate database records, other SQL dialects or independently authenticated custody.

## Implementation update — local reference-backed PNG blur ratio (CI pending)

The engine accepts an explicit `reference_files` mapping keyed by the declared `reference_artifact_version_id` and evaluates the fixed `variance-of-laplacian-v1` metric on bounded RGB8 PNG raster pairs. It compares the reference/candidate variance ratio against the contract threshold, with zero-variance and unsupported cases handled explicitly. Seven additional synthetic strict-API scenarios yield an expected **126 cases** (53 known violations, 17 clean local cases, 56 abstentions), subject to final CI validation. SSIM remains **UNKNOWN** until its exact implementation and image reference configuration are verified. Local references are not independently authenticated; Lot 5 custody is still open.

## Implementation update — pinned RGB PNG grayscale SSIM (latest CI pending)

The V0 runtime now evaluates the exact declared `ssim-skimage-v1` algorithm on aligned RGB8 PNG local evidence with `scikit-image==0.26.0`, `numpy==2.3.5` and `scipy==1.16.3`, fixed structural-similarity parameters and the existing BT.601 grayscale decoding. Seven new strict-API scenarios are included (2 clean, 2 altered, 3 abstentions), increasing the **expected** adversarial matrix to **133 cases** (55 known violations, 19 clean local cases, 59 abstentions). The latest CI still requires confirmation. The dependency is optional outside CI; absent/mismatched runtime versions and missing reference evidence yield UNKNOWN. Local SSIM does not prove remote custody, color fidelity or semantic integrity.
