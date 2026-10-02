#!/usr/bin/env python3
import json, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

OUT=Path("validation/pit_batch/eurostat")
OUT.mkdir(parents=True, exist_ok=True)

URL="https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all/latest?detail=allstubs"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
with urllib.request.urlopen(req,timeout=120) as r:
    xml=r.read()

root=ET.fromstring(xml)
flows=[]
for el in root.iter():
    if not el.tag.endswith("Dataflow"): 
        continue
    fid=el.attrib.get("id")
    names=[]
    for ch in el.iter():
        if ch.tag.endswith("Name") and (ch.text or "").strip():
            names.append((ch.text or "").strip())
    title=" | ".join(dict.fromkeys(names))
    hay=((fid or "")+" "+title).lower()
    if any(k in hay for k in ["retail","employment","employed","negotiated wage","negotiated wages","wage"]):
        flows.append({"id":fid,"title":title})

retail=[x for x in flows if "retail" in (x["id"]+" "+x["title"]).lower()]
employment=[x for x in flows if any(k in (x["id"]+" "+x["title"]).lower() for k in ["employment","employed"])]
wages=[x for x in flows if "wage" in (x["id"]+" "+x["title"]).lower()]

report={
  "schema":"GMFQ_EUR_REMAINING_CORE_DATAFLOW_DISCOVERY_V1",
  "created_at":"2026-10-02",
  "targets":{
    "EA_RETAIL_VOL_history_value":{"provider":"Eurostat","candidates":retail},
    "EA_EMPLOYMENT_history_value":{"provider":"Eurostat","candidates":employment},
    "EA_NEGOTIATED_WAGES_YOY_history_value":{"provider":"ECB","eurostat_wage_candidates":wages}
  },
  "counts":{"retail":len(retail),"employment":len(employment),"wages":len(wages)},
  "note":"Negotiated wages is expected to remain an ECB-source match; Eurostat wage matches are only cross-check candidates."
}
(OUT/"EUR_REMAINING_CORE_DATAFLOW_DISCOVERY_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["counts"],indent=2))
for k,arr in [("retail",retail),("employment",employment),("wages",wages)]:
    print("\n##",k)
    for x in arr[:40]:
        print(x["id"],"=>",x["title"][:180])
