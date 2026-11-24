#!/usr/bin/env python3
"""Read-only, bounded schema discovery for high-value official G8 datasets."""
from __future__ import annotations
import collections,csv,io,json,zipfile,urllib.request
from datetime import date

TABLES={
 "CAN_RETAIL_REAL":"https://www150.statcan.gc.ca/n1/tbl/csv/20100067-eng.zip",
 "CAN_CREDIT_HOUSE":"https://www150.statcan.gc.ca/n1/tbl/csv/36100639-eng.zip",
 "CAN_CREDIT_BUSINESS":"https://www150.statcan.gc.ca/n1/tbl/csv/36100640-eng.zip",
}
FRED={
 "CHF_INDUSTRY":"PRMNTO01CHQ657S",
 "CHF_HOUSE":"QCHN628BIS",
 "CHF_CREDIT":"QCHNAMUSDA",
 "AUD_JOBS":"LFEMTTTTAUQ647S",
 "JPN_CREDIT":"QJPPBMUSDA",
 "JPN_HOUSE":"JPNWSCNDW01MLSAM",
 "JPN_INDUSTRY":"JPNPROINDMISMEI",
 "CAN_RETAIL":"CANSLRTTO01GPSAM",
 "NZD_RETAIL":"NZLSLRTTO01GPSAM",
 "AUD_CREDIT":"QAUPBMUSDA",
 "CAN_CREDIT":"QCAPBMUSDA",
 "JPN_RETAIL":"JPNSLRTTO01GPSAM",
}
def get(url,max_size=25_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":"GMFQ-Research/1.0"})
    with urllib.request.urlopen(req,timeout=22) as r:
        payload=r.read(max_size+1)
        if not payload or len(payload)>max_size:raise ValueError("oversized or empty")
        return payload
def probe_fred(label,code):
    try:
        txt=get("https://fred.stlouisfed.org/graph/fredgraph.csv?id="+code,3_000_000).decode("utf-8-sig")
        reader=csv.DictReader(io.StringIO(txt))
        if code not in (reader.fieldnames or []):return {"error":"source id header mismatch","header":reader.fieldnames}
        obs=[(r[reader.fieldnames[0]],r[code]) for r in reader if r[code] not in (".","")]
        return {"valid":len(obs),"last":obs[-5:],"head":reader.fieldnames}
    except Exception as e:return {"error":str(e)[:160]}
def probe_statcan(label,url):
    try:
        payload=get(url,38_000_000)
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            options=[n for n in z.namelist() if n.endswith(".csv") and "MetaData" not in n]
            if not options:return {"error":"no data CSV","members":z.namelist()[:12]}
            f=next((n for n in options if n.rsplit("/",1)[-1]==url.rsplit("/",1)[-1].replace("-eng.zip",".csv")),options[0])
            with z.open(f) as handle:
                r=csv.DictReader(io.TextIOWrapper(handle,encoding="utf-8-sig",errors="replace"))
                cols=r.fieldnames or []
                dims={k:collections.Counter() for k in cols if k not in {"VALUE","VECTOR","COORDINATE","DECIMALS","TERMINATED","STATUS","DGUID","REF_DATE"}}
                sample=[];hit=0
                for i,row in enumerate(r):
                    if i>=18000:break
                    if row.get("GEO","Canada")!="Canada":continue
                    if len(sample)<2:sample.append(row)
                    for k in dims:dims[k][row.get(k,"")]+=1
                    hit+=1
                return {"bytes":len(payload),"members":z.namelist()[:5],"sample_rows":sample,
                    "rows_scanned":hit,"columns":cols,"dimension_examples":{
                    k:v.most_common(18) for k,v in dims.items()}}
    except Exception as e:return {"error":type(e).__name__+": "+str(e)[:170]}
if __name__=="__main__":
    for k,v in FRED.items():print("FRED",k,json.dumps(probe_fred(k,v))[:450])
    for k,v in TABLES.items():print("STATCAN",k,json.dumps(probe_statcan(k,v))[:10000])
