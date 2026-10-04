"""Apply validated official USD Macro Series releases to the staging data section.

This updater deliberately changes MACRO_SERIES only.  In the current runtime,
blockDynamics reads this section, whereas deriveCurrencyState reads the macro
layer in D; D is therefore fingerprinted and left untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(".")
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
D_PATH = ROOT / "live_data" / "sections" / "D.json"
AUDIT_PATH = ROOT / "validation" / "USD_MACRO_CORE_REFRESH_AUDIT_2026-10-04.json"

# Observation period, not release date. Values supplied from already-validated
# official BLS Employment Situation and JOLTS releases.
UPDATES = {
    "US_PAYEMS_history_value": {"date": "2026-09-01", "value": 159044, "release": "BLS Employment Situation September 2026"},
    "US_UNRATE_history_value": {"date": "2026-09-01", "value": 4.2, "release": "BLS Employment Situation September 2026"},
    "US_AHE_TOTAL_PRIVATE_history_value": {"date": "2026-09", "value": 37.81, "release": "BLS Employment Situation September 2026"},
    "US_JTSJOL_history_value": {"date": "2026-08", "value": 7079, "release": "BLS JOLTS August 2026"},
    "US_JTSHIR_history_JTSHIR": {"date": "2026-08-01", "value": 3.3, "release": "BLS JOLTS August 2026"},
    "US_JTSQUR_history_JTSQUR": {"date": "2026-08-01", "value": 1.9, "release": "BLS JOLTS August 2026"},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_series(row: dict, spec: dict) -> dict:
    dates, values = list(row["dates"]), list(row["values"])
    if len(dates) != len(values):
        raise ValueError(f"unaligned date/value arrays: {row['id']}")
    old = {"date": dates[-1], "value": values[-1], "n": len(values)}
    if dates[-1] == spec["date"]:
        values[-1] = spec["value"]
        action = "replace_latest"
    elif spec["date"] > dates[-1]:
        dates.append(spec["date"])
        values.append(spec["value"])
        action = "append"
    else:
        raise ValueError(f"non-monotonic update for {row['id']}: {spec['date']} <= {dates[-1]}")
    row["dates"], row["values"] = dates, values
    row["last_date"], row["last_value"] = dates[-1], values[-1]
    return {"id": row["id"], "label": row.get("label"), "category": row.get("category"), "action": action, "old": old, "new": {"date": dates[-1], "value": values[-1], "n": len(values)}, "release": spec["release"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the refreshed staging MACRO_SERIES section")
    args = parser.parse_args()

    d_before = sha256(D_PATH)
    data = json.loads(SERIES_PATH.read_text(encoding="utf-8"))
    by_id = {row.get("id"): row for row in data.get("USD", [])}
    if set(UPDATES) - set(by_id):
        raise KeyError(f"missing USD series: {sorted(set(UPDATES) - set(by_id))}")
    changes = [update_series(by_id[series_id], spec) for series_id, spec in UPDATES.items()]
    d_after = sha256(D_PATH)
    report = {
        "schema": "GMFQ_USD_MACRO_CORE_REFRESH_V1",
        "created_at": "2026-10-04",
        "target": "staging-live-data-refresh-v1-2026-10-04",
        "write_requested": args.write,
        "updates": changes,
        "D_sha256_before": d_before,
        "D_sha256_after": d_after,
        "D_unchanged": d_before == d_after,
        "note": "MACRO_SERIES feeds blockDynamics; D is intentionally not modified because deriveCurrencyState reads D's macro layer.",
    }
    if args.write:
        SERIES_PATH.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["D_unchanged"]:
        raise SystemExit("D_CHANGED")


if __name__ == "__main__":
    main()
