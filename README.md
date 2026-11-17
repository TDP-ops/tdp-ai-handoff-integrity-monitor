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

**Planning / initial repository setup.** No integrity engine is implemented yet. No production security or integrity guarantees are claimed.

The planned development sequence is:
1. Contract and schema definition
2. Selective review of reusable open-source components and licenses
3. Deterministic engine
4. Synthetic regression tests and GitHub Actions
5. Receiver-side evidence adapters
6. Static Hugging Face demonstration

## Open-source attribution

Upstream projects are being evaluated; **no third-party source code has been copied into this repository**. Any future reuse must be reviewed for license compliance, dependency cost, and test coverage.

## Security

Do not commit API keys, environment files, private traces, client files, credentials, or production artifacts. Use synthetic test fixtures only.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). Third-party components, if incorporated later, will retain their applicable licenses and attribution notices.
