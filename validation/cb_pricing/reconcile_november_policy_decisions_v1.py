#!/usr/bin/env python3
"""Atomic source-verified policy decision reconciliation for AUD/GBP.

Does not invent post-event OIS quotations, update historical market observations,
or change scoring/FX pair signals. Must be run with a matching payload checkout.
"""
from __future__ import annotations
import argparse, copy, json, pathlib, datetime as dt

HERE=pathlib.Path(__file__).resolve()
ROOT=HERE.parents[2]
DECISIONS={
 "AUD":{"old_rate":4.60,"rate":4.85,"date":"2026-11-03",
        "effective_date":"2026-11-04","next_meeting":"2026-12-08",
        "bank":"Reserve Bank of Australia","action":"RIALZO +25 pb",
        "stance":"HAWKISH · nuovo cash rate 4,85%",
        "source":"https://www.rba.gov.au/media-releases/2026/mr-26-30.html"},
 "GBP":{"old_rate":3.75,"rate":4.00,"date":"2026-11-05",
        "effective_date":"2026-11-05","next_meeting":"2026-12-17",
        "bank":"Bank of England","action":"RIALZO +25 pb",
        "stance":"HAWKISH · aumento Bank Rate al 4,00%, percorso dipendente dai dati",
        "source":"https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026"}
}
OIS_MARK=b"window.__GMFQ_DATA.OIS_DATA="
NATIVE_MARK=b"window.__GMFQ_DATA.NATIVE_CB_DATA="

def extract(raw:bytes, marker:bytes):
    pos=raw.find(marker)
    if pos<0: raise ValueError("missing runtime marker "+str(marker))
    start=pos+len(marker); val,n=json.JSONDecoder().raw_decode(raw[start:].decode("utf-8"))
    end=start+len(raw[start:].decode("utf-8")[:n].encode("utf-8"))
    if raw[end:].lstrip()[:1]!=b";": raise ValueError("missing assignment semicolon")
    return val,start,end

def replace(raw:bytes, marker:bytes, value:dict)->bytes:
    old,start,end=extract(raw,marker)
    new=raw[:start]+json.dumps(value,ensure_ascii=False,separators=(",",":")).encode()+raw[end:]
    if extract(new,marker)[0]!=value: raise ValueError("payload failed roundtrip")
    return new

