#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from pathlib import Path

OUT=Path("validation/pit_batch/eurostat")
OUT.mkdir(parents=True, exist_ok=True)
BASE="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

SPECS={
 "EA_IP":{
   "dataset":"EI_IS_M_VTG",
   "runtime_id":"EA_IP_history_value",
   "filters":{"freq":"M","s_adj":"SCA","nace_r2":"B-D","unit":"RT1","geo":"EA","sinceTimePeriod":"2021-01"},
   "category":"Crescita",
   "value_semantics":"Monthly growth rate on previous period, seasonally and calendar adjusted."
 },
 "EA_UNEMP":{
   "dataset":"EI_LM_M_VTG",
   "runtime_id":"EA_UNEMP_history_value",
   "filters":{"freq":"M","unit":"PC_ACT","s_adj":"SA","sex":"T","age":"TOTAL","geo":"EA","sinceTimePeriod":"2021-01"},
   "category":"Lavoro",
   "value_semantics":"Seasonally adjusted unemployment rate, total sex/age, percentage of labour force."
 }
}

def fetch(dataset,params):
    q=urllib.parse.urlencode({"lang":"en",**params})
    url=BASE+dataset+"?"+q
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
    with urllib.request.urlopen(req,timeout=180) as r:
        return url,json.loads(r.read().decode("utf-8"))

def ordered_codes(obj,dim):
    d=obj["dimension"][dim]["category"]
    idx=d.get("index",{})
    if isinstance(idx,dict):
        return [k for k,v in sorted(idx.items(), key=lambda kv: kv[1])]
    return list(idx)

def flat_index(coords,sizes):
    pos=0
    for c,sz in zip(coords,sizes):
        pos=pos*sz+c
    return pos

def first_release_rows(obj):
    ids=obj["id"]; sizes=obj["size"]; val=obj.get("value",{}) or {}
    rev_codes=ordered_codes(obj,"revdate")
    time_codes=ordered_codes(obj,"time")
    rpos=ids.index("revdate"); tpos=ids.index("time")
    fixed=[0]*len(ids)
    out=[]
    for ti,t in enumerate(time_codes):
        hits=[]
        for ri,r in enumerate(rev_codes):
            coords=fixed.copy(); coords[rpos]=ri; coords[tpos]=ti
            ix=str(flat_index(coords,sizes))
            if ix in val:
                hits.append((r,val[ix]))
        if hits:
            hits.sort(key=lambda x:x[0])
            r,v=hits[0]
            out.append({"observation_month":t,"first_release_date":r,"first_release_value":v,"vintage_count":len(hits)})
    return out

report={"schema":"GMFQ_EUROSTAT_PIT_BATCH_V1","created_at":"2026-10-02","series":{}}
for key,spec in SPECS.items():
    url,obj=fetch(spec["dataset"],spec["filters"])
    rows=first_release_rows(obj)
    report["series"][key]={
      "dataset":spec["dataset"],"runtime_id":spec["runtime_id"],"category":spec["category"],
      "source_url":url,"filters":spec["filters"],"value_semantics":spec["value_semantics"],
      "rows":rows,
      "qa":{
        "rows":len(rows),
        "start":rows[0]["observation_month"] if rows else None,
        "end":rows[-1]["observation_month"] if rows else None,
        "first_release_start":rows[0]["first_release_date"] if rows else None,
        "first_release_end":rows[-1]["first_release_date"] if rows else None
      }
    }

(OUT/"EUROSTAT_PIT_BATCH_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:v["qa"] for k,v in report["series"].items()},indent=2))
