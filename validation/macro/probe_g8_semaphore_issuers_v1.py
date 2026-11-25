#!/usr/bin/env python3
"""Read-only technical source probe. Never materializes market values to live data."""
from __future__ import annotations
import json, csv, io, urllib.request
from urllib.error import HTTPError
from zipfile import ZipFile
from openpyxl import load_workbook

URLS={
 "CH_SECO_GDP_CSV":"https://scheduler.swissdatas.ch/scheduled/ch-seco-gdp.csv",
 "CH_SECO_GDP_META":"https://scheduler.swissdatas.ch/scheduled/ch-seco-gdp.json",
 "ABS_REAL_HOUSEHOLD_TABLE15":"https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/sep-2026/5682015.xlsx",
 "NZALT_BNZ_PSI":"https://www.bnz.co.nz/institutional-banking/research/publications",
 "NZALT_BNZ_ECONOMY":"https://www.bnz.co.nz/institutional-banking/research/publications/economy-watch",
 "NZALT_STAT_HOUSE":"https://www.stats.govt.nz/topics/building/",
 "NZALT_STAT_RELEASE":"https://www.stats.govt.nz/information-releases/building-consents-issued-September-2026/",
 "NZALT_STAT_ALT":"https://stats.govt.nz/information-releases/building-consents-issued-september-2026/",
 "NZALT_STAT_BULK":"https://www.stats.govt.nz/large-datasets/csv-files-for-download/",
 "NZALT_INFOSHARE":"https://infoshare.stats.govt.nz/",
 "NZALT_RBNZ_EN":"https://www.rbnz.govt.nz/en/statistics/series/lending-and-monetary/registered-banks-and-non-bank-lending-institutions-sector-lending",
 "NZALT_RBNZ_C50":"https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/depository-corporations-money-and-credit-aggregates",
 "NZALT_TE_HOUSE":"https://tradingeconomics.com/new-zealand/building-permits-mom",
 "NZALT_TE_CREDIT":"https://tradingeconomics.com/new-zealand/private-sector-credit",
 "NZALT_FRED_HOUSE":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=NZLODCNPI03GPSAM",
 "NZALT_FRED_HOUSE2":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=ODCNPI03NZM657S",
 "NZALT_FRED_PRICE":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=QNZR368BIS",
 "NZALT_FRED_CREDIT":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=QNZPBMXDCA",
 "EUROSTAT_EA21":"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?geo=EA21&indic_bt=BPRM_DW&cpa2_1=CPA_F41001&s_adj=SCA&unit=I21&lang=EN",
 "EUROSTAT_EA20":"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?geo=EA20&indic_bt=BPRM_DW&cpa2_1=CPA_F41001&s_adj=SCA&unit=I21&lang=EN",
 "EUROSTAT_EA21_ALL_RESIDENTIAL_CODES":"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?geo=EA21&indic_bt=BPRM_DW&s_adj=SCA&unit=I21&lang=EN",
 "RBNZ_C5_FILE":"https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/c/c5/hc5.xlsx",
 "RBNZ_C5_WWW":"https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/c/c5/hc5.xlsx",
 "SNB_CREDIT_LEGACY":"https://data.snb.ch/api/cube/bakredinausbm/data/csv/en?fromDate=2025-01",
 "SNB_CREDIT_META":"https://data.snb.ch/api/cube/bakredinausbm/dimensions/en",
 "RBNZ_HOUSING":"https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m10/hm10.xlsx",
 "RBNZ_EXPECTATIONS":"https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m15/hm15.xlsx",
 "STATCAN_MANUFACTURING":"https://www150.statcan.gc.ca/n1/tbl/csv/16100047-eng.zip",
 "BUSINESSNZ_PSI_LATEST":"https://businessnz.org.nz/psi/pre-election-drinks",
 "BUSINESSNZ_PSI_INDEX":"https://businessnz.org.nz/psi",
 "ABS_SPENDING_SERVICES":"https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/latest-release",
}
def _coverage(doc):
    ids=doc.get("id",[])
    if "cpa2_1" not in ids:return {}
    cats=doc.get("dimension",{}).get("cpa2_1",{}).get("category",{}).get("index",{})
    sizes=doc.get("size",[])
    out={}
    values=doc.get("value",{})
    for code,index in cats.items():
        sample=[]
        for num,v in values.items():
            ordinal=int(num)
            coordinates={}
            for dim,size in zip(ids[::-1],sizes[::-1]):
                coordinates[dim]=ordinal%size;ordinal//=size
            if coordinates.get("cpa2_1")==index:
                time_keys=list(doc["dimension"]["time"]["category"]["index"])
                ix=coordinates["time"]
                if 0<=ix<len(time_keys):sample.append((time_keys[ix],v))
        out[code]={"count":len(sample),"last":sorted(sample)[-4:]}
    return out