def reconcile(ois:dict, native:dict):
    o,n=copy.deepcopy(ois),copy.deepcopy(native); report={}
    for c,p in DECISIONS.items():
        x=o["currencies"][c]; y=n[c]
        if x.get("status")!="ACTIVE": raise ValueError(c+" is not active")
        old=float(x["policy_rate"]); previous=float(y["rate"])
        if round(old,5) not in (p["old_rate"],p["rate"]) or round(previous,5) not in (p["old_rate"],p["rate"]):
            raise ValueError(c+" unexpected policy baseline")
        if x.get("as_of") is None or not isinstance(x.get("horizons"),dict):
            raise ValueError(c+" missing market provenance")
        if x["as_of"] > dt.date.today().isoformat():
            raise ValueError(c+" futures/OIS observation dated in future")
        if round(p["rate"]-p["old_rate"],5)!=.25:
            raise ValueError(c+" unexpected official change")
        x["policy_rate"]=p["rate"]
        x["meetings"]=[{"date":p["next_meeting"],"source":p["bank"]+" official MPC schedule","status":"mapped"}]
        x["policy_decision"]={"date":p["date"],"effective_date":p["effective_date"],
            "source":p["source"],"old_rate":p["old_rate"],"new_rate":p["rate"],
            "change_bp":25,"quality":"OFFICIAL_VERIFIED"}
        # A dated daily quote equal to the decision calendar day has no
        # independently verified *intraday* timestamp. A calendar equality
        # cannot prove that the observation followed the policy announcement.
        event_day=x["as_of"]==p["date"]
        post=x["as_of"]>p["date"]
        x["policy_comparison_temporally_aligned"]=post
        x["policy_reference_note"]=(
            "Market quote dated on/after decision. Descriptive rate minus policy, not meeting probability."
            if post else
            "Decision-day daily observation: intraday quote timestamp unavailable; post-event pricing WITHHELD."
            if event_day else
            "PRE-DECISION OIS: no post-announcement repricing inference; keep historical quoted levels.")
        for ten in ("3m","6m","12m"):
            h=x["horizons"][ten]
            if not isinstance(h.get("rate"),(int,float)): raise ValueError(c+" missing "+ten+" rate")
            h["policy_delta_bp"]=round((h["rate"]-p["rate"])*100,1) if post else None
            h["policy_comparison_temporally_aligned"]=post
        x["cuts_hikes_priced"]={ten+"_bp":x["horizons"][ten]["policy_delta_bp"] for ten in ("3m","6m","12m")}
        if post:
            vals=[x["horizons"][ten]["policy_delta_bp"] for ten in ("3m","6m","12m")]
            x["direction"]="UP" if all(v>1 for v in vals) else "DOWN" if all(v< -1 for v in vals) else "MIXED"
        elif event_day:
            x["direction"]="DECISION_DAY_TIMESTAMP_UNVERIFIED_NO_POLICY_REPRICING"
        else:
            x["direction"]="PRE_DECISION_NO_POST_EVENT_PRICING"
        y.update({"rate":p["rate"],"rate_text":f'{p["rate"]:.2f}%',"last_date":p["date"],
                  "action":p["action"],"impulse":"TIGHTENING","stance":p["stance"],
                  "context":p["bank"]+" official decision "+p["date"]+
                  ": +25 bp; analysis of subsequent repricing requires post-decision dated quotes.",
                  "official_next":"Next official decision "+p["next_meeting"]+"; no guaranteed subsequent increase.",
                  "next_meeting":p["next_meeting"]})
        y["policy_decision_source"]=p["source"]
        y["policy_change_bp"]=25
        if isinstance(y.get("market_pricing"),dict):
            y["market_pricing"]["policy_comparison_temporally_aligned"]=post
            y["market_pricing"]["policy_reference_as_of"]=p["date"]
            if event_day:
                y["market_pricing"]["freshness_status"]="DECISION_DAY_TIMING_UNVERIFIED"
                y["market_pricing"]["note"]=x["policy_reference_note"]
            elif not post:
                y["market_pricing"]["freshness_status"]="PRE_DECISION_MARKET_CURVE"
                y["market_pricing"]["note"]="OIS curve precedes latest official policy decision; levels preserved; no post-event repricing asserted."
            elif y["market_pricing"].get("freshness_status") in (
                    "PRE_DECISION_MARKET_CURVE","DECISION_DAY_TIMING_UNVERIFIED"):
                y["market_pricing"]["freshness_status"]="CURRENT_VALIDATED"
                y["market_pricing"]["note"]=x["policy_reference_note"]
        report[c]={"policy_rate":p["rate"],"policy_decision_date":p["date"],
          "market_quote_as_of":x["as_of"],"policy_comparison_aligned":post,
          "decision_day_timing_unverified":event_day}
    for c in set(o["currencies"])-set(DECISIONS):
        if o["currencies"][c]!=ois["currencies"][c] or n[c]!=native[c]:
            raise ValueError("non-target currency mutated: "+c)
    return o,n,report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=pathlib.Path,default=ROOT)
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    root=args.root
    op=root/"live_data/sections/OIS_DATA.json"
    np=root/"live_data/sections/NATIVE_CB_DATA.json"
    pp=root/"payload/part-00.txt"
    old_o=json.loads(op.read_text());old_n=json.loads(np.read_text())
    raw=pp.read_bytes()
    if extract(raw,OIS_MARK)[0]!=old_o or extract(raw,NATIVE_MARK)[0]!=old_n:
        raise ValueError("repository sections and runtime payload not synchronized")
    new_o,new_n,report=reconcile(old_o,old_n)
    updated=replace(replace(raw,OIS_MARK,new_o),NATIVE_MARK,new_n)
    if args.apply:
        op.write_text(json.dumps(new_o,ensure_ascii=False,separators=(",",":")))
        np.write_text(json.dumps(new_n,ensure_ascii=False,separators=(",",":")))
        pp.write_bytes(updated)
    print(json.dumps({"status":"PASS","apply":args.apply,"report":report,
       "changed":old_o!=new_o or old_n!=new_n},indent=2))
if __name__=="__main__": main()
