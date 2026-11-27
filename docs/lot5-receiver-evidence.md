# Lot 5 — Receiver evidence and provenance

## Status: tranche 1 — signed local receipt primitive; Exit Gate OPEN

The public deterministic monitor's Lot 4 V0-local Exit Gate is closed. Lot 5 adds a separate **receiver-side evidence producer** and **verifier**; it does not reinterpret prior local `PASS` results as authenticated delivery.

### First implemented component

`handoff_monitor/receiver_evidence.py` provides `create_receiver_receipt` and `verify_receiver_receipt`. The receiver-side function reads at most 32 MiB of a file using SHA-256 and signs a versioned canonical JSON receipt with a locally supplied Ed25519 private-key object. It records the receiver/key identity, receipt ID, run, handoff, contract and version, from/to steps, event IDs, artifact ID/version, attempt number, hash and byte count. Serialization is deterministic with a domain-separated signed prefix. **No private keys are committed or embedded in receipts.**

Verification requires an **independently provisioned** registry of trusted receiver public keys, indexed by `(receiver_id, key_id)`, plus an explicit independently expected event/contract context. An optional verifier-observed file may be rehashed and compared. The verifier returns **`VERIFIED_SIGNATURE`**, **`ALERT`** or **`UNKNOWN`**, deliberately not the existing core's `PASS`. Missing trusted key, expected context or verifier evidence cannot be upgraded to authenticated receipt.

An optional caller-supplied `seen_receipt_ids` set checks local replay claims, but it is **not** a durable trusted anti-replay store. The signature verifies possession of a private key corresponding to an independently pinned public key — **not** by itself the real-world identity of a remote agent, secure key provisioning, actual network delivery, retention or trusted timestamp. The caller must provide the receiver's trust boundary and defend it separately.

### Dependency / security boundary

- Optional pinned `cryptography==50.0.2` in `requirements-receiver-evidence.txt`; installed in CI. No new hosted services, API keys, paid subscriptions or client data.
- Private keys must be generated and stored by the receiver outside GitHub, outside logs and outside client-visible files.
- Public key registration and expected contract context must be controlled separately from the receipt producer; do **not** accept a public key supplied in the receipt itself.
- The module is a **standalone first tranche**. It is not yet wired to `compare_handoff_validated` or `compare_journey_validated` as a remote-custody override.
- Only synthetic files and ephemeral keys are used in tests; no external agent, network transfer or remote host is involved.

### Next Lot 5 work (based on original plan)

1. Define and test a receiver-boundary adapter invoking this primitive **on the actual recipient**, with separately trusted sender/receiver identities and key provisioning.
2. Add a reliable receipt registry with atomic replay checks, revocation and rotation, and explicit binding to the expected attempt / authorized policy.
3. Integrate receipt verification into a separately named custody decision, preserving the distinction between local file-integrity results and independently evidenced receipt.
4. Validate adversarial tests for forged receipts, swapped keys, mismatch between measured bytes and manifests, replay, ambiguous retries, expired/revoked authorization and missing evidence. Review the lot 5 Exit Gate with execution evidence.

**Exit Gate: OPEN.** Do not claim actual authenticated end-to-end delivery until the independent recipient adapter and trust registry have been exercised.
