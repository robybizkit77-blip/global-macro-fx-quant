#!/usr/bin/env python3
"""One-time BoJ Oct 30 official policy-source catch-up, separate from TONA.

Pinned issuer statement:
https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf
Issuer release: Oct 30, 2026 12:02 JST = 03:02 UTC = 04:02 CET.
Issuer meeting calendar:
https://www.boj.or.jp/en/mopo/mpmsche_minu/
No OIS, futures, pair, signal, forward or Core recomputation.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path

LAST_ISSUER_DECISION="2026-10-30"
NEXT_ISSUER_MEETING="2026-12-18"
PRIOR_DATE="2026-09-18"
OFFICIAL_DECISION_URL="https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf"
OFFICIAL_SCHEDULE_URL="https://www.boj.or.jp/en/mopo/mpmsche_minu/"
SOURCE_RELEASE_UTC=datetime(2026,10,30,3,2,tzinfo=timezone.utc)
NEW_ACTION="INVARIATO (8–1; un membro per +25 pb)"
NEW_IMPULSE="HOLD_HAWKISH_RISK"
NEW_STANCE="INVARIATA · rischio hawkish"
NEW_CONTEXT=("BoJ 30 ottobre 2026: tasso overnight intorno all'1,25% confermato "
             "con voto 8–1; Takata preferiva l'1,50%. Deciso anche l'aumento "
             "del ritmo di vendita ETF da circa ¥330 a ¥860 mld/anno, "
             "con attuazione da gennaio 2027. Prossima MPM 17–18 dicembre 2026.")
NEW_NEXT=("Nessun ulteriore rialzo già deciso: livello 1,25% confermato. "
          "Prossima decisione 18 dicembre 2026.")
NEW_BIAS="HOLD · RISCHIO RIALZO"

def patch(cb:dict)->tuple[dict,str]:
    if not isinstance(cb,dict) or set(cb)!={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}:
        raise ValueError("BOJ_CATCHUP_FAIL_CLOSED: unexpected G8 CB universe")
    current=cb.get("JPY")
    if not isinstance(current,dict):
        raise ValueError("BOJ_CATCHUP_FAIL_CLOSED: malformed JPY record")
    try:
        old_date=date.fromisoformat(current.get("last_date"))
    except (ValueError,TypeError):
        raise ValueError("BOJ_CATCHUP_FAIL_CLOSED: invalid JPY decision date")
    if old_date>date.fromisoformat(LAST_ISSUER_DECISION):
        return deepcopy(cb),"SKIP_NEWER_CERTIFIED_JPY_DECISION"
    result=deepcopy(cb)
    jpy=result["JPY"]
    fields={
        "last_date":LAST_ISSUER_DECISION,
        "next_meeting":NEXT_ISSUER_MEETING,
        "action":NEW_ACTION,
        "impulse":NEW_IMPULSE,
        "stance":NEW_STANCE,
        "context":NEW_CONTEXT,
        "official_next":NEW_NEXT,
        "official_bias":NEW_BIAS,
    }
    if old_date==date.fromisoformat(LAST_ISSUER_DECISION):
        if any(jpy.get(k)!=v for k,v in fields.items()):
            raise ValueError("BOJ_CATCHUP_FAIL_CLOSED: same decision date with conflicting facts")
        return result,"ALREADY_CERTIFIED_NO_CHANGE"
    if (current.get("last_date")!=PRIOR_DATE
            or current.get("bank")!="BoJ"
            or current.get("rate")!=1.25
            or current.get("rate_text")!="1.25%"
            or current.get("next_meeting")!=LAST_ISSUER_DECISION
            or current.get("action")!="RIALZO +25 pb"
            or current.get("impulse")!="TIGHTENING"):
        raise ValueError("BOJ_CATCHUP_FAIL_CLOSED: prior source does not match")
    for key,value in fields.items():
        jpy[key]=value
    if (jpy["rate"]!=current["rate"] or jpy["market_pricing"]!=current["market_pricing"]
            or any(result[k]!=cb[k] for k in cb if k!="JPY")):
        raise ValueError("BOJ_CATCHUP_FAIL_CLOSED: other pricing/CCY changed")
    return result,"OFFICIAL_BOJ_2026_10_30_CATCHUP_READY"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=Path("live_data/sections/NATIVE_CB_DATA.json"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if datetime.now(timezone.utc)<SOURCE_RELEASE_UTC:
        raise SystemExit("BOJ_CATCHUP_FAIL_CLOSED: official release not yet available")
    original=json.loads(a.input.read_text(encoding="utf-8"))
    candidate,status=patch(original)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if candidate==original:
        a.output.write_bytes(a.input.read_bytes())
    else:
        a.output.write_text(json.dumps(candidate,separators=(",",":"),ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":status,"changed":candidate!=original,
        "issuer_release_at_utc":SOURCE_RELEASE_UTC.isoformat(),
        "issuer_decision_date":LAST_ISSUER_DECISION,
        "issuer_next_meeting_date":NEXT_ISSUER_MEETING,
        "official_sources":[OFFICIAL_DECISION_URL,OFFICIAL_SCHEDULE_URL],
        "rate_level_changed":False,"market_pricing_unchanged":True,
        "core_or_ois_or_pair_effect":"NONE",
        "record_changed":["JPY"] if candidate!=original else []
    },sort_keys=True))

if __name__=="__main__":
    main()
