#!/usr/bin/env python3
"""US Federal Reserve H.8 bank credit via FRED TOTBKCR, research only.

Official Fed publisher, FRED data mirror. Weekly Wednesday, billions USD
seasonally adjusted. Revisable stock, NOT new loan originations, NOT macro
surprise, NOT observed FX flows. Strictly isolated from NATIVE_LIQ_DATA.
"""
from __future__ import annotations
import argparse
import ast
import csv
import io
import json
import math
import re
import sys
import urllib.request
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/"site/fx-quant-v2/next/us-h8-bank-credit-research-v1.js"
API="https://fred.stlouisfed.org/graph/fredgraph.csv?id=TOTBKCR&cosd=2026-06-01"
PUBLIC="https://fred.stlouisfed.org/series/TOTBKCR"
SERIES="TOTBKCR"
ANCHOR_DATE="2026-09-09"
ANCHOR_VALUE=19866.6568
SCHEMA="GMFQ_NEXT_US_H8_CREDIT_RESEARCH_V1"

def require(ok,why):
    if not ok:
        raise ValueError("US_H8_FRED_SOURCE_WITHHELD: "+why)

def fetch():
    req=urllib.request.Request(API,headers={
        "Accept":"text/csv","User-Agent":"FX-Quant-Research-Sources/1.0"})
    with urllib.request.urlopen(req,timeout=30) as response:
        require(response.geturl().startswith("https://fred.stlouisfed.org/graph/"),
                "unexpected redirect host")
        raw=response.read(1_000_001)
    require(len(raw)<1_000_001,"unexpected large source payload")
    return raw.decode("utf-8-sig")

