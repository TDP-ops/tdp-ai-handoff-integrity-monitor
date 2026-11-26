# Typed integrity assertions — V0 / lot 1

**Status:** V0 declarations with selected local runtime checks (exact bytes, CSV required columns, JSON required pointers, PCM WAV duration/sample rate, PNG RGB/RGBA dimensions and XLSX sheet names); other typed extractors, quality algorithms and independent receiver evidence remain unavailable.

The canonical file is `schemas/handoff-v0.schema.json`. The `artifact.checks` object has three optional components:
- `exact_bytes: true`: exact SHA-256 comparison of independently observed sender and receiver bytes.
- `required_structure: [ ... ]`: a list of typed checks. Each check has a `check_type` and mandatory parameters.
- `quality_invariants: [ ... ]`: a list of typed deterministic metric requirements.

**Strict behavior:** an unsupported check, incompatible file type, unavailable extractor, missing reference version, inaccessible bytes, or unverified observation must yield `UNKNOWN` for that check. Never label an unexecuted check `PASS`. Violated checks supported by independent evidence yield `ALERT`. Overall verdict follows `docs/coherence-rules-v0.md`.

## Supported declarative structure check types

| Artifact kind | check_type | Required parameters | Intended interpretation |
|---|---|---|---|
| image | `image_min_dimensions` | `width_px`, `height_px` | Observed pixel width/height must each meet minima; does not prove visual clarity |
| pdf | `pdf_min_pages` | `min_pages` | Observed page count minimum; does not prove no page is missing |
| pdf | `pdf_required_page_sha256` | `page_index`, `extracted_page_sha256`, `extractor_id` | Hash of a deterministically extracted page representation; extractor version and parameters must match |
| docx | `docx_required_paragraph_sha256` | `paragraph_index`, `extracted_paragraph_sha256`, `extractor_id` | Hash of deterministically extracted paragraph; ordering and extractor identity matter |
| csv | `csv_required_columns` | `column_names` | Required header fields must be observed; does not prove row completeness |
| xlsx | `xlsx_required_sheets` | `sheet_names` | Required sheets must be observed |
| xlsx | `xlsx_required_columns` | `sheet_name`, `column_names` | Required columns in specified sheet |
| db_schema | `db_required_table` | `table_name` | Required table exists in observable schema |
| db_schema | `db_required_column` | `table_name`, `column_name`, `data_type` | Required typed column exists |
| db_schema | `db_required_foreign_key` | `table_name`, `column_name`, `references_table`, `references_column` | Required foreign-key relation exists |
| json | `json_required_pointer` | `pointer` | JSON Pointer (RFC 6901) resolves in observed JSON |
| audio | `audio_min_duration_ms` | `duration_ms` | Minimum observed duration; does not prove required content |
| text | `text_required_segment_sha256` | `segment_locator`, `extracted_segment_sha256`, `extractor_id` | Deterministically extracted segment agrees with baseline |

**PDF/DOCX completeness:** a minimum count alone cannot detect a missing middle page/paragraph. Use exact-byte checks when unchanged bytes are mandatory; otherwise require reference-backed extracted content checks for the relevant middle segments. No claim of complete semantic equivalence.

**CSV/XLSX/DB:** a required column/sheet/table/key verifies only that named structure, not all rows, formulas, indexes or database contents. Additional checks require a separately versioned contract change; no invented guarantee.

## Implemented local check — CSV headers (lot 4; CI pending)

The `csv_required_columns` assertion is now executed from caller-provided sender and receiver file paths when `artifact.kind` is `csv`. It uses the standard-library CSV reader, UTF-8 (optional BOM), an exact case-sensitive set of header names, and refuses missing/duplicate/empty header names. A required header missing from either readable copy yields `MISSING_REQUIRED_RULE` / `ALERT`. An unreadable file, invalid UTF-8, missing local path, or malformed header yields `UNVERIFIABLE` / `UNKNOWN`. Exact-byte checks are still independent and may produce a higher-priority `ALERT`.

This proves only the observed header columns, **not row completeness, data types, general CSV dialect support, content semantics or authenticated remote custody**. No third-party parser, paid service or client data is used. Validation is pending for the latest CI SHA.

## Implemented local check — JSON Pointer (lot 4; CI pending)

`json_required_pointer` now resolves RFC 6901 JSON Pointers against locally supplied sender and receiver JSON files. Parsing uses the Python standard library, UTF-8 (optional BOM), rejects duplicate object keys and non-standard constants, and limits each parsed file to 8 MiB. `""` addresses the JSON root, escaped `~1` and `~0` tokens are decoded, and array indices must be canonical decimal indices.

