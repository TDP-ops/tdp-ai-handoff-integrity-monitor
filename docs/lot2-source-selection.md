# Lot 2 — Selective open-source reuse decision (V0)

Date: 2026-11-17  
Status: **source inventory and design selection complete; no third-party code imported, installed or vendored.**  
Prerequisite: lot 1 contract CI on latest main is **not independently verified** through the current GitHub integration; do not label lot 1 fully closed without the green Actions result.

## Decision

**Keep the standalone deterministic Handoff Integrity Monitor core self-owned.** Prefer Python standard library for immutable identity, version lineage, file SHA-256, matching sent/received manifests, and a small CLI. Existing JSON Schema validation depends on `jsonschema==4.23.0` for contract tests.

Treat external projects as **documented design benchmarks and optional future compatibility surfaces**, not automatic runtime dependencies. Reuse ideas and public specifications independently; copying source requires a separately reviewed change with the exact upstream commit, license and obligations.

## Reviewed public repositories

| Project | Confirmed license | Relevant surface | V0 selection | Risks and limits |
|---|---|---|---|---|
| [karimbaidar/agent-consistency](https://github.com/karimbaidar/agent-consistency) | Apache-2.0 | Outcome gates, receipts, state evidence and unverified-success discipline | **Pattern reference only**: do not import | Its outcome checks do not independently prove receiver-side file integrity |
| [gianpremrajaram/precept](https://github.com/gianpremrajaram/precept) | Apache-2.0 | Contracts at agent input boundaries, single intermediate representation, receiver-oriented checks | **Pattern reference only**: contracts and upstream enforcement | Repository identifies itself as research preview, unstable API, not production recommendation |
| [krivonosoff161/agentic-transfer-verifier](https://github.com/krivonosoff161/agentic-transfer-verifier) | MIT | Transfer envelopes, source/provenance, freshness, authority and auditability | **Potential adapter later**; no install or code copy | Broader trust/authority model than V0 artifact integrity; adapter coupling and extra dependency |
| [krivonosoff161/ai-agent-handoff](https://github.com/krivonosoff161/ai-agent-handoff) | MIT | File-based handoff and durable, reviewable transfer records | **Pattern reference only** | Coding-agent/git flow is not universal multi-agent artifact transport |
| [krivonosoff161/agentic-security-harness](https://github.com/krivonosoff161/agentic-security-harness) | Apache-2.0 | Reproducible synthetic adversarial cases and trace/scorecard reporting | **Benchmark design reference** for lot 4 | Security/authority suite is not proof our PDF/image/DB artifact verifier works |
| [Arrmlet/tracecraft](https://github.com/Arrmlet/tracecraft) | MIT | JSONL run traces, handoffs, independently controlled persistence | **Optional future trace adapter**; no bucket/account | Bucket storage is additional service, costs, privacy/data-transfer exposure; unnecessary for V0 static demo |

Primary sources: each upstream README and LICENSE as publicly accessible on GitHub, examined 2026-11-17. This document is a suitability review, **not** a source-code security audit, maintainer endorsement, upstream performance verification or certification.

## V0 implementation boundary and selective reuse

| Required capability | Chosen V0 approach | External code? |
|---|---|---|
| Single versioned contract | Existing `schemas/handoff-v0.schema.json`; maintain independently | None |
| Source/recipient manifests | Match `run_id`, `handoff_id`, `event_id`, contract and versions | None |
| Identity and lineage | `artifact_id`, `artifact_version_id`, parent links, replacements, rejections | None |
| Actual unchanged file byte integrity | SHA-256 calculated from opened bytes using `hashlib` on sender/receiver probe | None |
| Partial or missing receiver evidence | `UNKNOWN`, never auto-`PASS` | None |
| Adversarial acceptance tests | Local synthetic fixture corpus with visible expected outcomes | None |
| Reader-friendly results | Deterministic JSON + CLI summary, static demo without backend | None |
| Optional integrations | Explicit adapters **after** stable core; not through public GitHub for private TDP products | Deferred |

## License and provenance gate before any external source copy

1. Identify exact upstream repository, source file, immutable commit SHA and selected code span.
2. Verify the applicable license and copyright information for **that file**, not just repository-level badge.
3. Review dependency tree, transitive licenses, distribution terms, API stability, and any security implications.
4. Carry forward relevant MIT/Apache-2.0 notices, copyright headers, and Apache NOTICE obligations where applicable.
5. Record the imported code location, SHA, modifications and acceptance tests in a provenance log.
6. Reject direct import if it couples the public core to a framework, cloud account, opaque hosted API, unstable research interface, or nonessential personal data transfer.

**Current provenance ledger:** no third-party code copied; no upstream runtime packages installed. Links and conceptual benchmarking do not make source files dependencies.

## Lot 2 exit gate

- [x] Inspect named upstream READMEs and license texts.
- [x] Choose self-owned minimal V0 core vs importing third-party frameworks.
- [x] Record potential future adapters, dependency risks and source-license process.
- [x] Keep public repo separate from TFE, SignalForge, site, and customer information.
- [ ] Confirm current lot 1 / lot 2 GitHub Actions green on latest main commit.

**Decision ready:** proceed to lot 3 only after CI verification. Lot 3 implements deterministic checks; lot 5 implements independent receiver-side evidence. Do not mislabel synthetic expected verdicts as verified detection outcomes.
