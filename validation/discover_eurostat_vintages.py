#!/usr/bin/env python3
import io, json, re, urllib.request
from pathlib import Path

OUT=Path("validation/eurostat_discovery")
OUT.mkdir(parents=True, exist_ok=True)

URL="https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all/1.0?detail=allstubs"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
with urllib.request.urlopen(req,timeout=120) as r:
    xml=r.read().decode("utf-8","replace")

# Pull dataflow ids/titles with a lightweight regex; discovery only.
flows=[]
for m in re.finditer(r'<structure:Dataflow[^>]*id="([^"]+)"[\s\S]*?</structure:Dataflow>',xml):
    block=m.group(0)
    fid=m.group(1)
    names=re.findall(r'<common:Name[^>]*>([^<]+)</common:Name>',block)
    title=" | ".join(names[:3])
    hay=(fid+" "+title).lower()
    if any(k in hay for k in ["vintage","revision","unemployment","industrial production","industry","real-time","realtime"]):
        flows.append({"id":fid,"title":title})

# Keep all plausible real-time/vintage flows first, plus explicit industrial/unemployment candidates.
priority=[x for x in flows if any(k in (x["id"]+" "+x["title"]).lower() for k in ["vintage","revision","real-time","realtime"])]
fallback=[x for x in flows if any(k in (x["id"]+" "+x["title"]).lower() for k in ["unemployment","industrial production"])]
result={
  "schema":"GMFQ_EUROSTAT_VINTAGE_DATAFLOW_DISCOVERY_V1",
  "source":URL,
  "priority":priority[:200],
  "fallback":fallback[:200],
  "counts":{"priority":len(priority),"fallback":len(fallback)}
}
(OUT/"EUROSTAT_VINTAGE_DATAFLOW_DISCOVERY_V1.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result["counts"]))
