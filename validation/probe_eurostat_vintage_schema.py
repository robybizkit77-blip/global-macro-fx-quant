#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from pathlib import Path

OUT=Path("validation/pit_batch/eurostat")
OUT.mkdir(parents=True, exist_ok=True)

DATASETS=["EI_IS_M_VTG","EI_LM_M_VTG","EI_IS_M_VTGFIX","EI_LM_M_VTGFIX"]
BASE="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

def fetch(dataset):
    params=urllib.parse.urlencode({"lang":"en","time":"2021-01"})
    url=BASE+dataset+"?"+params
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        raw=r.read()
    return url,json.loads(raw.decode("utf-8"))

def compact(dataset,obj,url):
    ids=obj.get("id",[])
    sizes=obj.get("size",[])
    dim=obj.get("dimension",{})
    dims=[]
    for name in ids:
        cat=((dim.get(name) or {}).get("category") or {})
        idx=cat.get("index") or {}
        lab=cat.get("label") or {}
        # keep only first 120 categories per dimension
        if isinstance(idx,dict):
            keys=list(idx.keys())
        elif isinstance(idx,list):
            keys=idx
        else:
            keys=[]
        sample=[]
        for k in keys[:120]:
            sample.append({"code":k,"label":lab.get(k)})
        dims.append({
          "id":name,
          "size":sizes[ids.index(name)] if name in ids and ids.index(name)<len(sizes) else None,
          "label":(dim.get(name) or {}).get("label"),
          "sample_categories":sample
        })
    return {
      "dataset":dataset,
      "url":url,
      "label":obj.get("label"),
      "updated":obj.get("updated"),
      "id":ids,
      "size":sizes,
      "dimensions":dims,
      "value_count":len(obj.get("value",{}) or {})
    }

report={"schema":"GMFQ_EUROSTAT_VINTAGE_SCHEMA_PROBE_V1","created_at":"2026-10-02","datasets":{}}
for ds in DATASETS:
    try:
        url,obj=fetch(ds)
        report["datasets"][ds]=compact(ds,obj,url)
    except Exception as e:
        report["datasets"][ds]={"dataset":ds,"error":repr(e)}
(OUT/"EUROSTAT_VINTAGE_SCHEMA_PROBE_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:{"id":v.get("id"),"size":v.get("size"),"value_count":v.get("value_count"),"error":v.get("error")} for k,v in report["datasets"].items()},indent=2))
