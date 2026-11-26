# Lot 4 — Adversarial evaluation Exit Gate review

## Suite de l'audit — segments texte implémentés (CI du SHA final à confirmer)

Le blocage `text_required_segment_sha256` dispose maintenant d'un extracteur runtime versionné `tdp-text-utf8-line-sha256-v1` pour les lignes de texte UTF-8 LF bornées. Sept scénarios exécutables couvrent contrôle positif, modification et suppression d'une ligne centrale, encodage invalide, localisateur non supporté, identifiant d'extracteur invalide et absence d'observation du récepteur. La matrice attendue passe à **140 scénarios synthétiques** (57 violations, 20 témoins propres locaux et 63 abstentions). Aucun résultat de CI du dernier SHA n'est présumé.

**Statut du lot : OPEN.** Le blocage restant relatif aux forks/joins, retries et événements hors ordre du plan initial n'est pas traité par ce contrôle. Les preuves de réception distante restent au lot 5.

## Audit consolidé du 26 novembre 2026 — décision : EXIT GATE OPEN

**Source d'exécution vérifiée :** GitHub Actions, SHA `30009d201f51694ef3eaf1d802a1ffb365fce4a3`, job `140133732030`, [run #45885102178](https://github.com/TDP-ops/tdp-ai-handoff-integrity-monitor/actions/runs/45885102178) : **SUCCESS** (unittest, coverage et scoring). Logs consultés : **235 tests**, **133 scénarios synthétiques**, **55 TP / 0 FP / 0 FN / 19 TN / 59 abstentions non scorées**. Couverture en lignes mesurée sur les quatre modules centraux : core 91,4 %, journey 91,0 %, lineage 90,5 %, validation 98,5 %. Ces chiffres sont circonscrits au jeu synthétique, pas des taux de détection en production ni une preuve de couverture des extracteurs.

| Exigence du plan V0 | Verdict d'audit | Preuves / limitation |
| --- | --- | --- |
| Contrats, identités, versions, historique, remplacements, lifecycle, allowlist de transformation | **COUVERT sur cas sélectionnés** | Exécution par API stricte et tests adversariaux ; les opérations réelles de transformation et les autorisations indépendantes ne sont pas prouvées |
| Intégrité locale SHA-256, `ALERT` supérieur à `UNKNOWN`, absence de faux `PASS` observé | **COUVERT sur cas sélectionnés** | Fichiers locaux réels et tests de précédence ; pas de réception authentifiée |
| Contrôles réels image, PDF, DOCX, audio, CSV, XLSX, SQLite, JSON et SSIM/flou | **COUVERT SUR SOUS-FORMATS** | PNG RGB8, PDF classic-xref/restreint, DOCX simple, WAV PCM, SQLite3, etc. Les variantes non prises en charge donnent `UNKNOWN` ; aucune garantie sémantique générale |
| `text_required_segment_sha256` du contrat V0 | **BLOQUANT : NON IMPLÉMENTÉ** | Présent dans le JSON Schema ; absent de `handoff_monitor/structure.py` et non représenté par des scénarios de détection sur vrais fichiers texte |
| Forks/joins, ordonnancement/retry/concurrence, filiation de parcours non linéaires | **BLOQUANT : NON DÉMONTRÉ** | `compare_journey_validated` prend en charge une chaîne linéaire ; aucun modèle graphe et matrice de vérité terrain correspondants |
| Reproductibilité du rapport et dénominateurs | **COUVERT SUR LE CORPUS COURANT** | Logs bruts du job consultés, 133 scénarios observés ; les 59 `UNKNOWN` ne sont ni TP ni TN |
| Authentification du récepteur, provenance des références et grants | **REPORT EXPLICITE LOT 5** | Hors périmètre de clôture du lot 4 local : ne pas transformer en faux blocage local, ni prétendre que ces preuves existent |
| Démonstration publique Hugging Face | **LOT 6, non encore ouvert** | Dépend du lot 5 selon le plan actuel |