def call(name,url):
 try:
  r=urllib.request.Request(url,headers={"User-Agent":"FX-Quant-Macro-Research/1.0"})
  with urllib.request.urlopen(r,timeout=18) as x:
   data=x.read(28_000_000+1)
   if len(data)>28_000_000: return {"error":"file above 28MB budget"}
   if name=="CH_SECO_GDP_META":
    doc=json.loads(data)
    return {"source":doc.get("source_name"),"unit":doc.get("units"),"dim_order":doc.get("dim_order"),"seas_adj":doc.get("labels",{}).get("seas_adj"),"structure":{k:v.get("en") for k,v in doc.get("labels",{}).get("structure",{}).items()}}
   if name=="CH_SECO_GDP_CSV":
    decoded=data.decode("utf-8-sig")
    delim=csv.Sniffer().sniff(decoded[:4096],delimiters=",;\t").delimiter
    rows=list(csv.DictReader(io.StringIO(decoded),delimiter=delim))
    fields=list(rows[0]) if rows else []
    if not fields:return {"error":"empty CSV"}
    dims={k:sorted({str(row.get(k,"")) for row in rows})[:75] for k in fields if k.lower() in {"type","structure","seas_adj"}}
    groups={}
    for row in rows:
     key=tuple(row.get(k) for k in fields if k.lower() in {"type","structure","seas_adj"})
     if not key:continue
     groups[key]=row
    sample=[v for k,v in groups.items() if "gc_q" in k and any(x in k for x in ("trade","transp","com","findl","b_serv","health","admin","hotel","edu","entertain","other_serv","hh_prod"))]
    return {"bytes":len(data),"fields":fields,"dims":dims,"head":rows[:3],"tail":rows[-3:],"contribution_sample":sample[:20]}
   if name=="ABS_REAL_HOUSEHOLD_TABLE15":
    book=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
    sheets=[]
    for ws in book.worksheets:
     rows=list(ws.iter_rows(min_row=1,max_row=12,values_only=True))
     columns=[]
     for j,col in enumerate(zip(*rows),1):
      labels=[str(v) for v in col if v is not None]
      if j==1 or any("seasonally adjusted" in v.lower() or "series id" in v.lower() for v in labels):
       columns.append({"col":j,"meta":labels})
     sheets.append({"name":ws.title,"rows":ws.max_row,"cols":ws.max_column,"series":columns[:30],
       "last":[[str(v) if v is not None else None for v in row[:8]] for row in ws.iter_rows(min_row=max(1,ws.max_row-3),max_row=ws.max_row,values_only=True)]})
    return {"bytes":len(data),"sheets":sheets}
   if name.startswith("NZALT_"):
    import re
    from html.parser import HTMLParser
    class Plain(HTMLParser):
     def __init__(self):super().__init__();self.parts=[]
     def handle_data(self,s):self.parts.append(s)
    raw=data.decode("utf-8","replace");parser=Plain();parser.feed(raw)
    plain=" ".join(" ".join(parser.parts).split())
    terms=["The PSI for", "New dwellings consented", "Seasonally adjusted", "Annual growth rate", "Private sector credit","Building Permits","Private Sector Credit","BLDM.SFTZ1100A1S"]
    tables=[]
    if "STAT_" in name:
     from collect_g8_semaphore_gaps_v1 import _ReportTables
     t=_ReportTables();t.feed(raw)
     tables=[{"head":tab[:4],"tail":tab[-3:],"rows":len(tab)} for tab in t.tables[:12]]
    return {"bytes":len(data),"url":x.geturl(),"type":x.headers.get("Content-Type"),"tables":tables,
     "matches":{k:plain[max(0,plain.find(k)-50):plain.find(k)+600] for k in terms if k in plain},
     "links":[m for m in re.findall(r'href=["\x27]([^"\x27]+)',raw,re.I) if "building-consents" in m.lower() or "bld" in m.lower() or "psi" in m.lower()][:12],
     "tail":raw[-400:] if name.startswith("NZALT_FRED") else ""}
   if name.startswith("BUSINESSNZ") or name.startswith("ABS_"):
    txt=data.decode("utf-8","replace")
    terms=["PSI Time Series Table","BNZ – BusinessNZ PSI",
            "BNZ - BusinessNZ PSI","Household spending on services, current price, seasonally adjusted estimate"]
    return {"bytes":len(data),"tables":txt.lower().count("<table"),
       "fragments":{term:txt[max(0,txt.find(term)-350):txt.find(term)+1600]
                    for term in terms if txt.find(term)>=0},
       "psi_href_sample":__import__('re').findall(r"href=[\\x22\\x27]([^\\x22\\x27]*/psi/[^\\x22\\x27]+)[\\x22\\x27]",txt)[:10]}
   if name.startswith("SNB_"):
    text=data.decode("utf-8-sig","replace")
    return {"bytes":len(data),"content_type":x.headers.get("Content-Type"),"head":text[:4500],"tail":text[-3500:]}
   if name.startswith("EUROSTAT"):
    doc=json.loads(data)
    return {"status":x.status,"value_count":len(doc.get("value",{})),"code_coverage":_coverage(doc), "id":doc.get("id"),"size":doc.get("size"),
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
 from concurrent.futures import ThreadPoolExecutor
 with ThreadPoolExecutor(max_workers=5) as pool:
  results=pool.map(lambda kv:(kv[0],call(*kv)),URLS.items())
  for key,result in results:
   print(key,json.dumps(result,ensure_ascii=False)[:9500] if key.startswith("NZALT_") else json.dumps(result,ensure_ascii=False)[:5500],flush=True)
