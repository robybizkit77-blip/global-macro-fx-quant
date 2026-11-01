#!/usr/bin/env python3
"""Secondary Brent futures study quote, never canonical EIA Brent spot."""
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
SYMBOL = "BZ=F"
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
LANE = "BRENT.market_proxy"
MAX_CALENDAR_AGE_DAYS = 3
MAX_VINTAGE_EVENTS = 24


def _pct(a: float, b: float | None) -> float | None:
    if b is None or b <= 0:
        return None
    return round((a / b - 1.0) * 100.0, 4)


def fetch_source() -> dict:
    params = urllib.parse.urlencode({
        "range": "1mo", "interval": "1d", "includePrePost": "false",
        "events": "div,splits",
    })
    req = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 (GMFQ Brent market proxy; public secondary quote)",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"Brent chart HTTP {response.status}")
        return json.load(response)


def parse_chart(payload: dict, as_of: dt.date) -> tuple[list[tuple[str, float]], dict]:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Brent chart source error: {chart['error']}")
    results = chart.get("result") or []
    if len(results) != 1:
        raise ValueError("Brent chart must return exactly one contract")
    result = results[0]
    meta = result.get("meta") or {}
    if meta.get("symbol") != SYMBOL:
        raise ValueError("Brent futures source symbol drift")
    if meta.get("currency") != "USD":
        raise ValueError("Brent futures currency not independently verified as USD")
    if meta.get("instrumentType") != "FUTURE":
        raise ValueError("Brent source is not a futures contract")
    times = result.get("timestamp") or []
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    if not times or len(times) != len(closes):
        raise ValueError("Brent timestamps and close array must align")
    rows = []
    for ts, raw in zip(times, closes):
        if raw is None:
            continue
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Brent futures quote invalid")
        day = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date()
        if day > as_of:
            raise ValueError("Brent chart future-dated observation")
        rows.append((day.isoformat(), value))
    if len(rows) < 10:
        raise ValueError("Brent source must contain at least ten genuine closes")
    dates = [date for date, _ in rows]
    if dates != sorted(set(dates)):
        raise ValueError("Brent chart dates duplicated or nonmonotonic")
    age = (as_of - dt.date.fromisoformat(dates[-1])).days
    if age < 0 or age > MAX_CALENDAR_AGE_DAYS:
        raise ValueError(f"Brent futures source stale: date={dates[-1]}, days={age}")
    return rows, meta


