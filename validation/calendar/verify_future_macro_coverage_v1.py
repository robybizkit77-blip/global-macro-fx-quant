#!/usr/bin/env python3
"""Verify the published future macro calendar against dated OFFICIAL seed rows.

G8 source coverage is NOT the same as G8 future-event coverage: after an
official event expires, its currency may genuinely have no further dated
release in the current reviewed seed. Preserve strict event/source integrity
and disclose the gap instead of inventing a replacement or blocking Pages.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
G8 = {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}
SOURCE = "MACRO_RELEASE_OFFICIAL_SEED_V1"
CB_SOURCE = "NATIVE_CB_DATA"


def check(condition, why):
    if not condition:
        raise ValueError("CALENDAR_FUTURE_SOURCE_CONTRACT_FAILED: "+why)


def key(event):
    return (event.get("ccy"), event.get("date"),
            event.get("event_type"), event.get("title"))


def verify(calendar, seed, instant):
    check(instant.tzinfo is not None and instant.utcoffset() is not None,
          "timezone-aware instant required")
    today = instant.astimezone(ROME).date()
    check(seed.get("schema") == "GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1"
          and seed.get("status") == "ACTIVE_VERIFIED_SEED",
          "unverified official macro seed")
    check(calendar.get("schema") == "GMFQ_CALENDAR_OPERATIONAL_VIEW_V3"
          and calendar.get("status") ==
          "ACTIVE_CB_PLUS_MACRO_OFFICIAL_WITH_SECONDARY_CONTEXT",
          "calendar schema/status drift")
    coverage = calendar.get("coverage")
    scope = calendar.get("scope")
    check(isinstance(coverage,dict) and isinstance(scope,dict)
          and coverage.get("g8_total")==8
          and scope.get("core_score_impact")==0
          and scope.get("consensus_context_only") is True
          and scope.get("consensus_never_changes_official_date") is True,
          "coverage or no-Core guarantee drift")
    original = seed.get("events")
    actual = calendar.get("events")
    check(isinstance(original,list) and isinstance(actual,list),
          "missing source or calendar event arrays")
    check({e.get("ccy") for e in original} == G8,
          "original reviewed macro seed no longer covers G8")
    wanted = {}
    for e in original:
        check(e.get("ccy") in G8
              and str(e.get("quality","")).startswith("OFFICIAL_"),
              "invalid seed currency/source class")
        try:
            d = date.fromisoformat(e["date"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("bad official source event date") from exc
        k=key(e)
        check(k not in wanted, "duplicate original source event")
        wanted[k]=e
    expected={k:e for k,e in wanted.items()
              if date.fromisoformat(e["date"]) >= today}
    observed_macro={}
    cb=[]
    for e in actual:
        try:
            d=date.fromisoformat(e["date"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("bad published event date") from exc
        check(d >= today, "expired event still marked UPCOMING")
        check(e.get("status")=="UPCOMING", "event status drift")
        if e.get("event_type")=="CENTRAL_BANK_DECISION":
            check(e.get("source_layer")==CB_SOURCE
                  and e.get("ccy") in G8
                  and e.get("quality")=="OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER",
                  "non-certified central-bank date")
            cb.append(e)
        else:
            k=key(e)
            check(k not in observed_macro,"duplicated future official macro event")
            check(k in expected and e.get("source_layer")==SOURCE,
                  "fabricated or noncanonical future macro event")
            check(all(e.get(field)==expected[k].get(field)
                      for field in ("ccy","date","title","event_type","importance","quality")),
                  "issuer event altered in public calendar")
            check(e.get("consensus_status") in
                  {"AVAILABLE","PREVIOUS_ONLY","NOT_PRESENT"},
                  "invalid separate consensus label")
            observed_macro[k]=e
    check(set(observed_macro)==set(expected),
          "reviewed future issuer event missing or added")
    check(len(cb)==8 and {e["ccy"] for e in cb}==G8
          and coverage.get("cb_schedule_available")==8,
          "G8 certified next central-bank meetings incomplete")
    future_currencies={e["ccy"] for e in observed_macro.values()}
    check(coverage.get("macro_ccy_coverage")==len(future_currencies)
          and coverage.get("upcoming_macro_events")==len(observed_macro)
          and coverage.get("upcoming_total_events")==len(actual)
          and set(scope.get("macro_release_currencies",[]))==future_currencies,
          "future-only coverage counters diverge from actual events")
    check(Counter(e.get("consensus_status") for e in observed_macro.values())
          ["AVAILABLE"]==coverage.get("consensus_available_events")
          and Counter(e.get("consensus_status") for e in observed_macro.values())
          ["PREVIOUS_ONLY"]==coverage.get("previous_only_events"),
          "consensus counters mismatch")
    missing=sorted(G8-future_currencies)
    return {
        "schema":"GMFQ_FUTURE_MACRO_SEED_PARITY_RECEIPT_V1",
        "status":("PASS_COMPLETE_G8_FUTURE_MACRO"
                  if not missing else "PASS_EXACT_SOURCE_WITH_DISCLOSED_FUTURE_GAPS"),
        "checked_date_rome":today.isoformat(),
        "seed_currency_coverage":8,
        "future_macro_currency_coverage":len(future_currencies),
        "currency_without_next_seed_event":missing,
        "source_matched_future_events":len(observed_macro),
        "verified_CB_meetings":len(cb),
        "no_fabricated_events":True,
        "no_core_or_fx_model_effect":True,
        "future_dates_only":True,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--calendar",type=Path,
                   default=Path("live_data/sections/CALENDAR_OPERATIONAL_VIEW.json"))
    p.add_argument("--seed",type=Path,
                   default=Path("live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json"))
    args=p.parse_args()
    receipt=verify(json.loads(args.calendar.read_text(encoding="utf-8")),
                   json.loads(args.seed.read_text(encoding="utf-8")),
                   datetime.now(timezone.utc))
    print(json.dumps(receipt,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
