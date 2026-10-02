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
    agency=el.attrib.get("agencyID")
    version=el.attrib.get("version")
    names=[]
    for ch in el.iter():
        if ch.tag.endswith("Name") and (ch.text or "").strip():
            names.append((ch.text or "").strip())
    title=" | ".join(dict.fromkeys(names))
    hay=((fid or "")+" "+title).lower()
    if any(k in hay for k in ["vintage","real-time","real time","revision"]) or (
        "industrial" in hay and "production" in hay
    ) or "unemployment" in hay:
        flows.append({"id":fid,"agency":agency,"version":version,"title":title})

# Strong candidates are any dataflow whose id/title explicitly references vintage/revision/real-time.
strong=[x for x in flows if any(k in ((x["id"] or "")+" "+x["title"]).lower() for k in ["vintage","real-time","real time","revision"])]
ip=[x for x in flows if "industrial" in x["title"].lower() and "production" in x["title"].lower()]
unemp=[x for x in flows if "unemployment" in x["title"].lower()]

report={
 "schema":"GMFQ_EUROSTAT_DATAFLOW_DISCOVERY_V2",
 "created_at":"2026-10-02",
 "source":URL,
 "official_context":{
   "vintage_scope":["industrial production","unemployment","GDP"],
   "vintage_dimension":"revision date",
   "split_rule":"industrial production and unemployment use static older vintages through 2020 and updated vintages from 2021 onward"
 },
 "strong_candidates":strong,
 "industrial_production_candidates":ip,
 "unemployment_candidates":unemp,
 "counts":{"all_matches":len(flows),"strong":len(strong),"ip":len(ip),"unemployment":len(unemp)},
 "next_action":"Probe candidate dataflows for dimensions and select the exact euro-area industrial-production and unemployment vintage datasets."
}
(OUT/"EUROSTAT_DATAFLOW_DISCOVERY_V2_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["counts"],indent=2))
for x in strong[:50]:
    print(x["id"],"=>",x["title"][:180])