**Décision vérifiée :** ne pas fermer le lot 4 et ne pas ouvrir le lot 5. Les travaux de clôture prioritaires, **sans inventer un nouveau périmètre**, sont (1) construire et tester le contrôle de segment texte déclaré V0, (2) traiter explicitement et tester les scénarios forks/joins et ordre/retries du plan original ou faire approuver une limitation V0 distincte, (3) réexécuter les scénarios et revalider l'Exit Gate sur le SHA final. Les limites des formats multimodaux doivent rester visibles, sans revendiquer une exhaustivité absente. Ne pas confondre la couverture unitaire des quatre modules centraux avec celle des parseurs.

---

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

## Follow-up — 2026-11-25, gap-matrix inventory (CI pending)

- GitHub Actions for the prior `9c17511` Exit Gate draft was **green as confirmed by the project owner**.
- See [Lot 4 coverage and gaps](lot4-coverage-gap-matrix.md), which maps each originally planned format and scenario to actual executed evidence and missing implementation.
- **Exit Gate remains OPEN**; the project plan still includes multimodal and more complex adversarial coverage. This inventory does not authorize a scope reduction.
- Next targeted test stage: rejection/transformation lifecycle cases on the current strict engine; do not claim transformed content validation. This documentation commit requires its own CI check.

## Follow-up — 2026-11-25: transformation allowlist enforcement gap

- The latest prior tranche `65a080a` CI was confirmed green by the owner.
- The audit documented in [Transformation authorization gap](lot4-transform-policy-gap.md) confirms `allowed_transforms` is required by the schema but not enforced by the V0 runtime, because existing lifecycle events do not identify a transformation operation. Version transition tests do not establish compliance with this allowlist.
- **Exit Gate remains OPEN.** A backward-compatible schema/API design decision and executable mismatch/abstention cases are prerequisites before claiming supported transformation authorization; no engine code was changed in this audit.

## Build progress — transform allowlist now enforced (latest CI pending)

A backward-compatible V0 extension adds optional `transform_id` to `modified` lifecycle events and checks declared IDs against the active `allowed_transforms` list in strict single-hop and cross-hop evaluation. Disallowed identifiers produce `ALERT`; matching identifiers and legacy missing identifiers remain `UNKNOWN` without independent policy and content evidence. See [transform policy status](lot4-transform-policy-gap.md).

The synthetic evaluation is expected to cover **63** cases (35 known violations, four clean local byte witnesses, 24 unscored abstentions). These numbers are **not yet CI-confirmed for the latest implementation**. The full Lot 4 Exit Gate remains OPEN because actual transformation contents, multimedia structures and quality metrics are still not verified; remote receipt is outside this local V0 gate.

## Implementation update — real CSV header checks (CI pending)

A minimal deterministic CSV structure checker now parses UTF-8/UTF-8-BOM headers from actual local sender and receiver files and checks `csv_required_columns`. Correct headers can produce a local byte-integrity `PASS` when exact bytes also match; missing required headers produce `ALERT`; absent/invalid evidence remains `UNKNOWN`. Real fixture tests and the scoring script are included. See [typed-checks documentation](typed-checks-v0.md) and [coverage matrix](lot4-coverage-gap-matrix.md).

The previous **63 synthetic cases** were confirmed green by the owner. The new expected sample is **68** (36 violations, 5 local clean, 27 abstentions); the newest CI has **not yet been confirmed**. This does not demonstrate independent receiver custody, row completeness, or other multimedia/quality checks. The full Lot 4 Exit Gate remains **OPEN**.

## Implementation update — JSON Pointer check (CI pending)

`json_required_pointer` is now evaluated against actually opened local JSON bytes with the standard library, RFC 6901 pointer resolution, duplicate-key rejection and an 8 MiB input bound. Six strict-API fixture scenarios cover valid pointers, escaping, absence, malformed/invalid encodings and missing receiver evidence. See [typed checks](typed-checks-v0.md).

The preceding **68-case** CI was confirmed green by the owner. Expected expanded suite: **74 synthetic cases** (37 known violations, 7 clean local examples, 30 unscored abstentions); results **not confirmed for the latest SHA**. Actual JSON value semantics, multimedia parsing, remote custody, and broader original Lot 4 acceptance requirements remain unverified. Exit Gate stays OPEN.

## Implementation update — bounded PCM WAV observations (CI pending)

