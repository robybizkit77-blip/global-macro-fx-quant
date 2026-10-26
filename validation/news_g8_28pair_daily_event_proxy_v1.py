#!/usr/bin/env python3
"""28-pair G8 daily ECB fixing context around a nominated date: research only.

A comparison between *daily reference fixings* is not an intraday response,
a counterfactual event impact, or a trading signal. Nothing is estimated here.
This script never downloads vendor data or writes live_data/site/models.
"""
from __future__ import annotations

import argparse
from datetime import date
from itertools import combinations
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
G8 = ("EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
SCHEMA = "GMFQ_G8_28PAIR_DAILY_EVENT_CONTEXT_RESEARCH_V1"
SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"


def _day(value):
    if not isinstance(value, str):
        raise ValueError("ISO date is required")
    d = date.fromisoformat(value)
    if d.isoformat() != value:
        raise ValueError("noncanonical ISO date")
    return d


def _quote(value):
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("invalid ECB reference rate")
    return float(value)


def _rows(fx, cutoff):
    if (not isinstance(fx, dict)
        or fx.get("schema") != "GMFQ_ECB_G8_PRICE_HISTORY_V1"
        or fx.get("status") != "CURRENT_OFFICIAL_HISTORY"
        or fx.get("source_url") != SOURCE_URL
        or fx.get("base") != "EUR"
        or set(fx.get("currencies", ())) != set(G8)):
        raise ValueError("invalid official ECB source/schema")
    raw = fx.get("rows")
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing reference history")
    rows, last = {}, None
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("malformed fixing row")
        day = _day(item.get("Date"))
        if last is not None and day <= last:
            raise ValueError("unordered or duplicated ECB fixing dates")
        last = day
        if item.get("EUR") != 1 and item.get("EUR") != 1.0:
            raise ValueError("EUR base of ECB fixing is not 1")
        # Validate values even in rows outside cutoff: data are official or missing,
        # never synthetic placeholders. One missing cross does not erase the rest.
        vals = {ccy: _quote(item.get(ccy)) for ccy in G8}
        if day <= cutoff:
            rows[day] = vals
    return rows


def _pair_rate(row, base, quote):
    x, y = row.get(base), row.get(quote)
    return None if x is None or y is None else y / x


def build(fx, *, event_date, as_of, event_label="EVENT_DATE_REFERENCE_ONLY"):
    event, cutoff = _day(event_date), _day(as_of)
    if cutoff < event:
        raise ValueError("as_of cannot precede event date")
    if not isinstance(event_label, str) or not event_label or len(event_label) > 120:
        raise ValueError("event label required")
    values = _rows(fx, cutoff)
    prev = max((d for d in values if d < event), default=None)
    later = min((d for d in values if d > event), default=None)
    available = event in values and prev is not None and later is not None
    gap_pre = (event - prev).days if prev else None
    gap_post = (later - event).days if later else None
    near = available and gap_pre <= 4 and gap_post <= 4
    result = []
    for base, quote in combinations(G8, 2):
        name = base + quote
        item = {
            "pair": name, "base_ccy": base, "quote_ccy": quote,
            "status": "NO_EVENT_DAY_FIXING" if event not in values else
                      "WAITING_ADJACENT_FIXINGS" if not available else
                      "GAP_TOO_LARGE" if not near else "MISSING_CURRENCY_FIXING",
            "observed_daily_reference_only": True,
            "event_window_proof": False,
            "intraday_reaction_pips": None,
            "estimated_event_impact_pips": None,
            "causal_attribution": "NOT_ESTABLISHED",
        }
        if near:
            p = _pair_rate(values[prev], base, quote)
            e = _pair_rate(values[event], base, quote)
            n = _pair_rate(values[later], base, quote)
            if p is not None and e is not None and n is not None:
                pip_size = 0.01 if quote == "JPY" else 0.0001
                item.update({
                    "status": "DAILY_REFERENCE_PROXY_OBSERVED",
                    "quote_unit": f"{quote}_PER_{base}",
                    "pip_size": pip_size,
                    "previous_fixing": round(p, 9),
                    "event_day_fixing": round(e, 9),
                    "next_fixing": round(n, 9),
                    "previous_to_event_fixing_pips": round((e-p)/pip_size, 3),
                    "event_to_next_fixing_pips": round((n-e)/pip_size, 3),
                    "event_to_next_return_pct": round((n/e-1)*100, 5),
                    "interpolation_used": False,
                })
        result.append(item)
    count = sum(x["status"] == "DAILY_REFERENCE_PROXY_OBSERVED" for x in result)
    return {
        "schema": SCHEMA, "event_label": event_label, "event_date": event.isoformat(),
        "as_of": cutoff.isoformat(),
        "status": "DAILY_REFERENCE_CONTEXT_AVAILABLE" if count else "NO_COMPARABLE_DAILY_REFERENCE_WINDOW",
        "source": "ECB euro foreign exchange reference rates",
        "source_url": SOURCE_URL,
        "pair_count": 28,
        "observed_pair_count": count,
        "missing_pair_count": 28 - count,
        "previous_fixing_date": prev.isoformat() if prev else None,
        "event_day_fixing_date": event.isoformat() if event in values else None,
        "next_fixing_date": later.isoformat() if later else None,
        "previous_calendar_gap_days": gap_pre,
        "next_calendar_gap_days": gap_post,
        "cross_method": "ECB_EUR_BASE_REFERENCE_CROSS_RATIO_QUOTE_OVER_BASE",
        "daily_reference_not_market_intraday": True,
        "date_filter_only_not_historical_pit_vintage_certification": True,
        "event_causality": "NOT_ESTABLISHED",
        "estimated_intraday_reaction": None,
        "event_impact_score": None,
        "eligible_for_live_signals": False,
        "eligible_for_backtest": False,
        "eligible_for_pair_rank_change": False,
        "writes_live_data": False,
        "limitations": [
            "ECB fixing dates do not timestamp the market price exactly around a release",
            "Previous, event-day and next-day fixings may straddle other news/weekends",
            "The supplied ECB history has observation dates, not certified historical PIT publication vintages",
            "Cross rates are arithmetic transformations of official EUR-base fixings",
        ],
        "pairs": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-date", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--event-label", default="EVENT_DATE_REFERENCE_ONLY")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        parser.error("research receipt output only under /tmp")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    receipt = build(data, event_date=args.event_date, as_of=args.as_of,
                    event_label=args.event_label)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"status":receipt["status"],"date":receipt["event_date"],
                      "observed":receipt["observed_pair_count"],"total":28}))


if __name__ == "__main__":
    main()