An absent required pointer yields `MISSING_REQUIRED_RULE` / `ALERT`; invalid JSON, invalid encoding, duplicate keys, oversized JSON or missing local bytes yield `UNVERIFIABLE` / `UNKNOWN`. The check proves only the local existence of the indicated path, **not its value, semantics, completeness or independently authenticated receiver custody**.

## Implemented local checks — PCM WAV duration and sample rate (lot 4; CI pending)

The stdlib `wave` parser now evaluates `audio_min_duration_ms` and `audio_min_sample_rate_hz` on locally supplied **uncompressed PCM WAV** sender/receiver files. Duration is compared with integer frame counts (`nframes * 1000` versus `duration_ms * sample_rate`), avoiding floating-point threshold drift. The checker confirms the declared WAV frame data are readable and limits each input to 16 MiB. Short duration or insufficient sample rate yields `MISSING_REQUIRED_RULE` / `ALERT`; unsupported, truncated or missing WAV observations yield `UNVERIFIABLE` / `UNKNOWN`.

The checks **do not** establish audio intelligibility, channel semantics, transcription fidelity, compressed-format support, or authenticated remote receipt. They do not implement image perceptual quality metrics.

## Implemented local check — PNG image dimensions (lot 4; CI pending)

`image_min_dimensions` now measures **bounded uncompressed RGB/RGBA PNG raster dimensions** from actual sender/receiver files, using only Python's standard library. It validates PNG signature, required chunks and CRCs, supported 8-bit non-interlaced RGB/RGBA layout, the zlib stream, the expected scanline length and filter tags, before comparing width and height to the declared minima. Input is capped at 8 MiB and decoded pixels at 4 million. Dimension violations produce `MISSING_REQUIRED_RULE` / `ALERT`. Corrupt, missing or unsupported files produce `UNVERIFIABLE` / `UNKNOWN`.

**Scope limitation:** PNG palette, grayscale, interlaced, high-bit-depth, animated and other image formats are not supported; neither SSIM nor blur is measured. PNG scanline payload validation does not establish perceptual quality, semantic content, authentic custody or image rendering equivalence.

## Implemented local checks — XLSX sheets and first-row columns (lot 4; latest CI pending)

`xlsx_required_sheets` now reads actual local XLSX/OOXML ZIP archives with the Python standard library. The parser checks required workbook parts, ZIP CRCs, internal worksheet relationships and unique declared sheet names. It bounds the archive to 8 MiB, total decompressed entries to 24 MiB and 128 members. Missing named sheets produce `MISSING_REQUIRED_RULE` / `ALERT`; malformed, oversized, inconsistent or unavailable archives produce `UNVERIFIABLE` / `UNKNOWN`.

The `xlsx_required_columns` assertion is now additionally evaluated on the **first row** of a named worksheet for supported literal text headers: inline strings, shared-string references and direct string values. Column IDs are validated, duplicated/blank labels rejected, and formula-derived headers yield `UNKNOWN`. A missing required sheet or column yields `ALERT`; malformed/unsupported XML and missing observations yield `UNKNOWN`. Tests include both inline and shared-string fixtures. **CI for this extension is pending.**

**Not implemented:** spreadsheet data-row validation, formula evaluation, rich/typed cell semantics, external relationships, non-standard packages and authenticated receiver custody. These checks establish locally observed sheet names and first-row text labels only, not spreadsheet completeness or quality.

## Implemented local check — DOCX simple body paragraph hash (lot 4; CI pending)

`docx_required_paragraph_sha256` is evaluated using the pinned extractor `tdp-docx-body-paragraph-utf8-v1`. The extractor reads a bounded DOCX ZIP package, parses `word/document.xml`, enumerates direct body paragraphs (`w:p`) in order, concatenates supported direct run text (`w:r/w:t`) without whitespace normalization, and hashes the UTF-8 bytes with SHA-256. A missing or altered declared paragraph yields `MISSING_REQUIRED_RULE` / `ALERT`. Unsupported extractor IDs, rich body structures, unreadable packages or missing evidence yield `UNVERIFIABLE` / `UNKNOWN`.

This does **not** verify tables, tracked changes, text boxes, fields, styles, hyperlinks, semantic fidelity, authenticated sender/receiver observations or full DOCX document completeness. The check covers precisely the pinned extractor's simple-text paragraph representation, never arbitrary DOCX semantics.

## Implemented local check — classic PDF page-tree count (lot 4; CI pending)

