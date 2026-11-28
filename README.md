# TDP AI Handoff Integrity Monitor

Open-source project by The Digital Phenix (TDP).

## Purpose

A deterministic integrity monitor for multi-agent AI handoffs. Its objective is to identify missing, altered, stale, or unexpectedly replaced artifacts and requirements across agent and workflow boundaries, using independently observable evidence whenever available.

## Design principles

- Compare **sent** and **received** manifests against explicit, versioned handoff contracts.
- Track stable artifact identities, version identities, provenance, allowed transformations, rejections, and replacements.
- Support multimodal files and structured data through type-specific validators.
- Return **PASS**, **ALERT**, **UNKNOWN**, or optional **BLOCK**; never treat unavailable evidence as proof of success.
- Keep raw customer data and secrets out of logs and public demos.
- Prefer deterministic, local checks; avoid mandatory paid APIs or LLM judges.

## Project status

**Lots 1–4 completed for the bounded V0 local/synthetic scope; Lot 5 (independent receiver evidence) remains pending.** The deterministic engine has a verified 155-case synthetic adversarial evaluation and an opt-in DAG mode with bounded declared retries. This is **not** a production-ready authenticated end-to-end receipt system. The comparator can verify caller-provided local bytes and flag manifest and contract inconsistencies, but it cannot independently prove that a remote AI agent received an artifact.

Schema-first public Python entrypoints (recommended for untrusted manifest input):

```python
from handoff_monitor import compare_handoff_validated, compare_journey_validated

single = compare_handoff_validated(plan, sent, received)
journey = compare_journey_validated(plan, [{"sent": sent, "received": received}])
```

`jsonschema==4.23.0` is required to call these validated entrypoints (installed by the repository CI). `compare_handoff` and `compare_journey` remain available for callers that separately enforce the canonical schema; **do not use them directly with untrusted manifests**. The `PASS` verdict of a local single-handoff byte check is not proof of independent remote receiver custody, and a coherent multi-hop journey remains `UNKNOWN` without that proof. Validated API input checks also do not authenticate caller-supplied histories, policy grants or file paths.

Lot 5 has begun with a standalone, cryptographically signed receiver-side receipt primitive; **this does not yet establish authenticated end-to-end custody**. See [Lot 5 receiver evidence and trust boundary](docs/lot5-receiver-evidence.md) and [Lot 4 scoped Exit Gate](docs/lot4-exit-gate.md), [Lot 3 implementation boundaries](docs/lot3-engine-initial.md) and [canonical JSON Schema](schemas/handoff-v0.schema.json).

The planned development sequence is:
1. Contract and schema definition
2. Selective review of reusable open-source components and licenses
3. Deterministic engine
4. Adversarial synthetic regression suite and measured test coverage
5. Receiver-side evidence adapters
6. Static Hugging Face demonstration

## Hugging Face demo (Lot 6)

The [Static Space demo](docs/lot6-hugging-face-demo.md) is implemented on GitHub and generated from real CI synthetic results. **Publication to Hugging Face requires the account holder to create a Static Space and configure a scoped GitHub Actions secret; no external Space deployment is claimed yet.** The manually triggered `Publish static demo to Hugging Face (manual)` workflow publishes only the reviewed static page, read-only synthetic report, and Hugging Face README. Lot 5 independent receiver custody remains open.

## Open-source attribution

Upstream projects are being evaluated; **no third-party source code has been copied into this repository**. Any future reuse must be reviewed for license compliance, dependency cost, and test coverage.

## Security

Do not commit API keys, environment files, private traces, client files, credentials, or production artifacts. Use synthetic test fixtures only.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). Third-party components, if incorporated later, will retain their applicable licenses and attribution notices.