def build_output(doc: dict, rows: list[tuple[str, float]], meta: dict,
                 fetched_at: dt.datetime) -> dict:
    if doc.get("schema") != "GMFQ_ESTIMATED_RESIDUAL_GAPS_V1":
        raise ValueError("Brent residual schema mismatch")
    if doc.get("official_lanes_untouched") is not True:
        raise ValueError("Brent must never modify official lanes")
    gov = doc.get("governance") or {}
    if any(gov.get(key) != "NONE" for key in (
            "core_score_effect", "bias_effect", "sizing_effect",
            "pair_engine_effect", "forward_logger_effect")) or (
            gov.get("backtest_eligible_as_official") is not False):
        raise ValueError("Brent futures cannot enter Core, risk trades or backtests")
    if meta.get("symbol") != SYMBOL or meta.get("currency") != "USD" or (
            meta.get("instrumentType") != "FUTURE"):
        raise ValueError("Brent output source identity mismatch")
    if len(rows) < 10:
        raise ValueError("Brent output requires a source history")
    day, price = rows[-1]
    old = (doc.get("lanes") or {}).get(LANE) or {}
    old_day = old.get("proxy_as_of")
    if old_day and day < old_day:
        raise ValueError("Brent source rollback: would overwrite a newer observation")
    # Repeated fetches of the same observation are idempotent. Do not make a
    # fake "fresh" print merely by updating fetched_at_utc.
    rounded = round(price, 4)
    d1 = _pct(price, rows[-2][1])
    d5 = _pct(price, rows[-6][1]) if len(rows) >= 6 else None
    same_snapshot = (
        day == old_day and old.get("value") == rounded
        and old.get("change_1d_pct") == d1
        and old.get("change_1w_pct") == d5
        and old.get("vendor_symbol") == SYMBOL
        and old.get("currency") == "USD"
        and old.get("instrument_type") == "FUTURE"
        and old.get("source_endpoint") == BASE_URL
    )
    if same_snapshot:
        return copy.deepcopy(doc)

    # This is a difference between two secondary-provider snapshots for the
    # same *market* date. Never call it a new trading day's return or an
    # official exchange correction. Preserve the prior as-of and fetch clock.
    revisions = copy.deepcopy(old.get("same_date_source_vintages", []))
    if not isinstance(revisions, list) or len(revisions) > MAX_VINTAGE_EVENTS:
        raise ValueError("Brent vintage audit schema/count mismatch")
    if old.get("proxy_as_of") == day and isinstance(old.get("value"), (float, int)):
        stamp = fetched_at.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        prior_stamp = old.get("fetched_at_utc")
        if prior_stamp and (not isinstance(prior_stamp, str)
                            or prior_stamp >= stamp):
            raise ValueError("Brent same-date source snapshot clock is not increasing")
        event = {
            "kind": "SECONDARY_SAME_DATE_SNAPSHOT_DIFFERENCE",
            "market_date": day,
            "prior_fetched_at_utc": prior_stamp,
            "new_fetched_at_utc": stamp,
            "prior_value": old["value"],
            "new_value": rounded,
            "prior_change_1d_pct": old.get("change_1d_pct"),
            "new_change_1d_pct": d1,
            "prior_change_1w_pct": old.get("change_1w_pct"),
            "new_change_1w_pct": d5,
            "interpretation": "Vendor snapshot changed; not a new market session or official settlement revision.",
        }
        revisions.append(event)
        revisions = revisions[-MAX_VINTAGE_EVENTS:]
    result = copy.deepcopy(doc)
    result["lanes"][LANE] = {
        "status": "MARKET_PROXY_ACTIVE_SECONDARY",
        "confidence": "B_FOR_DIRECTION_ONLY",
        "proxy_as_of": day,
        "value": rounded,
        "change_1d_pct": d1,
        "change_1w_pct": d5,
        "source": "Yahoo Finance public chart JSON · Brent Crude Oil Last Day Financial Futures (BZ=F)",
        "source_endpoint": BASE_URL,
        "vendor_symbol": SYMBOL,
        "currency": "USD",
        "exchange_name": meta.get("exchangeName"),
        "instrument_type": "FUTURE",
        "fetched_at_utc": fetched_at.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "official_canonical_untouched": True,
        "same_date_source_vintages": revisions,
        "vintage_audit_count": len(revisions),
        "interpretation": (
            "Secondary futures market proxy for live Brent level/direction only. "
            "It does not replace canonical EIA Brent spot, does not certify ICE "
            "history, and has no Core/backtest effect."
        ),
    }
    if any(result["lanes"][key] != value
           for key, value in doc["lanes"].items() if key != LANE):
        raise ValueError("Brent output changed another residual lane")
    if {key: value for key, value in result.items() if key != "lanes"} != {
            key: value for key, value in doc.items() if key != "lanes"}:
        raise ValueError("Brent output changed governance or metadata")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    as_of = dt.date.fromisoformat(args.as_of)
    rows, meta = parse_chart(fetch_source(), as_of)
    current = json.loads(OUT.read_text(encoding="utf-8"))
    new = build_output(current, rows, meta, dt.datetime.now(dt.timezone.utc))
    args.out.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lane = new["lanes"][LANE]
    print(json.dumps({
        "status": "PASS_SECONDARY_ONLY", "lane": LANE,
        "proxy_as_of": lane["proxy_as_of"], "value": lane["value"],
        "change_1d_pct": lane["change_1d_pct"],
        "change_1w_pct": lane["change_1w_pct"],
        "source": "Yahoo Finance secondary BZ=F futures",
        "official_canonical_untouched": True, "backtest_eligible_as_official": False,
        "observation_count": len(rows),
    }))


if __name__ == "__main__":
    main()
