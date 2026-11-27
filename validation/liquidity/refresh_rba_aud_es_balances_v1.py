#!/usr/bin/env python3
"""Reserve Bank of Australia weekly Balance Sheet ES reserves, read-only FX research.

Official source: https://www.rba.gov.au/statistics/balance-sheet/
"Exchange Settlement balances" current balance and weekly movement, AUD millions.
Cross-checked with A3 AESAT and canonical weekly AUD liquidity for 2026-09-16.

Do NOT confuse RBA settlement account balances with credit supply, net liquidity
injections, commercial bank lending or any FX flows. The weekly movement is
published directly; previous balance is *implied*, not independently fetched.
Neither current nor historical release timestamp or PIT vintage is certified.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
SOURCE="https://www.rba.gov.au/statistics/balance-sheet/"
DEST=ROOT/"site/fx-quant-v2/next/aud-rba-es-balances-research-v1.js"
CANONICAL=ROOT/"live_data/sections/NATIVE_LIQ_DATA.json"
SCHEMA="GMFQ_NEXT_AUD_RBA_ES_BALANCES_V1"
ANCHOR_DATE="2026-09-16"
ANCHOR_VALUE=173965
MONTHS={v:i for i,v in enumerate(("","January","February","March","April",
                                  "May","June","July","August","September",
                                  "October","November","December")) if v}
MONTHS_LOWER={k.lower():v for k,v in MONTHS.items()}

def require(ok,why):
    if not ok: raise ValueError("RBA_AUD_ES_SOURCE_WITHHELD: "+why)

class RbaBalanceSheetHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.segments=[]
        self.tables=[]
        self.table_depth=0
        self.rows=None
        self.cells=None
        self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table":
            self.table_depth+=1
            if self.table_depth==1:self.rows=[]
        if tag=="tr" and self.table_depth==1:self.cells=[]
        if tag in ("td","th") and self.cells is not None:self.cell=[]
    def handle_data(self,s):
        self.segments.append(s)
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell=None
        if tag=="tr" and self.cells is not None:
            self.rows.append(self.cells)
            self.cells=None
        if tag=="table" and self.table_depth:
            if self.table_depth==1:self.tables.append(self.rows)
            self.table_depth-=1
            self.rows=None
    @property
    def text(self):return " ".join(" ".join(self.segments).split())

def fetch():
    request=urllib.request.Request(SOURCE,headers={
        "User-Agent":"FX-Quant-Official-Source-Research/1.0",
        "Accept":"text/html"})
    with urllib.request.urlopen(request,timeout=25) as response:
        p=urllib.parse.urlsplit(response.geturl())
        require(p.scheme=="https" and p.hostname=="www.rba.gov.au" and
                p.path=="/statistics/balance-sheet/",
                "issuer URL changed unexpectedly")
        raw=response.read(1_500_001)
    require(len(raw)<1_500_001,"RBA document unexpectedly large")
    return raw.decode("utf-8",errors="replace")

def parse_value(raw,allow_negative=False):
    s=raw.replace("\u2212","-").replace("\xa0","").strip()
    require(bool(re.fullmatch(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)",s)),
            "unparseable RBA audited balance-sheet value")
    value=int(s.replace(",",""))
    require(allow_negative or value>0,"nonpositive RBA reserve balance")
    return value

def parse(html,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    doc=RbaBalanceSheetHTML()
    doc.feed(html);doc.close()
    text=doc.text
    require("Reserve Bank of Australia Balance Sheet" in text,
            "source is not RBA official balance-sheet report")
    match=re.search(r"At close of business on (Monday|Tuesday|Wednesday|Thursday|Friday),?\s+"
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",text)
    require(match is not None,"issuer close-of-business observation date absent")
    weekday,day,month,year=match.groups()
    month_n=MONTHS_LOWER.get(month.lower())
    require(month_n is not None,"unknown RBA month")
    observed=date(int(year),month_n,int(day))
    require(observed.strftime("%A")==weekday,"issuer weekday/date mismatch")
    require(observed.weekday()==2,"A3 comparable weekly RBA balance sheet must be Wednesday")
    require(observed<=today,"future observation from issuer")
    require((today-observed).days<=25,"official weekly observation excessively stale")
    require("$ million" in text or "$ million" in html,
            "RBA AUD million unit missing")
    candidates=[]
    for table in doc.tables:
        for row in table or []:
            if len(row)>=3 and row[0].strip().lower()=="exchange settlement balances":
                candidates.append(row)
    require(len(candidates)==1,
            "nonunique official Exchange Settlement balances liability row")
    raw_row=candidates[0]
    current=parse_value(raw_row[1])
    change=parse_value(raw_row[2],allow_negative=True)
    require(10000<current<900000,"implausible RBA ES balance stock")
    require(abs(change)<=150000,"implausible RBA weekly movement")
    previous=current-change
    require(previous>0 and abs(change)/previous<.8,
            "weekly change too large for source continuity")
    return {
      "source_period":observed.isoformat(),
      "latest_balance_million_aud":current,
      "weekly_movement_million_aud":change,
      "previous_implied_million_aud":previous,
      "source_release_timestamp_verified":False
    }

def validate_canonical(raw=None):
    raw=json.loads(CANONICAL.read_text(encoding="utf-8")) if raw is None else raw
    a=raw["AUD"]["liquidity"]
    dates,values=a["dates"],a["values"]
    require(bool(dates) and len(dates)==len(values) and dates==sorted(set(dates)),
            "invalid canonical RBA weekly chronology")
    require(a["last_date"]==dates[-1] and a["last_value"]==values[-1],
            "canonical RBA weekly last observation mismatch")
    history=dict(zip(dates,values))
    # Preserve the verified historical observation, not the old end of series.
    require(history.get(ANCHOR_DATE)==ANCHOR_VALUE,
            "existing canonical weekly AUD liquidity anchor changed: recheck overlap")
    return history

def validate_source_overlap(parsed,history):
    observed=parsed["source_period"]
    previous=(date.fromisoformat(observed)-timedelta(days=7)).isoformat()
    for period,value in ((observed,parsed["latest_balance_million_aud"]),
                         (previous,parsed["previous_implied_million_aud"])):
        if period in history:
            require(history[period]==value,
                    "RBA weekly source/canonical overlap mismatch on "+period)
    return [period for period in (observed,previous) if period in history]

def emit_js(data,checked):
    obj={
       "schema":SCHEMA,
       "status":"VERIFIED_RBA_WEEKLY_ES_BALANCE_RESEARCH_ONLY",
       "country":"AUD",
       "publisher":"Reserve Bank of Australia",
       "source_url":SOURCE,
       "source_contract":"RBA weekly balance sheet / Exchange Settlement balances",
       "a3_comparison_contract":"A3 AESAT / Total ES Balances, same category, different source frequency",
       "unit":"milioni AUD",
       "frequency":"W",
       "asof_canonical_overlap":ANCHOR_DATE,
       "value_canonical_overlap":ANCHOR_VALUE,
       "last_checked_rome":checked,
       **data,
       "first_release_pit_verified":False,
       "eligible_for_fx_core":False,
       "eligible_for_backtest":False,
       "observation_is_not_publication_date":True,
       "inference":"Riserve presso RBA, non credito nuovo, non liquidità netta disponibile a nonbanche, non flussi Forex. Movimento settimanale pubblicato direttamente, precedente ricavato per sottrazione."
    }
    return ("'use strict';\n"
      "/* Official RBA weekly settlement balances; separate research source. */\n"
      "(function(root){\n const data="+json.dumps(obj,ensure_ascii=False,indent=1)
      +";\n root.FXQuantAUDESBalancesResearch=Object.freeze(data);\n"
      " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
      "})(typeof window!=='undefined'?window:globalThis);\n")

def previous_values(text):
    out={}
    for key in ("source_period","latest_balance_million_aud",
                "weekly_movement_million_aud","previous_implied_million_aud"):
        m=re.search(r"['\"]?"+key+r"['\"]?\s*:\s*(\"[^\"]*\"|-?\d+)",text)
        if not m:return None
        out[key]=json.loads(m.group(1))
    return out

def run(*,destination=DEST,fixture=None,apply=False,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    history=validate_canonical()
    parsed=parse(Path(fixture).read_text(encoding="utf-8") if fixture else fetch(),
                 today=today)
    overlap=validate_source_overlap(parsed,history)
    old=previous_values(destination.read_text(encoding="utf-8")) if destination.exists() else None
    require(old is None or parsed["source_period"]>=old["source_period"],
            "issuer rolled back to an older balance-sheet observation")
    changed=old!={
      key:parsed[key] for key in (
        "source_period","latest_balance_million_aud","weekly_movement_million_aud",
        "previous_implied_million_aud")
    }
    receipt={
       "schema":"GMFQ_RBA_ES_BALANCES_RECEIPT_V1",
       "status":"UPDATE_AVAILABLE" if changed else "NO_CHANGE",
       "source":SOURCE,
       "source_period":parsed["source_period"],
       "value_million_aud":parsed["latest_balance_million_aud"],
       "weekly_movement_million_aud":parsed["weekly_movement_million_aud"],
       "prior_balance_implied_not_directly_observed":True,
       "current_source_canonical_overlap_dates":overlap,
       "canonical_overlap":ANCHOR_DATE,
       "canonical_overlap_value":ANCHOR_VALUE,
       "checked_rome":today.isoformat(),
       "first_release_pit_verified":False,
       "canonical_liquidity_unchanged":True,
       "fx_rank_effect":"NONE",
       "write_state":"NO_MUTATION"
    }
    if apply and changed:
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
    a=p.parse_args()
    try:
        result=run(destination=a.destination,fixture=a.fixture,apply=a.apply)
    except (OSError,TimeoutError,ValueError,UnicodeError) as ex:
        result={
          "schema":"GMFQ_RBA_ES_BALANCES_RECEIPT_V1",
          "status":"WITHHELD_SOURCE_UNAVAILABLE_OR_UNVERIFIED",
          "reason":str(ex)[:320],
          "write_state":"NO_MUTATION",
          "canonical_liquidity_unchanged":True,
          "fx_rank_effect":"NONE"
        }
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        a.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__":
    main()
