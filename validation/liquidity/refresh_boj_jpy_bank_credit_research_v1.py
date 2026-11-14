#!/usr/bin/env python3
"""Official BOJ JPY credit stock (MD11 DLCLAEDBLTTO), research-only.

Reuses validated repository collector:
  validation/fetch_boj_jpy_bank_credit_candidate.py
The legacy fetcher proves every overlapping runtime month matches official
BoJ source exactly, before creating the source candidate. This script
validates candidate identity, chronology, next months, scale and no revisions
to the canonical history, then writes ONLY a research sidecar.

Units: 100 million JPY (not yen, millions JPY, new loan volume, nor balances
on banks' current accounts held with BOJ). Monthly end of period, not average
daily credit and not 2026-October preliminary lending-growth statistics.
"""
from __future__ import annotations
import argparse
import ast
import calendar
import json
import math
import re
import sys
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
CANON=ROOT/"live_data/sections/NATIVE_LIQ_DATA.json"
DEST=ROOT/"site/fx-quant-v2/next/jpy-boj-bank-credit-research-v1.js"
CODE="DLCLAEDBLTTO"
DB="MD11"
SOURCE="https://www.stat-search.boj.or.jp/ssi/mtshtml/md11_m_1_en.html"
SCHEMA="GMFQ_NEXT_JPY_BOJ_BANK_CREDIT_RESEARCH_V1"
ORIGINAL_PERIOD="2026-07"
ORIGINAL_VALUE=6764306

def require(ok,why):
    if not ok:raise ValueError("BOJ_JPY_CREDIT_SOURCE_WITHHELD: "+why)

def month_num(token):
    require(isinstance(token,str) and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",token),
            "bad monthly date")
    return int(token[:4])*12+int(token[5:])

def numeric(value,*,label):
    try:v=float(value)
    except (ValueError,TypeError) as exc:
        raise ValueError(f"BOJ_JPY_CREDIT_SOURCE_WITHHELD: bad numeric {label}") from exc
    require(math.isfinite(v) and 2_000_000<v<12_000_000,
            f"implausible yen bank credit stock: {label}")
    return round(v,5)

