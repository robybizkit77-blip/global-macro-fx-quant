#!/usr/bin/env python3
"""Optional licensed eolas API fallback for RBNZ B2 NZD government yields.

Requires EOLAS_API_KEY from GitHub Actions secrets. No scraping/paywall bypass.
Provider-sourced data are *not* independently reconciled RBNZ XLSX and are
strictly informational for FX Quant V2; official RBNZ HTML remains first choice.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

SCHEMA="GMFQ_FXV2_NZD_RBNZ_B2_REPUBLISHED_API_RESEARCH_V1"
DATASET="rbnz_b2_wholesale_rates_daily"
URL="https://api.eolas.nz/v1/datasets/"+DATASET+"/data"
NZ=ZoneInfo("Pacific/Auckland")
ROLL="2026-10-30"
NEW_2="April 2029"
NEW_10="April 2037"
TWO="secondary_market_government_bond_closing_yields_2_year"
TEN="secondary_market_government_bond_closing_yields_10_year"
TWO_BOND="secondary_market_government_bond_closing_yields_april_2029"
TEN_BOND="secondary_market_government_bond_closing_yields_april_2037"

def must(value,why):
    if not value: raise ValueError("FXV2_EO_B2_GUARD: "+why)

def iso(value):
    must(isinstance(value,str) and len(value)==10,"date format")
    d=dt.date.fromisoformat(value)
    must(d.isoformat()==value,"not ISO date")
    return d

def yield_rate(value,kind):
    must(type(value) in (int,float) and math.isfinite(value) and -5 < value < 25,
         "missing/invalid "+kind)
    return float(value)

def rows_from_api(payload):
    # eolas documents a plain JSON list; other shapes require contract review.
    must(isinstance(payload,list) and 0<len(payload)<=500,"unexpected eolas response shape/count")
    return payload

def parse(payload,*,now_nz:dt.datetime) -> dict:
    must(now_nz.tzinfo is not None and now_nz.utcoffset() is not None,
         "timezone-aware input required")
    today=now_nz.astimezone(NZ).date()
    rows=rows_from_api(payload)
    observations=[]
    for row in rows:
        must(isinstance(row,dict),"nonobject row")
        day=iso(row.get("date"))
        must(day<=today,"future provider observation")
        if day<dt.date.fromisoformat(ROLL): continue
        y2=yield_rate(row.get(TWO),"2Y government")
        y10=yield_rate(row.get(TEN),"10Y government")
        b2=yield_rate(row.get(TWO_BOND),"April-2029 instrument")
        b10=yield_rate(row.get(TEN_BOND),"April-2037 instrument")
        # The RBNZ benchmark roll at 30 October is confirmed by instrument IDs:
        # never mix generic 2Y from an old bond with a new 10Y benchmark.
        must(abs(y2-b2)<0.011 and abs(y10-b10)<0.011,
             "benchmark instrument mismatch or unidentified roll")
        observations.append((day,y2,y10))
    must(len(observations)>=2,"insufficient post-roll rows")
    must(len({x[0] for x in observations})==len(observations),"duplicate provider dates")
    observations.sort(key=lambda x:x[0])
    last=observations[-1]
    must((today-last[0]).days<=8,"eolas provider not current enough")
    must(observations[0][0]==dt.date.fromisoformat(ROLL),"post-roll anchor not supplied")
    return {
        "schema":SCHEMA,"status":"THIRD_PARTY_API_RBNZ_B2_REPUBLISHED_RESEARCH_ONLY",
        "as_of":last[0].isoformat(),"2Y":last[1],"10Y":last[2],
        "curve_bp":round((last[2]-last[1])*100,2),
        "release_date":last[0].isoformat(), # NOT an official release timestamp!
        "release_date_quality":"UNVERIFIED_PROVIDER_AS_OF_ONLY",
        "benchmark_roll_date":ROLL,"benchmark_2Y":NEW_2,"benchmark_10Y":NEW_10,
        "benchmark_note_date":"2026-11-02",
        "post_roll_table_rows":[{"date":x[0].isoformat(),"2Y":x[1],"10Y":x[2]}
                                for x in observations[-12:]],
        "source":"eolas API · redistributed RBNZ B2 closes",
        "source_url":"https://eolas.fyi/datasets/"+DATASET,
        "provider_api_url":URL,
        "source_authority":"RBNZ via eolas; not independently sourced from RBNZ",
        "provider":"eolas","official_html_observed":False,
        "third_party_redistribution":True,
        "independent_xlsx_reconciled":False,
        "eligible_for_core":False,"eligible_for_fx_pair_engine":False,
        "eligible_for_backtests":False,
        "notes":"API key licensed from eolas; B2 redistribution only. Benchmark bond columns required; provider date is NOT source-release date. No Core, no OIS, no cross-roll changes."
    }

def fetch(api_key:str,now:dt.datetime):
    must(bool(api_key.strip()),"EOLAS_API_KEY not configured")
    end=now.astimezone(NZ).date()
    start=dt.date.fromisoformat(ROLL)
    url=URL+"?start="+start.isoformat()+"&end="+end.isoformat()+"&limit=100&format=json"
    req=Request(url,headers={
        "X-API-Key":api_key,
        "Accept":"application/json",
        "User-Agent":"FXQuantV2-NZD-Eolas-API-Research/1.0"
    })
    with urlopen(req,timeout=20) as response:
        must(response.status==200,"provider HTTP response invalid")
        raw=response.read(250_000)
    must(len(raw)<250_000,"provider response size exceeds contract")
    return json.loads(raw.decode("utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--input",type=Path,help="test fixture, no network")
    ap.add_argument("--as-of-nz",help="aware local date fixture")
    a=ap.parse_args()
    now=dt.datetime.fromisoformat(a.as_of_nz) if a.as_of_nz else dt.datetime.now(NZ)
    data=json.loads(a.input.read_text("utf-8")) if a.input else fetch(
        os.environ.get("EOLAS_API_KEY",""),now
    )
    x=parse(data,now_nz=now)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("FXV2_NZD_EO_API_RESEARCH",
          json.dumps({k:x[k] for k in ("as_of","2Y","10Y","provider","third_party_redistribution")}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
