#!/usr/bin/env python3
"""US Federal Reserve H.8 bank credit and SLOOS via FRED, research only.

Official Fed publisher, FRED data mirror. H.8 is a revisable weekly stock in
billions USD, seasonally adjusted. SLOOS is a quarterly net percentage for
large and middle-market C&I borrowers. Both are isolated from NATIVE_LIQ_DATA.
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
M2_SERIES="M2SL"
M2_API="https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL&cosd=2024-01-01"
M2_PUBLIC="https://fred.stlouisfed.org/series/M2SL"
SLOOS_SERIES="DRTSCILM"
SLOOS_API="https://fred.stlouisfed.org/graph/fredgraph.csv?id=DRTSCILM&cosd=2024-01-01"
SLOOS_PUBLIC="https://fred.stlouisfed.org/series/DRTSCILM"

def require(ok,why):
    if not ok:
        raise ValueError("US_H8_FRED_SOURCE_WITHHELD: "+why)

def fetch(url=API):
    req=urllib.request.Request(url,headers={
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
        token=row.get(date_key)
        datum=row.get(SERIES)
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

def parse_sloos(text,*,today):
    rows=csv.DictReader(io.StringIO(text))
    date_key="observation_date" if "observation_date" in (rows.fieldnames or []) else "DATE"
    if rows.fieldnames!=[date_key,SLOOS_SERIES]:
        raise ValueError("SLOOS exact series/CSV key mismatch")
    observations=[]
    for row in rows:
        when=date.fromisoformat(row[date_key] or "")
        if when.day!=1 or when.month not in (1,4,7,10) or when>today:
            raise ValueError("SLOOS invalid survey period")
        datum=(row[SLOOS_SERIES] or "").strip()
        if datum in ("","."):
            continue
        net=float(datum)
        if not -100<=net<=100:
            raise ValueError("SLOOS net percentage outside range")
        if observations:
            previous=date.fromisoformat(observations[-1][0])
            if (when.year-previous.year)*12+when.month-previous.month!=3:
                raise ValueError("SLOOS quarterly ordering or gap")
        observations.append([when.isoformat(),net])
    if len(observations)<4:
        raise ValueError("SLOOS insufficient quarterly observations")
    if observations[-1][0]<"2026-10-01":
        raise ValueError("SLOOS series predates the verified October 2026 release")
    return {"series_id":SLOOS_SERIES,"source_url":SLOOS_PUBLIC,"frequency":"Q",
            "observations":observations[-12:]}

def parse_m2(text,*,today):
    reader=csv.DictReader(io.StringIO(text))
    date_key="observation_date" if "observation_date" in (reader.fieldnames or []) else "DATE"
    require(reader.fieldnames==[date_key,M2_SERIES],"M2 exact series/CSV key mismatch")
    values={}
    for row in reader:
        d=date.fromisoformat(row[date_key])
        raw=(row[M2_SERIES] or "").strip()
        if raw in ("","."):continue
        require(d.day==1 and (d.year,d.month)<(today.year,today.month),"M2 invalid or unfinished month")
        v=float(raw)
        require(math.isfinite(v) and 15000<v<40000,"M2 stock outside USD billions range")
        month=d.isoformat()[:7]
        require(month not in values,"M2 duplicate month")
        values[month]=v
    months=sorted(values)
    require(len(months)>=12 and list(values) in (months,list(reversed(months))),"M2 insufficient or unordered history")
    require("2026-08" in values and abs(values["2026-08"]/23342.8-1)<.02,"M2 August canonical overlap mismatch")
    for prior,current in zip(months,months[1:]):
        py,pm=map(int,prior.split("-"));y,m=map(int,current.split("-"))
        require(y*12+m-py*12-pm==1,"M2 nonconsecutive months")
        require(abs(values[current]/values[prior]-1)<.10,"M2 unexpected monthly jump")
    y,m=map(int,months[-1].split("-"))
    require((today.year-y)*12+today.month-m<=3,"M2 stale source")
    months=months[-36:]
    return {"series_id":M2_SERIES,"source_url":M2_PUBLIC,"frequency":"M",
            "unit":"miliardi USD","seasonally_adjusted":True,"dates":months,
            "values":[values[m] for m in months],"latest_observation":months[-1],
            "first_release_pit_verified":False,"eligible_for_fx_core":False}

def existing_payload(text):
    json_start=text.find("const data=")
    if json_start!=-1:
        try:
            return json.JSONDecoder().raw_decode(text[json_start+len("const data="):])[0]
        except ValueError:
            pass
    return {}

def emit_js(data,checked,lending_standards=None,money_stock=None):
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
    if lending_standards is not None:
        obj["lending_standards"]=lending_standards
    if money_stock is not None:
        obj["money_stock"]=money_stock
    return ("'use strict';\n/* Validated Fed H.8 and SLOOS via FRED; research-only. */\n"
        "(function(root){\n const data="+json.dumps(obj,ensure_ascii=False,indent=1)
        +";\n root.FXQuantUSBanksCreditResearch=Object.freeze(data);\n"
        " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
        "})(typeof window!=='undefined'?window:globalThis);\n")

def run(destination=DEST,*,apply=False,fixture=None,sloos_fixture=None,m2_fixture=None,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    text=destination.read_text(encoding="utf-8") if destination.exists() else ""
    previous=existing_payload(text)
    before=existing_obs(text)
    prior_sloos=previous.get("lending_standards")
    sloos=prior_sloos
    sloos_status={"status":"SKIPPED_FIXTURE"}
    if sloos_fixture or not fixture:
        try:
            candidate=parse_sloos(Path(sloos_fixture).read_text(encoding="utf-8")
                                  if sloos_fixture else fetch(SLOOS_API),today=today)
            period=candidate["observations"][-1][0]
            if prior_sloos and period<prior_sloos["observations"][-1][0]:
                raise ValueError("SLOOS latest survey regressed")
            sloos=candidate
            sloos_status={"status":"VERIFIED","latest_survey_period":period}
        except (OSError,ValueError,UnicodeError) as error:
            sloos_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:320]}
            if prior_sloos:
                sloos_status["retained_survey_period"]=prior_sloos["observations"][-1][0]
    prior_m2=previous.get("money_stock")
    money_stock=prior_m2
    m2_status={"status":"SKIPPED_FIXTURE"}
    if m2_fixture or not fixture:
        try:
            candidate=parse_m2(Path(m2_fixture).read_text(encoding="utf-8") if m2_fixture else fetch(M2_API),today=today)
            if prior_m2 and candidate["latest_observation"]<prior_m2["latest_observation"]:
                raise ValueError("M2 source rolled back")
            money_stock=candidate
            m2_status={"status":"VERIFIED","latest_observation":candidate["latest_observation"]}
        except (OSError,ValueError,UnicodeError) as error:
            m2_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:320]}
            if prior_m2:m2_status["retained_observation"]=prior_m2["latest_observation"]
    h8_status={"status":"VERIFIED"}
    try:
        parsed=parse(Path(fixture).read_text(encoding="utf-8") if fixture else fetch(),today=today)
    except (OSError,ValueError,UnicodeError) as error:
        if not (before and previous.get("schema")==SCHEMA and (sloos!=prior_sloos or money_stock!=prior_m2)):
            raise
        parsed=previous
        h8_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:320]}
    changed=before!=(parsed["dates"],parsed["values"]) or sloos!=prior_sloos or money_stock!=prior_m2
    state="UPDATE_AVAILABLE" if changed else "NO_CHANGE"
    receipt={
      "schema":"GMFQ_US_H8_FRED_CREDIT_SOURCE_RECEIPT_V1","status":state,
      "series":SERIES,"source":PUBLIC,"latest_observation":parsed["latest_observation"],
      "series_count":len(parsed["dates"]),"canonical_reference_revision_pct":parsed["reference_week_revision_pct"],
      "retrieved_on_rome":today.isoformat(),"first_release_verified":False,
      "h8":h8_status,"sloos":sloos_status,"m2":m2_status,
      "canonical_liquidity_unchanged":True,"fx_rank_effect":"NONE",
      "write_state":"NO_MUTATION"}
    if apply and state=="UPDATE_AVAILABLE":
        destination.parent.mkdir(parents=True,exist_ok=True)
        checked=today.isoformat() if h8_status["status"]=="VERIFIED" else previous["last_checked_rome"]
        destination.write_text(emit_js(parsed,checked,sloos,money_stock),encoding="utf-8")
        receipt["write_state"]="RESEARCH_SIDECAR_ONLY"
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--fixture",type=Path)
    p.add_argument("--sloos-fixture",type=Path)
    p.add_argument("--m2-fixture",type=Path)
    p.add_argument("--destination",type=Path,default=DEST)
    p.add_argument("--receipt",type=Path)
    args=p.parse_args()
    try:
        receipt=run(args.destination,apply=args.apply,fixture=args.fixture,sloos_fixture=args.sloos_fixture,m2_fixture=args.m2_fixture)
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
