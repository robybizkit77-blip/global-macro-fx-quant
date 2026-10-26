#!/usr/bin/env python3
"""Historical public-source daily reference proxy, not an intraday event reaction.

Only ECM/ECB FX reference rates and independently dated U.S. Treasury history.
No network, unauthorized tick feeds, trading signals, model or production writes.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FX_PATH = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
RATES_PATH = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
OIS_PATH = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
REG_PATH = ROOT / "validation/event_market_evidence_registry_v1.json"
SCHEMA = "GMFQ_BLS_DAILY_REFERENCE_PROXY_SHADOW_V1"
EVENT_ID = "BLS_EMPLOYMENT_SITUATION_SEPT_2026"


def _day(raw):
    if not isinstance(raw, str):
        raise ValueError("ISO day string required")
    x = date.fromisoformat(raw)
    if x.isoformat() != raw:
        raise ValueError("non-canonical date")
    return x


def _positive(raw):
    return type(raw) in (int, float) and math.isfinite(raw) and raw > 0


def _series(records, cutoff):
    if not isinstance(records, list):
        raise ValueError("missing FX rows")
    seen, values = set(), {}
    last = None
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("malformed FX row")
        day = _day(row.get("Date"))
        if day in seen or last is not None and day <= last:
            raise ValueError("unordered/duplicate FX fixing day")
        seen.add(day)
        last = day
        val = row.get("USD")
        if not _positive(val):
            raise ValueError("invalid EURUSD fixing")
        if day <= cutoff:
            values[day] = float(val)
    return values


def _treasury_history(rates, event_day, cutoff):
    rates = rates.get("USD") if isinstance(rates, dict) else None
    if not isinstance(rates, dict) or rates.get("quality") != "FULL_CURRENT_OFFICIAL":
        return {"status": "SOURCE_QUALITY_NOT_ACCEPTED", "event_reaction_proof": False}
    series = rates.get("history2")
    if not isinstance(series, dict):
        return {"status": "NO_HISTORICAL_2Y", "event_reaction_proof": False}
    dates, vals = series.get("dates"), series.get("values")
    if not isinstance(dates, list) or not isinstance(vals, list) or len(dates) != len(vals) or not dates:
        return {"status": "INCONSISTENT_2Y_HISTORY", "event_reaction_proof": False}
    try:
        ordered = [_day(x) for x in dates]
        if any(a >= b for a, b in zip(ordered, ordered[1:])):
            raise ValueError("unordered")
        if any(not _positive(x) for x in vals):
            raise ValueError("nonpositive yield")
        if _day(rates.get("date")) < event_day:
            return {"status": "OUTDATED_2Y_SOURCE", "event_reaction_proof": False}
    except ValueError:
        return {"status": "INCONSISTENT_2Y_HISTORY", "event_reaction_proof": False}
    historic = {x: float(y) for x, y in zip(ordered, vals) if x <= cutoff}
    if event_day not in historic:
        return {"status": "EVENT_DAY_MISSING", "event_reaction_proof": False}
    prev = max((x for x in historic if x < event_day), default=None)
    lag = (event_day - prev).days if prev else None
    # Cannot imply an adjacent business-day rate move across missing official dates.
    matched = prev is not None and lag <= 3
    return {
        "status": "DAILY_2Y_REFERENCE_ONLY",
        "event_date": event_day.isoformat(),
        "event_date_yield_pct": historic[event_day],
        "previous_observation_date": prev.isoformat() if prev else None,
        "previous_observation_yield_pct": historic[prev] if prev else None,
        "previous_observation_calendar_gap_days": lag,
        "valid_adjacent_comparison": matched,
        "daily_2y_change_bp": round((historic[event_day] - historic[prev]) * 100, 3) if matched else None,
        "source": rates.get("source"),
        "event_reaction_proof": False,
        "method_note": "Treasury 2Y daily curve, not timestamped pre/post market prices",
    }


def _ois_historic_context(ois, event_day):
    usd = ((ois or {}).get("currencies") or {}).get("USD", {})
    if not isinstance(usd, dict):
        usd = {}
    try:
        as_of = _day(usd.get("as_of"))
    except (ValueError, TypeError):
        return {"status": "NO_EVENT_DATE_FUTURES_OIS_PROXY", "event_reaction_proof": False}
    # Only a real, separately archived observation around event day is relevant.
    # Do not backfill today's estimated 6M level into earlier market history.
    if abs((as_of - event_day).days) > 1:
        return {
            "status": "NOT_EVENT_DATE_ALIGNED",
            "available_as_of": as_of.isoformat(),
            "event_reaction_proof": False,
            "estimated_6m_event_repricing_bp": None,
        }
    return {
        "status": "DAILY_CONTEXT_NOT_EVENT_REPRICING",
        "available_as_of": as_of.isoformat(),
        "event_reaction_proof": False,
        "estimated_6m_event_repricing_bp": None,
    }


def build(event, fx, rates, ois, *, as_of):
    cutoff = _day(as_of)
    ev = event.get("event") if isinstance(event, dict) else None
    if not isinstance(ev, dict) or ev.get("event_id") != EVENT_ID:
        raise ValueError("pilot only accepts registered BLS September 2026 release")
    if ev.get("expected_scheduled_utc") != "2026-10-02T12:30:00Z":
        raise ValueError("unexpected scheduled release clock")
    event_day = _day(ev.get("embargo_calendar_date"))
    if cutoff < event_day:
        raise ValueError("as_of cannot precede scheduled event")
    if not isinstance(fx, dict) or fx.get("schema") != "GMFQ_ECB_G8_PRICE_HISTORY_V1" or fx.get("status") != "CURRENT_OFFICIAL_HISTORY" or fx.get("base") != "EUR":
        raise ValueError("official ECB FX history required")
    if fx.get("source_url") != "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml":
        raise ValueError("ECB provenance mismatch")
    if _day(fx.get("last_as_of")) < event_day:
        raise ValueError("ECB FX series older than event")
    values = _series(fx.get("rows"), cutoff)
    if event_day not in values:
        status, fixing = "NO_EVENT_DATE_ECB_FIXING", None
    else:
        previous = max((d for d in values if d < event_day), default=None)
        later = min((d for d in values if d > event_day), default=None)
        if previous is None or later is None or (later-event_day).days > 4:
            status, fixing = "INCOMPLETE_ADJACENT_ECB_FIXINGS", None
        else:
            before, onday, after = values[previous], values[event_day], values[later]
            status = "DAILY_REFERENCE_MOVEMENT_OBSERVED_NOT_INTRADAY"
            fixing = {
                "instrument": "EURUSD",
                "unit": "USD_PER_EUR",
                "previous_fixing_date": previous.isoformat(),
                "previous_fixing": before,
                "event_day_fixing_date": event_day.isoformat(),
                "event_day_fixing": onday,
                "next_fixing_date": later.isoformat(),
                "next_fixing": after,
                "previous_to_event_day_pips": round((onday-before)*10000, 3),
                "event_day_to_next_fixing_pips": round((after-onday)*10000, 3),
                "event_day_to_next_fixing_return_pct": round((after/onday-1)*100, 4),
                "post_fixing_calendar_gap_days": (later-event_day).days,
                "official_fixing_concertation_time_approx_local": "14:10 Europe/Frankfurt",
                "fixing_time_verified_for_individual_day": False,
                "event_window_proof": False,
                "source": fx["source"],
                "source_url": fx["source_url"],
            }
    return {
        "schema": SCHEMA,
        "event_id": EVENT_ID,
        "as_of": cutoff.isoformat(),
        "status": status,
        "estimated_intraday_reaction": None,
        "observed_daily_fx_reference": fixing,
        "daily_us_2y_reference": _treasury_history(rates, event_day, cutoff),
        "event_date_ois_futures": _ois_historic_context(ois, event_day),
        "economic_interpretation": "Observed ECB daily reference context only, not identified market response to BLS",
        "strength_of_attribution": "NOT_ESTABLISHED",
        "causal_attribution": "NOT_ESTABLISHED",
        "market_reaction": "NOT_CERTIFIED",
        "source_data_type": "OFFICIAL_DAILY_OBSERVATIONS_NOT_ESTIMATED_INTRADAY_QUOTES",
        "context_quality": "LIMITED_BY_DAILY_FREQUENCY_AND_OBSERVATION_CLOCK",
        "not_a_forecast_or_trading_signal": True,
        "eligible_for_score": False,
        "eligible_for_backtest": False,
        "safe_to_update_pair_theses": False,
        "safe_to_publish_live_data": False,
        "writes_live_data": False,
        "limitations": [
            "ECB reference fixing is set around 14:10 local and not a traded intraday event quote",
            "ECB day-to-next-fixing interval may contain a weekend and other news",
            "Treasury daily par yield is based on afternoon prices, not event-window tick yields",
            "OIS/futures levels at different dates cannot reconstruct event-day repricing",
            "An official scheduled embargo is not actual tick-time dissemination evidence",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        parser.error("output must be inside /tmp; research only")
    result = build(
        json.loads(REG_PATH.read_text(encoding="utf-8")),
        json.loads(FX_PATH.read_text(encoding="utf-8")),
        json.loads(RATES_PATH.read_text(encoding="utf-8")),
        json.loads(OIS_PATH.read_text(encoding="utf-8")),
        as_of=args.as_of,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
