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
import re
from datetime import date
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
    pre_decision=[]
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
        # A *dated* pre-decision official futures settlement must retain the
        # policy rate from its own trading session. Never re-anchor old 3/6/12M
        # policy deltas to a new CB rate decided the following day.
        require(equal(x.get("policy_rate"),o.get("policy_rate")),
                c+" source-day policy rate")
        if not equal(x.get("policy_rate"),cb[c]["rate"]):
            source_day=o.get("as_of")
            decision_day=cb[c].get("last_date")
            action=str(cb[c].get("action") or "")
            action_bp=re.search(r"([+-]\d+)\s*pb",action)
            try:
                dated=(date.fromisoformat(str(source_day)) <
                       date.fromisoformat(str(decision_day)))
            except ValueError:
                dated=False
            note=p.get("note")
            require(
                dated and
                p.get("freshness_status")=="HISTORICAL_PRE_DECISION" and
                action_bp is not None and
                equal(cb[c]["rate"]-o["policy_rate"],int(action_bp.group(1))/100) and
                isinstance(note,str) and "NON confrontabili" in note and
                isinstance(cb[c].get("pricing_status"),str) and
                "PRECEDENTI" in cb[c]["pricing_status"],
                c+" unacknowledged pre-decision policy rate mismatch"
            )
            pre_decision.append(c)
        for t in HORIZONS:
            original=o["horizons"][t]
            displayed=x["horizons"][t]
            require(original==displayed,c+" "+t+" same-date official horizon")
            require(equal(displayed.get("rate"),p["h"+t]),c+" "+t+" CB price mismatch")
    # New separately certified sources may become active in the future; never
    # pin the count to today's four or allow the view to invent that promotion.
    require(len(active)>0, "no official sources")
    require(view["summary"]["green_official"]==len(active), "certified count mismatch")
    return {"status":"PASS","aligned_currencies":active,
            "pre_decision_policy_anchor_currencies":pre_decision,
            "as_of":{c:v[c]["as_of"] for c in active},
            "official_only":True,"estimated_promoted":False}

def main():
    ois=json.loads(OIS.read_text())
    cb=json.loads(CB.read_text())
    view=json.loads(OPERATIONAL.read_text())
    receipt=check(ois,cb,view)
    # Current live source may advance past the 28 Oct BoC decision.
    # Do not pin the live runtime to the historical 27 Oct overnight rate.
    cad_source=ois["currencies"]["CAD"]
    cad_cb=cb["CAD"]
    if date.fromisoformat(cad_source["as_of"]) >= date.fromisoformat(cad_cb["last_date"]):
        require(equal(cad_source["policy_rate"],cad_cb["rate"]),
                "CAD post-decision official settlement must use current BoC policy rate")
        require("CAD" not in receipt["pre_decision_policy_anchor_currencies"],
                "post-decision CAD cannot retain historical mismatch exemption")

    # FROZEN QA-ONLY historical fixture: actual 27 Oct MX CRA settlements,
    # followed by the 28 Oct +25bp BoC decision. No fixture data is written.
    # Exercise the narrow temporal exception even after live source advances.
    historic_prices={"3m":2.715,"6m":2.995,"12m":3.360}
    historic_moves={"3m":(-1.5,-1.5),"6m":(-1.5,-2.5),"12m":(-2.0,-2.5)}
    hist_ois=copy.deepcopy(ois)
    hist_cb=copy.deepcopy(cb)
    hist_view=copy.deepcopy(view)
    original=hist_ois["currencies"]["CAD"]
    before=hist_cb["CAD"]
    exposed=hist_view["currencies"]["CAD"]
    original.update(as_of="2026-10-27",policy_rate=2.25)
    exposed.update(as_of="2026-10-27",policy_rate=2.25)
    for tenor,rate in historic_prices.items():
        daily,weekly=historic_moves[tenor]
        original["horizons"][tenor].update(
            rate=rate,change_1d_bp=daily,change_1w_bp=weekly,
            policy_delta_bp=round((rate-2.25)*100,1))
        exposed["horizons"][tenor]=copy.deepcopy(original["horizons"][tenor])
        before["market_pricing"]["h"+tenor]=rate
    before["market_pricing"].update(
        as_of="2026-10-27",freshness_status="HISTORICAL_PRE_DECISION",
        note="Verified 27 Oct CRA, NON confrontabili con il nuovo tasso 2,50%.")
    before["pricing_status"]="CRA 27 ottobre PRECEDENTI al rialzo BoC del 28 ottobre."
    historic_receipt=check(hist_ois,hist_cb,hist_view)
    require("CAD" in historic_receipt["pre_decision_policy_anchor_currencies"],
            "historical CAD pre-decision protection regression")

    for label,change in (
        ("no CAD predecision marker",lambda d:d["CAD"]["market_pricing"].update(
            freshness_status="LIVE_OR_RECENT_SESSION")),
        ("no CAD policy action",lambda d:d["CAD"].update(action="INVARIATO")),
        ("no CAD decision lag",lambda d:d["CAD"].update(last_date="2026-10-27")),
        ("no CAD caveat",lambda d:d["CAD"]["market_pricing"].update(note="")),
        ("incorrect CAD rate change",lambda d:d["CAD"].update(rate=2.75)),
    ):
        malformed=copy.deepcopy(hist_cb)
        change(malformed)
        try:check(hist_ois,malformed,hist_view)
        except ValueError:pass
        else:raise AssertionError("Failed to reject "+label)
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
