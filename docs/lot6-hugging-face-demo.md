# Lot 6 — Hugging Face Static Space, GitHub handoff

## Status

**GitHub implementation ready; external Hugging Face publication NOT YET EXECUTED.** Lot 5 remains open for an independently attested receiver handoff. The Lot 6 Space is a public **read-only visualization** of actual synthetic CI results, not a live Python engine or claim of remote custody.

## Source, build and scope

- `demo/space/index.html`: accessible, responsive static HTML/CSS/JS explorer with per-case search, verdict filters and evidence-scope explanation. No third-party JS, analytics, external inference, forms or uploads.
- `demo/space-README.md`: Hugging Face frontmatter, `sdk: static`, `app_file: index.html` and Apache-2.0 disclosure.
- `scripts/build_lot6_demo.py`: invokes the **real** `scripts/measure_lot4_adversarial.py` in a subprocess, verifies each allowlisted synthetic case and aggregate counters, then exports **only** `README.md`, `index.html`, `report.json` into `demo/dist/`. Any changed counts/case labels must be reviewed and explicitly approved in the source before publishing.
- `tests/test_lot6_demo_export.py`: refuses unexpected scope, duplicate/unsafe case identifiers, manipulated verdicts, counter mismatches, or non-synthetic report.
- `.github/workflows/ci.yml`: builds the static package from live regression tests and verifies it on every commit.
- `.github/workflows/publish-hf-static.yml`: **manual** upload to a *preexisting* Space, limited to the three reviewed files. No auto-publication on push. The workflow installs a pinned Hugging Face Hub client **only when manually publishing** and runs the full regression suite before upload.

### Evidence in the Space

The CI-derived evaluation includes **155 synthetic scenarios** (69 known violations flagged, 20 local clean controls, 66 evidence-unavailable abstentions), with zero FP/FN **on this specific synthetic corpus only**. These are not production performance estimates. The read-only Space is intentionally not capable of processing user-provided artefacts, executing agents or independently authenticating receipt.

## One-time steps for the TDP operator (only after GitHub CI is green)

1. Open https://huggingface.co/spaces/launch and sign into your existing Hugging Face account. Create a **public Static** Space. Recommended name: `tdp-ai-handoff-integrity-monitor` (check name availability). **Do not choose Gradio or Docker:** they are outside the planned free static hosting scope. Choose Apache-2.0 if the setup asks for a license.
2. In Hugging Face account settings → Access Tokens (https://huggingface.co/settings/tokens), create a **fine-grained token** that can **write to that one Space only**, if the available permissions permit this. If the specific repository write scope is not offered, stop and review the least-privilege option before using a broader token. **Never paste the token into ChatGPT, the repository, README, or a Space variable.**
3. In the GitHub repository `TDP-ops/tdp-ai-handoff-integrity-monitor`, open **Settings → Secrets and variables → Actions**. Under **Variables**, create `HF_SPACE` with the exact `namespace/space-name` identifier from Hugging Face; under **Repository secrets**, create `HF_TOKEN` with the token created in step 2. This permits the manual GitHub Action to upload files to that Space. Treat the token as a third-party write credential; revoke it when no longer needed.
4. In GitHub **Actions**, choose **Publish static demo to Hugging Face (manual)** → **Run workflow** on `main`. Watch the workflow result. It rechecks the tests, builds the allowlisted static bundle, verifies the Space exists, and uploads only `README.md`, `index.html`, `report.json` to that Space. **No Space ID or URL is presumed until created by the operator.**
5. On Hugging Face, verify the Space loads; compare the live totals to the **GitHub Actions build** (155 total, 69 flagged, 20 clean, 66 abstentions), try filters and mobile display, and check that the disclaimer is visible. Confirm that there are no private keys, customer records, or extra repository files in its **Files** view.

## Exit gate and separation of concerns

**GitHub delivery gate**: source code, tests, static package and manual deployment workflow committed; final `main` CI green. A successful GitHub build alone does not mean the external Space was deployed.

**Hugging Face publication gate**: public Space created, write permission configured, manual upload workflow green, and live URL reviewed. This gate cannot be closed without the Hugging Face account holder's explicit setup.

**Lot 5 independent receiver evidence gate**: still open. Publishing this demo does not satisfy it.

**Security and costs**: Static Space hosting itself is free, per Hugging Face documentation, and runs no Python back end. The required fine-grained write token is a new credential in GitHub Actions secrets, limited to the one Space where possible. No paid hardware, new runtime account, customer data or private keys are used in the demonstration. Any public Space reveals the demo and its synthetic results by design.
