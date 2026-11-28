"""Build a no-backend Hugging Face Static Space from actual regression results.

The published JSON is deliberately an allowlisted, synthetic-only projection
of the *executed* evaluation. Never publish raw test fixtures, traces, paths,
private keys, manifests, or arbitrary CI artifacts.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "demo" / "space"
OUTPUT = ROOT / "demo" / "dist"
SCORE = ROOT / "scripts" / "measure_lot4_adversarial.py"
CASE_NAME = re.compile(r"[A-Za-z0-9_:.+-]{1,120}\Z", re.ASCII)
TRUTH = {"violation", "clean", "evidence_unavailable"}
VERDICT = {"ALERT", "PASS", "UNKNOWN"}
EXPECTED = {"TP": 69, "FP": 0, "FN": 0, "TN": 20,
            "unknown_violation": 0, "unknown_clean": 0,
            "abstentions_unscored": 66}


def sanitize(raw, *, commit=""):
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        raise ValueError("Expected executed scoring report")
    if raw.get("scope") != "small_synthetic_V0_local_only":
        raise ValueError("Unexpected evaluation scope")
    cases = []
    seen = set()
    for row in raw["rows"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid synthetic scenario")
        name, truth, verdict = row.get("case"), row.get("truth"), row.get("verdict")
        if (not isinstance(name, str) or not CASE_NAME.fullmatch(name)
                or name in seen or truth not in TRUTH or verdict not in VERDICT):
            raise ValueError("Unsafe, duplicate or invalid synthetic scenario")
        seen.add(name)
        cases.append({"case": name, "truth": truth, "verdict": verdict})
    counts = raw.get("counts")
    if not isinstance(counts, dict) or any(type(counts.get(key)) is not int
                                             for key in EXPECTED):
        raise ValueError("Missing or invalid counters")
    counts = {key: counts[key] for key in EXPECTED}
    if counts != EXPECTED or len(cases) != 155 or raw.get("total_cases") != len(cases):
        raise ValueError("Scoring baseline changed: review source and demo before publishing")
    recomputed = {key: 0 for key in EXPECTED}
    for row in cases:
        truth, verdict = row["truth"], row["verdict"]
        if truth == "evidence_unavailable":
            if verdict != "UNKNOWN":
                raise ValueError("Unscored uncertainty misclassified")
            recomputed["abstentions_unscored"] += 1
        elif truth == "violation":
            recomputed[{"ALERT": "TP", "PASS": "FN",
                        "UNKNOWN": "unknown_violation"}[verdict]] += 1
        else:
            recomputed[{"ALERT": "FP", "PASS": "TN",
                        "UNKNOWN": "unknown_clean"}[verdict]] += 1
    if recomputed != counts:
        raise ValueError("Counter mismatch against per-scenario observations")
    if commit and not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid source commit")
    return {
        "schema_version": 1,
        "scope": raw["scope"],
        "source_commit": commit,
        "total_cases": len(cases),
        "known_ground_truth_cases": 89,
        "counts": counts,
        "cases": sorted(cases, key=lambda x: x["case"]),
        "limitations": [
            "Synthetic local benchmark; not representative of production accuracy.",
            "UNKNOWN cases are abstentions and not true negatives.",
            "Lot 5 authenticated independent receiver-custody exit gate remains OPEN.",
            "No Python engine, inference or file uploads run in this static demonstration."
        ]
    }


def build():
    runner = subprocess.run(
        [sys.executable, str(SCORE)], cwd=ROOT,
        capture_output=True, text=True, timeout=120, check=True)
    raw = json.loads(runner.stdout)
    dataset = sanitize(raw, commit=os.environ.get("GITHUB_SHA", ""))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC / "index.html", OUTPUT / "index.html")
    shutil.copyfile(ROOT / "demo" / "space-README.md", OUTPUT / "README.md")
    (OUTPUT / "report.json").write_text(
        json.dumps(dataset, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8")
    if (OUTPUT / "report.json").stat().st_size > 100_000:
        raise ValueError("Unexpected demo report size")
    print(f"Built Static Space: {len(dataset['cases'])} tested scenarios, "
          f"{dataset['counts']['TP']} flagged violations, "
          f"{dataset['counts']['abstentions_unscored']} abstentions.")


if __name__ == "__main__":
    build()
