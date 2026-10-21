#!/usr/bin/env python3
"""Certified monetary pricing must agree across official OIS, CB and Preview.

Read-only check for the G8 operational view built from canonical OIS_DATA.
The source of official status is the validated original OIS runtime; no
secondary futures estimates or stale published views are promoted.
"""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OIS = ROOT / "live_data/sections/OIS_DATA.json"
CB = ROOT / "live_data/sections/NATIVE_CB_DATA.json"
OPERATIONAL = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
HORIZONS = ("3m", "6m", "12m")

def require(ok, label):
    if not ok:
        raise ValueError("OIS_OFFICIAL_RUNTIME_CROSS_SECTION_MISMATCH: " + label)

def equal(a,b):
    return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<1e-8

def check(ois:dict, cb:dict, view:dict):
    source=ois["currencies"]
    v=view["currencies"]
    require(set(source)>=set(G8) and set(cb)>=set(G8) and set(v)>=set(G8), "G8 currencies")
    require(view.get("schema")=="GMFQ_OIS_OPERATIONAL_VIEW_V1", "schema")
    active=[]
    for c in G8:
        o=source[c]
        p=cb[c]["market_pricing"]
        x=v[c]
        if o.get("status")!="ACTIVE":
            require(x.get("operational_status")!="GREEN_OFFICIAL" and
                    x.get("backtest_eligible_as_official") is False,
                    c+" unauthorized official upgrade")
            continue
        active.append(c)
        require(x.get("operational_status")=="GREEN_OFFICIAL" and
                x.get("quality")=="OFFICIAL_CERTIFIED" and
                x.get("official_status")=="ACTIVE" and
                x.get("backtest_eligible_as_official") is True,
                c+" official qualification")
        require(x.get("as_of")==o.get("as_of")==p.get("as_of"),c+" as-of drift")
        require(x.get("source")==o.get("source")==p.get("source"),c+" source lineage")
        require(equal(x.get("policy_rate"),o.get("policy_rate")) and
                equal(x.get("policy_rate"),cb[c]["rate"]),c+" policy rate")
        for t in HORIZONS:
            original=o["horizons"][t]
            displayed=x["horizons"][t]
            require(original==displayed,c+" "+t+" same-date official horizon")
            require(equal(displayed.get("rate"),p["h"+t]),c+" "+t+" CB price mismatch")
    # New separately certified sources may become active in the future; never
    # pin the count to today's four or allow the view to invent that promotion.
    require(len(active)>0, "no official sources")
    require(view["summary"]["green_official"]==len(active), "certified count mismatch")
    return {"status":"PASS","aligned_currencies":active,"as_of":{c:v[c]["as_of"] for c in active},
            "official_only":True,"estimated_promoted":False}

def main():
    ois=json.loads(OIS.read_text())
    cb=json.loads(CB.read_text())
    view=json.loads(OPERATIONAL.read_text())
    receipt=check(ois,cb,view)
    for code,mutate in (
        ("stale GBP as-of",lambda d:d["currencies"]["GBP"].update(as_of="2026-10-19")),
        ("wrong GBP 6m",lambda d:d["currencies"]["GBP"]["horizons"]["6m"].update(rate=4.48)),
        ("illegal USD promotion",lambda d:d["currencies"]["USD"].update(operational_status="GREEN_OFFICIAL")),
        ("fake GBP 1w delta",lambda d:d["currencies"]["GBP"]["horizons"]["6m"].update(change_1w_bp=0)),
    ):
        wrong=copy.deepcopy(view);mutate(wrong)
        try:check(ois,cb,wrong)
        except ValueError: pass
        else:raise AssertionError("Failed to reject "+code)
    wrong=copy.deepcopy(cb)
    wrong["GBP"]["market_pricing"]["as_of"]="2026-10-19"
    try:check(ois,wrong,view)
    except ValueError: pass
    else:raise AssertionError("Failed to reject GBP CB date drift")
    print("OIS_OFFICIAL_CB_OPERATIONAL_FOUR_WAY_PARITY_PASS",json.dumps(receipt,sort_keys=True))

if __name__=="__main__":main()
