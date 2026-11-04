#!/usr/bin/env python3
"""Isolated automatic AUD F2 government yield research for FX Quant V2.

Reads the RBA's public weekly F2 release; same-row 2Y/10Y only.
Does NOT modify NATIVE_RATES_DATA, FX signals, official OIS or backtests.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "site/fx-quant-v2/aud-rba-f2-research.json"
CANONICAL = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
URL = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
SCHEMA = "GMFQ_FXV2_AUD_RBA_F2_RESEARCH_V1"
SERIES_2Y = "FCMYGBAG2D"
SERIES_10Y = "FCMYGBAG10D"
SYDNEY = ZoneInfo("Australia/Sydney")

def demand(condition, reason):
    if not condition:
        raise ValueError("FXV2_AUD_F2_GUARD: " + reason)

def parse_f2(raw: bytes, today: dt.date) -> dict:
    demand(len(raw) > 250, "CSV unexpectedly short")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    demand(len(rows) > 12, "RBA F2 lacks data rows")
    ids = rows[10]
    demand(ids and ids[0].strip() == "Series ID", "official series ID header absent")
    demand(SERIES_2Y in ids and SERIES_10Y in ids, "required official series absent")
    i2, i10 = ids.index(SERIES_2Y), ids.index(SERIES_10Y)
    for i, ten in ((i2, "2 year"), (i10, "10 year")):
        demand(ten in rows[1][i].lower(), f"{ten} semantic header mismatch")
        demand(rows[3][i].strip() == "Daily", "RBA F2 frequency changed")
        demand(rows[8][i].strip() == "RBA", "RBA authority field changed")
    p2 = dt.datetime.strptime(rows[9][i2].strip(), "%d-%b-%Y").date()
    p10 = dt.datetime.strptime(rows[9][i10].strip(), "%d-%b-%Y").date()
    demand(p2 == p10 and p2 <= today, "source publication future or inconsistent")
    observations = []
    for row in rows[11:]:
        if len(row) <= max(i2, i10):
            continue
        if not row[0].strip() or not row[i2].strip() or not row[i10].strip():
            continue
        try:
            day = dt.datetime.strptime(row[0].strip(), "%d-%b-%Y").date()
            y2, y10 = float(row[i2]), float(row[i10])
        except ValueError:
            continue
        demand(all(math.isfinite(x) and -5 < x < 25 for x in (y2,y10)), "implausible yield")
        demand(day <= p2, "future observation relative to file publication")
        observations.append((day, y2, y10))
    demand(len(observations) >= 2, "need at least two same-row observations")
    observations.sort(key=lambda r: r[0])
    demand(len({x[0] for x in observations}) == len(observations), "duplicate observation date")
    current, prior = observations[-1], observations[-2]
    demand(current[0] <= today, "future last observation")
    return {
        "as_of": current[0].isoformat(),
        "2Y": current[1], "10Y": current[2],
        "curve_bp": round((current[2]-current[1])*100, 2),
        "publication_date": p2.isoformat(),
        "previous_same_series_as_of": prior[0].isoformat(),
        "change_2y_bp": round((current[1]-prior[1])*100, 2),
        "change_10y_bp": round((current[2]-prior[2])*100, 2),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }

def next_friday(today: dt.date) -> dt.date:
    # Planning context only, not a promise of publication or a market observation.
    return today + dt.timedelta(days=(4-today.weekday()) % 7)

def build(observation: dict, canonical: dict, previous: dict | None, today: dt.date) -> dict:
    aud = canonical["AUD"]
    old_date = dt.date.fromisoformat(aud["date"])
    obs_date = dt.date.fromisoformat(observation["as_of"])
    pub_date = dt.date.fromisoformat(observation["publication_date"])
    demand(obs_date >= old_date and obs_date <= pub_date <= today,
           "latest official F2 observation older than canonical or future")
    demand((today-obs_date).days <= 14, "F2 observation outside weekly source-age window")
    if previous and previous.get("source_download_verified") is True:
        demand(obs_date >= dt.date.fromisoformat(previous["as_of"]),
               "official source rollback compared to last approved V2 research")
        demand(pub_date >= dt.date.fromisoformat(previous["publication_date"]),
               "RBA F2 publication date rolled backwards")
    for k in ("2Y", "10Y"):
        demand(math.isfinite(observation[k]) and -5 < observation[k] < 25, f"invalid {k}")
    demand(abs(round((observation["10Y"]-observation["2Y"])*100,2)-
               observation["curve_bp"]) < 0.02, "curve arithmetic inconsistent")
    return {
        "schema": SCHEMA, "currency": "AUD", "status": "OFFICIAL_F2_CSV_FETCHED_RESEARCH_ONLY",
        "as_of": observation["as_of"], "2Y": observation["2Y"],
        "10Y": observation["10Y"], "curve_bp": observation["curve_bp"],
        "source_download_verified": True, "publication_date": observation["publication_date"],
        "previous_same_series_as_of": observation["previous_same_series_as_of"],
        "change_2y_bp": observation["change_2y_bp"],
        "change_10y_bp": observation["change_10y_bp"],
        "source_sha256": observation["source_sha256"],
        "source": "Reserve Bank of Australia · F2 Capital Market Yields – Government Bonds – Daily",
        "source_url": URL, "series_2Y": SERIES_2Y, "series_10Y": SERIES_10Y,
        "same_date_same_source": True,
        "cadence": "WEEKLY_FRIDAY_14_00_AUSTRALIA_SYDNEY__THROUGH_TWO_BUSINESS_DAYS_EARLIER",
        "next_regular_release_friday_sydney": next_friday(today).isoformat(),
        "next_release_is_schedule_not_confirmed": True,
        "research_only": True, "canonical_government_rates_untouched": True,
        "eligible_for_core": False, "eligible_for_fx_pair_engine": False,
        "eligible_for_backtests": False,
        "note": "Published F2 is weekly although daily observations are listed. This is an independent V2 research reading; never retimestamp last observation, overwrite Core, or call futures an observed government yield."
    }

def fetch() -> bytes:
    request = Request(URL, headers={
        "User-Agent": "global-macro-fx-quant-AUD-F2-research/1.0",
        "Accept": "text/csv,*/*",
    })
    with urlopen(request, timeout=45) as response:
        demand(response.status == 200, f"F2 HTTP {response.status}")
        return response.read()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=TARGET)
    ap.add_argument("--as-of", type=dt.date.fromisoformat,
                    default=dt.datetime.now(SYDNEY).date())
    ap.add_argument("--input", type=Path, help="offline test fixture (never used in production workflow)")
    args = ap.parse_args()
    prior = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else None
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
    info = parse_f2(args.input.read_bytes() if args.input else fetch(), args.as_of)
    report = build(info, canonical, prior, args.as_of)
    # Avoid synthetic new timestamps and commits with no changed market observation.
    if prior and prior.get("source_download_verified") is True and all(
        report.get(k) == prior.get(k) for k in
        ("as_of", "publication_date", "2Y", "10Y", "source_sha256")
    ):
        print("FXV2_AUD_F2_UNCHANGED_OBSERVATION; no synthetic clock refresh")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("FXV2_AUD_F2_RESEARCH_UPDATED", json.dumps({
        "as_of": report["as_of"], "publication_date": report["publication_date"],
        "official_core_changed": False, "source_verified": True
    }))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