Following owner-confirmed green CI for `c4a49a3` (JSON), the V0 engine now observes uncompressed PCM WAV **duration** and **sample rate** on locally provided sender and receiver file paths. Actual synthetic WAV test files check compliant values, threshold violations, truncated frames, and unavailable receiver evidence. The parser is stdlib-only and bounded at 16 MiB; non-PCM/unsupported files remain `UNKNOWN`.

The new expected suite contains **79 synthetic cases** (39 violations, 8 clean local cases, 32 abstentions), **pending the CI of the latest commit**. This does not measure intelligibility, transcription or authenticated custody. Other typed structure/quality extractors remain incomplete, so **Lot 4 Exit Gate stays OPEN**.

## Implementation update — bounded PNG dimensions (CI pending)

After the owner-confirmed green CI for `d3e6ec3` (WAV), the engine now verifies `image_min_dimensions` for actual locally observed 8-bit RGB/RGBA, non-interlaced PNG files. The parser checks chunk CRC and decoded scanline structure before accepting dimensional measurements. Five new synthetic fixture scenarios evaluate compliant PNG, insufficient dimensions, CRC corruption, truncated raster and missing receiver evidence.

The expanded suite expects **84 synthetic scenarios** (40 known violations, 9 clean local cases, 35 abstentions), pending verification of the latest CI. Other image formats, SSIM, blur and semantic image integrity are **not** validated. The Lot 4 Exit Gate remains OPEN.

## Implementation update — XLSX sheet-name integrity (CI pending)

The owner confirmed the previous PNG commit `aaabe31` green. A bounded Python stdlib OOXML ZIP/XML parser now validates declared XLSX worksheet names and the referenced worksheet parts for `xlsx_required_sheets`. Five fixture scenarios cover present/missing sheets, missing workbook parts, malformed ZIP archives and unavailable receiver bytes. Expected score: **89 synthetic cases** (41 known violations, 10 local clean controls, 38 abstentions), **not yet CI-confirmed**.

`xlsx_required_columns`, spreadsheet cell semantics/formulas, other document formats and quality algorithms remain unsupported. Authenticated remote evidence remains a separate lot. Lot 4 Exit Gate stays OPEN.

## Implementation update — XLSX first-row required columns (CI pending)

The owner confirmed CI green for prior XLSX sheet-name commit `7fae56b`. The engine now checks `xlsx_required_columns` from actual local worksheets, supporting literal inline, shared-string and direct-string first-row headers. Missing required sheets or header names are `ALERT`; formula-derived or unsupported headers, malformed files and missing observations are `UNKNOWN`. Six new strict-API cases are added to the adversarial matrix.

Expected expanded suite: **95 synthetic cases**, including 43 known violations, 12 clean local controls and 40 unscored abstentions. **CI for the final commit is pending.** Formula evaluation, cell contents, other format extractors and authenticated remote custody remain outside verified scope, so the Lot 4 Exit Gate stays **OPEN**.

## Implementation update — DOCX paragraph hash (CI pending)

Following owner-confirmed green CI for `15feaa3` (XLSX columns), the engine now supports the pinned local DOCX extractor `tdp-docx-body-paragraph-utf8-v1`. It reads bounded OOXML files and hashes direct simple-text body paragraphs with deterministic UTF-8 SHA-256. A changed or missing required paragraph yields `ALERT`; unsupported rich structures, extractor identity mismatch and missing observations remain `UNKNOWN`. Six strict synthetic cases added.

Expected extended benchmark: **101 cases** (45 known violations, 13 locally clean examples and 43 abstentions), **CI of latest SHA pending**. This is not a generic DOCX parser or proof of independent remote custody; PDF, DB and image quality requirements remain incomplete. **Lot 4 Exit Gate OPEN.**

## Implementation update — strict classic PDF page count (CI pending)

After the owner-confirmed green CI of `2bdbda3` (DOCX), the engine now supports `pdf_min_pages` on a narrow, bounded classic-xref PDF 1.x subset. It follows the actual `/Root` and `/Pages` tree and checks child/parent references and declared counts. Unsupported PDF variants abstain; a supported document below its required minimum raises `ALERT`. Five synthetic fixtures cover compliant/insufficient page trees and invalid or missing evidence.

