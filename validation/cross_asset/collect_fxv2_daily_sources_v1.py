#!/usr/bin/env python3
"""Read-only market-source collector feeding only the FX Quant V2 research UI.

Inputs: public FRED graph CSV for SP500, NASDAQCOM, IG/HY OAS; official Cboe VIX CSV.
No core/FX/pair/payload mutation. No estimates, interpolation or stale-date promotion.
Source failures leave the last independently dated observation unchanged.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "site/fx-quant-v2/cross-asset-live-data.json"
SCHEMA = "GMFQ_FXV2_CROSS_ASSET_SOURCE_OVERLAY_V1"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
SOURCES = {
    "SP500": {"url": FRED_URL + "SP500", "kind": "INDEX", "max_days": 6,
              "source": "S&P Dow Jones Indices via FRED", "unit": "index"},
    "NASDAQCOM": {"url": FRED_URL + "NASDAQCOM", "kind": "INDEX", "max_days": 6,
                  "source": "Nasdaq, Inc. via FRED", "unit": "index"},
    "IG_OAS": {"url": FRED_URL + "BAMLC0A0CM", "kind": "CREDIT_OAS", "max_days": 7,
               "source": "ICE Data Indices via FRED", "unit": "percent"},
    "HY_OAS": {"url": FRED_URL + "BAMLH0A0HYM2", "kind": "CREDIT_OAS", "max_days": 7,
               "source": "ICE Data Indices via FRED", "unit": "percent"},
    "VIX": {"url": VIX_URL, "kind": "VOLATILITY_INDEX", "max_days": 6,
            "source": "Cboe Global Markets, VIX daily close", "unit": "index"},
}


def as_date(raw: str) -> dt.date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError("Unrecognized source date: " + repr(raw))


def parse_csv(source: str, payload: str, cutoff: dt.date) -> list[tuple[str, float]]:
    rows = csv.DictReader(io.StringIO(payload.lstrip("\ufeff")))
    if not rows.fieldnames:
        raise ValueError("Empty source CSV")
    names = {x.strip().upper(): x for x in rows.fieldnames}
    if source == "VIX":
        key_date, key_value = names.get("DATE"), names.get("CLOSE")
    else:
        key_date = names.get("OBSERVATION_DATE") or names.get("DATE")
        key_value = names.get(source) or names.get("VALUE")
        if key_value is None:
            wanted = {"IG_OAS": "BAMLC0A0CM", "HY_OAS": "BAMLH0A0HYM2"}
            key_value = names.get(wanted.get(source, source))
    if not key_date or not key_value:
        raise ValueError("Unexpected source CSV columns: " + str(rows.fieldnames))
    parsed: list[tuple[str, float]] = []
    seen: set[str] = set()
    for item in rows:
        raw_date = (item.get(key_date) or "").strip()
        raw_value = (item.get(key_value) or "").strip()
        if not raw_date or raw_value in ("", ".", "NA", "N/A"):
            continue
        day = as_date(raw_date)
        if day > cutoff:
            continue
        value = float(raw_value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Invalid non-positive market level")
        if source in ("SP500", "NASDAQCOM") and not (100 <= value <= 100000):
            raise ValueError("Index level out of accepted bounds")
        if source == "VIX" and not (5 <= value <= 150):
            raise ValueError("VIX level out of accepted bounds")
        if source in ("IG_OAS", "HY_OAS") and not (0.05 <= value <= 30):
            raise ValueError("ICE OAS percent out of accepted bounds")
        date = day.isoformat()
        if date in seen:
            raise ValueError("Duplicated source date: " + date)
        seen.add(date)
        parsed.append((date, round(value, 5)))
    if len(parsed) < 10 or parsed != sorted(parsed):
        raise ValueError("Insufficient or unordered historical observations")
    return parsed[-100:]


def validate_series(key: str, rows: list[tuple[str, float]], asof: dt.date,
                    old: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = SOURCES[key]
    last_date = dt.date.fromisoformat(rows[-1][0])
    age = (asof - last_date).days
    if age < 0 or age > spec["max_days"]:
        raise ValueError("Date outside source cadence: " + last_date.isoformat() + "; age=" + str(age))
    if old and old.get("date") and rows[-1][0] < old["date"]:
        raise ValueError("Source rollback vs stored stream " + key)
    today = rows[-1][1]
    previous = rows[-2][1]
    pct = 100 * (today / previous - 1)
    if key in ("SP500", "NASDAQCOM") and abs(pct) > 25:
        raise ValueError("Single close-to-close index move > 25%: source review required")
    if key == "VIX" and abs(pct) > 75:
        raise ValueError("Single close-to-close VIX move > 75%: source review required")
    obj = {
        "date": rows[-1][0],
        "previous_date": rows[-2][0],
        "value": today,
        "previous": previous,
        "change_1d_pct": round(pct, 4),
        "history": [[d, v] for d, v in rows],
        "quality": "PUBLISHED_SOURCE_RESEARCH_ONLY",
        "publisher": spec["source"],
        "source_url": spec["url"],
        "kind": spec["kind"],
        "unit": spec["unit"],
        "max_source_age_days": spec["max_days"],
        "source_age_calendar_days": age,
        "not_intraday": True,
        "no_core_or_backtest_effect": True,
    }
    return obj


def download(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (GMFQ FXV2 cross-asset dated sources, research-only)",
        "Accept": "text/csv,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=25) as res:
        if res.status != 200:
            raise ValueError("Unexpected source HTTP " + str(res.status))
        raw = res.read(1_600_001)
        if len(raw) > 1_600_000:
            raise ValueError("Unexpected source download size")
    return raw.decode("utf-8-sig", "strict")


def produce(asof: dt.date, previous: dict[str, Any],
            payloads: dict[str, str]) -> dict[str, Any]:
    if previous.get("schema") != SCHEMA:
        raise ValueError("Unexpected previous V2-only feed schema")
    streams = dict(previous.get("streams") or {})
    errors = {}
    accepted = []
    for key in SOURCES:
        try:
            if key not in payloads:
                raise ValueError("Source download unavailable")
            rows = parse_csv(key, payloads[key], asof)
            row = validate_series(key, rows, asof, streams.get(key))
            streams[key] = row
            accepted.append(key)
        except (ValueError, KeyError, TypeError) as exc:
            errors[key] = str(exc)
    if not accepted:
        raise ValueError("No independently validated fresh feed: " + str(errors))
    return {
        "schema": SCHEMA,
        "status": "FIVE_STREAMS_VERIFIED" if len(accepted) == 5 else "PARTIAL_SOURCE_SUCCESS",
        "collected_on": asof.isoformat(),
        "attempted_sources": list(SOURCES),
        "verified_on_attempt": accepted,
        "source_errors": errors,
        "streams": streams,
        "source_tiers": {
            "FRED": "Public disseminator of index and ICE OAS observations",
            "CBOE": "Official VIX closing-value CSV",
        },
        "source_dates_independent": True,
        "eligible_for_fx_core": False,
        "eligible_for_backtest": False,
        "contains_market_estimates": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date())
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--fixture-dir", type=Path)
    args = parser.parse_args()
    previous = json.loads(OUTPUT.read_text())
    payloads = {}
    errors = {}
    for name, cfg in SOURCES.items():
        try:
            payloads[name] = ((args.fixture_dir / (name + ".csv")).read_text()
                              if args.fixture_dir else download(cfg["url"]))
        except Exception as exc:
            errors[name] = str(exc)
    print(json.dumps({"source_download_errors": errors}, ensure_ascii=False))
    if not payloads:
        # Do not commit an empty feed or claim a successful data update.
        raise SystemExit("No feed downloaded; preserve original V2 source JSON")
    result = produce(args.as_of, previous, payloads)
    result["source_errors"].update(errors)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "verified": result["verified_on_attempt"],
                      "errors": result["source_errors"],
                      "dates": {k: v.get("date") for k, v in result["streams"].items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
