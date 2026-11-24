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
from html.parser import HTMLParser
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
LYNX_URL="https://www.bankofcanada.ca/rates/indicators/market-operations-indicators/"
SLOS_API="https://www.bankofcanada.ca/valet/observations/group/slos/json?start_date=2023-01-01"
SLOS_PUBLIC="https://www.bankofcanada.ca/publications/slos/"
SLOS_ID="SLOS_BUS_LEND"

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

class SettlementTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.row=[]
        if tag in ("th","td") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("th","td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell=None
        if tag=="tr" and self.row is not None:
            self.rows.append(self.row);self.row=None

def fetch_lynx():
    req=urllib.request.Request(LYNX_URL,headers={"User-Agent":"FX-Quant-Research-Sources/1.0","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=30) as response:
        require(response.geturl().startswith(LYNX_URL),"unexpected Lynx source redirect")
        raw=response.read(3000001)
    require(len(raw)<3000001,"Lynx source too large")
    return raw.decode("utf-8-sig")

def parse_lynx(html,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    page=SettlementTable();page.feed(html);page.close()
    rows=page.rows
    selected=[i for i,r in enumerate(rows) if r and r[0].strip().lower()=="amount in lynx"]
    require(len(selected)==1,"Lynx actual row absent or ambiguous")
    idx=selected[0];lynx=rows[idx]
    total=next((r for r in rows[max(0,idx-3):idx] if r and r[0].lower().startswith("total settlement balances")),None)
    rtr=next((r for r in rows[idx+1:idx+4] if r and r[0].lower().startswith("amount in real-time rail")),None)
    require(total is not None and rtr is not None,"Lynx/RTR breakdown absent")
    def normal(s):return s.translate(str.maketrans({"‑":"-","–":"-","−":"-","\u00a0":" "}))
    header=None
    for r in reversed(rows[max(0,idx-5):idx]):
        if len(r)==len(lynx) and "millions of dollars" in r[0].lower() and all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",normal(d)) for d in r[1:]):
            header=r;break
    require(header is not None,"Lynx date header or millions units missing")
    require(len(total)==len(rtr)==len(lynx),"Lynx row length mismatch")
    def val(token):
        s=normal(token).replace(",","").replace(" ","")
        if s in ("","-","—"):return None
        require(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?",s) is not None,"invalid settlement balance")
        return float(s)
    records={}
    for i,token in enumerate(header[1:],1):
        d=date.fromisoformat(normal(token))
        a,t,z=val(lynx[i]),val(total[i]),val(rtr[i])
        if a is None:continue
        require(d<=today and d not in records and d.weekday()<5,"invalid Lynx observation date")
        require(t is not None and z is not None and 0<=a<=1000000 and abs(t-a-z)<=1,"Lynx/RTR total does not reconcile")
        records[d]=a
    days=sorted(records)
    require(len(days)>=2 and (today-days[-1]).days<=7,"Lynx insufficient or stale source")
    require(list(records)==days or list(records)==list(reversed(days)),"Lynx chronology")
    return {"source_url":LYNX_URL,"series_id":"BOC_LYNX_ACTUAL_DAILY","frequency":"D","unit":"milioni CAD",
            "dates":[d.isoformat() for d in days],"values":[records[d] for d in days],
            "latest_observation":days[-1].isoformat(),"preliminary_may_be_revised":True,
            "canonical_monthly_equivalence_verified":False,"eligible_for_fx_core":False,"eligible_for_backtest":False}

def fetch_slos():
    request=urllib.request.Request(SLOS_API,headers={"User-Agent":"FX-Quant-Research-Sources/1.0","Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=25) as response:
        require(response.geturl().startswith("https://www.bankofcanada.ca/valet/"),"unexpected SLOS redirect")
        raw=response.read(1000001)
    require(len(raw)<1000001,"SLOS payload too large")
    return json.loads(raw)

def parse_slos(payload,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    meta=payload.get("seriesDetail",{}).get(SLOS_ID,{})
    require(meta.get("label")=="Overall business lending conditions" and meta.get("dateFormat")=="quarterly","SLOS source identity")
    records={}
    for row in payload.get("observations",[]):
        raw=row.get(SLOS_ID,{}).get("v")
        if raw in (None,"","."):continue
        d=date.fromisoformat(row["d"])
        q=(d.month-1)//3+1
        require(d.day==1 and d.month in (1,4,7,10) and (d.year,q)<(today.year,(today.month-1)//3+1),"SLOS invalid or unfinished quarter")
        v=float(raw)
        require(math.isfinite(v) and -100<=v<=100,"SLOS net balance out of range")
        require(d not in records,"SLOS duplicate quarter")
        records[d]=v
    days=sorted(records)
    require(len(days)>=4 and list(records) in (days,list(reversed(days))),"SLOS insufficient or unordered history")
    require(abs(records.get(date(2026,4,1),999)+1.04)<.1,"SLOS canonical Q2 overlap mismatch")
    for a,b in zip(days,days[1:]):
        require((b.year-a.year)*12+b.month-a.month==3,"SLOS quarter gap")
    require((today-days[-1]).days<=220,"SLOS stale source")
    days=days[-16:]
    return {"series_id":SLOS_ID,"source_url":SLOS_PUBLIC,"frequency":"Q","unit":"net_balance_pct_points",
            "positive_means":"tightening","negative_means":"easing","dates":[d.isoformat() for d in days],
            "values":[records[d] for d in days],"latest_observation":days[-1].isoformat(),
            "first_release_pit_verified":False,"eligible_for_fx_core":False,"eligible_for_backtest":False}

def existing_payload(text):
    start=text.find("const data=")
    if start!=-1:
        try:return json.JSONDecoder().raw_decode(text[start+len("const data="):])[0]
        except ValueError:pass
    return {}

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

def emit_js(candidate,verified_on,settlement_balances=None,lending_conditions=None):
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
    if settlement_balances is not None:data['settlement_balances']=settlement_balances
    if lending_conditions is not None:data['lending_conditions']=lending_conditions
    return ("'use strict';\n"
      "/* Source: Bank of Canada Valet V122667770; research only, NOT FX Core. */\n"
      "(function(root){\n const data="+json.dumps(data,ensure_ascii=False,indent=1)
      +";\n root.FXQuantCADCreditResearch=Object.freeze(data);\n"
      " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
      "})(typeof window!=='undefined'?window:globalThis);\n")

def run(destination=DEST,*,apply=False,fixture=None,lynx_fixture=None,slos_fixture=None,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    old=destination.read_text(encoding="utf-8") if destination.exists() else ""
    prior_payload=existing_payload(old)
    prior=existing_observations(old) if old else None
    prior_lynx=prior_payload.get("settlement_balances")
    lynx=prior_lynx
    lynx_status={"status":"SKIPPED_FIXTURE"}
    if lynx_fixture or not fixture:
        try:
            candidate=parse_lynx(Path(lynx_fixture).read_text(encoding="utf-8") if lynx_fixture else fetch_lynx(),today=today)
            if prior_lynx and candidate["latest_observation"]<prior_lynx["latest_observation"]:
                raise ValueError("Lynx source rolled back")
            # Retain only issuer-observed dates; never interpolate missing days.
            merged=dict(zip(prior_lynx["dates"],prior_lynx["values"])) if prior_lynx else {}
            merged.update(zip(candidate["dates"],candidate["values"]))
            dates=sorted(merged)[-80:]
            lynx={**candidate,"dates":dates,"values":[merged[d] for d in dates]}
            lynx_status={"status":"VERIFIED","latest_observation":candidate["latest_observation"]}
        except (OSError,ValueError,UnicodeError) as error:
            lynx_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:300]}
            if prior_lynx:lynx_status["retained_observation"]=prior_lynx["latest_observation"]
    prior_slos=prior_payload.get("lending_conditions")
    slos=prior_slos
    slos_status={"status":"SKIPPED_FIXTURE"}
    if slos_fixture or not fixture:
        try:
            candidate=parse_slos(json.loads(Path(slos_fixture).read_text(encoding="utf-8")) if slos_fixture else fetch_slos(),today=today)
            if prior_slos and candidate["latest_observation"]<prior_slos["latest_observation"]:
                raise ValueError("SLOS source rolled back")
            slos=candidate
            slos_status={"status":"VERIFIED","latest_observation":candidate["latest_observation"]}
        except (OSError,ValueError,UnicodeError,TypeError,KeyError) as error:
            slos_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:300]}
            if prior_slos:slos_status["retained_observation"]=prior_slos["latest_observation"]
    credit_status={"status":"VERIFIED"}
    try:
        parsed=parse(json.loads(Path(fixture).read_text(encoding="utf-8")) if fixture else fetch(),today=today)
    except (OSError,ValueError,UnicodeError) as error:
        if not (prior and prior_payload.get("schema")==SCHEMA and (lynx!=prior_lynx or slos!=prior_slos)):raise
        parsed={**prior_payload,"revised_august_2026":False}
        credit_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:300]}
    now=(parsed["dates"],parsed["values"])
    status="NO_CHANGE" if prior and prior==now and lynx==prior_lynx and slos==prior_slos else "UPDATE_AVAILABLE"
    receipt={"schema":"GMFQ_BOC_CAD_CREDIT_COLLECTOR_V1",
        "status":status,"last_observation":parsed["latest_observation"],
        "observation_count":len(parsed["dates"]),
        "revised_august_2026":parsed["revised_august_2026"],
        "source":SOURCE_URL,"series":SOURCE_ID,"verified_on_rome":today.isoformat(),
        "canonical_runtime_unchanged":True,"fx_ranking_effect":"NONE",
        "release_date_certified":False,"credit":credit_status,"lynx":lynx_status,"slos":slos_status}
    if apply and status=="UPDATE_AVAILABLE":
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(parsed,today.isoformat() if credit_status["status"]=="VERIFIED" else prior_payload["last_checked_rome"],lynx,slos),encoding="utf-8")
        receipt["write_state"]="RESEARCH_SIDECAR_ONLY"
    else:
        receipt["write_state"]="NO_MUTATION"
    return receipt

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--fixture",type=Path)
    parser.add_argument("--lynx-fixture",type=Path)
    parser.add_argument("--slos-fixture",type=Path)
    parser.add_argument("--destination",type=Path,default=DEST)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    try:
        receipt=run(args.destination,apply=args.apply,fixture=args.fixture,lynx_fixture=args.lynx_fixture,slos_fixture=args.slos_fixture)
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
