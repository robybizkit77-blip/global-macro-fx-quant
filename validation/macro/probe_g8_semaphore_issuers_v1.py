#!/usr/bin/env python3
"""Read-only technical source probe. Never materializes market values to live data."""
from __future__ import annotations
import json, csv, io, urllib.request
from urllib.error import HTTPError
from zipfile import ZipFile
from openpyxl import load_workbook

URLS={
 "EUROSTAT_EA21":"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?geo=EA21&indic_bt=BPRM_DW&cpa2_1=CPA_F41001&s_adj=SCA&unit=I21&lang=EN",
 "EUROSTAT_EA20":"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?geo=EA20&indic_bt=BPRM_DW&cpa2_1=CPA_F41001&s_adj=SCA&unit=I21&lang=EN",
 "RBNZ_HOUSING":"https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m10/hm10.xlsx",
 "RBNZ_EXPECTATIONS":"https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m15/hm15.xlsx",
 "STATCAN_MANUFACTURING":"https://www150.statcan.gc.ca/n1/tbl/csv/16100047-eng.zip",
}
def call(name,url):
 try:
  r=urllib.request.Request(url,headers={"User-Agent":"FX-Quant-Macro-Research/1.0"})
  with urllib.request.urlopen(r,timeout=18) as x:
   data=x.read(28_000_000+1)
   if len(data)>28_000_000: return {"error":"file above 28MB budget"}
   if name.startswith("EUROSTAT"):
    doc=json.loads(data)
    return {"status":x.status,"id":doc.get("id"),"size":doc.get("size"),
      "dims":{k:list(v.get("category",{}).get("index",{}).keys())[:25]
              for k,v in doc.get("dimension",{}).items()},
      "message":str(doc.get("error",""))[:500],"last_periods":list(doc.get("dimension",{}).get("time",{}).get("category",{}).get("index",{}))[-8:],"last_values":list(doc.get("value",{}).items())[-8:]}
   if name.startswith("RBNZ_"):
    book=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
    ret={"bytes":len(data),"sheets":[]}
    for ws in book.worksheets[:5]:
     sample=[]
     for row in ws.iter_rows(min_row=1,max_row=min(14,ws.max_row or 14),
                             max_col=min(16,ws.max_column or 16),values_only=True):
      sample.append([str(v)[:55] if v is not None else None for v in row])
     ret["sheets"].append({"name":ws.title,"max_row":ws.max_row,
         "max_col":ws.max_column,"head":sample})
    return ret
   if name=="STATCAN_MANUFACTURING":
    z=ZipFile(io.BytesIO(data));files=z.namelist()
    valid=[t for t in files if t.endswith(".csv") and not "MetaData" in t]
    if not valid:return {"files":files[:15],"error":"no csv"}
    with z.open(valid[0]) as src:
     h=io.TextIOWrapper(src,encoding="utf-8-sig",errors="replace")
     reader=csv.DictReader(h)
     sample=[]
     for i,row in enumerate(reader):
      if i>20000:break
      if str(row.get("GEO","")).strip()!="Canada":continue
      sample.append({k:v for k,v in row.items() if k!="VECTOR" and k!="COORDINATE"})
      if len(sample)>=5:break
     return {"bytes":len(data),"files":files[:10],"csv":valid[0],
             "fields":reader.fieldnames,"sample":sample}
 except HTTPError as e:
  return {"HTTP":e.code,"body":e.read(700).decode("utf-8","replace")}
 except Exception as e:
  return {"error":type(e).__name__,"detail":str(e)[:250]}

if __name__=="__main__":
 for key,url in URLS.items():
  print(key,json.dumps(call(key,url),ensure_ascii=False)[:5500])
