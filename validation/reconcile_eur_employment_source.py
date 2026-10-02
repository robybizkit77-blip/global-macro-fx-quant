#!/usr/bin/env python3
import json,re,urllib.parse,urllib.request
from pathlib import Path

OUT=Path("validation/pit_batch/eurostat")
OUT.mkdir(parents=True,exist_ok=True)

# Parse runtime series directly from production payload.
txt=Path("payload/part-01.txt").read_text(encoding="utf-8")
m=re.search(r'\{"id":"EA_EMPLOYMENT_history_value".*?\}',txt)
if not m:
    raise SystemExit("runtime employment series not found")
runtime=json.loads(m.group(0))
runtime_map=dict(zip(runtime.get("dates",[]),runtime.get("values",[])))

BASE="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/namq_10_pe"
def get(params):
    url=BASE+"?"+urllib.parse.urlencode(params,doseq=True)
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return url,json.load(r)

# Probe a narrow current slice first to learn exact dimension codes.
url_probe,probe=get({"lang":"en","freq":"Q","unit":"THS_PER","s_adj":"SCA","sinceTimePeriod":"2016-Q1"})
dims=probe.get("id",[])
sizes=probe.get("size",[])
dim_meta={}
for d in dims:
    cat=probe.get("dimension",{}).get(d,{}).get("category",{})
    idx=cat.get("index",{})
    lab=cat.get("label",{})
    codes=sorted(idx,key=lambda k: idx[k]) if isinstance(idx,dict) else []
    dim_meta[d]=[{"code":x,"label":lab.get(x)} for x in codes]

na_items=[x["code"] for x in dim_meta.get("na_item",[])]
geos=[x["code"] for x in dim_meta.get("geo",[])]
# Keep euro-area aggregates only; test all available employment concepts.
ea_geos=[g for g in geos if g.startswith("EA")]
candidates=[]
for geo in ea_geos:
  for item in na_items:
    try:
      url,j=get({"lang":"en","freq":"Q","unit":"THS_PER","s_adj":"SCA","geo":geo,"na_item":item,"sinceTimePeriod":"2016-Q1"})
    except Exception as e:
      candidates.append({"geo":geo,"na_item":item,"error":str(e)})
      continue
    ids=j.get("id",[]); size=j.get("size",[])
    timecat=j.get("dimension",{}).get("time",{}).get("category",{})
    tidx=timecat.get("index",{})
    times=sorted(tidx,key=lambda k:tidx[k]) if isinstance(tidx,dict) else []
    vals=j.get("value",{})
    # With all non-time dims filtered, positions should map directly to time.
    series=[]
    for i,t in enumerate(times):
      v=vals.get(str(i)) if isinstance(vals,dict) else None
      if v is not None:
        series.append((t,float(v)))
    if not series:
      continue
    smap=dict(series)
    common=sorted(set(runtime_map)&set(smap))
    diffs=[abs(float(runtime_map[t])-float(smap[t])) for t in common if runtime_map[t] is not None]
    exact=sum(1 for t in common if abs(float(runtime_map[t])-float(smap[t]))<1e-9)
    candidates.append({
      "geo":geo,"na_item":item,
      "label":next((x["label"] for x in dim_meta.get("na_item",[]) if x["code"]==item),None),
      "url":url,
      "rows":len(series),
      "first":series[0] if series else None,
      "last":series[-1] if series else None,
      "common":len(common),
      "exact":exact,
      "max_abs_diff":max(diffs) if diffs else None,
      "mean_abs_diff":sum(diffs)/len(diffs) if diffs else None
    })

valid=[x for x in candidates if x.get("common",0)>0]
valid.sort(key=lambda x:(-(x.get("exact") or 0), x.get("max_abs_diff") if x.get("max_abs_diff") is not None else 1e99, -(x.get("common") or 0)))
best=valid[0] if valid else None
status="EXACT_RUNTIME_SOURCE_MATCH_VERIFIED" if best and best.get("exact")==best.get("common") and best.get("common",0)>=20 else "NO_EXACT_MATCH_YET"
report={
 "schema":"GMFQ_EUR_EMPLOYMENT_SOURCE_RECONCILIATION_V1",
 "created_at":"2026-10-02",
 "runtime":{"id":runtime.get("id"),"unit":runtime.get("unit"),"frequency":runtime.get("frequency"),"rows":len(runtime_map),"first":next(iter(runtime_map.items())) if runtime_map else None,"last":list(runtime_map.items())[-1] if runtime_map else None},
 "probe_url":url_probe,
 "dimensions":dim_meta,
 "tested_candidates":len(candidates),
 "status":status,
 "best_match":best,
 "top_matches":valid[:12],
 "guardrail":"Do not reconstruct PIT employment releases until exact current-series identity is proven."
}
(OUT/"EUR_EMPLOYMENT_SOURCE_RECONCILIATION_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"status":status,"best_match":best,"tested":len(candidates)},indent=2))