Expected score: **106 synthetic cases** (46 known violations, 14 clean local observations, 46 abstentions). **CI for the newest commit remains to be confirmed.** `pdf_required_page_sha256`, modern PDF variants, document quality metrics and authenticated custody remain unimplemented. **Lot 4 Exit Gate OPEN.**

## Implementation update — pinned raw PDF page stream (CI pending)

The owner confirmed CI green for the preceding PDF xref syntax fix `c5b1bc2`. The engine now implements a **bounded raw unfiltered PDF page-stream fingerprint** under pinned extractor ID `tdp-pdf-simple-page-stream-sha256-v1`. Six synthetic tests examine identical content, changed content, missing page, unsupported compressed stream, mismatched extractor ID, and missing receiver evidence. The SHA-256 binds the directly declared page MediaBox and raw unfiltered stream bytes; it is **not** a rendered page, semantic-text or general PDF fidelity check.

Expected matrix: **112 synthetic cases** (48 known violations, 15 clean local controls, 49 abstentions), **CI for the final SHA not confirmed yet**. Complex PDF layouts, independent custody and other original Lot 4 requirements remain unverified. **Exit Gate OPEN.**

## Implementation update — read-only SQLite schema controls (CI pending)

The owner confirmed the previous PDF page-stream SHA `abb522a` green. The V0 engine now supports three local SQLite 3 checks: `db_required_table`, `db_required_column` (declared type string), and `db_required_foreign_key`. It opens bounded SQLite files in read-only immutable mode, checks structure and compares actual schema definitions. Seven new strict-API scenarios exercise valid and absent table/column/foreign-key cases, wrong column type, non-SQLite evidence and missing receiver data.

Expected matrix: **119 synthetic cases** (52 known violations, 16 locally clean examples, 51 abstentions), **latest SHA CI pending**. Other database dialects, row-level data validity and remote custody are not measured. The image perceptual quality metrics and other remaining Lot 4 Exit Gate requirements remain OPEN.

## Implementation update — referenced PNG Laplacian blur ratio (CI pending)

The owner confirmed the prior SQLite CI `f80ae4b` green. The V0 engine now accepts explicit `reference_files` paths keyed by declared reference artifact version ID and implements `image_max_blur_score_ratio` for bounded RGB8 PNG images using versioned integer-grayscale, four-neighbor Laplacian population variance. Seven additional strict-API cases cover compliant/blurred images, absent references, unaligned rasters, zero-variance ambiguity, unreadable candidate bytes and the still unsupported SSIM algorithm. Expected matrix: **126 synthetic cases** (53 violations, 17 clean local samples, 56 abstentions), latest CI **not yet confirmed**.

`image_min_ssim` with `ssim-skimage-v1` remains `UNKNOWN`: the specified external algorithm/configuration has not been pinned, reproduced or validated. Local reference files do **not** establish trustworthy reference provenance, full perceptual quality or authenticated recipient custody. The Lot 4 Exit Gate remains **OPEN** until all agreed acceptance conditions are reviewed.

## Implementation update — pinned scikit-image grayscale SSIM (CI pending)

Following owner-confirmed green CI for the image blur milestone `500a67f`, the V0 engine now evaluates the declared `image_min_ssim` control for aligned bounded RGB8 PNG local reference and observed files. The required `ssim-skimage-v1` implementation is pinned to `scikit-image==0.26.0`, `numpy==2.3.5`, `scipy==1.16.3`, using fixed `win_size=7`, `gaussian_weights=False`, `use_sample_covariance=True`, `data_range=255`, `channel_axis=None`, and BT.601 integer grayscale. Numeric dependencies are optional outside CI: missing/incompatible versions force UNKNOWN, not an alternative metric. This adds a narrowly scoped maintenance and installation dependency.

Seven executable synthetic strict-API cases cover two local PASS cases, two known image degradation ALERT cases, and three evidence-limited UNKNOWN cases. **Expected** expanded benchmark: **133 synthetic cases** (55 known violations, 19 clean locally observed cases, 59 abstentions), **final CI not yet confirmed**. None of these asserts full visual semantic fidelity or independently authenticated reference/receiver custody. **Lot 4 Exit Gate remains OPEN** pending explicit review of original remaining acceptance criteria, unsupported formats, adversarial journey graph/fork/join scope, and end-to-end reproducibility.
