# Typed integrity assertions — V0 / lot 1

**Status:** Declarative contract only. No parser, quality algorithm, independent receiver probe, or detection engine is implemented by this document.

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
