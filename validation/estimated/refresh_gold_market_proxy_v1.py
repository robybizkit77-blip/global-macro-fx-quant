#!/usr/bin/env python3
"""Informational COMEX gold futures market proxy; never a canonical Gold spot price."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("live_data/sections/ESTIMATED_RESIDUAL_GAPS.json")
SYMBOL = "GC=F"
SOURCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
LANE = "GOLD.market_proxy"
MAX_CALENDAR_AGE_DAYS = 3


def percent_change(current: float, previous: float | None) -> float | None:
    if previous is None or previous <= 0:
        return None
    return round((current / previous - 1) * 100, 4)


def fetch_source() -> dict:
    query = urllib.parse.urlencode({
        "range": "1mo", "interval": "1d", "includePrePost": "false",
        "events": "div,splits",
    })
    req = urllib.request.Request(
        SOURCE_URL + "?" + query,
        headers={
            "User-Agent": "Mozilla/5.0 (GMFQ Gold futures informational secondary feed)",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"Yahoo Gold chart HTTP {response.status}")
        return json.load(response)


def parse_chart(source: dict, as_of: dt.date) -> tuple[list[tuple[str, float]], dict]:
    chart = source.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Yahoo chart rejected Gold feed: {chart['error']}")
    results = chart.get("result") or []
    if len(results) != 1:
        raise ValueError("Gold futures chart must contain exactly one result")
    result = results[0]
    meta = result.get("meta") or {}
    if meta.get("symbol") != SYMBOL:
        raise ValueError("Gold futures source symbol drift")
    if meta.get("currency") != "USD":
        raise ValueError("Gold futures quote currency is not USD")
    if meta.get("instrumentType") != "FUTURE":
        raise ValueError("Gold source is not a futures contract")
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    if not timestamps or len(timestamps) != len(closes):
        raise ValueError("Gold chart has missing/misaligned timestamps")
    rows = []
    for ts, raw in zip(timestamps, closes):
        if raw is None:
            continue
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Gold chart has invalid quote")
        day = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date()
        if day > as_of:
            raise ValueError("Gold chart contains future-dated observation")
        rows.append((day.isoformat(), value))
    if len(rows) < 10:
        raise ValueError("Gold futures proxy needs at least ten valid observations")
    dates = [day for day, _ in rows]
    if dates != sorted(set(dates)):
        raise ValueError("Gold chart dates duplicated or nonmonotone")
    age = (as_of - dt.date.fromisoformat(dates[-1])).days
    if age < 0 or age > MAX_CALENDAR_AGE_DAYS:
        raise ValueError(f"Gold futures source too old: {dates[-1]}, age={age}")
    return rows, meta


def build_output(doc: dict, rows: list[tuple[str, float]], meta: dict,
                 fetched_at: dt.datetime) -> dict:
    if doc.get("schema") != "GMFQ_ESTIMATED_RESIDUAL_GAPS_V1":
        raise ValueError("Residual gaps schema drift")
    if doc.get("official_lanes_untouched") is not True:
        raise ValueError("Official lane mutation policy not certified")
    governance = doc.get("governance") or {}
    for key in ("core_score_effect", "bias_effect", "sizing_effect",
                "pair_engine_effect", "forward_logger_effect"):
        if governance.get(key) != "NONE":
            raise ValueError(f"Gold proxy cannot affect {key}")
    if governance.get("backtest_eligible_as_official") is not False:
        raise ValueError("Gold proxy cannot enter official backtests")
    if not rows:
        raise ValueError("Empty Gold source")
    result = copy.deepcopy(doc)
    day, price = rows[-1]
    prev = rows[-2][1] if len(rows) > 1 else None
    weekly = rows[-6][1] if len(rows) >= 6 else None
    result["lanes"][LANE] = {
        "status": "MARKET_PROXY_ACTIVE_SECONDARY",
        "confidence": "B_FOR_DIRECTION_ONLY",
        "proxy_as_of": day,
        "value": round(price, 4),
        "change_1d_pct": percent_change(price, prev),
        "change_1w_pct": percent_change(price, weekly),
        "source": "Yahoo Finance public chart JSON · COMEX Gold Futures (GC=F)",
        "source_endpoint": SOURCE_URL,
        "vendor_symbol": SYMBOL,
        "currency": "USD",
        "unit": "USD per troy ounce",
        "exchange_name": meta.get("exchangeName"),
        "instrument_type": "FUTURE",
        "observation_count_1mo": len(rows),
        "fetched_at_utc": fetched_at.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "official_canonical_untouched": True,
        "interpretation": (
            "Informational delayed futures market proxy, not LBMA Gold Price, "
            "not physical spot, not certified exchange settlement, and not "
            "eligible for canonical Gold history, core, signals, sizing or official backtests."
        ),
    }
    if any(result["lanes"][k] != v for k, v in doc["lanes"].items() if k != LANE):
        raise ValueError("Gold proxy modified another residual lane")
    if {k: v for k, v in result.items() if k != "lanes"} != {
            k: v for k, v in doc.items() if k != "lanes"}:
        raise ValueError("Gold proxy modified residual metadata or governance")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    as_of = dt.date.fromisoformat(args.as_of)
    source = fetch_source()
    rows, meta = parse_chart(source, as_of)
    baseline = json.loads(OUT.read_text(encoding="utf-8"))
    new = build_output(baseline, rows, meta, dt.datetime.now(dt.timezone.utc))
    args.out.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lane = new["lanes"][LANE]
    print(json.dumps({
        "status": "PASS_SECONDARY_ONLY",
        "lane": LANE, "source": SYMBOL, "as_of": lane["proxy_as_of"],
        "value": lane["value"], "observations": len(rows),
        "official_canonical_untouched": True, "output_path": str(args.out),
        "settlement_certified": False, "market_proxy_only": True,
    }))


if __name__ == "__main__":
    main()
