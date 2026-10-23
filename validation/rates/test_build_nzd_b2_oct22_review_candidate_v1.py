#!/usr/bin/env python3
"""NZD source and full-G8 draft regression; production modifications prohibited."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from build_nzd_b2_oct22_review_candidate_v1 import (
  FIRST,SECOND,PRIOR,RATES,REGISTRY,build,check_second,check_approved_live
)

def read(x):return json.loads(x.read_text())
first,second,prior,live,reg=map(read,(FIRST,SECOND,PRIOR,RATES,REGISTRY))
draft,proof=build(first,second,prior,live,reg)
assert proof["schema"]=="GMFQ_NZD_OFFICIAL_B2_OCT22_DRAFT_CANDIDATE_V1"
assert proof["status"]=="PREVIEW_VALIDATED_NOT_APPROVED"
assert proof["second_source_independent_xlsx"] is False
assert proof["separate_human_reviewer"] is False
assert proof["live_promotion_allowed"] is False
assert proof["production_effect"]=="NONE"
assert proof["old_live_as_of"]=="2026-10-16"
assert proof["draft_as_of"]=="2026-10-22"
assert proof["draft_2Y"]==3.91 and proof["draft_10Y"]==4.98
assert proof["weekly_change_bp"]=={"2Y":10.0,"10Y":4.0}
assert proof["weekly_reference"]=={"2Y":"2026-10-15","10Y":"2026-10-15"}
assert proof["curve_state"]=="Bear flattening"
assert all(draft[c]==live[c] for c in live if c!="NZD")
n=draft["NZD"]
assert n["date"]=="2026-10-22" and n["curve_bp"]==107.0
assert n["quality"]=="STAGING_ONLY_NOT_APPROVED"
assert n["freshness_status"]=="STAGING_SECOND_WEB_READ_REQUIRES_APPROVAL"
assert n["tenors"][0]["tenor"]=="2Y" and n["tenors"][0]["date"]=="2026-10-22"
assert n["tenors"][1]==live["NZD"]["tenors"][1], "5Y not updated by a 2Y/10Y source"
for tenor,k in (("2Y","history2"),("10Y","history10")):
    series=n[k];ds=series["dates"];vs=series["values"]
    assert len(ds)==len(vs) and ds==sorted(set(ds)) and ds[-1]=="2026-10-22"
    assert series["last_date"]==ds[-1] and series["last_value"]==n[tenor]
    prior_map=dict(zip(live["NZD"][k]["dates"],live["NZD"][k]["values"]))
    new_map=dict(zip(ds,vs))
    assert all(new_map[day]==value for day,value in prior_map.items()), "cannot rewrite canonical history"
    assert new_map["2026-10-15"]=={"2Y":3.81,"10Y":4.94}[tenor]
    assert new_map["2026-10-22"]=={"2Y":3.91,"10Y":4.98}[tenor]
try:
    check_approved_live(draft,reg)
except ValueError:pass
else:raise AssertionError("draft bypassed canonical approval validator")
assert check_approved_live(live,reg)["as_of"]=="2026-10-16"

def refuse(change):
    a,b,c,d,e=copy.deepcopy((first,second,prior,live,reg))
    change(a,b,c,d,e)
    try:build(a,b,c,d,e)
    except ValueError:return
    raise AssertionError("missing fail-closed check")
refuse(lambda a,b,c,d,e:b["source_rows"][-1].update({"2Y":3.92}))
refuse(lambda a,b,c,d,e:b["source_rows"][0].update({"10Y":5.05}))
refuse(lambda a,b,c,d,e:b.update(independent_xlsx_review_completed=True))
refuse(lambda a,b,c,d,e:b.update(independent_human_reviewer_confirmed=True))
refuse(lambda a,b,c,d,e:b.update(manual_approval_reference="https://github.com/example/pr/1"))
refuse(lambda a,b,c,d,e:b.update(live_data_promotion_allowed=True))
refuse(lambda a,b,c,d,e:b.update(column_locations={"date":0,"two_year":9,"ten_year":11}))
refuse(lambda a,b,c,d,e:b.update(source_url="https://other.example/interest-rates"))
refuse(lambda a,b,c,d,e:d["NZD"]["history2"]["dates"].append("2026-10-23"))
refuse(lambda a,b,c,d,e:e["currencies"]["NZD"].update(automatic_promotion_allowed=True))
refuse(lambda a,b,c,d,e:c["observations"][-1].update({"10Y":5.02}))
print("NZD_B2_SECOND_WEB_READ_DRAFT_EVIDENCE_AND_NO_PROMOTION_PASS")
