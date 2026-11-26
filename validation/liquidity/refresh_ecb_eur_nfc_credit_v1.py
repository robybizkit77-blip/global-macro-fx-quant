#!/usr/bin/env python3
"""ECB BSI MFI loans to NFCs (stock), euro area, research-only.

Official series: BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E.
Unadjusted, end-period stock in millions EUR. It is NOT flow/new lending,
NOT adjusted credit growth and NOT a policy/euro exchange-rate signal.

The source may revise past data. Exact series, overlap, time order, units,
plausible size and month-to-month changes are verified before updating the
independent research sidecar. NATIVE_LIQ_DATA and rankings are never written.
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
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
DEST=ROOT/"site/fx-quant-v2/next/eur-ecb-nfc-credit-research-v1.js"
SERIES="BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E"
API="https://data-api.ecb.europa.eu/service/data/BSI/M.U2.N.A.A20.A.1.U2.2240.Z01.E?format=csvdata&startPeriod=2024-01"
PUBLIC="https://data.ecb.europa.eu/data/datasets/BSI/"+SERIES
ANCHOR_DATE="2026-07"
ANCHOR_VALUE=5481083.172910931
SCHEMA="GMFQ_NEXT_EUR_ECB_NFC_CREDIT_RESEARCH_V1"
EXLIQ_SERIES="ILM.D.U2.C.EXLIQ.U2.EUR"
EXLIQ_API="https://data-api.ecb.europa.eu/service/data/ILM/D.U2.C.EXLIQ.U2.EUR?format=csvdata&startPeriod=2026-09-01"
EXLIQ_PUBLIC="https://data.ecb.europa.eu/data/datasets/ILM/"+EXLIQ_SERIES

def require(ok,why):
    if not ok:
        raise ValueError("ECB_EUR_NFC_SOURCE_WITHHELD: "+why)

def fetch(url=API):
    req=urllib.request.Request(url,headers={
        "Accept":"text/csv", "User-Agent":"FXQuant-Research-Sources/1.0"})
    with urllib.request.urlopen(req,timeout=30) as response:
        require(response.geturl().startswith("https://data-api.ecb.europa.eu/"),
                "unexpected response host")
        raw=response.read(2_000_001)
    require(len(raw)<2_000_001,"unexpectedly large ECB response")
    return raw.decode("utf-8-sig")

def parse(content,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    reader=csv.DictReader(io.StringIO(content))
    require(bool(reader.fieldnames),"empty ECB CSV")
    columns=set(reader.fieldnames)
    require({"TIME_PERIOD","OBS_VALUE"}<=columns,
            "missing ECB time and value column")
    require("KEY" in columns or "SERIES_KEY" in columns,
            "missing exact ECB series identity column")
    key="KEY" if "KEY" in columns else "SERIES_KEY"
    records={}
    seen=[]
    for rec in reader:
        require(isinstance(rec,dict),"unexpected ECB record")
        require(rec.get(key)==SERIES,
                "cross-series or alternative ECB adjusted loan measure")
        month=rec.get("TIME_PERIOD")
        require(isinstance(month,str) and re.fullmatch(r"\d{4}-\d{2}",month),
                "unexpected ECB monthly timestamp")
        raw=rec.get("OBS_VALUE")
        if raw in (None,"","."):
            continue
        try:
            num=float(raw)
        except (TypeError,ValueError) as exc:
            raise ValueError("ECB_EUR_NFC_SOURCE_WITHHELD: nonnumeric ECB observation") from exc
        require(math.isfinite(num) and 3_000_000<num<9_000_000,
                "NFC credit stock outside source-scale bounds")
        if rec.get("UNIT_MULT") not in (None,"","6"):
            require(False,"ECB unit multiplier differs from millions")
        if rec.get("DECIMALS") not in (None,"","0","1","2","3","4","5","6"):
            require(False,"ECB decimals unexpected")
        require(month not in records,"duplicated monthly ECB observation")
        records[month]=round(num,4)
        seen.append(month)
    require(len(records)>=10,"insufficient monthly ECB observations")
    months=sorted(records)
    require(seen==months or seen==list(reversed(months)),
            "ECB source observations not chronological")
    require(ANCHOR_DATE in records,
            "no overlap with the existing canonical EUR NFC loan series")
    reference_diff=(records[ANCHOR_DATE]/ANCHOR_VALUE-1)*100
    require(abs(reference_diff)<2.0,
            "source variant or revised July 2026 level diverges more than 2%")
    for i in range(1,len(months)):
        yy,mm=map(int,months[i].split("-"))
        py,pm=map(int,months[i-1].split("-"))
        require(yy*12+mm-py*12-pm==1,"gap in monthly ECB stock history")
        require(abs(records[months[i]]/records[months[i-1]]-1)<.10,
                "unexpected >10% month-to-month credit level change")
    y,m=map(int,months[-1].split("-"))
    require((y,m)<(today.year,today.month),"future or incomplete monthly credit observation")
    require(months[-1]>=ANCHOR_DATE,
            "source older than the canonical EUR credit series")
    require(len(months)<=60,"unexpected ECB sample size")
    subset=months[-36:]
    return {
       "dates":subset,
       "values":[records[m] for m in subset],
       "latest_observation":subset[-1],
       "anchor_revision_pct":round(reference_diff,4),
    }

def parse_excess_liquidity(content,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    reader=csv.DictReader(io.StringIO(content))
    columns=set(reader.fieldnames or [])
    require({"TIME_PERIOD","OBS_VALUE","UNIT_MULT"}<=columns,"missing ECB excess liquidity data or units")
    require("KEY" in columns or "SERIES_KEY" in columns,"missing ECB excess liquidity identity")
    key="KEY" if "KEY" in columns else "SERIES_KEY"
    records={}
    for rec in reader:
        require(rec.get(key)==EXLIQ_SERIES,"wrong ECB excess liquidity series")
        raw=rec.get("OBS_VALUE")
        if raw in (None,"","."):continue
        require(rec.get("UNIT_MULT")=="6","ECB excess liquidity must be in millions")
        day=date.fromisoformat(rec["TIME_PERIOD"])
        require(day<=today and day not in records,"future or duplicate liquidity date")
        value=float(raw)
        require(math.isfinite(value) and -1000000<value<10000000,"ECB excess liquidity outside plausible range")
        records[day]=value
    days=sorted(records)
    require(len(days)>=15 and list(records) in (days,list(reversed(days))),"insufficient or unordered liquidity history")
    anchor=records.get(date(2026,9,21))
    require(anchor is not None and abs(anchor/2123137-1)<.02,"ECB liquidity canonical overlap mismatch")
    require((today-days[-1]).days<=10,"ECB liquidity source stale")
    require(all((b-a).days<=5 for a,b in zip(days,days[1:])),"unexplained excess liquidity observation gap")
    days=days[-80:]
    return {"series_id":EXLIQ_SERIES,"source_url":EXLIQ_PUBLIC,"frequency":"D","unit":"milioni EUR",
            "dates":[d.isoformat() for d in days],"values":[records[d] for d in days],
            "latest_observation":days[-1].isoformat(),"first_release_pit_verified":False,
            "eligible_for_fx_core":False,"eligible_for_backtest":False}

def existing_payload(text):
    start=text.find("const data=")
    if start!=-1:
        try:return json.JSONDecoder().raw_decode(text[start+len("const data="):])[0]
        except ValueError:pass
    return {}

def existing_observations(text):
    keys=[]
    for k in ("dates","values"):
        match=re.search(r"['\"]?"+k+r"['\"]?\s*:\s*(\[[^\]]*\])",text)
        if not match:return None
        try:keys.append(ast.literal_eval(match.group(1)))
        except (SyntaxError,ValueError):return None
    return tuple(keys)

def emit_js(parsed,checked,excess_liquidity=None,lending_conditions=None):
    x={
      "schema":SCHEMA,
      "status":"VERIFIED_ECB_BSI_NFC_STOCK_RESEARCH_ONLY",
      "country":"EUR",
      "publisher":"European Central Bank / ESCB",
      "series_id":SERIES,
      "source_url":PUBLIC,
      "api_url":API,
      "label":"Loans to euro area non-financial corporations",
      "category":"nfc_loans_stock",
      "unit":"milioni EUR",
      "frequency":"M",
      "seasonally_adjusted":False,
      "first_release_pit_verified":False,
      "eligible_for_fx_core":False,
      "eligible_for_backtest":False,
      "observation_is_not_publication_date":True,
      "last_checked_rome":checked,
      "latest_observation":parsed["latest_observation"],
      "anchor_revision_pct":parsed["anchor_revision_pct"],
      "dates":parsed["dates"],
      "values":parsed["values"],
      "inference":"Stock prestiti MFI alle imprese non finanziarie, non nuove erogazioni, non credit impulse corretto per cessioni; ricerca separata."
    }
    if excess_liquidity is not None:x['excess_liquidity']=excess_liquidity
    if lending_conditions is not None:x['lending_conditions']=lending_conditions
    return ("'use strict';\n"
            "/* Official ECB BSI NFC stock: research only, revision aware. */\n"
            "(function(root){\n const data="+json.dumps(x,ensure_ascii=False,indent=1)+";\n"
            " root.FXQuantEURNFCCreditResearch=Object.freeze(data);\n"
            " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
            "})(typeof window!=='undefined'?window:globalThis);\n")

def parse_bls(content, *, today):
    from validation.liquidity.probe_ecb_eur_bls_actual_v1 import parse, quarter_label, KEY, API
    records=parse(content,today)
    quarters=sorted(records)[-36:]
    return {"series_id":KEY,"source_url":"https://data.ecb.europa.eu/data/datasets/BLS/"+KEY,
            "api_url":API,"frequency":"Q","unit":"net_percentage_balance",
            "positive_means":"tightening","reference_period_is_previous_quarter":True,
            "publication_quarters":[quarter_label(q) for q in quarters],
            "dates":[quarter_label(q-1) for q in quarters],
            "values":[records[q] for q in quarters],
            "latest_observation":quarter_label(quarters[-1]-1),
            "first_release_pit_verified":False,"eligible_for_fx_core":False,"eligible_for_backtest":False}

def run(destination=DEST,*,apply=False,fixture=None,exliq_fixture=None,bls_fixture=None,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    old=destination.read_text(encoding="utf-8") if destination.exists() else ""
    prior=existing_payload(old)
    previous=existing_observations(old) if old else None
    prior_exliq=prior.get("excess_liquidity")
    exliq=prior_exliq
    exliq_status={"status":"SKIPPED_FIXTURE"}
    if exliq_fixture or not fixture:
        try:
            candidate=parse_excess_liquidity(Path(exliq_fixture).read_text(encoding="utf-8") if exliq_fixture else fetch(EXLIQ_API),today=today)
            if prior_exliq and candidate["latest_observation"]<prior_exliq["latest_observation"]:
                raise ValueError("ECB excess liquidity source rolled back")
            exliq=candidate
            exliq_status={"status":"VERIFIED","latest_observation":candidate["latest_observation"]}
        except (OSError,ValueError,UnicodeError) as error:
            exliq_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:320]}
            if prior_exliq:exliq_status["retained_observation"]=prior_exliq["latest_observation"]
    prior_bls=prior.get("lending_conditions")
    bls=prior_bls
    bls_status={"status":"SKIPPED_FIXTURE"}
    if bls_fixture or not fixture:
        try:
            from validation.liquidity.probe_ecb_eur_bls_actual_v1 import API as BLS_API
            candidate=parse_bls(Path(bls_fixture).read_text(encoding="utf-8") if bls_fixture else fetch(BLS_API),today=today)
            if prior_bls and candidate["latest_observation"]<prior_bls["latest_observation"]:
                raise ValueError("ECB BLS source rolled back")
            bls=candidate
            bls_status={"status":"VERIFIED","latest_observation":bls["latest_observation"]}
        except (OSError,ValueError,UnicodeError) as error:
            bls_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:320]}
            if prior_bls:bls_status["retained_observation"]=prior_bls["latest_observation"]
    nfc_status={"status":"VERIFIED"}
    try:
        data=parse(Path(fixture).read_text(encoding="utf-8") if fixture else fetch(),today=today)
        if prior.get("schema")==SCHEMA and prior.get("latest_observation") and data["latest_observation"]<prior["latest_observation"]:
            raise ValueError("ECB NFC monthly source rolled back; preserve last verified vintage")
    except (OSError,ValueError,UnicodeError) as error:
        if not (previous and prior.get("schema")==SCHEMA and (exliq!=prior_exliq or bls!=prior_bls)):raise
        data=prior
        nfc_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:320]}
    changed=previous!=(data["dates"],data["values"]) or exliq!=prior_exliq or bls!=prior_bls
    receipt={
      "schema":"GMFQ_ECB_NFC_CREDIT_SOURCE_RECEIPT_V1",
      "status":"UPDATE_AVAILABLE" if changed else "NO_CHANGE",
      "series_id":SERIES,
      "publisher":"European Central Bank / ESCB",
      "source":PUBLIC,
      "last_observation":data["latest_observation"],
      "last_value":data["values"][-1],
      "observation_count":len(data["dates"]),
      "overlap_revision_pct":data["anchor_revision_pct"],
      "verified_on_rome":today.isoformat(),
      "first_release_pit_verified":False,
      "nfc":nfc_status,"excess_liquidity":exliq_status,"lending_conditions":bls_status,
      "canonical_runtime_unchanged":True,
      "fx_rank_effect":"NONE",
      "write_state":"NO_MUTATION"
    }
    if apply and changed:
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(data,today.isoformat() if nfc_status["status"]=="VERIFIED" else prior["last_checked_rome"],exliq,bls),encoding="utf-8")
        receipt["write_state"]="RESEARCH_SIDECAR_ONLY"
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--fixture",type=Path)
    p.add_argument("--exliq-fixture",type=Path)
    p.add_argument("--bls-fixture",type=Path)
    p.add_argument("--destination",type=Path,default=DEST)
    p.add_argument("--receipt",type=Path)
    args=p.parse_args()
    try:
        out=run(args.destination,apply=args.apply,fixture=args.fixture,exliq_fixture=args.exliq_fixture,bls_fixture=args.bls_fixture)
    except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
        out={"schema":"GMFQ_ECB_NFC_CREDIT_SOURCE_RECEIPT_V1",
             "status":"WITHHELD_SOURCE_INACCESSIBLE_OR_UNVERIFIED",
             "reason":str(exc)[:320],
             "write_state":"NO_MUTATION",
             "canonical_runtime_unchanged":True,
             "fx_rank_effect":"NONE"}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False))
    if out["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__":
    main()
