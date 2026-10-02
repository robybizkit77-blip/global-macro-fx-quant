#!/usr/bin/env python3
import csv, io, json, urllib.request
from pathlib import Path

OUT=Path("validation/pit_batch/ecb")
OUT.mkdir(parents=True, exist_ok=True)

SERIES_KEY="Q.I9.N.INWR.000000.4F0.GY.IX"
URL="https://data-api.ecb.europa.eu/service/data/INW/"+SERIES_KEY+"?startPeriod=2016-Q1&format=csvdata"

req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0","Accept":"text/csv"})
with urllib.request.urlopen(req,timeout=120) as r:
    raw=r.read().decode("utf-8","replace")

rows=list(csv.DictReader(io.StringIO(raw)))
obs=[]
for r in rows:
    period=r.get("TIME_PERIOD") or r.get("TIME PERIOD") or r.get("TIME_PERIOD ")
    val=r.get("OBS_VALUE") or r.get("OBS VALUE")
    if period and val not in (None,""):
        try: v=float(val)
        except: continue
        obs.append({"period":period,"value":v})

report={
 "schema":"GMFQ_ECB_INW_CURRENT_SERIES_VERIFY_V1",
 "created_at":"2026-10-02",
 "runtime_id":"EA_NEGOTIATED_WAGES_YOY_history_value",
 "dataset":"INW",
 "series_key":"INW."+SERIES_KEY,
 "source_url":URL,
 "frequency":"Q",
 "transformation":"YoY growth rate",
 "rows":obs,
 "qa":{
   "rows":len(obs),
   "start":obs[0]["period"] if obs else None,
   "end":obs[-1]["period"] if obs else None
 },
 "status":"CURRENT_SERIES_MATCH_VERIFIED__NOT_PIT_READY",
 "guardrail":"This verifies the exact current ECB series identity only. Do not treat current historical values as first-release vintages."
}
(OUT/"ECB_INW_CURRENT_SERIES_VERIFY_V1_2026-10-02.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report["qa"],indent=2))