def parse(text,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    rows=list(csv.DictReader(io.StringIO(text)))
    require(len(rows)>=10,"source has insufficient weekly history")
    columns=set(rows[0])
    date_key="observation_date" if "observation_date" in columns else "DATE"
    require(date_key in columns and SERIES in columns,"exact series/CSV key mismatch")
    observations=[]
    for row in rows:
        ds=row.get(date_key),raw=row.get(SERIES)
        token,datum=ds
        require(isinstance(token,str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",token),
                "invalid weekly observation date")
        if datum is None or datum.strip() in (".",""):
            continue
        try:
            num=float(datum)
        except (TypeError,ValueError) as exc:
            raise ValueError("US_H8_FRED_SOURCE_WITHHELD: nonnumeric value") from exc
        when=date.fromisoformat(token)
        require(when.weekday()==2,"week ending Wednesday violated")
        require(15000<num<35000 and math.isfinite(num),"bank-credit stock outside plausible series range")
        observations.append((when,round(num,4)))
    require(len(observations)>=10,"too few finite weekly observations")
    original_dates=[x[0] for x in observations]
    ordered=sorted(observations,key=lambda x:x[0])
    require(original_dates in ([x[0] for x in ordered],list(reversed([x[0] for x in ordered]))),
            "nonmonotonic official observations")
    require(len(set(original_dates))==len(observations),"duplicate FRED date")
    anchor=dict((d.isoformat(),v) for d,v in ordered).get(ANCHOR_DATE)
    require(anchor is not None,"canonical reference week not found in official series")
    revision=(anchor/ANCHOR_VALUE-1)
    require(abs(revision)<.02,"canonical vs FRED official source diverges >2% on matching week")
    for i,(day,val) in enumerate(ordered[1:],1):
        prev,previous=ordered[i-1]
        require(7<=(day-prev).days<=21 and (day-prev).days%7==0,"unexplained weekly gap")
        require(abs(val/previous-1)<.10,"unexplained 10% week-to-week stock jump")
    recent=ordered[-1][0]
    require(recent>=date(2026,9,9) and recent<=today,"source latest date out of scope")
    require((today-recent).days<=35,"source period too old to claim successful update")
    window=ordered[-72:]
    return {"dates":[d.isoformat() for d,_ in window],
            "values":[v for _,v in window],
            "latest_observation":recent.isoformat(),
            "reference_week_revision_pct":round(100*revision,4)}

def existing_obs(txt):
    dt=re.search(r"['\"]?dates['\"]?\s*:\s*(\[[^\]]*\])",txt)
    v=re.search(r"['\"]?values['\"]?\s*:\s*(\[[^\]]*\])",txt)
    if not dt or not v:return None
    try:return ast.literal_eval(dt.group(1)),ast.literal_eval(v.group(1))
    except (SyntaxError,ValueError):return None

def emit_js(data,checked):
    obj={
      "schema":SCHEMA,
      "status":"VERIFIED_FED_H8_FRED_MIRROR_RESEARCH_ONLY",
      "country":"USD",
      "publisher":"Board of Governors of the Federal Reserve System (US)",
      "mirror":"FRED (Federal Reserve Bank of St. Louis)",
      "series_id":SERIES,"source_url":PUBLIC,"api_url":API,
      "label":"Bank Credit, All Commercial Banks",
      "category":"bank_credit_stock","unit":"miliardi USD",
      "frequency":"W","seasonally_adjusted":True,
      "first_release_pit_verified":False,
      "eligible_for_fx_core":False,"eligible_for_backtest":False,
      "observation_is_not_publication_date":True,
      "last_checked_rome":checked,
      "latest_observation":data["latest_observation"],
      "reference_week_revision_pct":data["reference_week_revision_pct"],
      "dates":data["dates"],"values":data["values"],
      "inference":"Stock Fed H.8 rivisto via FRED; non nuovi prestiti, prestiti originati o easing automatico. Ricerca separata dalla serie canonica."
    }
    return ("'use strict';\n/* Validated Fed H.8 source via FRED; research-only. */\n"
        "(function(root){\n const data="+json.dumps(obj,ensure_ascii=False,indent=1)
        +";\n root.FXQuantUSBanksCreditResearch=Object.freeze(data);\n"
        " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
        "})(typeof window!=='undefined'?window:globalThis);\n")

def run(destination=DEST,*,apply=False,fixture=None,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    parsed=parse(Path(fixture).read_text(encoding="utf-8") if fixture else fetch(),today=today)
    before=existing_obs(destination.read_text(encoding="utf-8")) if destination.exists() else None
    state="NO_CHANGE" if before==(parsed["dates"],parsed["values"]) else "UPDATE_AVAILABLE"
    receipt={
      "schema":"GMFQ_US_H8_FRED_CREDIT_SOURCE_RECEIPT_V1","status":state,
      "series":SERIES,"source":PUBLIC,"latest_observation":parsed["latest_observation"],
      "series_count":len(parsed["dates"]),"canonical_reference_revision_pct":parsed["reference_week_revision_pct"],
      "retrieved_on_rome":today.isoformat(),"first_release_verified":False,
      "canonical_liquidity_unchanged":True,"fx_rank_effect":"NONE",
      "write_state":"NO_MUTATION"}
    if apply and state=="UPDATE_AVAILABLE":
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(parsed,today.isoformat()),encoding="utf-8")
        receipt["write_state"]="RESEARCH_SIDECAR_ONLY"
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--fixture",type=Path)
    p.add_argument("--destination",type=Path,default=DEST)
    p.add_argument("--receipt",type=Path)
    args=p.parse_args()
    try:
        receipt=run(args.destination,apply=args.apply,fixture=args.fixture)
    except (OSError,TimeoutError,ValueError,UnicodeError) as error:
        receipt={"schema":"GMFQ_US_H8_FRED_CREDIT_SOURCE_RECEIPT_V1",
                 "status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE",
                 "reason":str(error)[:320],
                 "write_state":"NO_MUTATION","canonical_liquidity_unchanged":True,
                 "fx_rank_effect":"NONE"}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))
    if receipt["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__":
    main()
