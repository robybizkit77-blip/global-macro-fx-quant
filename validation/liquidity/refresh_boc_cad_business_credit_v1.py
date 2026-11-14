#!/usr/bin/env python3
"""Bank of Canada Valet V122667770 research-only series refresh.

- Bank of Canada V122667770: BUSINESS LOANS TOTAL, OUTSTANDING BALANCES.
- This is a month-end stock (millions CAD), NOT monthly funds advanced.
- No writes to NATIVE_LIQ_DATA, Macro FX Core, or COT/rankings.
- Source observation dates are not first-publication times.
- First source checked: official issuer table, 2026-11-14.
- A candidate is applied only after source identity, chronology, units,
  August-2026 overlap, sanity and revision guards pass.
"""
from __future__ import annotations
import argparse
import ast
import json
import math
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/"site/fx-quant-v2/next/cad-official-credit-research-v1.js"
SOURCE_ID="V122667770"
SOURCE_URL="https://www.bankofcanada.ca/rates/banking-and-financial-statistics/funds-advanced-and-outstanding-balances-for-new-and-existing-lending-by-chartered-banks/"
API_URL=f"https://www.bankofcanada.ca/valet/observations/{SOURCE_ID}/json?recent=24"
INITIAL_OBSERVED={"2026-04":922171,"2026-05":927358,"2026-06":937138,
                  "2026-07":941686,"2026-08":944614}
SCHEMA="GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1"

def require(flag,why):
    if not flag:
        raise ValueError("B0C_CAD_CREDIT_WITHHELD: "+why)

