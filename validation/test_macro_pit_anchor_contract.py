#!/usr/bin/env python3
"""Self-contained positive and negative tests for the macro PIT anchor contract."""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERIES = ROOT / "live_data/sections/MACRO_SERIES.json"
HEAT = ROOT / "live_data/sections/MACRO_THERMOMETER_DATA.json"
CONTRACT = ROOT / "validation/macro_pit_anchor_contract.py"
sys.path.insert(0, str(ROOT / "validation"))
from build_macro_candidate import apply_candidate


def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    out = subprocess.run([sys.executable, str(CONTRACT), *args], cwd=ROOT, text=True, capture_output=True)
    if out.returncode != expected:
        raise AssertionError(f"expected {expected}, got {out.returncode}: {out.stderr}\n{out.stdout}")
    return out


def write(path: pathlib.Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def target() -> tuple[str, str, str]:
    series, heat = json.loads(SERIES.read_text()), json.loads(HEAT.read_text())
    c, d = "JPY", "labour"
    sid = f"{heat['currencies'][c][d]['series_id']}_history_value"
    rows = [r for r in series[c] if r["id"] == sid]
    if len(rows) != 1:
        raise AssertionError("test target not uniquely resolvable")
    return c, d, sid


def main() -> int:
    currency, dimension, series_id = target()
    with tempfile.TemporaryDirectory(prefix="gmfq-pit-contract-test-") as tmp:
        evidence = pathlib.Path(tmp) / "evidence"
        common = ("--evidence-dir", str(evidence), "--currency", currency, "--dimension", dimension, "--macro-series-id", series_id)
        run("capture-before", *common)

        before_s = evidence / "before" / "MACRO_SERIES.json"
        before_h = evidence / "before" / "MACRO_THERMOMETER_DATA.json"
        series, heat = json.loads(before_s.read_text()), json.loads(before_h.read_text())
        row = next(r for r in series[currency] if r["id"] == series_id)
        h = heat["currencies"][currency][dimension]
        candidate = {"currency": currency, "dimension": dimension, "macro_series_id": series_id,
                     "observation_date": "2099-12", "value": float(row["last_value"]) + 0.001,
                     "source": h["source"], "series_id": h["series_id"], "frequency": h["frequency"],
                     "transformation": h["transformation"]}
        after_series, after_heat = copy.deepcopy(series), copy.deepcopy(heat)
        apply_candidate(after_series, after_heat, candidate)
        after_s, after_h = evidence / "after" / "MACRO_SERIES.json", evidence / "after" / "MACRO_THERMOMETER_DATA.json"
        after_s.parent.mkdir(parents=True)
        write(after_s, after_series); write(after_h, after_heat)
        before_meta = json.loads((evidence / "before" / "capture.json").read_text())
        after_meta = copy.deepcopy(before_meta)
        after_meta["phase"] = "AFTER"
        for name, path, obj in (("MACRO_SERIES.json", after_s, after_series), ("MACRO_THERMOMETER_DATA.json", after_h, after_heat)):
            after_meta["artifacts"][name]["sha256"] = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
            after_meta["artifacts"][name]["semantic_sha256"] = __import__("hashlib").sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        (evidence / "after" / "capture.json").write_text(json.dumps(after_meta), encoding="utf-8")
        run("verify", *common)
        # A cell in another series makes the release ineligible for certification.
        tampered = json.loads(after_h.read_text())
        tampered["currencies"]["USD"]["inflation"]["latest_value"] = -999.0
        write(after_h, tampered)
        run("verify", *common, expected=1)

    print(json.dumps({"status": "PASS", "positive_replay": True, "negative_non_atomic_delta": True, "live_data_written": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
