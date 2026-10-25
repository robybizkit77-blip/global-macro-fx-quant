#!/usr/bin/env python3
"""Fail-closed event/market proof gate for official News Pulse headlines.

A publisher RSS timestamp may be a disclosure timestamp, not necessarily when
trading received information. Daily 2Y yields and exchange/OIS repricing never
establish a news-specific intraday reaction. We may show dated daily *context*,
but cannot promote it to post-announcement evidence.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
import math

FX_G8 = frozenset({"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
OIS_OFFICIAL = ("GREEN_OFFICIAL", "OFFICIAL_CERTIFIED")
OIS_ESTIMATED = ("GREEN_ESTIMATED", "ESTIMATED_INFORMATIONAL")


def parse_day(s):
    try:
        d = date.fromisoformat(s) if type(s) is str else None
        return d
    except ValueError:
        return None


def finite(x):
    return type(x) in (float, int) and math.isfinite(x)


def relation(observed, event_day):
    if observed < event_day:
        return "PRIOR_CALENDAR_DATE"
    if observed > event_day:
        return "LATER_CALENDAR_DATE"
    return "SAME_CALENDAR_DATE_DAILY_ONLY"


def daily_ois(ccy, event_day, ois):
    r = (ois.get("currencies") or {}).get(ccy, {})
    if not isinstance(r, dict):
        r = {}
    as_of = parse_day(r.get("as_of"))
    source = r.get("source")
    status = (r.get("operational_status"), r.get("quality"))
    rate6 = ((r.get("horizons") or {}).get("6m") or {}).get("rate")
    if status not in (OIS_OFFICIAL, OIS_ESTIMATED) or not as_of or (
        not isinstance(source, str) or not source.strip()
    ) or not finite(rate6):
        return {"status": "NOT_VALIDATED_DAILY_CONTEXT"}
    instrument = "FUTURES_IMPLIED" if "futures" in source.lower() else (
        "OIS_ESTIMATED" if status == OIS_ESTIMATED else "OIS_OBSERVED"
    )
    return {
        "status": "DAILY_CONTEXT_ONLY", "date": as_of.isoformat(),
        "relative_to_release_day": relation(as_of, event_day),
        "instrument": instrument, "6m_rate_pct": rate6,
        "source": source, "quality": r["quality"],
        "event_window_proof": False,
    }


def daily_2y(ccy, event_day, rates):
    r = rates.get(ccy, {})
    if not isinstance(r, dict):
        r = {}
    as_of = parse_day(r.get("date"))
    y2 = r.get("2Y")
    source = r.get("source")
    quality = r.get("quality")
    if not as_of or not finite(y2) or not isinstance(source, str) or (
        not source.strip() or
        not isinstance(quality, str) or not quality.startswith("FULL_CURRENT_OFFICIAL")
    ):
        return {"status": "NOT_VALIDATED_DAILY_CONTEXT"}
    return {
        "status": "DAILY_CONTEXT_ONLY", "date": as_of.isoformat(),
        "relative_to_release_day": relation(as_of, event_day),
        "yield_2y_pct": y2, "source": source, "quality": quality,
        "event_window_proof": False,
    }


def assess(event, ois, rates, now=None):
    """Record actual data availability, explicitly withhold event attribution."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Expected aware current timestamp")
    now = now.astimezone(timezone.utc)
    raw = event.get("published_at_utc")
    try:
        instant = datetime.fromisoformat(raw.replace("Z", "+00:00")) if type(raw) is str else None
    except ValueError:
        instant = None
    valid = (instant is not None and instant.tzinfo is not None and
             instant.utcoffset() is not None and instant <= now)
    base = {
        "schema": "GMFQ_NEWS_REACTION_PROOF_GATE_V1",
        "status": "NOT_VERIFIABLE_INTRADAY",
        "direction": "NOT_DETERMINED",
        "causal_attribution": "NOT_ESTABLISHED",
        "market_reaction": "NOT_MEASURED",
        "valid_release_timestamp": bool(valid),
        "required_proof": "TIMESTAMPED_SAME_INSTRUMENT_PRE_AND_POST_RELEASE",
        "scope": "INFORMATION_ONLY_NO_SCORE_OR_TRADING_SIGNAL",
    }
    if not valid:
        base["status"] = "INVALID_EVENT_TIMESTAMP"
        base["reason"] = "Data o ora della pubblicazione non certificabile."
        return base
    ccy = event.get("ccy")
    event_day = instant.astimezone(timezone.utc).date()
    if ccy in FX_G8:
        base["ois_or_futures"] = daily_ois(ccy, event_day, ois)
        base["yield_2y"] = daily_2y(ccy, event_day, rates)
        base["fx"] = {
            "status": "NO_CERTIFIED_EVENT_WINDOW",
            "reason": "Assenti prezzi FX pre/post su finestra intraday verificata.",
        }
        base["reason"] = (
            "OIS/futures e 2Y disponibili al più come chiusure giornaliere; "
            "mancano prezzi FX e confronti allineati prima/dopo la notizia."
        )
    elif ccy == "ENERGY":
        base["energy_supply_context"] = {
            "status": "ARTICLE_TITLE_ONLY",
            "reason": "La pubblicazione EIA non fornisce in questa pipeline "
                      "uno snapshot certificato di scorte/produzione prima e dopo."
        }
        base["wti"] = {
            "status": "NO_CERTIFIED_EVENT_WINDOW",
            "reason": "Assenti prezzi WTI intraday pre/post collegati al rilascio."
        }
        base["reason"] = (
            "Titolo EIA validato, ma nessuno snapshot WTI pre/post; "
            "nessuna reazione o attribuzione causale dimostrata."
        )
    else:
        base["status"] = "UNSUPPORTED_MARKET_CLASS"
        base["reason"] = "Categoria non coperta dal gate di prova di reazione."
    return base


def annotate(official, ois, rates, now=None):
    result = dict(official)
    result["headlines"] = [
        dict(row, reaction_evidence=assess(row, ois, rates, now=now))
        for row in official.get("headlines", [])
    ]
    result["reaction_proof_contract"] = {
        "schema": "GMFQ_NEWS_REACTION_PROOF_GATE_V1",
        "verified_event_reactions": 0,
        "method": "FAIL_CLOSED_NO_PRE_POST_INTRADAY_SNAPSHOTS",
        "daily_rates_are_not_event_window_proof": True,
        "no_automatic_stance_or_fx_bias": True,
    }
    return result
