#!/usr/bin/env python3
"""Official RBA financial aggregates: break-adjusted business-credit growth.

IMPORTANT RBA source distinction (Sep 2026 release):
* D2 credit stocks are NOT adjusted for breaks. Growth rates must NOT be
  computed from D2 stock levels.
* This publisher release provides adjusted monthly and year-ended changes.
* An observation month is different from the actual publication date.
* Research-only sidecar: NATIVE_LIQ_DATA, Core FX rankings untouched.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/"site/fx-quant-v2/next/aud-rba-business-credit-growth-research-v1.js"
BASE="https://www.rba.gov.au"
ARCHIVE="/statistics/frequency/fin-agg/{year}/"
SCHEMA="GMFQ_NEXT_AUD_RBA_BUSINESS_CREDIT_GROWTH_V1"
SOURCE="Reserve Bank of Australia"
MTH={m:i for i,m in enumerate([
 "","January","February","March","April","May","June","July","August",
 "September","October","November","December"]) if m}

def require(ok,why):
    if not ok: raise ValueError("RBA_AUD_GROWTH_WITHHELD: "+why)

class HTMLReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.tables=[]
        self.current_table=None
        self.current_row=None
        self.current_cell=None
        self.links=[]
        self.anchor=None
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if tag=="a":
            self.anchor={"href":data.get("href") or "","text":[]}
        if tag=="table":
            require(self.current_table is None,"unexpected nested release table")
            self.current_table=[]
        if tag=="tr" and self.current_table is not None:
            self.current_row=[]
        if tag in ("td","th") and self.current_row is not None:
            self.current_cell=[]
    def handle_data(self,data):
        self.parts.append(data)
        if self.current_cell is not None:self.current_cell.append(data)
        if self.anchor is not None:self.anchor["text"].append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.current_cell is not None:
            self.current_row.append(" ".join("".join(self.current_cell).split()))
            self.current_cell=None
        if tag=="tr" and self.current_row is not None:
            self.current_table.append(self.current_row)
            self.current_row=None
        if tag=="table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table=None
        if tag=="a" and self.anchor is not None:
            self.anchor["text"]=" ".join("".join(self.anchor["text"]).split())
            self.links.append(self.anchor)
            self.anchor=None
    @property
    def text(self):
        return " ".join(" ".join(self.parts).split())

def html_reader(html):
    h=HTMLReader()
    h.feed(html)
    h.close()
    return h

def get(url):
    parsed=urllib.parse.urlparse(url)
    require(parsed.scheme=="https" and parsed.netloc=="www.rba.gov.au",
            "nonofficial URL or host")
    req=urllib.request.Request(url,headers={"Accept":"text/html",
        "User-Agent":"FXQuant-Research-Sources/1.0"})
    with urllib.request.urlopen(req,timeout=25) as response:
        returned=urllib.parse.urlparse(response.geturl())
        require(returned.scheme=="https" and returned.netloc=="www.rba.gov.au",
                "unexpected RBA redirect")
        raw=response.read(1_500_001)
    require(len(raw)<1_500_001,"unexpected source size")
    return raw.decode("utf-8",errors="replace")

def latest_release_from_archive(html,year,*,today):
    page=html_reader(html)
    choices=[]
    for link in page.links:
        href=urllib.parse.urljoin(BASE+ARCHIVE.format(year=year),link["href"])
        url=urllib.parse.urlparse(href)
        if url.scheme!="https" or url.netloc!="www.rba.gov.au":continue
        m=re.fullmatch(r"/statistics/frequency/fin-agg/(\d{4})/fin-agg-(\d{2})(\d{2})\.html",url.path)
        if not m:continue
        yy,mm,short=map(int,m.groups())
        if yy!=year or yy%100!=short or not 1<=mm<=12:continue
        if (yy,mm)>(today.year,today.month):continue
        choices.append((yy,mm,href))
    require(len(choices)>0,"no official monthly release URLs in archive")
    yy,mm,url=max(choices)
    return {"period":f"{yy}-{mm:02}", "url":url}

def parse_release(html,*,expected_period,url,today):
    reader=html_reader(html)
    body=reader.text
    require("Financial Aggregates" in body,"not an official financial aggregates release")
    mat=re.search(r"\bRelease date\s*:\s*(\d{1,2})\s+("+
           "|".join(MTH)+r")\s+(\d{4})",body,re.IGNORECASE)
    require(mat is not None,"missing issuer publication date")
    dd=int(mat.group(1))
    mm=next((v for k,v in MTH.items() if k.lower()==mat.group(2).lower()),None)
    yy=int(mat.group(3))
    released=date(yy,mm,dd)
    require(released<=today,"future-dated or unpublished release")
    require("breaks in the series" in body.lower() and
            "growth rates should not be calculated from data on the levels of credit" in body.lower(),
            "mandatory break-adjustment disclaimer missing")
    require(expected_period[:4]==str(yy) or (released.year-1)==int(expected_period[:4]),
            "release year inconsistent with source period")
    months=[]
    for table in reader.tables:
        for row in table:
            if not row: continue
            label=row[0].strip().lower().lstrip("–-— ").strip()
            if label.startswith("business") and ("credit" not in label or len(label)<32):
                vals=[]
                for item in row[1:]:
                    v=item.replace(",","").strip()
                    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{1,2})?",v):
                        vals.append(float(v))
                if len(vals)==4:months.append(vals)
    require(len(months)==1,"RBA business-credit growth row not uniquely identified")
    before_mom,current_mom,old_yoy,current_yoy=months[0]
    require(all(math.isfinite(v) and -20<v<30 for v in months[0]),
            "outlier / malformed adjusted growth rate")
    require(-8<=before_mom<=8 and -8<=current_mom<=8,
            "monthly business-credit growth beyond safe bounds")
    require(expected_period in body or
            (next(name for name,index in MTH.items() if index==int(expected_period[5:]))+" "+expected_period[:4]) in body,
            "expected source observation month not present")
    return {
      "observation_period":expected_period,
      "release_date":released.isoformat(),
      "source_url":url,
      "monthly_growth_pct":current_mom,
      "prior_month_growth_pct":before_mom,
      "annual_growth_pct":current_yoy,
      "prior_year_growth_pct":old_yoy,
      "source_breaks_adjusted":True,
      "source_seasonally_adjusted":True
    }

def emit_js(data,checked):
    obj={
      "schema":SCHEMA,
      "status":"VERIFIED_RBA_FIN_AGG_BUSINESS_GROWTH_RESEARCH_ONLY",
      "country":"AUD","publisher":SOURCE,
      "source_archive":BASE+ARCHIVE.format(year=int(data["observation_period"][:4])),
      "source_url":data["source_url"],
      "label":"Business credit growth (non-financial businesses), break-adjusted",
      "category":"business_credit_growth_adjusted",
      "frequency":"M","unit":"percent",
      "source_table":"RBA Financial Aggregates — Business",
      "breaks_adjusted":True,
      "seasonally_adjusted":True,
      "is_credit_stock":False,
      "observation_is_not_publication_date":True,
      "first_release_pit_verified":False,
      "eligible_for_fx_core":False,"eligible_for_backtest":False,
      "last_checked_rome":checked,
      **{k:data[k] for k in ("observation_period","release_date",
       "monthly_growth_pct","prior_month_growth_pct",
       "annual_growth_pct","prior_year_growth_pct")},
      "inference":"Official adjusted monthly and year-ended business credit growth (D1 economic meaning); never infer this from D2 stocks, and no causal FX claim."
    }
    return ("'use strict';\n/* RBA official growth, source-dated, research-only. */\n"
      "(function(root){\n const data="+json.dumps(obj,ensure_ascii=False,indent=1)+";\n"
      " root.FXQuantAUDBusinessCreditGrowthResearch=Object.freeze(data);\n"
      " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
      "})(typeof window!=='undefined'?window:globalThis);\n")

def run(*,destination=DEST,today=None,archive_fixture=None,release_fixture=None,apply=False):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    release_year=today.year
    index=get(BASE+ARCHIVE.format(year=release_year)) if archive_fixture is None \
          else Path(archive_fixture).read_text(encoding="utf-8")
    ref=latest_release_from_archive(index,release_year,today=today)
    release=get(ref["url"]) if release_fixture is None \
          else Path(release_fixture).read_text(encoding="utf-8")
    parsed=parse_release(release,expected_period=ref["period"],url=ref["url"],today=today)
    earlier=destination.read_text(encoding="utf-8") if destination.exists() else ""
    changed=not earlier or not all(
        f'"{key}": {json.dumps(parsed[key])}' in earlier
        for key in ("observation_period","monthly_growth_pct",
                    "prior_month_growth_pct","annual_growth_pct",
                    "prior_year_growth_pct","release_date"))
    report={"schema":"GMFQ_AUD_RBA_BUSINESS_GROWTH_RECEIPT_V1",
            "status":"UPDATE_AVAILABLE" if changed else "NO_CHANGE",
            "publisher":SOURCE,"source":ref["url"],
            "observation_period":parsed["observation_period"],
            "release_date":parsed["release_date"],
            "monthly_growth_pct":parsed["monthly_growth_pct"],
            "prior_month_growth_pct":parsed["prior_month_growth_pct"],
            "annual_growth_pct":parsed["annual_growth_pct"],
            "prior_year_growth_pct":parsed["prior_year_growth_pct"],
            "checked_rome":today.isoformat(),
            "source_breaks_adjusted":True,
            "stock_levels_untouched":True,
            "canonical_liquidity_unchanged":True,
            "fx_rank_effect":"NONE","write_state":"NO_MUTATION"}
    if apply and changed:
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(parsed,today.isoformat()),encoding="utf-8")
        report["write_state"]="RESEARCH_SIDECAR_ONLY"
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--archive-fixture",type=Path)
    p.add_argument("--release-fixture",type=Path)
    p.add_argument("--destination",type=Path,default=DEST)
    p.add_argument("--receipt",type=Path)
    a=p.parse_args()
    try:
        r=run(destination=a.destination,apply=a.apply,
              archive_fixture=a.archive_fixture,
              release_fixture=a.release_fixture)
    except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
        r={"schema":"GMFQ_AUD_RBA_BUSINESS_GROWTH_RECEIPT_V1",
           "status":"WITHHELD_SOURCE_INACCESSIBLE_OR_UNVERIFIED",
           "reason":str(exc)[:320],"write_state":"NO_MUTATION",
           "canonical_liquidity_unchanged":True,"fx_rank_effect":"NONE"}
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        a.receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r,ensure_ascii=False))
    if r["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__": main()
