#!/usr/bin/env python3
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("live_data/sections/ESTIMATED_RESIDUAL_GAPS.json")
SYMBOL = "BZ=F"
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((float(a) / float(b) - 1.0) * 100.0, 4)


def fetch_series():
    params = urllib.parse.urlencode({
        "range": "1mo",
        "interval": "1d",
        "includePrePost": "false",
        "events": "div,splits",
    })
    req = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 (GMFQ Brent market proxy; public secondary quote)",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Yahoo chart HTTP {resp.status}")
        payload = json.load(resp)

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError("Yahoo chart returned no result")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quotes.get("close") or []
    if len(timestamps) != len(closes):
        raise RuntimeError("Yahoo timestamp/close length mismatch")

    rows = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        value = float(close)
        if not math.isfinite(value) or value <= 0:
            continue
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
        rows.append((d, value))
    if len(rows) < 2:
        raise RuntimeError("Insufficient Brent observations")
    return rows, result.get("meta") or {}


def main():
    rows, meta = fetch_series()
    latest_date, latest = rows[-1]
    prev = rows[-2][1]
    week_base = rows[-6][1] if len(rows) >= 6 else None

    doc = json.loads(OUT.read_text(encoding="utf-8"))
    lane = doc["lanes"]["BRENT.market_proxy"]
    lane.update({
        "status": "MARKET_PROXY_ACTIVE_SECONDARY",
        "confidence": "B_FOR_DIRECTION_ONLY",
        "proxy_as_of": latest_date,
        "value": round(latest, 4),
        "change_1d_pct": _pct(latest, prev),
        "change_1w_pct": _pct(latest, week_base),
        "source": "Yahoo Finance public chart JSON · Brent Crude Oil Last Day Financial Futures (BZ=F)",
        "source_endpoint": BASE_URL,
        "vendor_symbol": SYMBOL,
        "currency": meta.get("currency") or "USD",
        "exchange_name": meta.get("exchangeName"),
        "instrument_type": meta.get("instrumentType") or "FUTURE",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "official_canonical_untouched": True,
        "interpretation": "Secondary futures market proxy for live Brent level/direction only. It does not replace canonical EIA Brent spot, does not certify ICE history, and has no Core/backtest effect."
    })
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "lane": "BRENT.market_proxy",
        "proxy_status": lane["status"],
        "proxy_as_of": latest_date,
        "value": lane["value"],
        "change_1d_pct": lane["change_1d_pct"],
        "change_1w_pct": lane["change_1w_pct"],
        "observations": len(rows),
        "official_canonical_untouched": True,
    }))


if __name__ == "__main__":
    main()
