#!/usr/bin/env python3
"""Regression: one RBNZ B2 page read can NEVER promote new NZD yields."""
import copy
import json
from pathlib import Path
from check_nzd_b2_oct22_first_review_v1 import validate,STAGED,CERTIFIED,RATES,REGISTRY

new=json.loads(STAGED.read_text());old=json.loads(CERTIFIED.read_text())
rates=json.loads(RATES.read_text());registry=json.loads(REGISTRY.read_text())

def get(x=new,p=old,r=rates,g=registry):return validate(x,p,r,g)
v=get()
assert v["status"]=="PENDING_INDEPENDENT_SECOND_REVIEW"
assert v["latest_staged_as_of"]=="2026-10-22"
assert v["staged_2Y"]==3.91 and v["staged_10Y"]==4.98
assert v["previously_certified_as_of"]=="2026-10-16"
assert v["old_overlap_rows_verified"]>=5
assert v["new_dates"]==["2026-10-19","2026-10-20","2026-10-21","2026-10-22"]
assert v["automatic_promotion_allowed"] is False
assert v["live_rates_changed"] is False
assert v["macro_scores_changed"] is False
assert v["pair_rankings_changed"] is False
assert rates["NZD"]["date"]=="2026-10-16"
assert registry["currencies"]["NZD"]["current_snapshot"]=="2026-10-16"

def refuse(f):
    x=copy.deepcopy(new);p=copy.deepcopy(old);r=copy.deepcopy(rates);g=copy.deepcopy(registry)
    f(x,p,r,g)
    try: get(x,p,r,g)
    except ValueError: return
    raise AssertionError("Source/approval mutation passed erroneously")
refuse(lambda x,p,r,g:x.update(live_data_promotion_allowed=True))
refuse(lambda x,p,r,g:x.update(usable_for_automatic_promotion=True))
refuse(lambda x,p,r,g:x.update(independent_approval_reference="inferred"))
refuse(lambda x,p,r,g:x.update(source_url="https://thirdparty.example/data"))
refuse(lambda x,p,r,g:x.update(status="INDEPENDENTLY_CERTIFIED"))
refuse(lambda x,p,r,g:x.update(snapshot_previously_certified="2026-10-15"))
refuse(lambda x,p,r,g:x["observations"][5].update({"2Y":4.0}))
refuse(lambda x,p,r,g:x["observations"][0].update({"10Y":4.0}))
refuse(lambda x,p,r,g:x["observations"][-1].update({"10Y":"4.98"}))
refuse(lambda x,p,r,g:x["observations"].pop())
refuse(lambda x,p,r,g:x["observations"].append(copy.deepcopy(x["observations"][-1])))
refuse(lambda x,p,r,g:x["columns"].update(two_year="Swap rate 2 year"))
refuse(lambda x,p,r,g:g["currencies"]["NZD"].update(automatic_promotion_allowed=True))
refuse(lambda x,p,r,g:r["NZD"].update(date="2026-10-22"))
assert 'live_data' not in str(STAGED)
print("RBNZ_B2_OCT22_SOURCE_FIRST_REVIEW_STAGING_FAIL_CLOSED_PASS")
