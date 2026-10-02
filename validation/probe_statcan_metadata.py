#!/usr/bin/env python3
import json, urllib.request
from pathlib import Path

OUT=Path("validation/statcan_metadata")
OUT.mkdir(parents=True, exist_ok=True)

URL="https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata"
PIDS=[36100491,20100082]

def post(payload):
    data=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(URL,data=data,headers={
        "Content-Type":"application/json",
        "User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"
    },method="POST")
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def compact(obj):
    x=obj[0]["object"] if isinstance(obj,list) and obj and "object" in obj[0] else obj
    dims=[]
    for d in x.get("dimension",[]) or x.get("dimensions",[]):
        members=[]
        for m in d.get("member",[])[:500]:
            members.append({
                "memberId":m.get("memberId"),
                "memberNameEn":m.get("memberNameEn"),
                "classificationCode":m.get("classificationCode"),
                "terminated":m.get("terminated"),
                "memberUomCode":m.get("memberUomCode")
            })
        dims.append({
            "dimensionPositionId":d.get("dimensionPositionId"),
            "dimensionNameEn":d.get("dimensionNameEn"),
            "hasUom":d.get("hasUom",d.get("hasUOM")),
            "members":members
        })
    return {
        "productId":x.get("productId"),
        "cubeTitleEn":x.get("cubeTitleEn"),
        "cubeStartDate":x.get("cubeStartDate"),
        "cubeEndDate":x.get("cubeEndDate"),
        "nbSeriesCube":x.get("nbSeriesCube"),
        "nbDatapointsCube":x.get("nbDatapointsCube"),
        "releaseTime":x.get("releaseTime"),
        "archiveStatusEn":x.get("archiveStatusEn"),
        "issueDate":x.get("issueDate"),
        "dimensions":dims
    }

report={"schema":"GMFQ_STATCAN_CUBE_METADATA_PROBE_V1","tables":{}}
for pid in PIDS:
    raw=post([{"productId":pid}])
    c=compact(raw)
    report["tables"][str(pid)]=c
    (OUT/f"{pid}_metadata_compact.json").write_text(json.dumps(c,indent=2),encoding="utf-8")

(OUT/"STATCAN_CUBE_METADATA_PROBE_V1.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({
    pid:{
      "title":v["cubeTitleEn"],
      "series":v["nbSeriesCube"],
      "datapoints":v["nbDatapointsCube"],
      "dimensions":[{"name":d["dimensionNameEn"],"members":len(d["members"])} for d in v["dimensions"]]
    } for pid,v in report["tables"].items()
},indent=2))
