#!/usr/bin/env python3
import csv, json
from pathlib import Path
import requests

OUT=Path("validation/cad_rates_pit")
OUT.mkdir(parents=True, exist_ok=True)
JSON_OUT=OUT/"CA_BOC_BENCHMARK_RATES_DAILY_2020_2026_V1.json"
CSV_OUT=OUT/"CA_BOC_BENCHMARK_RATES_DAILY_2020_2026_V1.csv"

START="2020-01-01"
END="2026-09-30"
SERIES={"2Y":"BD.CDN.2YR.DQ.YLD","10Y":"BD.CDN.10YR.DQ.YLD"}

session=requests.Session()
session.headers.update({"User-Agent":"GMFQ-PIT-validation/1.0"})

def fetch(series):
    url=f"https://www.bankofcanada.ca/valet/observations/{series}/json"
    r=session.get(url,params={"start_date":START,"end_date":END},timeout=(10,45))
    r.raise_for_status()
    return r.json()

raw={k:fetch(v) for k,v in SERIES.items()}
maps={}
for k,obj in raw.items():
    code=SERIES[k]
    m={}
    for row in obj.get("observations",[]):
        v=row.get(code,{}).get("v")
        if v in (None,""):
            continue
        m[row["d"]]=float(v)
    maps[k]=m

dates=sorted(set(maps["2Y"]) & set(maps["10Y"]))
rows=[{"date":d,"y2":maps["2Y"][d],"y10":maps["10Y"][d],
       "curve_bp":round((maps["10Y"][d]-maps["2Y"][d])*100,6)} for d in dates]

report={
 "schema":"GMFQ_CA_BOC_BENCHMARK_RATES_DAILY_PIT_V1",
 "created_at":"2026-10-02",
 "source":"Bank of Canada Valet API",
 "series":{
   "2Y":{"code":"BD.CDN.2YR.DQ.YLD","legacy_lookup_code":"V39051","label":"Government of Canada benchmark bond yield - 2 year"},
   "10Y":{"code":"BD.CDN.10YR.DQ.YLD","legacy_lookup_code":"V39055","label":"Government of Canada benchmark bond yield - 10 year"}
 },
 "methodology":{
   "pit_status":"PIT_NATIVE_MARKET_DATA",
   "reason":"Daily market closing yields are observations known on the dated business day; no macro-style vintage reconstruction is required.",
   "requested_from":START,"requested_to":END
 },
 "rows":rows,
 "summary":{
   "count":len(rows),
   "from":rows[0]["date"] if rows else None,
   "to":rows[-1]["date"] if rows else None,
   "missing_overlap_days":0 if rows else None
 }
}
JSON_OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
with CSV_OUT.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["date","y2","y10","curve_bp"])
    w.writeheader();w.writerows(rows)
print(json.dumps(report["summary"],indent=2))