`pdf_min_pages` now counts leaf `/Type /Page` nodes in an actual **bounded classic-xref PDF 1.x page tree**, following the catalog and validating `/Pages`, `/Kids`, parent references and declared `/Count`. Files are limited to 4 MiB and 1,000 xref objects; object streams, xref streams, encrypted or incremental PDFs, binary/compressed page objects, and unsupported layouts abstain to `UNVERIFIABLE` / `UNKNOWN`. A readable supported page tree with fewer than the required number of leaves yields `MISSING_REQUIRED_RULE` / `ALERT`.

This is deliberately **not** a general PDF parser, page renderer, extractable page-content hash or a guarantee that no middle page was removed from a larger file. `pdf_required_page_sha256` remains unsupported. Independent receiver custody is not established.

## Implemented local check — pinned PDF raw page stream fingerprint (lot 4)

`pdf_required_page_sha256` is now evaluated using the exact pinned extractor ID `tdp-pdf-simple-page-stream-sha256-v1` for the bounded classic-xref PDF 1.x subset. This requires a directly referenced **unfiltered** stream in the selected page and a directly declared integer `/MediaBox`. The SHA-256 input is the UTF-8/ASCII bytes of `TDP-PDF-PAGE-RAW-V1\n`, the four MediaBox integers joined by spaces, one NUL delimiter, and the complete raw content-stream bytes. This is a *byte-oriented fingerprint*, not text extraction or rendering comparison. Modified or absent referenced page data yields `ALERT`; unknown extractor ID, compressed streams, unsupported structures or unavailable local files produce `UNKNOWN`.

**Trust limitation:** This does not prove visual or semantic equivalence, resolve inherited graphics state, validate page resources, or authenticate recipient custody. It must never be described as a general PDF page text or image hash. Other modern PDF layouts are unsupported.

## Implemented local checks — SQLite schema (lot 4; CI pending)

For `artifact.kind = db_schema`, the `db_required_table`, `db_required_column`, and `db_required_foreign_key` checks inspect actual local **SQLite 3 database files** through the Python standard-library `sqlite3` driver. The connection uses `mode=ro&immutable=1` and `PRAGMA query_only=ON`. The implementation validates the SQLite header, bounds the input at 8 MiB, runs `PRAGMA quick_check`, and inspects table definitions, declared column types and foreign-key relations. Identifiers are safely quoted; no user-supplied SQL is executed.

A missing table/column, a mismatched declared type, or an absent foreign-key relationship yields `MISSING_REQUIRED_RULE` / `ALERT`. Non-SQLite formats, malformed or inaccessible evidence yield `UNVERIFIABLE` / `UNKNOWN`. This does **not** establish actual row integrity, referential integrity of stored values, semantic equivalence of SQL types, transactions, WAL consistency, or independent receiver custody. Other database dialects are not implemented.

## Supported declarative quality checks

| Artifact kind | check_type | Required parameters | Limitation |
|---|---|---|---|
| image | `image_min_ssim` | `reference_artifact_version_id`, `minimum_ssim` (0–1), `algorithm_id: "ssim-skimage-v1"` | SSIM requires exact image alignment, reference bytes and a defined image decoding pipeline; algorithm identifier is a **reserved specification label**, not an implemented algorithm |
| image | `image_max_blur_score_ratio` | `reference_artifact_version_id`, `maximum_ratio` (>0), `algorithm_id: "variance-of-laplacian-v1"` | Relative focus metric is sensitive to scaling/texture; algorithm identifier is **reserved**, and the score convention must be defined before runtime implementation |
| audio | `audio_min_sample_rate_hz` | `sample_rate_hz` | Sample rate alone does not prove intelligibility, transcription completeness or audio quality |

**No thresholds are recommended by default**; thresholds must originate from an explicit versioned policy and an appropriate benchmark for the use case. The image metric algorithms listed here are **not yet operational**. Until implemented, tests concerning them cannot return `PASS`.

## Binding, traceability and evidence

Each declared rule is scoped to an artifact version and handoff contract. An extractor must record its exact version/configuration, the source bytes/hash, the generated observation and whether a reference artifact was accessible. A declared `extractor_id` is not proof an extractor ran. Only receiver-side or approved independent observations can establish arrival. Results stay scoped to the specific assertion; an invariant may be `UNKNOWN` even if another check is `PASS`.

## Stability

The `checks.required_structure` and `checks.quality_invariants` fields are now **arrays**, replacing the previous unrestricted objects. Existing published lot 1 fixtures with `exact_bytes` only remain compatible. Schema strictness rejects unsupported check types **and incompatible combinations with `artifact.kind`** using conditional JSON Schema constraints. Runtime execution, extractor provenance, authorization and independent evidence verification remain separate obligations.

This project is public, synthetic and independent of TFE, SignalForge and internal TDP systems.
