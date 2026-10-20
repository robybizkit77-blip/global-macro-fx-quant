#!/usr/bin/env python3
"""Fail closed on known GBP LFS rolling-period first-vintage drift.

Runs *before* any GBP.labour adapter or price/score write. Unlike a full
backtest PIT replay, only the 2026 June/July/August period-specific ONS
first-release anchors have been independently checked. No rewrites here.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from validation.macro.rebase_readiness_v1 import ROOT

CONTRACT = "validation/macro/GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_2026-10-20.json"
SERIES = "live_data/sections/MACRO_SERIES.json"
HEAT = "live_data/sections/MACRO_THERMOMETER_DATA.json"
EXPECTED = {"2026-06": 4.9, "2026-07": 4.9, "2026-08": 4.7}


def ensure(ok, why):
    if not ok:
        raise ValueError("GBP_LFS_TEMPORAL_GUARD_FAIL_CLOSED: " + why)


def build(root=ROOT, asof=date(2026, 10, 20), *, contract=None, series=None, heat=None):
    root = Path(root)
    contract = contract or json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    series = series or json.loads((root / SERIES).read_text(encoding="utf-8"))
    heat = heat or json.loads((root / HEAT).read_text(encoding="utf-8"))
    ensure(contract.get("schema") == "GMFQ_GBP_MGSX_ROLLING_WINDOW_FIRST_RELEASE_MAP_V1" and
           contract.get("storage_contract") == "THREE_MONTH_LFS_WINDOW_END_MONTH" and
           contract.get("source_ons_month_label") == "CENTER_MONTH_OF_THREE_MONTH_WINDOW" and
           contract.get("claim_full_historical_vintage_certified") is False,
           "source crosswalk contract changed")
    anchors = contract.get("official_periods")
    ensure(isinstance(anchors, list) and len(anchors) == 3,
           "exact three latest official rolling periods required")
    mapped = {}
    for row in anchors:
        end, start, center = (row.get(k) for k in (
            "canonical_end_month", "window_start_month", "source_center_month"))
        ensure(isinstance(end, str) and isinstance(start, str) and isinstance(center, str),
               "incomplete rolling-window identity")
        from validation.sources.gbp_ons_core import uk_lfs_rolling_window
        computed = uk_lfs_rolling_window(center + "-01")
        ensure((computed["canonical_end_month"][:7],computed["window_start_month"][:7]) ==
               (end,start), "ONS center-to-end month translation drift")
        ensure(end not in mapped and end in EXPECTED and
               type(row.get("unemployment_pct")) in (float,int) and
               row["unemployment_pct"] == EXPECTED[end], "period/value official anchor changed")
        rd = date.fromisoformat(row["release_date"])
        ensure(rd <= asof and rd >= date.fromisoformat(end+"-01"),
               "future/early first release")
        url = urlparse(str(row.get("source_url", "")))
        ensure(url.scheme == "https" and url.hostname in ("ons.gov.uk","www.ons.gov.uk"),
               "official domain missing")
        mapped[end] = row
    ensure(set(mapped) == set(EXPECTED), "exact period anchors lost")
    matches = [r for r in series.get("GBP", []) if r.get("id") == "UK_UNEMP_RATE_history_value"]
    ensure(len(matches) == 1, "unique MGSX canonical series missing")
    times, values = matches[0].get("dates"), matches[0].get("values")
    ensure(isinstance(times,list) and isinstance(values,list) and
           len(times)>=3 and len(times)==len(values), "canonical source history incomplete")
    dates = [str(d)[:7] for d in times]
    ensure(len(dates)==len(set(dates)) and dates==sorted(dates),
           "duplicate/unsorted original LFS dates")
    present = dict(zip(dates, values))
    changes = []
    for m, official in EXPECTED.items():
        current = present.get(m)
        if current is None:
            changes.append({"month":m,"action":"MISSING_FIRST_RELEASE_WINDOW","official":official,"current":None})
        elif type(current) not in (int,float) or not math.isfinite(current) or not math.isclose(current, official, abs_tol=1e-12,rel_tol=0):
            changes.append({"month":m,"action":"VINTAGE_OR_PERIOD_VALUE_MISMATCH","official":official,"current":current})
    first_release_repair_required = bool(changes)
    latest_asof = heat.get("currencies",{}).get("GBP",{}).get("labour",{}).get("as_of")
    if str(latest_asof)[:7] != dates[-1]:
        changes.append({"action":"HEATMAP_OBSERVATION_PERIOD_MISMATCH",
                        "canonical_latest":dates[-1],"heatmap_asof":latest_asof})
    hold = first_release_repair_required or len(changes)>0
    return {
        "schema":"GMFQ_GBP_ONS_MGSX_TEMPORAL_GUARD_RECEIPT_V1",
        "status":"HOLD_UNTIL_EXPLICIT_PERIOD_VINTAGE_REPAIR" if hold else "ALLOW_GBP_LABOUR_SOURCE_REFRESH",
        "safe_to_persist_gbp_labour":not hold,
        "canonical_source_latest_period":dates[-1],
        "heatmap_asof":latest_asof,
        "official_periods_checked":len(EXPECTED),
        "issues":changes,
        "historical_rebase_approved":False,
        "structural_fx_label_rebase_approved":False,
        "manual_repair_requires":"July 2026 must preserve May-July first release 4.9; August 2026 must preserve June-August first release 4.7. Recompute thermometer with a full independent atomic PIT validation before any write.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--asof",default=date.today().isoformat())
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    result=build(args.repo_root, date.fromisoformat(args.asof))
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(result["status"])
    print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    main()
