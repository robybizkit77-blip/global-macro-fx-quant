#!/usr/bin/env python3
"""Read-only PIT replay of the historical CHF September 2026 CPI release."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "validation"))
from build_macro_candidate import apply_candidate

BEFORE = "a38d0b1eca8e39c3081bb4a706834c9ca41bfffc"
AFTER = "c22364703d9977be3a8faf73b46287d4bfd5dcea"
SERIES = "live_data/sections/MACRO_SERIES.json"
HEAT = "live_data/sections/MACRO_THERMOMETER_DATA.json"


def git_json(ref: str, path: str) -> dict:
    return json.loads(subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True))


def main() -> int:
    before_series, after_series = git_json(BEFORE, SERIES), git_json(AFTER, SERIES)
    before_heat, after_heat = git_json(BEFORE, HEAT), git_json(AFTER, HEAT)
    before_rows = {row.get("id"): row for row in before_series["CHF"]}
    after_rows = {row.get("id"): row for row in after_series["CHF"]}
    changed_ids = [key for key in sorted(set(before_rows) | set(after_rows)) if before_rows.get(key) != after_rows.get(key)]
    if changed_ids != ["CH_CPI_HEADLINE_YOY_history_value"]:
        raise SystemExit(f"Expected only CHF CPI to change, got {changed_ids}")

    row = after_rows[changed_ids[0]]
    heat = after_heat["currencies"]["CHF"]["inflation"]
    candidate = {
        "currency": "CHF",
        "dimension": "inflation",
        "macro_series_id": row["id"],
        "observation_date": row["last_date"],
        "value": row["last_value"],
        "source": heat["source"],
        "series_id": heat["series_id"],
        "frequency": heat["frequency"],
        "transformation": heat["transformation"],
    }
    if row.get("unit") is not None:
        candidate["unit"] = row["unit"]

    replay_series, replay_heat = copy.deepcopy(before_series), copy.deepcopy(before_heat)
    summary = apply_candidate(replay_series, replay_heat, candidate)
    out = {
        "status": "PASS" if replay_series == after_series and replay_heat == after_heat else "FAIL",
        "anchor_before": BEFORE,
        "anchor_after": AFTER,
        "macro_series_exact_match": replay_series == after_series,
        "heatmap_exact_match": replay_heat == after_heat,
        "candidate": candidate,
        "builder_summary": summary,
        "live_data_written": False,
        "engine_rules_changed": False,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
