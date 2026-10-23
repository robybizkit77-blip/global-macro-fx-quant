#!/usr/bin/env python3
"""Negative/source-transition tests for atomic OIS readiness parity."""
from __future__ import annotations
import copy,json
from pathlib import Path
from check_ois_readiness_parity_v1 import OP,READINESS,OFFICIAL,PLAN,validate

def reject(view,ready,official,plan,label):
    try:validate(view,ready,official,plan)
    except ValueError as error:
        assert str(error).startswith("OIS_READINESS_OPERATIONAL_PARITY_FAIL:"),error
    else:raise AssertionError("FAIL-CLOSED test not enforced: "+label)

def main():
    originals=[json.loads(Path(x).read_text(encoding="utf-8"))
               for x in (OP,READINESS,OFFICIAL,PLAN)]
    view,ready,official,plan=originals
    receipt=validate(*originals)
    assert receipt["certified"]==view["summary"]["green_official"]
    assert receipt["pending"]==len(ready["currencies"])
    scenarios=[
        ("wrong summary",lambda v,r,o,p:r["operational_summary"].update(green_official=99)),
        ("missing dossier",lambda v,r,o,p:r["currencies"].pop("CHF")),
        ("outdated status",lambda v,r,o,p:r["currencies"]["EUR"].update(status="GREEN_ESTIMATED")),
        ("outdated date",lambda v,r,o,p:r["currencies"]["USD"].update(operational_as_of="2026-10-01")),
        ("wrong source URL",lambda v,r,o,p:r["currencies"]["NZD"].update(source_url="https://invalid.example")),
        ("wrong count",lambda v,r,o,p:r.update(blocked_currency_count=r["blocked_currency_count"]+1)),
        ("promoted backtest",lambda v,r,o,p:r["currencies"]["USD"].update(backtest_eligible_as_official=True)),
        ("promoted price",lambda v,r,o,p:r["currencies"]["EUR"].update(usable_for_policy_pricing=True)),
        ("embedded rate",lambda v,r,o,p:r["currencies"]["CHF"].update(price_or_curve_embedded=True)),
        ("unsafe governance",lambda v,r,o,p:r.update(no_automatic_promotions=False)),
        ("old review",lambda v,r,o,p:r.update(source_reviewed_as_of="2026-10-18")),
        ("wrong source stamp",lambda v,r,o,p:r.update(as_of="2026-10-17")),
        ("EUR futures cross-date joined",lambda v,r,o,p:
             r["currencies"]["EUR"]["research_context"].update(cross_date_join_allowed=True)),
        ("EUR falsely equal dates",lambda v,r,o,p:
             r["currencies"]["EUR"]["research_context"].update(same_date_across_horizons=True)),
        ("NZD bank bill policy pricing",lambda v,r,o,p:
             r["currencies"]["NZD"]["research_context"].update(policy_delta_allowed=True)),
        ("NZD false bank bill asof",lambda v,r,o,p:
             r["currencies"]["NZD"]["research_context"].update(proxy_as_of="2026-10-01")),
        ("faked certified",lambda v,r,o,p:(v["currencies"]["USD"].update(
            operational_status="GREEN_OFFICIAL",official_status="ACTIVE",
            quality="OFFICIAL_CERTIFIED",backtest_eligible_as_official=True),
            v["summary"].update(green_official=5,operational_green=5,operational_withheld=3),
            r.update(operational_summary=copy.deepcopy(v["summary"]),blocked_currency_count=3),
            r["currencies"].pop("USD"))),
    ]
    for label,fn in scenarios:
        copies=copy.deepcopy(originals)
        fn(*copies)
        reject(*copies,label)
    # A new separately certified source must be allowed ONLY with coherent
    # original certified runtime, revised derived view and reduced dossier set.
    v,r,o,p=copy.deepcopy(originals)
    v["currencies"]["USD"]=copy.deepcopy(v["currencies"]["GBP"])
    o["currencies"]["USD"]=copy.deepcopy(o["currencies"]["GBP"])
    # A pending USD may already be GREEN_ESTIMATED, so promote only the
    # simulated official certification and count all source states anew.
    states=[row["operational_status"] for row in v["currencies"].values()]
    v["summary"].update(
        g8_total=8,
        green_official=states.count("GREEN_OFFICIAL"),
        green_estimated=states.count("GREEN_ESTIMATED"),
        operational_green=sum(x.startswith("GREEN_") for x in states),
        operational_withheld=states.count("WITHHELD"),
    )
    r["operational_summary"]=copy.deepcopy(v["summary"])
    r["currencies"].pop("USD")
    r["blocked_currency_count"]=sum(
        v["currencies"][c]["operational_status"]=="WITHHELD"
        for c in r["currencies"])
    future=validate(v,r,o,p)
    assert future["certified"]==5 and future["pending"]==3
    stale=copy.deepcopy(originals[1])
    reject(v,stale,o,p,"fifth source with former readiness")
    print("OIS_READINESS_ATOMIC_REFRESH_FAIL_CLOSED_TESTS_PASS",
          json.dumps({"negative_cases":len(scenarios)+1,"original":receipt["pending"],
                      "promoted_fixture_pending":future["pending"]},sort_keys=True))

if __name__=="__main__":main()
