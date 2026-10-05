#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "validation"))
from build_macro_candidate import apply_candidate  # noqa: E402

BEFORE = "0467d03f500dbaaf640bc653466457c5962e88b5"
AFTER = "f1bb0f6256277f092f0d540a9c34d63dc7ddbd60"
SERIES_PATH = "live_data/sections/MACRO_SERIES.json"
HEATMAP_PATH = "live_data/sections/MACRO_THERMOMETER_DATA.json"


def git_json(ref: str, path: str):
    raw = subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
    return json.loads(raw)


def changed_ids(before_rows, after_rows):
    b = {r.get("id"): r for r in before_rows}
    a = {r.get("id"): r for r in after_rows}
    return [k for k in sorted(set(b) | set(a)) if b.get(k) != a.get(k)]


def field_diffs(actual: dict, expected: dict):
    out = {}
    for key in sorted(set(actual) | set(expected)):
        if actual.get(key) != expected.get(key):
            av = actual.get(key)
            ev = expected.get(key)
            if key == "history" and isinstance(av, list) and isinstance(ev, list):
                out[key] = {
                    "actual_n": len(av),
                    "expected_n": len(ev),
                    "actual_tail": av[-6:],
                    "expected_tail": ev[-6:],
                }
            else:
                out[key] = {"actual": av, "expected": ev}
    return out


def main() -> int:
    before_series = git_json(BEFORE, SERIES_PATH)
    after_series = git_json(AFTER, SERIES_PATH)
    before_heat = git_json(BEFORE, HEATMAP_PATH)
    after_heat = git_json(AFTER, HEATMAP_PATH)

    ids = changed_ids(before_series["JPY"], after_series["JPY"])
    if len(ids) != 1:
        raise SystemExit(f"Expected exactly one changed JPY macro series, got {ids}")
    sid = ids[0]
    after_row = next(r for r in after_series["JPY"] if r.get("id") == sid)
    h_before = before_heat["currencies"]["JPY"]["labour"]
    h_after = after_heat["currencies"]["JPY"]["labour"]

    candidate = {
        "currency": "JPY",
        "dimension": "labour",
        "macro_series_id": sid,
        "observation_date": after_row["last_date"],
        "value": after_row["last_value"],
        "source": h_after["source"],
        "series_id": h_after["series_id"],
        "frequency": h_after["frequency"],
        "transformation": h_after["transformation"],
    }
    if after_row.get("unit") is not None:
        candidate["unit"] = after_row.get("unit")

    replay_series = copy.deepcopy(before_series)
    replay_heat = copy.deepcopy(before_heat)
    summary = apply_candidate(replay_series, replay_heat, candidate)

    series_equal = replay_series == after_series
    heat_equal = replay_heat == after_heat
    h_actual = replay_heat["currencies"]["JPY"]["labour"]

    result = {
        "status": "PASS" if series_equal and heat_equal else "FAIL",
        "before": BEFORE,
        "after": AFTER,
        "changed_jpy_series_id": sid,
        "candidate": candidate,
        "builder_summary": summary,
        "macro_series_exact_match": series_equal,
        "heatmap_exact_match": heat_equal,
        "engine_rules_changed": False,
        "live_data_written": False,
        "jpy_labour_context": {
            "before_tail": h_before.get("history", [])[-8:],
            "after_tail": h_after.get("history", [])[-8:],
            "replay_tail": h_actual.get("history", [])[-8:],
            "before_direction": h_before.get("direction"),
            "before_acceleration": h_before.get("acceleration"),
            "after_direction": h_after.get("direction"),
            "after_acceleration": h_after.get("acceleration"),
            "replay_direction": h_actual.get("direction"),
            "replay_acceleration": h_actual.get("acceleration"),
        },
    }

    if not series_equal:
        result["series_diagnostics"] = {
            "jpy_target_equal": next(r for r in replay_series["JPY"] if r.get("id") == sid) == after_row,
            "changed_currency_keys_vs_after": [c for c in replay_series if replay_series.get(c) != after_series.get(c)],
        }
    if not heat_equal:
        result["heatmap_diagnostics"] = {
            "jpy_labour_equal": h_actual == h_after,
            "jpy_labour_field_diffs": field_diffs(h_actual, h_after),
            "jpy_as_of_detail_equal": replay_heat["currencies"]["JPY"].get("as_of_detail") == after_heat["currencies"]["JPY"].get("as_of_detail"),
            "changed_currency_keys_vs_after": [c for c in replay_heat["currencies"] if replay_heat["currencies"].get(c) != after_heat["currencies"].get(c)],
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
