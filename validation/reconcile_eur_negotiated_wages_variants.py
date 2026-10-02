#!/usr/bin/env python3
import csv,io,json,re,urllib.request
from pathlib import Path

OUT=Path("validation/pit_batch/ecb/EUR_NEGOTIATED_WAGES_VARIANT_RECONCILIATION_V1_2026-10-02.json")
RUNTIME={
"2016-Q1":1.3,"2016-Q2":1.33,"2016-Q3":1.42,"2016-Q4":1.39,
"2017-Q1":1.53,"2017-Q2":1.43,"2017-Q3":1.44,"2017-Q4":1.49,
"2018-Q1":1.77,"2018-Q2":2.23,"2018-Q3":2.14,"2018-Q4":2.11,
"2019-Q1":2.25,"2019-Q2":1.98,"2019-Q3":2.58,"2019-Q4":1.99,
"2020-Q1":1.95,"2020-Q2":1.68,"2020-Q3":1.61,"2020-Q4":1.93,
"2021-Q1":1.34,"2021-Q2":1.6,"2021-Q3":1.14,"2021-Q4":1.35,
"2022-Q1":3.01,"2022-Q2":2.56,"2022-Q3":3.05,"2022-Q4":3.15,
"2023-Q1":4.27,"2023-Q2":4.4,"2023-Q3":4.71,"2023-Q4":4.51,
"2024-Q1":4.85,"2024-Q2":3.69,"2024-Q3":5.51,"2024-Q4":4.21,
"2025-Q1":2.51,"2025-Q2":4.04,"2025-Q3":1.99,"2025-Q4":2.94,
"2026-Q1":2.57,"2026-Q2":2.45
}
SERIES={
 "EA20_FIXED":"Q.I9.N.INWR.000000.4F0.GY.IX",
 "EA_CHANGING":"Q.U2.N.INWR.000000.4F0.GY.IX",
 "EA21_FIXED":"Q.I10.N.INWR.000000.4F0.GY.IX"
}

def fetch(key):
    url="https://data-api.ecb.europa.eu/service/data/INW/"+key+"?startPeriod=2016-Q1&format=csvdata"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/2.0","Accept":"text/csv"})
    with urllib.request.urlopen(req,timeout=120) as r:
        raw=r.read().decode("utf-8","replace")
    out={}
    for row in csv.DictReader(io.StringIO(raw)):
        p=row.get("TIME_PERIOD") or row.get("TIME PERIOD")
        v=row.get("OBS_VALUE") or row.get("OBS VALUE")
        if p and v not in (None,""):
            try: out[p]=float(v)
            except: pass
    return url,out

def score(obs):
    common=sorted(set(RUNTIME)&set(obs))
    diffs=[abs(RUNTIME[p]-obs[p]) for p in common]
    exact=[p for p in common if abs(RUNTIME[p]-obs[p])<1e-9]
    close=[p for p in common if abs(RUNTIME[p]-obs[p])<=0.011]
    return {
      "common":len(common),
      "exact":len(exact),
      "within_0_01pp":len(close),
      "max_abs_diff_pp":round(max(diffs),6) if diffs else None,
      "mean_abs_diff_pp":round(sum(diffs)/len(diffs),6) if diffs else None,
      "tail":[{"period":p,"runtime":RUNTIME[p],"candidate":obs[p],"diff":round(RUNTIME[p]-obs[p],6)}
              for p in common[-10:]]
    }

results={}
for name,key in SERIES.items():
    try:
        url,obs=fetch(key)
        results[name]={"series_key":"INW."+key,"url":url,"score":score(obs),
                       "start":min(obs) if obs else None,"end":max(obs) if obs else None}
    except Exception as e:
        results[name]={"series_key":"INW."+key,"error":str(e)}

valid=[(n,x["score"]["mean_abs_diff_pp"],-x["score"]["common"]) for n,x in results.items() if "score" in x and x["score"]["mean_abs_diff_pp"] is not None]
best=sorted(valid,key=lambda z:(z[1],z[2]))[0][0] if valid else None
report={
 "schema":"GMFQ_EUR_NEGOTIATED_WAGES_VARIANT_RECONCILIATION_V1",
 "created_at":"2026-10-02",
 "runtime_id":"EA_NEGOTIATED_WAGES_YOY_history_value",
 "candidates":results,
 "best_current_variant":best,
 "interpretation":"Variant identity test only. Even an exact current-series match does not make revised history point-in-time; release vintages must still be reconstructed or certified.",
 "guardrail":"Do not promote negotiated wages to PIT_READY from this test alone."
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"best":best,"scores":{k:v.get("score") for k,v in results.items()}},indent=2))
