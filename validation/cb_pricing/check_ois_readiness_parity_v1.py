#!/usr/bin/env python3
"""Read-only fail-closed parity proof for OIS source-readiness publication.

The access-plan inventory persists independently from the currently pending
dossiers. Check both feed IDs, provenance and exact operational statuses before
publishing; never promote a quote, create missing history or mutate inputs.
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OP=ROOT/"live_data/sections/OIS_OPERATIONAL_VIEW.json"
READINESS=ROOT/"live_data/sections/OIS_SOURCE_READINESS_VIEW.json"
OFFICIAL=ROOT/"live_data/sections/OIS_DATA.json"
PLAN=ROOT/"validation/cb_pricing/OIS_SOURCE_ACCESS_PLAN_V1_2026-10-19.json"
G8={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}
PENDING={"WITHHELD","GREEN_ESTIMATED"}
GUARDS=("no_automatic_promotions","no_core_score_effect","no_bias_effect",
        "no_sizing_effect","no_backtest_effect","prices_omitted")

def need(ok,detail):
    if not ok:
        raise ValueError("OIS_READINESS_OPERATIONAL_PARITY_FAIL: "+detail)

def validate(operational,readiness,official,plan):
    need(operational.get("schema")=="GMFQ_OIS_OPERATIONAL_VIEW_V1","operational schema")
    need(readiness.get("schema")=="GMFQ_OIS_SOURCE_READINESS_VIEW_V1"
         and readiness.get("status")=="READ_ONLY_SOURCE_READINESS","readiness source contract")
    need(plan.get("schema")=="GMFQ_OIS_SOURCE_ACCESS_PLAN_V1","source access plan contract")
    need(all(readiness.get(g) is True for g in GUARDS),"non-promotional governance")
    need(readiness.get("operational_summary")==operational.get("summary"),"summary differs from operational")
    need(readiness.get("source_reviewed_as_of")==plan.get("reviewed_as_of"),"source review stamp")
    need(set(operational.get("currencies",{}))==G8 and
         set(official.get("currencies",{}))==G8,"canonical G8")
    try:
        stamp=date.fromisoformat(readiness["as_of"])
        review=date.fromisoformat(readiness["source_reviewed_as_of"])
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError("OIS_READINESS_OPERATIONAL_PARITY_FAIL: invalid source date") from exc
    need(stamp>=review,"stale dossier generation date")
    states=operational["currencies"]
    summary=operational["summary"]
    need(summary.get("g8_total")==8 and
         summary.get("green_official")==sum(x["operational_status"]=="GREEN_OFFICIAL" for x in states.values()) and
         summary.get("green_estimated")==sum(x["operational_status"]=="GREEN_ESTIMATED" for x in states.values()) and
         summary.get("operational_withheld")==sum(x["operational_status"]=="WITHHELD" for x in states.values()) and
         summary.get("operational_green")==summary["green_official"]+summary["green_estimated"] and
         summary["operational_green"]+summary["operational_withheld"]==8,"operational summary counts")
    pending={k for k,x in states.items() if x["operational_status"] in PENDING}
    active=G8-pending
    need(all(states[k]["operational_status"]=="GREEN_OFFICIAL" for k in active),"invalid official state")
    need(all(states[k].get("official_status")=="ACTIVE" and
             states[k].get("quality")=="OFFICIAL_CERTIFIED" and
             states[k].get("backtest_eligible_as_official") is True and
             official["currencies"][k].get("status")=="ACTIVE" and
             states[k].get("as_of")==official["currencies"][k].get("as_of")
             for k in active),"unapproved official runtime promotion")
    rows=readiness.get("currencies")
    need(isinstance(rows,dict) and set(rows)==pending,"pending identities diverged")
    need(set(rows).issubset(set(plan.get("blocked_sources",{}))),"pending source absent from reviewed inventory")
    need(readiness.get("blocked_currency_count")==
         sum(states[k]["operational_status"]=="WITHHELD" for k in pending),"blocked count")
    for k in pending:
        p=rows[k]
        need(p.get("currency")==k and
             p.get("status")==states[k]["operational_status"] and
             p.get("operational_as_of")==states[k].get("as_of"),k+" status/as-of mismatch")
        need(p.get("source_reviewed_as_of")==readiness["source_reviewed_as_of"] and
             p.get("source_url")==plan["blocked_sources"][k].get("source_url"),k+" source audit mismatch")
        need(p.get("usable_for_policy_pricing") is False and
             p.get("backtest_eligible_as_official") is False and
             p.get("price_or_curve_embedded") is False and
             p.get("dates_joinable") is False,k+" unsafe promotion flags")
        need(isinstance(p.get("obstacle"),str) and bool(p["obstacle"]) and
             isinstance(p.get("activation_requirement"),str) and bool(p["activation_requirement"]),
             k+" missing access explanation")
    return {"status":"PASS","certified":len(active),"pending":len(pending),
            "withheld":readiness["blocked_currency_count"],"as_of":readiness["as_of"],
            "official_ois_promoted":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--view",default=str(OP))
    parser.add_argument("--readiness",default=str(READINESS))
    parser.add_argument("--official",default=str(OFFICIAL))
    parser.add_argument("--plan",default=str(PLAN))
    a=parser.parse_args()
    sources=[json.loads(Path(p).read_text(encoding="utf-8"))
             for p in (a.view,a.readiness,a.official,a.plan)]
    print("OIS_READINESS_ATOMIC_CROSS_FEED_PARITY_PASS",
          json.dumps(validate(*sources),sort_keys=True))

if __name__=="__main__":
    main()
