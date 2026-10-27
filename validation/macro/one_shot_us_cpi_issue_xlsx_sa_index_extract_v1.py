#!/usr/bin/env python3
"""Read-only issuer-month CPI-U SA index + historical 12M base extraction.

Uses only actual official BLS issue-month XLSX bytes acquired by one-shot
retrieval in /tmp. No current-revised CPIAUCSL, NSA headline, interpolation,
ALFRED page value, or missing October 2025 data may substitute for a
publisher source workbook; late-2026 downloads are not proven original bytes
as served in the historical release instant.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MONTHS = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,
          "Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}

def need(cond,why):
    if not cond: raise ValueError("BLS_ORIGINAL_ISSUE_XLSX_INDEX_REJECTED: "+why)

def cell_value(c, shared):
    value=c.find(X+"v")
    inline=c.find(X+"is")
    if inline is not None:
        return "".join(t.text or "" for t in inline.iter(X+"t"))
    if value is None: return ""
    raw=value.text or ""
    if c.get("t")=="s":
        return shared[int(raw)]
    return raw

def read_candidate_index(raw,period):
    with ZipFile(__import__("io").BytesIO(raw)) as source:
        need("xl/sharedStrings.xml" in source.namelist()
             and "xl/worksheets/sheet1.xml" in source.namelist(),
             "issuer US worksheet and shared strings required")
        root=ET.fromstring(source.read("xl/sharedStrings.xml"))
        shared=["".join(t.text or "" for t in row.iter(X+"t")) for row in root]
        root=ET.fromstring(source.read("xl/worksheets/sheet1.xml"))
        rows={}
        for row in root.iter(X+"row"):
            if row.get("r") in ("1","4","5","8"):
                rows[row.get("r")]={re.match(r"[A-Z]+",c.get("r","")).group():
                                   cell_value(c,shared)
                                   for c in row.findall(X+"c")}
        need(all(x in rows for x in ("1","4","5","8")),
             "BLS complete US sheet and first All items row required")
        title=rows["1"].get("B","")
        need("Consumer Price Index for All Urban Consumers" in title
             and "U.S. city average" in title
             and rows["8"].get("B")=="All items",
             "wrong BLS CPI-U source, city or index row")
        year,month=map(int,period.split("-"))
        issue_month=["January","February","March","April","May","June","July",
                     "August","September","October","November","December"][month-1]
        need(f"{issue_month} {year}" in title, "current BLS workbook issue month mismatch")
        cols={}
        for column,label in rows["4"].items():
            if label != "Seasonally adjusted indexes": continue
            monthheader=rows["5"].get(column,"").replace("\n"," ")
            mo=re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*(20\d\d)",monthheader)
            if mo:
                key=f"{int(mo.group(2)):04d}-{MONTHS[mo.group(1)]:02d}"
                need(key not in cols,"duplicate month in SA index group")
                cols[key]=column
        need(period in cols,"missing exact monthly SA index column")
        current_index=rows["8"].get(cols[period],"")
        need(re.fullmatch(r"\d{3}(?:\.\d+)?",current_index) is not None,
             "missing current numeric issuer SA CPI-U index")
        value=Decimal(current_index).quantize(Decimal("0.001"),rounding=ROUND_HALF_UP)
        need(Decimal("100")<=value<=Decimal("500"), "SA index range")
        previous=f"{(year*12+month-1-12)//12:04d}-{(year*12+month-1-12)%12+1:02d}"
        base_col=cols.get(previous)
        base_raw=rows["8"].get(base_col,"") if base_col else ""
        base=None
        yoy=None
        if base_raw and re.fullmatch(r"\d{3}(?:\.\d+)?",base_raw):
            base=Decimal(base_raw).quantize(Decimal("0.001"),rounding=ROUND_HALF_UP)
            yoy=((value/base-1)*100).quantize(Decimal("0.000001"),rounding=ROUND_HALF_UP)
        return {"economic_month":period,"current_index_SA":str(value),
                "same_issue_vintage_12mo_base":str(base) if base is not None else None,
                "same_issue_vintage_SA_index_yoy_pct":str(yoy) if yoy is not None else None,
                "SA_columns_present":len(cols),"BLS_source_title":title,
                "BLS_series_semantic":"CUSR0000SA0_BLS_SA_ALL_ITEMS_CPI_U",
                "issue_day_xlsx_vintage_original_download_proven":False,
                "NSA_index_mistaken_for_SA":False}

def main():
    out=Path("/tmp/bls_cpi_research_probe")
    receipt=json.loads((out/"receipt.json").read_text(encoding="utf-8"))
    need(receipt.get("schema")=="GMFQ_MACRO_V2_US_CPI_BLS_ALFRED_BYTES_ONE_SHOT_PROBE_V1",
         "source transport receipt must precede extraction")
    root=Path(__file__).resolve().parents[2]
    register=json.loads((root/"validation/macro/fixtures/v2_bls_us_cpi_25_month_first_news_release_ledger_2026_10_27.json").read_text(encoding="utf-8"))
    by_month={x["reference_month"]:x for x in register["records"]}
    result=[]
    for period,original in by_month.items():
        if period=="2025-10":
            result.append({"economic_month":period,"status":"BLS_ALL_ITEMS_NOT_PUBLISHED_SHUTDOWN",
                           "issuer_SA_index_value":None,"original_issuer_first_index_certified":False})
            continue
        item=next((x for x in receipt["results"] if x["target"]=="bls_cpi_u_"+period.replace("-","")),None)
        if item is None or item.get("download_sha256") is None:
            result.append({"economic_month":period,"status":"OFFICIAL_XLSX_NOT_ACQUIRED",
                           "issuer_SA_index_value":None,"original_issuer_first_index_certified":False,
                           "transport_status":item.get("http_status") if item else None})
            continue
        p=out/"raw_research_sources"/("bls_cpi_u_"+period.replace("-","")+".xlsx")
        raw=p.read_bytes()
        need(hashlib.sha256(raw).hexdigest()==item["download_sha256"],
             "source workbook SHA-256 must match actual transport bytes")
        extract=read_candidate_index(raw,period)
        need(original["publisher_release_day"] is not None,
             "issuer exact dated release evidence required")
        extract.update({
          "status":"ISSUE_MONTH_BLS_SA_INDEX_CANDIDATE_RETRIEVED_OCT2026_NOT_ORIGINAL_DAY_BYTES",
          "issuer_release_day":original["publisher_release_day"],
          "download_sha256":item["download_sha256"],
          "downloaded_bytes":item["downloaded_bytes"],
          "source_url":item["url"],
          "original_issuer_first_index_certified":False
        })
        result.append(extract)
        print("ISSUE_SA_INDEX: "+json.dumps(extract,sort_keys=True),flush=True)
    observed=[x for x in result if "current_index_SA" in x]
    need(len(result)==25 and sum(x["economic_month"]=="2025-10"
         and x["issuer_SA_index_value"] is None for x in result)==1,
         "October gap must be preserved")
    out_json={"schema":"GMFQ_MACRO_V2_US_CPI_ISSUE_MONTH_XLSX_SA_INDEX_CANDIDATES_V1",
              "acquisition_day_utc":datetime.now(timezone.utc).date().isoformat(),
              "status":"LATE_CAPTURED_PUBLISHER_ISSUE_MONTH_XLSX_NOT_HISTORIC_SOURCE_DAY_SHA",
              "source_months":result,
              "summary":{"published_calendar_months":24,
                         "issuer_xlsx_current_sa_index_candidates":len(observed),
                         "same_issue_12month_base_available":sum(x["same_issue_vintage_12mo_base"] is not None for x in observed),
                         "BLS_original_issuer_day_bytes_captured":0,
                         "BLS_model_PIT_certified":0},
              "safe_to_publish_new_D":False,
              "safe_to_change_28_pairs":False,"safe_for_beta":False,
              "safe_for_forward":False,"writes_live_data":False}
    (out/"issuer_index_candidates.json").write_text(json.dumps(out_json,indent=2)+"\n",encoding="utf-8")
    print("ISSUE_CPI_SUMMARY: "+json.dumps(out_json["summary"],sort_keys=True),flush=True)

if __name__=="__main__":
    main()
