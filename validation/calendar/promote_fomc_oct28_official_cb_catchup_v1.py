#!/usr/bin/env python3
"""One-time verified FOMC Oct 28 decision and official Dec 8-9 next meeting.

This updates ONLY the Fed's last action / meeting date / explanatory context
in a candidate NATIVE_CB_DATA. A separate direct-section integrity gate handles
the canonical payload replacement. No live OIS, pricing, Macro D, FX or model
inputs are inferred from the issuer's press release.
Official issuer documentation:
https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm
https://www.federalreserve.gov/newsevents/2026-december.htm
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

LAST_ISSUER_DECISION = "2026-10-28"
NEXT_ISSUER_MEETING = "2026-12-09"
PRIOR_DATE = "2026-09-16"
OFFICIAL_DECISION_URL = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm"
OFFICIAL_SCHEDULE_URL = "https://www.federalreserve.gov/newsevents/2026-december.htm"
NEW_ACTION = "INVARIATO (10–2; due membri per +25 pb)"
NEW_IMPULSE = "HOLD_HAWKISH_RISK"
NEW_STANCE = "INVARIATA · rischio hawkish"
NEW_CONTEXT = ("FOMC 28 ottobre 2026: range 3,75–4,00% invariato (voto 10–2). "
               "Attività economica in espansione a ritmo forte, inflazione ancora "
               "elevata; Cook e Hammack avrebbero preferito +25 pb. "
               "Prossima riunione 8–9 dicembre 2026.")
NEW_NEXT = ("Nessun rialzo automaticamente annunciato: la Fed valuterà nuovi "
            "dati di inflazione e attività. Prossima decisione 9 dicembre 2026.")
NEW_BIAS = "HOLD · RISCHIO RIALZO"


def patch(cb: dict) -> tuple[dict, str]:
    if not isinstance(cb, dict) or set(cb) != {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}:
        raise ValueError("FOMC_CATCHUP_FAIL_CLOSED: unexpected G8 CB universe")
    current = cb["USD"]
    if not isinstance(current, dict):
        raise ValueError("FOMC_CATCHUP_FAIL_CLOSED: malformed Fed CB record")
    date_raw = current.get("last_date")
    try:
        old_date = date.fromisoformat(date_raw)
    except (ValueError, TypeError):
        raise ValueError("FOMC_CATCHUP_FAIL_CLOSED: invalid current Fed decision date")
    if old_date > date.fromisoformat(LAST_ISSUER_DECISION):
        return deepcopy(cb), "SKIP_NEWER_CERTIFIED_USD_DECISION"
    result = deepcopy(cb)
    usd = result["USD"]
    fields = {
        "last_date": LAST_ISSUER_DECISION,
        "next_meeting": NEXT_ISSUER_MEETING,
        "action": NEW_ACTION,
        "impulse": NEW_IMPULSE,
        "stance": NEW_STANCE,
        "context": NEW_CONTEXT,
        "official_next": NEW_NEXT,
        "official_bias": NEW_BIAS
    }
    if old_date == date.fromisoformat(LAST_ISSUER_DECISION):
        if any(usd.get(k) != v for k,v in fields.items()):
            raise ValueError("FOMC_CATCHUP_FAIL_CLOSED: decision date already present with different facts")
        return result, "ALREADY_CERTIFIED_NO_CHANGE"
    if (date_raw != PRIOR_DATE
            or usd.get("bank") != "Fed"
            or usd.get("rate") != 3.875
            or usd.get("rate_text") != "3.75-4.00%"
            or usd.get("next_meeting") != LAST_ISSUER_DECISION
            or usd.get("action") != "RIALZO +25 pb"
            or usd.get("impulse") != "TIGHTENING"):
        raise ValueError("FOMC_CATCHUP_FAIL_CLOSED: prior certified Fed source does not match")
    for field,value in fields.items():
        usd[field] = value
    assert usd["rate"] == current["rate"] == 3.875
    assert usd["market_pricing"] == current["market_pricing"]
    assert all(result[k]==cb[k] for k in cb if k!="USD")
    return result, "OFFICIAL_FOMC_2026_10_28_CATCHUP_READY"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,default=Path("live_data/sections/NATIVE_CB_DATA.json"))
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    original=json.loads(args.input.read_text(encoding="utf-8"))
    candidate,status=patch(original)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # If already current, copy the raw input exactly to avoid an artificial
    # diff from reserializing a previously certified record.
    if candidate == original:
        args.output.write_bytes(args.input.read_bytes())
    else:
        args.output.write_text(
            json.dumps(candidate,separators=(",",":"),ensure_ascii=False)+"\n",
            encoding="utf-8")
    print(json.dumps({
        "status":status,
        "changed":candidate!=original,
        "official_decision_date":LAST_ISSUER_DECISION,
        "official_next_meeting":NEXT_ISSUER_MEETING,
        "official_sources":[OFFICIAL_DECISION_URL,OFFICIAL_SCHEDULE_URL],
        "rate_level_changed":False,
        "market_pricing_unchanged":True,
        "core_or_ois_or_pair_effect":"NONE",
        "record_changed":["USD"] if candidate!=original else [],
    },sort_keys=True))


if __name__ == "__main__":
    main()
