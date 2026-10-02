#!/usr/bin/env python3
import io, json, os, re, sys, zipfile
from pathlib import Path
from urllib.request import Request, urlopen
import pandas as pd

OUT=Path("validation/raw_structured")
OUT.mkdir(parents=True, exist_ok=True)

SOURCES={
 "CAD_GDP":{"url":"https://www150.statcan.gc.ca/n1/tbl/csv/36100491-eng.zip","runtime_id":"CA_REAL_GDP_M_history_value"},
 "CAD_RETAIL":{"url":"https://www150.statcan.gc.ca/n1/tbl/csv/20100082-eng.zip","runtime_id":"CA_RETAIL_VOLUME_history_value"},
}

def dl(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 GMFQ-validation/1.0"})
    with urlopen(req, timeout=120) as r:
        return r.read()

def csv_from_zip(blob):
    z=zipfile.ZipFile(io.BytesIO(blob))
    names=[n for n in z.namelist() if n.lower().endswith(".csv")]
    data=[n for n in names if "metadata" not in n.lower()]
    if not data: raise RuntimeError("no csv in zip")
    # Prefer the largest CSV; StatCan full-table ZIP usually contains data + metadata.
    name=max(data,key=lambda n:z.getinfo(n).file_size)
    with z.open(name) as f:
        return pd.read_csv(f, low_memory=False), name

def norm(s): return str(s).strip().lower()

def col(df,*needles):
    for c in df.columns:
        lc=norm(c)
        if all(n in lc for n in needles): return c
    return None

def summarize(df):
    info={"rows":len(df),"columns":list(df.columns)}
    dims={}
    for c in df.columns:
        if df[c].dtype=="object":
            vals=df[c].dropna().astype(str).unique()
            if len(vals)<=30:
                dims[c]=vals[:30].tolist()
    info["small_dimensions"]=dims
    return info

def filter_gdp(df):
    x=df.copy()
    # geography
    c=col(x,"geo")
    if c is not None:
        m=x[c].astype(str).str.contains("^Canada",case=False,regex=True,na=False)
        if m.any(): x=x[m]
    # All industries
    cand=[c for c in x.columns if "industry" in norm(c) or "naics" in norm(c)]
    for c in cand:
        m=x[c].astype(str).str.contains("All industries",case=False,na=False)
        if m.any(): x=x[m]; break
    # seasonally adjusted
    c=next((c for c in x.columns if "seasonal" in norm(c)),None)
    if c:
        m=x[c].astype(str).str.contains("seasonally adjusted",case=False,na=False)
        if m.any(): x=x[m]
    # volume/chained dollars
    c=next((c for c in x.columns if "price" in norm(c)),None)
    if c:
        m=x[c].astype(str).str.contains("chained|volume",case=False,regex=True,na=False)
        if m.any(): x=x[m]
    # 2020 onward by REF_DATE or reference period when available
    rc=next((c for c in x.columns if norm(c)=="ref_date" or "reference period" in norm(c)),None)
    if rc:
        m=x[rc].astype(str).str.extract(r"(\d{4})",expand=False)
        x=x[pd.to_numeric(m,errors="coerce")>=2020]
    return x

def filter_retail(df):
    x=df.copy()
    c=col(x,"geo")
    if c is not None:
        m=x[c].astype(str).str.contains("^Canada",case=False,regex=True,na=False)
        if m.any(): x=x[m]
    # prefer total retail / all stores if such a dimension exists
    for c in x.columns:
        lc=norm(c)
        if "industry" in lc or "retail trade" in lc or "store" in lc:
            s=x[c].astype(str)
            m=s.str.contains("Total|All retail|Retail trade \[",case=False,regex=True,na=False)
            if m.any(): x=x[m]; break
    # volume measure
    for c in x.columns:
        lc=norm(c)
        if "measure" in lc or "price" in lc or "sales" in lc:
            s=x[c].astype(str)
            m=s.str.contains("volume|chained",case=False,regex=True,na=False)
            if m.any(): x=x[m]; break
    rc=next((c for c in x.columns if norm(c)=="ref_date" or "reference period" in norm(c)),None)
    if rc:
        m=x[rc].astype(str).str.extract(r"(\d{4})",expand=False)
        x=x[pd.to_numeric(m,errors="coerce")>=2020]
    return x

report={"schema":"GMFQ_CAD_STRUCTURED_VINTAGE_RAW_EXTRACT_V1","sources":{}}
for name,spec in SOURCES.items():
    blob=dl(spec["url"])
    df,csvname=csv_from_zip(blob)
    raw_summary=summarize(df)
    sel=filter_gdp(df) if name=="CAD_GDP" else filter_retail(df)
    outcsv=OUT/f"{name}_2020_2026_candidate.csv"
    sel.to_csv(outcsv,index=False)
    report["sources"][name]={
      "runtime_id":spec["runtime_id"],"url":spec["url"],"zip_bytes":len(blob),
      "csv_member":csvname,"raw":raw_summary,
      "candidate_rows":len(sel),"candidate_columns":list(sel.columns),
      "candidate_file":str(outcsv)
    }

(OUT/"CAD_STRUCTURED_VINTAGE_RAW_EXTRACT_V1.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:{"candidate_rows":v["candidate_rows"],"zip_bytes":v["zip_bytes"]} for k,v in report["sources"].items()},indent=2))