def parse(candidate,*,today=None,canonical=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    if canonical is None: canonical=json.loads(CANON.read_text(encoding="utf-8"))
    require(isinstance(candidate,dict) and
            candidate.get("schema")=="GMFQ_LIQUIDITY_JPY_BANK_CREDIT_CANDIDATE_V1" and
            candidate.get("status")=="GREEN_SOURCE_CANDIDATE_ONLY" and
            candidate.get("runtime_match_confirmed") is True and
            candidate.get("publication_performed") is False and
            candidate.get("runtime_mutated") is False,
            "source candidate is not green and independent")
    source=candidate.get("source") or {}
    require(source.get("publisher")=="Bank of Japan" and
            source.get("database")==DB and source.get("series_id")==CODE and
            source.get("unit")=="100 million yen" and
            source.get("frequency")=="MONTHLY" and
            str(source.get("url","")).startswith(
                "https://www.stat-search.boj.or.jp/api/v1/getDataCode?"),
            "wrong issuer, series definition or units")
    row=canonical["JPY"]["credit"]
    dates=list(row.get("dates") or [])
    values=list(row.get("values") or [])
    require(len(dates)>=24 and len(dates)==len(values),"canonical JPY credit malformed")
    require(row.get("last_date")==dates[-1] and
            numeric(row.get("last_value"),label="last")==numeric(values[-1],label="last-array"),
            "canonical JPY credit last-date/amount inconsistency")
    require(dates[-1]==ORIGINAL_PERIOD and
            numeric(values[-1],label="original anchor")==ORIGINAL_VALUE,
            "canonical JPY credit contract has moved; re-evaluate core isolation")
    for i,period in enumerate(dates):
        require(i==0 or month_num(period)==month_num(dates[i-1])+1,
                "gap or duplicate in canonical monthly history")
    r=candidate.get("runtime") or {}
    require(r.get("last_date")==dates[-1] and
            numeric(r.get("last_value"),label="candidate anchor")==ORIGINAL_VALUE,
            "candidate was proven against a different canonical feed")
    cnt=candidate.get("runtime_overlap_count")
    require(isinstance(cnt,int) and cnt>=12 and
            candidate.get("runtime_exact_match_count")==cnt,
            "BoJ matched overlap insufficient or nonexact")
    added=[]
    next_serial=month_num(dates[-1])+1
    for item in candidate.get("new_observations") or []:
        require(isinstance(item,dict),"malformed BoJ monthly record")
        period=item.get("date")
        require(month_num(period)==next_serial,
                "nonconsecutive or duplicated new BoJ monthly observations")
        val=numeric(item.get("value"),label=period)
        require(abs(val/values[-1]-1)<.12 if not added
                else abs(val/added[-1][1]-1)<.12,
                "unexplained >12% monthly loan-stock jump")
        added.append((period,val))
        next_serial+=1
    require(len(added)<=18,"unexpectedly many new monthly observations")
    require(bool(added)==bool(candidate.get("candidate_update_available")),
            "candidate availability does not match actual records")
    all_dates=dates+[p for p,v in added]
    all_values=[numeric(v,label="canonical") for v in values]+[v for p,v in added]
    require(candidate.get("latest_date")==all_dates[-1] and
            numeric(candidate.get("latest_value"),label="candidate latest")==all_values[-1],
            "source last-value/date contract mismatch")
    year,month=map(int,all_dates[-1].split("-"))
    end=date(year,month,calendar.monthrange(year,month)[1])
    require(end<=today,"future source observation")
    require((today-end).days<=110,"verified BoJ bank credit report older than 110 days")
    return {
      "dates":all_dates[-36:],"values":all_values[-36:],
      "last_observation":all_dates[-1],
      "matched_canonical_months":cnt,
      "new_after_canonical":len(added)
    }

def existing(text):
    arrays=[]
    for key in ("dates","values"):
        m=re.search(r"['\"]?"+key+r"['\"]?\s*:\s*(\[[^\]]*\])",text)
        if not m:return None
        try:arrays.append(ast.literal_eval(m.group(1)))
        except (SyntaxError,ValueError):return None
    return tuple(arrays)

def emit_js(result,checked):
    out={
      "schema":SCHEMA,
      "status":"VERIFIED_BOJ_MD11_MONTHLY_BANK_CREDIT_RESEARCH_ONLY",
      "country":"JPY","publisher":"Bank of Japan",
      "database":DB,"series_id":CODE,"source_url":SOURCE,
      "source_contract":"Outstanding Loans and Bills Discounted / End of Period / Banking, Trust and Overseas Office Accounts / Domestically Licensed Banks",
      "category":"bank_credit_end_period_stock",
      "frequency":"M","unit":"100 milioni JPY","end_of_period":True,
      "first_release_pit_verified":False,"eligible_for_fx_core":False,
      "eligible_for_backtest":False,"observation_is_not_publication_date":True,
      "original_canonical_last":ORIGINAL_PERIOD,
      "original_canonical_value":ORIGINAL_VALUE,
      "checked_rome":checked,
      **result,
      "inference":"Monthly BoJ bank-credit stock including trust and overseas-office accounts: not new loans, not BoJ settlement reserves or observed yen demand. FX and funding response require independent confirmation."
    }
    return ("'use strict';\n"
       "/* Official BoJ MD11 credit, exact match to canonical history; research-only. */\n"
       "(function(root){\n const data="+json.dumps(out,ensure_ascii=False,indent=1)+";\n"
       " root.FXQuantJPYBankCreditResearch=Object.freeze(data);\n"
       " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
       "})(typeof window!=='undefined'?window:globalThis);\n")

def run(*,candidate_file,destination=DEST,apply=False,today=None,canonical=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    candidate=json.loads(Path(candidate_file).read_text(encoding="utf-8"))
    item=parse(candidate,today=today,canonical=canonical)
    original=existing(destination.read_text(encoding="utf-8")) if destination.exists() else None
    require(not original or not original[0] or item["last_observation"]>=original[0][-1],
            "official BoJ credit observation rolled backward")
    current=(item["dates"],item["values"])
    changed=original!=current
    result={
      "schema":"GMFQ_BOJ_JPY_BANK_CREDIT_SOURCE_RECEIPT_V1",
      "status":"UPDATE_AVAILABLE" if changed else "NO_CHANGE",
      "source":SOURCE,"database":DB,"series":CODE,
      "last_observation":item["last_observation"],
      "last_stock_100m_jpy":item["values"][-1],
      "prior_stock_100m_jpy":item["values"][-2],
      "official_exact_overlap_months":item["matched_canonical_months"],
      "new_months_after_canonical":item["new_after_canonical"],
      "checked_rome":today.isoformat(),
      "first_release_pit_verified":False,
      "canon_jpy_credit_unchanged":True,
      "fx_ranking_effect":"NONE","write_state":"NO_MUTATION"
    }
    if changed and apply:
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(item,today.isoformat()),encoding="utf-8")
        result["write_state"]="RESEARCH_SIDECAR_ONLY"
    return result

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--candidate",type=Path,required=True)
    a.add_argument("--destination",type=Path,default=DEST)
    a.add_argument("--apply",action="store_true")
    a.add_argument("--receipt",type=Path)
    args=a.parse_args()
    try:
        result=run(candidate_file=args.candidate,destination=args.destination,apply=args.apply)
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        result={
          "schema":"GMFQ_BOJ_JPY_BANK_CREDIT_SOURCE_RECEIPT_V1",
          "status":"WITHHELD_OFFICIAL_SOURCE_UNVERIFIED",
          "reason":str(exc)[:340],"write_state":"NO_MUTATION",
          "canon_jpy_credit_unchanged":True,"fx_ranking_effect":"NONE"
        }
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__":main()