def fetch():
    request=urllib.request.Request(API_URL,headers={
      "User-Agent":"FX-Quant-Research-Sources/1.0",
      "Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=25) as handle:
        require(handle.geturl().startswith("https://www.bankofcanada.ca/valet/"),
                "unexpected response host")
        payload=handle.read(5_000_001)
    require(len(payload)<5_000_001,"source payload too large")
    return json.loads(payload)

def parse(data,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    require(isinstance(data,dict),"invalid JSON")
    obs=data.get("observations")
    require(isinstance(obs,list) and len(obs)>=4,"insufficient series")
    selected={}
    for record in obs:
        require(isinstance(record,dict),"invalid observation")
        token=record.get("d")
        require(isinstance(token,str) and re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?",token),
                "unrecognized monthly date")
        month=token[:7]
        entry=record.get(SOURCE_ID)
        if not isinstance(entry,dict) or entry.get("v") in (None,".",""):
            continue
        try:
            value=float(entry["v"])
        except (ValueError,TypeError) as e:
            raise ValueError("B0C_CAD_CREDIT_WITHHELD: nonnumeric official value") from e
        require(math.isfinite(value) and 300_000<value<1_800_000,"value outside bank-credit stock bounds")
        require(month not in selected,"duplicate monthly observation")
        selected[month]=round(value,3)
    months=sorted(selected)
    require(len(months)>=4,"too few usable months")
    source_order=list(selected)
    require(source_order==months or source_order==list(reversed(months)),
            "unusual source chronology")
    require("2026-08" in selected,"issuer source does not overlap verified August 2026")
    overlap=selected["2026-08"]/INITIAL_OBSERVED["2026-08"]-1
    require(abs(overlap)<.03,"August source vintage/series mismatch exceeds 3%")
    require(months[-1]>="2026-08","source older than original issuer snapshot")
    endyear,endmonth=map(int,months[-1].split("-"))
    require((endyear,endmonth)<=(today.year,today.month),"future-period input")
    for i,month in enumerate(months[1:],1):
        y,m=map(int,month.split("-"))
        py,pm=map(int,months[i-1].split("-"))
        require((y*12+m)-(py*12+pm)==1,"unexpected nonconsecutive monthly history")
        ratio=selected[month]/selected[months[i-1]]
        require(.88<ratio<1.12,"unexplained monthly 12% level jump")
    require(len(months)<=36,"unexpected number of source months")
    return {"dates":months,"values":[selected[m] for m in months],
            "latest_observation":months[-1],"revised_august_2026":abs(overlap)>.0000001}

def existing_observations(text):
    # Accept both initial literal JS keys and JSON-quoted generated keys.
    d=re.search(r"['\"]?dates['\"]?\s*:\s*(\[[^\]]*\])",text)
    v=re.search(r"['\"]?values['\"]?\s*:\s*(\[[^\]]*\])",text)
    if not d or not v:
        return None
    try:
        return ast.literal_eval(d.group(1)),ast.literal_eval(v.group(1))
    except (SyntaxError, ValueError):
        return None

def emit_js(candidate,verified_on):
    data={
      "schema":SCHEMA,"status":"VERIFIED_BOCA_VALET_MONTHLY_STOCK_RESEARCH_ONLY",
      "country":"CAD","publisher":"Bank of Canada",
      "series_id":SOURCE_ID,"source_url":SOURCE_URL,"api_url":API_URL,
      "label":"Prestiti alle imprese · totale in essere",
      "category":"outstanding_business_loans","units":"milioni CAD","frequency":"M",
      "seasonally_adjusted":"not_verified",
      "first_release_pit_verified":False,
      "eligible_for_fx_core":False,"eligible_for_backtest":False,
      "observation_is_not_publication_date":True,
      "last_checked_rome":verified_on,
      "latest_observation":candidate["latest_observation"],
      "dates":candidate["dates"],"values":candidate["values"],
      "inference":"Stock bancario, non nuove erogazioni, domanda di prestiti o standard. Serie separata da NATIVE_LIQ_DATA.CAD.credit."
    }
    return ("'use strict';\n"
      "/* Source: Bank of Canada Valet V122667770; research only, NOT FX Core. */\n"
      "(function(root){\n const data="+json.dumps(data,ensure_ascii=False,indent=1)
      +";\n root.FXQuantCADCreditResearch=Object.freeze(data);\n"
      " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
      "})(typeof window!=='undefined'?window:globalThis);\n")

def run(destination=DEST,*,apply=False,fixture=None,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    parsed=parse(json.loads(Path(fixture).read_text(encoding="utf-8")) if fixture else fetch(),
                 today=today)
    prior=existing_observations(destination.read_text(encoding="utf-8")) if destination.exists() else None
    now=(parsed["dates"],parsed["values"])
    status="NO_CHANGE" if prior and prior==now else "UPDATE_AVAILABLE"
    receipt={"schema":"GMFQ_BOC_CAD_CREDIT_COLLECTOR_V1",
        "status":status,"last_observation":parsed["latest_observation"],
        "observation_count":len(parsed["dates"]),
        "revised_august_2026":parsed["revised_august_2026"],
        "source":SOURCE_URL,"series":SOURCE_ID,"verified_on_rome":today.isoformat(),
        "canonical_runtime_unchanged":True,"fx_ranking_effect":"NONE",
        "release_date_certified":False}
    if apply and status=="UPDATE_AVAILABLE":
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(parsed,today.isoformat()),encoding="utf-8")
        receipt["write_state"]="RESEARCH_SIDECAR_ONLY"
    else:
        receipt["write_state"]="NO_MUTATION"
    return receipt

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--fixture",type=Path)
    parser.add_argument("--destination",type=Path,default=DEST)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    try:
        receipt=run(args.destination,apply=args.apply,fixture=args.fixture)
    except (OSError,TimeoutError,ValueError,json.JSONDecodeError) as error:
        receipt={"schema":"GMFQ_BOC_CAD_CREDIT_COLLECTOR_V1","status":"WITHHELD_SOURCE_UNAVAILABLE_OR_UNVERIFIED",
                 "reason":str(error)[:300],"canonical_runtime_unchanged":True,
                 "fx_ranking_effect":"NONE","write_state":"NO_MUTATION"}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))
    if receipt["status"].startswith("WITHHELD"):
        sys.exit(2)

if __name__=="__main__":
    main()
