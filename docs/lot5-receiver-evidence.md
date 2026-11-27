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

### Tranche 2 — persistent trust registry and receiver-boundary adapter (27 November 2026)

- `handoff_monitor/receiver_registry.py` implements a verifier-controlled **SQLite trust registry**: independent key enrollment, revocation, atomic rotation, and durable uniqueness of accepted receipt IDs and per-`receiver/run/handoff/artifact/attempt` identities. It uses `BEGIN IMMEDIATE` for concurrent SQLite writers, an atomic insert/commit, and refuses to consume an invalid receipt. Newly created files receive restrictive POSIX permissions; production operators must additionally protect directories, backups and host access.
- `handoff_monitor/receiver_adapter.py` provides `receive_and_sign`, intended to run **inside the actual recipient trust boundary**. It validates the handoff records and contract, reads receiver-local bytes, checks the receiver manifest's declared SHA-256/size against the opened file, and signs a receipt with a receiver-held key. Receipt IDs are randomly generated inside the adapter.
- The registry now requires an **independently supplied expected receiver ID and expected SHA-256**, in addition to the complete expected run/handoff/attempt context, before atomic acceptance. It cannot derive those facts from the receipt being verified. Without them it abstains to `UNKNOWN`. A valid signed receipt from the wrong receiver or for different bytes must not establish custody.
- Regression tests `tests/test_lot5_receiver_registry.py` and `tests/test_lot5_receiver_adapter.py` use synthetic bytes and ephemeral keys for restart replay protection, receipt-fork collision, corruption, revoked/rotated key behavior, manifest mismatch, and end-to-end local adapter-to-registry verification.
- **This remains a simulated local separation**, not evidence that an actual independent remote recipient has deployed the adapter or protected its signing key. No hosted service, actual private key, network receiver, trusted timestamp, production directory or client data has been provisioned.

**Current Exit Gate: OPEN.** Next must demonstrate independent verifier/receiver execution, authenticated key provisioning and separation, concurrency/restart handling, revocation semantics, and integration of validated receipt evidence with the main handoff verdict without upgrading a locally measured PASS into remote authenticity.

### Tranche 3 — custody result integration and separate-process simulation (27 November 2026)

- `handoff_monitor/custody.py` adds `compare_handoff_with_custody`, which **separately reports** the original schema-validated local integrity verdict, per-artifact signed receipt results, and `custody_status`. It derives the expected run/contract/attempt/artefact details from validated manifests, but **requires the receiver identity to be pinned separately** and hashes the sender-observed bytes for an independent expected SHA-256 and size. A local `ALERT` is never overridden by a receipt. A missing or untrusted receipt remains `UNKNOWN`. A verified signature may produce `custody_status=VERIFIED_SIGNATURES`, but the combined verdict deliberately remains **`UNKNOWN`**, not an authenticated remote-delivery `PASS`.
- `tests/test_lot5_custody.py` exercises valid signatures, tampering, wrong receiver, replays, missing sender bytes or receipts, and the precedence of local integrity alarms over signed observations.
- `tests/test_lot5_separate_processes.py` uses two distinct Python OS processes: the receiver subprocess generates and holds its ephemeral private key and signs actual synthetic file bytes; the verification process registers the public key, verifies the signed receipt, rejects its replay and retains the conservative `UNKNOWN` end-to-end verdict. This proves **process-level separation only**, not an external deployment or an independently authenticated key enrollment.
- **Risks remaining:** the test harness conveys the test public key; actual public-key ownership is not independently certified. There is no protected cross-host transfer, independently attested policy grant, external key provisioning, identity lifecycle service, or trusted event timestamp. The registry and private-key storage must run with real separate operational permissions before the signed record can substantiate receiver identity.

**Lot 5 Exit Gate stays OPEN** until real independent receiver/verifier execution and safe key enrollment/authorization can be verified. The user should not need to provision any account, hosted service or production keys for this synthetic implementation.

### Tranche 4 — verifier-side key pinning (27 November 2026)

- The registry now exposes `enroll_pinned_key(receiver_id, key_id, public_key, independently_expected_sha256)`. It computes SHA-256 over the raw 32-byte Ed25519 public key and checks the digest against the **verifier-side independently approved** lowercase hexadecimal fingerprint using constant-time comparison before allowing immutable enrollment. Mismatched, malformed or substituted keys are rejected without registry entry. `enroll_key` remains a privileged lower-level administrative method and must not be exposed to untrusted callers.
- Adversarial regression cases explicitly reject a substituted key, malformed pin and an attacker attempting to enroll under an approved fingerprint. The separate-process synthetic test exercises the pin-checking API, but its fingerprint is generated by the **test harness from the received test public key**: this is a **mechanics test only, not independent enrollment or identity authentication**.
- **Operational requirement not completed:** a verifier administrator must establish the fingerprint using an independently authenticated channel **before** trusting a receiver's signed receipts; receiver key custody, permissions and key lifecycle must be tested across truly separate hosts/administrative domains. No private key, customer artifact or external service is used in this tranche.
- **Lot 5 Exit Gate remains OPEN** until those real boundaries and authorization controls are demonstrated. Green CI only proves the synthetic tests and cannot be presented as verified remote custody.

### Tranche 5 — interface exécutable récepteur / vérificateur (27 novembre 2026)

`python -m handoff_monitor.receiver_cli` fournit quatre commandes sans service externe : `receiver-init` (génération de clé Ed25519 privée, fichier 0600 sous POSIX, et clé publique séparée), `receiver-sign` (signature des octets locaux et du contexte d'un handoff), `verifier-enroll` (registre SQLite avec empreinte publique pré-approuvée), et `verifier-verify` (validation du reçu contre un contexte attendu propre au vérificateur et protection durable anti-replay).

Le test `tests/test_lot5_receiver_cli.py` lance chaque opération dans un sous-processus Python distinct, avec espaces de fichiers séparés : refuse un pin erroné, la réinitialisation d'une clé existante, les preuves incomplètes et les replays. Une commande vérificateur utilise seulement la clé **publique** et un document de contexte attendu, sans accès à la clé privée du récepteur.

**Délimitation :** le banc de test crée lui-même le pin de la clé éphémère ; il ne prouve pas l'authentification indépendante d'une identité organisationnelle, ni un transfert réseau entre machines contrôlées séparément. En production, le vérificateur doit approuver et enregistrer le pin par un canal distinct et fiable **avant** l'enrôlement. Les permissions, la propriété des clés, les transports et les politiques ne sont pas attestés par cette CI. Le lot 5 demeure **OPEN** tant qu'un vrai essai de séparation administrative et de transfert n'est pas exécuté.

### Next Lot 5 work (based on original plan)

1. Define and test a receiver-boundary adapter invoking this primitive **on the actual recipient**, with separately trusted sender/receiver identities and key provisioning.
2. Add a reliable receipt registry with atomic replay checks, revocation and rotation, and explicit binding to the expected attempt / authorized policy.
3. Integrate receipt verification into a separately named custody decision, preserving the distinction between local file-integrity results and independently evidenced receipt.
4. Validate adversarial tests for forged receipts, swapped keys, mismatch between measured bytes and manifests, replay, ambiguous retries, expired/revoked authorization and missing evidence. Review the lot 5 Exit Gate with execution evidence.

**Exit Gate: OPEN.** Do not claim actual authenticated end-to-end delivery until the independent recipient adapter and trust registry have been exercised.
