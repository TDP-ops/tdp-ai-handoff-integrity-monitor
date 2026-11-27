# Lot 5 — Cross-environment acceptance protocol

**Status:** READY TO EXECUTE; **NOT EXECUTED against two independently administered environments.** This is the remaining real-world Exit Gate of Lot 5. It must not be satisfied solely by another CI simulation or two processes on one machine.

## Prerequisites

- **Receiver environment R:** controlled by the receiving operator; only R has the Ed25519 private key and access to the actual receiver-side file.
- **Verifier environment V:** controlled by a **different administrative authority**; only V controls its SQLite trust registry and independent expected-context record.
- Both environments run the same reviewed version of the TDP monitor, Python and pinned `cryptography` dependency. No new cloud service or paid account is required if R and V already exist.
- Synthetic test artefact only. Use a transport channel approved by both administrators; do not place private keys, real customer data or secrets in this public repository, CI artifacts or chat.
- Before accepting the public key, V obtains the receiver identity and SHA-256 fingerprint through an **independently authenticated** channel. Copying a fingerprint from the same untrusted package as its public key is not independent verification.
- V creates a trusted `expected.json` with receiver ID, hash, byte length, run, handoff, contract, contract version, from/to steps, sender/receiver event IDs, artefact ID/version and attempt number **from its own approved run policy and sender observation**, not by copying the receipt under test. An operator must approve the expected context before the receipt arrives.

## Role R — receiver (commands run only on R)

Install Python requirements locally and keep a receiver-only working directory with restrictive permissions.

```bash
python3 -m pip install -r requirements-receiver-evidence.txt
umask 077
python3 -m handoff_monitor.receiver_cli receiver-init \
  --private-key /receiver-private/ed25519.key \
  --public-key /receiver-public/ed25519.pub
```

R independently gives V the public key and separately authenticates the **public-key fingerprint** through the trusted enrollment procedure. The private key remains on R. No pre-existing key is overwritten by `receiver-init`.

After the transferred synthetic file has actually arrived at R and R has produced its own recipient observation and manifests:

```bash
python3 -m handoff_monitor.receiver_cli receiver-sign \
  --private-key /receiver-private/ed25519.key \
  --plan /receiver-input/run-plan.json \
  --sent /receiver-input/sent.json \
  --received /receiver-input/received.json \
  --artifact-id ART-001 \
  --file /receiver-data/observed.bin \
  --receiver-id RECEIVER-B --key-id KEY-B-01 \
  --output /receiver-out/receipt.json
```

R transfers **only** the signed `receipt.json` and authorized public metadata to V. Preserve an operator-visible record of when and how the receipt was sent. **No built-in transport** or network-service authentication is provided by the CLI.

## Role V — verifier (commands run only on V)

V establishes its approved fingerprint independently before enrollment. The variable below represents the **previously approved value**, never the value copied from an untrusted receipt.

```bash
python3 -m pip install -r requirements-receiver-evidence.txt
umask 077
python3 -m handoff_monitor.receiver_cli verifier-enroll \
  --registry /verifier-private/trust.sqlite \
  --public-key /verifier-in/ed25519.pub \
  --receiver-id RECEIVER-B --key-id KEY-B-01 \
  --approved-fingerprint "$APPROVED_RECEIVER_KEY_SHA256"
```

Only after V has independently established `expected.json` should it check the receipt:

```bash
python3 -m handoff_monitor.receiver_cli verifier-verify \
  --registry /verifier-private/trust.sqlite \
  --receipt /verifier-in/receipt.json \
  --expected /verifier-private/expected.json
```

If V also holds a separately observed copy of the file, pass `--observed-file /verifier-observed/observed.bin`. **Do not claim that the file was independently observed by V when it was merely copied from an untrusted receipt.**

## Required acceptance checks

| Scenario | Expected observation | Evidence required |
| --- | --- | --- |
| Receiver signs exact received bytes with its own private key | `VERIFIED_SIGNATURE` with independently pinned key + expected context | Separate R and V execution records, receiver key-protection evidence, approved pin record |
| V receives a different public key under same receiver identity | Enrollment rejects fingerprint mismatch | Verifier-side enrollment log |
| Receipt contents/signature tampered with | `ALERT` | Signed original and tampered test receipt, verifier outcome |
| Different bytes / handoff ID / receiver ID | `ALERT` | Independent expected-context snapshot and verifier outcome |
| Receipt replay after verifier restart | `ALERT` | Persistent registry and second verifier outcome |
| Receiver key revoked | `ALERT` for new receipts | Revocation record and verifier outcome |
| Expected context or independent pin unavailable | `UNKNOWN` or enrollment rejection | Verifier outcome |
| No actual receiver file to inspect | No signed receipt; cannot assert delivery | Receiver-side failure record |

**Stop/rollback:** on any unexpected `VERIFIED_SIGNATURE`, registry corruption, private-key exposure or inability to confirm pin independence, stop the acceptance run, preserve nonsecret evidence and keep the Lot 5 Exit Gate **OPEN**.

## Exit Gate decision

Closing Lot 5 requires **actual proof** that:
1. R and V are independently administered and run the adapter / registry on separate environments; the private key never reaches V or GitHub.
2. R signs bytes observed at its real receiving boundary, not sender-declared bytes alone.
3. V independently approves key ownership/pin and expected sender/run context before trusting R's receipt.
4. Approved and adversarial scenarios above execute with recorded results, including persistence, revocation and replays.
5. `compare_handoff_with_custody` continues to distinguish local integrity, `VERIFIED_SIGNATURES`, and unproven remote transport; **there is no automatic global `PASS` upgrade**.

The current CLI/tests establish the underlying mechanics, not the actual independent administrative trust boundary. **No environment R/V or real cross-host run is represented as available or completed here.**

**Next necessary operator input:** identify an existing receiving environment R and an independent verifying environment V (without sharing credentials or private keys). Once these are identified, execute the approved synthetic protocol and record proof. If these two environments do not exist, defer the real Exit Gate instead of creating unnecessary infrastructure.
