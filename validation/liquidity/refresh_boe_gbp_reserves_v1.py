#!/usr/bin/env python3
"""BoE weekly sterling reserve balances — verified official research only.

Source: Bank of England Weekly Report, Sterling Liabilities / Reserves balances,
matching IADB RPWB56A. The current and prior weekly figures are reported
side-by-side by the issuer, in GBP millions (not daily flows or commercial credit).

This collector never updates G8 native sources, FX rankings or market pricing.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/"site/fx-quant-v2/next/gbp-boe-reserves-research-v1.js"
CANON=ROOT/"live_data/sections/NATIVE_LIQ_DATA.json"
INDEX="https://www.bankofengland.co.uk/weekly-report/balance-sheet-and-weekly-report"
SCHEMA="GMFQ_NEXT_GBP_BOE_WEEKLY_RESERVES_V1"
SERIES="RPWB56A"
ANCHOR_DATE="2026-09-16"
ANCHOR_VALUE=638012
MONTHS={name.lower():n for n,name in enumerate(("","January","February","March","April",
"May","June","July","August","September","October","November","December")) if n}
DATE_PATTERN=r"(\d{1,2})\s+("+"|".join(MONTHS)+r")\s+(\d{4})"

def require(ok,why):
    if not ok:raise ValueError("BOE_GBP_RESERVES_WITHHELD: "+why)

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words=[]
        self.links=[]
        self.active_link=None
        self.tables=[]
        self.in_table=False
        self.row=None
        self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.active_link={"href":dict(attrs).get("href",""),"parts":[]}
        if tag=="table":self.in_table=True
        if tag=="tr" and self.in_table:self.row=[]
        if tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        self.words.append(data)
        if self.active_link is not None:self.active_link["parts"].append(data)
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell=None
        if tag=="tr" and self.row is not None:
            self.tables.append(self.row)
            self.row=None
        if tag=="table":self.in_table=False
        if tag=="a" and self.active_link is not None:
            self.active_link["text"]=" ".join("".join(self.active_link["parts"]).split())
            self.links.append(self.active_link)
            self.active_link=None
    @property
    def text(self):return " ".join(" ".join(self.words).split())

def fetch(url):
    parsed=urllib.parse.urlsplit(url)
    require(parsed.scheme=="https" and parsed.hostname=="www.bankofengland.co.uk" and
            parsed.path.startswith("/weekly-report/"),
            "official BoE path required")
    request=urllib.request.Request(url,headers={
        "Accept":"text/html","User-Agent":"FXQuant-Official-Source-Research/1.0"})
    with urllib.request.urlopen(request,timeout=30) as response:
        location=urllib.parse.urlsplit(response.geturl())
        require(location.scheme=="https" and location.hostname=="www.bankofengland.co.uk" and
                location.path.startswith("/weekly-report/"),
                "unexpected issuer redirect")
        raw=response.read(2_000_001)
    require(len(raw)<2_000_001,"unexpected large BoE document")
    return raw.decode("utf-8",errors="replace")

def latest_link(html,*,today):
    parser=Page();parser.feed(html);parser.close()
    matches=[]
    for item in parser.links:
        url=urllib.parse.urljoin(INDEX,item["href"])
        p=urllib.parse.urlsplit(url)
        if p.scheme!="https" or p.hostname!="www.bankofengland.co.uk":continue
        m=re.fullmatch(r"/weekly-report/(\d{4})/(\d{1,2})-([a-z]+)-(\d{4})/?",p.path.lower())
        if not m:continue
        year,day,month,year2=m.groups()
        month_number=MONTHS.get(month)
        if year!=year2 or month_number is None:continue
        when=date(int(year),month_number,int(day))
        if when.weekday()!=2 or when>today:continue
        matches.append((when,url))
    require(matches,"no official BoE weekly report links detected")
    when,url=max(matches,key=lambda a:a[0])
    require((today-when).days<=21,"index is stale or links failed to refresh")
    return when,url

def month_date(day,month,year):
    n=MONTHS.get(month.lower())
    require(n is not None,"unknown English month in issuer date")
    return date(int(year),n,int(day))

def balance(s):
    raw=s.replace("\xa0","").strip()
    require(re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+",raw) is not None,
            "reserve balance not an issuer integer amount")
    n=int(raw.replace(",",""))
    require(300000<n<1400000,"reserve level outside plausible BoE stock range")
    return n

def parse_report(html,expected,source_url,*,today):
    page=Page();page.feed(html);page.close()
    txt=page.text
    require("Weekly report" in txt or "Weekly Report" in txt,
            "BoE weekly report title not found")
    require("Reserves balances" in txt and
            ("Sterling Liabilities" in txt or "Sterling liabilities" in txt),
            "reserve liability meaning absent")
    pub=re.search(r"Published on\s+"+DATE_PATTERN,txt,re.I)
    require(pub is not None,"BoE issue publication date not present")
    published=month_date(*pub.groups())
    require(expected<=published<=today,"publication timing inconsistent with observation")
    require((published-expected).days<=7,"observation/publication gap not plausible")
    require(expected.strftime("%d %B %Y").lstrip("0") in txt or
            expected.strftime("%d-%m-%Y") in txt or
            expected.strftime("%d/%m/%Y") in txt,
            "official report header does not match selected Wednesday")
    require("£mn" in txt or "£ mn" in txt or "£ million" in txt,
            "sterling millions unit not verified")
    candidates=[row for row in page.tables if len(row)>=3 and
                " ".join(row[0].split()).lower()=="reserves balances"]
    require(len(candidates)==1,"reserve liability row not uniquely identified")
    current,previous=map(balance,candidates[0][1:3])
    previous_date=expected-timedelta(days=7)
    require(previous_date.strftime("%d %B %Y").lstrip("0") in txt or
            previous_date.strftime("%d-%m-%Y") in txt or
            previous_date.strftime("%d/%m/%Y") in txt,
            "prior Wednesday date not independently identified")
    move=current-previous
    require(abs(move)<150000 and abs(move)/previous<.25,
            "unexplained reserve-stock weekly discontinuity")
    return {
      "source_period":expected.isoformat(),
      "previous_period":previous_date.isoformat(),
      "published_on":published.isoformat(),
      "latest_balance_million_gbp":current,
      "previous_balance_million_gbp":previous,
      "weekly_change_million_gbp":move,
      "source_url":source_url
    }

def guard_canonical():
    native=json.loads(CANON.read_text(encoding="utf-8"))["GBP"]["liquidity"]
    require(native["last_date"]==ANCHOR_DATE and native["last_value"]==ANCHOR_VALUE,
            "canonical GBP liquidity anchor changed; revalidate source overlap")
    require(native["dates"][-1]==ANCHOR_DATE and native["values"][-1]==ANCHOR_VALUE,
            "canonical GBP weekly source history changed")

def emit_js(x,checked):
    data={
      "schema":SCHEMA,
      "status":"VERIFIED_BOE_WEEKLY_RESERVE_STOCK_RESEARCH_ONLY",
      "country":"GBP","publisher":"Bank of England",
      "source_index":INDEX,
      "series_id":SERIES,
      "source_contract":"BoE Weekly Report / Sterling Liabilities / Reserves balances",
      "frequency":"W","unit":"milioni GBP",
      "seasonally_adjusted":False,
      "asof_canonical_overlap":ANCHOR_DATE,
      "value_canonical_overlap":ANCHOR_VALUE,
      "last_checked_rome":checked,
      **x,
      "observation_is_not_publication_date":True,
      "first_release_pit_verified":False,
      "eligible_for_fx_core":False,"eligible_for_backtest":False,
      "inference":"Reserves balances: stock of BoE liabilities held by banks; not new credit, not net liquidity to markets, not observed GBP flows. Weekly issuer reports both values."
    }
    return ("'use strict';\n/* Issuer-verified Bank of England sterling reserves, research only. */\n"
      "(function(root){\n const data="+json.dumps(data,ensure_ascii=False,indent=1)+";\n"
      " root.FXQuantGBPBoEReservesResearch=Object.freeze(data);\n"
      " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
      "})(typeof window!=='undefined'?window:globalThis);\n")

def previous(text):
    found={}
    for key in ("source_period","latest_balance_million_gbp",
                "previous_balance_million_gbp","weekly_change_million_gbp"):
        m=re.search(r"['\"]?"+key+r"['\"]?\s*:\s*(\"[^\"]*\"|-?\d+)",text)
        if not m:return None
        found[key]=json.loads(m.group(1))
    return found

def run(*,destination=DEST,index_fixture=None,report_fixture=None,today=None,apply=False):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    guard_canonical()
    homepage=Path(index_fixture).read_text(encoding="utf-8") if index_fixture else fetch(INDEX)
    expected,url=latest_link(homepage,today=today)
    report=Path(report_fixture).read_text(encoding="utf-8") if report_fixture else fetch(url)
    data=parse_report(report,expected,url,today=today)
    old=previous(destination.read_text(encoding="utf-8")) if destination.exists() else None
    require(old is None or data["source_period"]>=old["source_period"],
            "BoE source unexpectedly rolled back to an earlier observation")
    comparable={k:data[k] for k in ("source_period","latest_balance_million_gbp",
                     "previous_balance_million_gbp","weekly_change_million_gbp")}
    status="NO_CHANGE" if old==comparable else "UPDATE_AVAILABLE"
    receipt={
      "schema":"GMFQ_BOE_WEEKLY_GBP_RESERVES_RECEIPT_V1",
      "status":status,
      "source_url":url,
      "source_period":data["source_period"],
      "published_on":data["published_on"],
      "latest_balance_million_gbp":data["latest_balance_million_gbp"],
      "previous_balance_million_gbp":data["previous_balance_million_gbp"],
      "weekly_change_million_gbp":data["weekly_change_million_gbp"],
      "source_contract":SERIES,
      "last_checked_rome":today.isoformat(),
      "observation_not_release_time":True,
      "canonical_liquidity_unchanged":True,
      "fx_ranking_effect":"NONE",
      "write_state":"NO_MUTATION"}
    if apply and status=="UPDATE_AVAILABLE":
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(data,today.isoformat()),encoding="utf-8")
        receipt["write_state"]="RESEARCH_SIDECAR_ONLY"
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--index-fixture",type=Path)
    p.add_argument("--report-fixture",type=Path)
    p.add_argument("--destination",type=Path,default=DEST)
    p.add_argument("--receipt",type=Path)
    args=p.parse_args()
    try:
        result=run(destination=args.destination,index_fixture=args.index_fixture,
                   report_fixture=args.report_fixture,apply=args.apply)
    except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
        result={"schema":"GMFQ_BOE_WEEKLY_GBP_RESERVES_RECEIPT_V1",
                "status":"WITHHELD_SOURCE_UNAVAILABLE_OR_UNVERIFIED",
                "reason":str(exc)[:320],
                "write_state":"NO_MUTATION",
                "canonical_liquidity_unchanged":True,"fx_ranking_effect":"NONE"}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__":main()
