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
import urllib.request
from html.parser import HTMLParser
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
TANKAN_INDEX="https://www.boj.or.jp/en/statistics/tk/yoshi/index.htm"

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
    # The certified original observation is a historical anchor, not a
    # permanent last-date constraint. Every current overlapping observation
    # must still be exactly matched by the official candidate.
    require(ORIGINAL_PERIOD in dates and
            numeric(values[dates.index(ORIGINAL_PERIOD)],label="original anchor")==ORIGINAL_VALUE,
            "canonical JPY credit contract has moved; re-evaluate core isolation")
    for i,period in enumerate(dates):
        require(i==0 or month_num(period)==month_num(dates[i-1])+1,
                "gap or duplicate in canonical monthly history")
    r=candidate.get("runtime") or {}
    require(r.get("last_date")==dates[-1] and
            numeric(r.get("last_value"),label="candidate anchor")==numeric(values[-1],label="current canonical anchor"),
            "candidate was proven against a different canonical feed")
    cnt=candidate.get("runtime_overlap_count")
    require(isinstance(cnt,int) and cnt>=12 and
            candidate.get("runtime_exact_match_count")==cnt and cnt<=len(dates),
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

class TankanTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table":self.table={"caption":"","rows":[]}
        if tag=="caption" and self.table is not None:self.cell=[]
        if tag=="tr" and self.table is not None:self.row=[]
        if tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag=="caption" and self.table is not None and self.cell is not None:
            self.table["caption"]=" ".join(" ".join(self.cell).split());self.cell=None
        if tag in ("td","th") and self.row is not None and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None and self.table is not None:
            self.table["rows"].append(self.row);self.row=None
        if tag=="table" and self.table is not None:self.tables.append(self.table);self.table=None

def tankan_fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"FX-Quant-Research-Sources/1.0","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=30) as response:
        require(response.geturl().startswith("https://www.boj.or.jp/en/statistics/tk/yoshi/"),"unexpected Tankan redirect")
        raw=response.read(3000001)
    require(len(raw)<3000001,"Tankan page too large")
    return raw.decode("utf-8-sig")

def tankan_latest_url(index,today):
    candidates=set(re.findall(r"(?:/en/statistics/tk/yoshi/)?tk([0-9]{4})\.htm",index))
    valid=[]
    for token in candidates:
        year,month=2000+int(token[:2]),int(token[2:])
        if month in (3,6,9,12) and (year,month)<=(today.year,today.month):
            valid.append((year,month,token))
    require(bool(valid),"Tankan official outline links missing")
    return "https://www.boj.or.jp/en/statistics/tk/yoshi/tk"+max(valid)[2]+".htm"

def parse_tankan(html,url,*,today):
    match=re.fullmatch(r"https://www\.boj\.or\.jp/en/statistics/tk/yoshi/tk([0-9]{2})(03|06|09|12)\.htm",url)
    require(match is not None,"Tankan outline URL identity")
    year,month=2000+int(match[1]),int(match[2])
    require((year,month)<=(today.year,today.month),"future Tankan survey")
    prior_year,prior_month=(year-1,12) if month==3 else (year,month-3)
    current=f"{year:04d}-Q{month//3}"
    previous=f"{prior_year:04d}-Q{prior_month//3}"
    require((today-date(year,month,1)).days<=155,"Tankan stale release")
    table=TankanTables();table.feed(html);table.close()
    def read(label,semantic,*,forecast=False):
        hits=[t for t in table.tables if label.lower() in t["caption"].lower() and "all industries" in t["caption"].lower()]
        require(len(hits)==1,"Tankan missing or ambiguous table "+label)
        t=hits[0]
        headers=" ".join(" ".join(r) for r in t["rows"][:3])
        description=t["caption"]+" "+headers
        require(all(word in description.lower() for word in semantic),"Tankan sign definition missing "+label)
        require(str(year) in headers and str(prior_year) in headers,"Tankan survey year header mismatch")
        rows=[r for r in t["rows"] if r and r[0]=="All Enterprises"]
        require(len(rows)==1,"Tankan all-enterprise row missing "+label)
        r=rows[0]
        require(len(r)==(6 if forecast else 4),"Tankan unexpected actual/forecast columns")
        def number(s):
            s=s.replace("−","-").replace("△","-").strip()
            require(re.fullmatch(r"[+-]?[0-9]+",s) is not None,"Tankan nonnumeric DI")
            n=int(s);require(-100<=n<=100,"Tankan DI out of range");return n
        a,b,delta=map(number,r[1:4])
        require(b-a==delta,"Tankan actual change does not reconcile")
        return [a,b]
    lending=read("Lending Attitude of Financial institutions",["accommodative","severe"])
    financial=read("Financial Position",["easy","tight"])
    rates=read("Change in Interest Rate on Loans",["rise","fall"],forecast=True)
    if previous=="2026-Q2":require(lending[0]==13,"Tankan canonical Q2 overlap mismatch")
    return {"source_url":url,"frequency":"Q","unit":"diffusion_index_points","scope":"all enterprises, all industries",
            "positive_lending_means":"accommodative","positive_loan_rate_means":"rise",
            "dates":[previous,current],"lending_attitude":lending,"financial_position":financial,"loan_rate_change":rates,
            "latest_observation":current,"eligible_for_fx_core":False,"eligible_for_backtest":False,
            "first_release_pit_verified":False}

def existing_payload(text):
    start=text.find("const data=")
    if start!=-1:
        try:return json.JSONDecoder().raw_decode(text[start+len("const data="):])[0]
        except ValueError:pass
    return {}

def existing(text):
    arrays=[]
    for key in ("dates","values"):
        m=re.search(r"['\"]?"+key+r"['\"]?\s*:\s*(\[[^\]]*\])",text)
        if not m:return None
        try:arrays.append(ast.literal_eval(m.group(1)))
        except (SyntaxError,ValueError):return None
    return tuple(arrays)

def emit_js(result,checked,tankan=None):
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
    if tankan is not None:out['tankan']=tankan
    return ("'use strict';\n"
       "/* Official BoJ MD11 credit, exact match to canonical history; research-only. */\n"
       "(function(root){\n const data="+json.dumps(out,ensure_ascii=False,indent=1)+";\n"
       " root.FXQuantJPYBankCreditResearch=Object.freeze(data);\n"
       " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
       "})(typeof window!=='undefined'?window:globalThis);\n")

def run(*,candidate_file,destination=DEST,apply=False,today=None,canonical=None,tankan_fixture=None,tankan_url=None,fetch_survey=False):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    candidate=json.loads(Path(candidate_file).read_text(encoding="utf-8"))
    item=parse(candidate,today=today,canonical=canonical)
    old=destination.read_text(encoding="utf-8") if destination.exists() else ""
    original=existing(old) if old else None
    prior=existing_payload(old)
    prior_tankan=prior.get("tankan")
    survey=prior_tankan
    tankan_status={"status":"SKIPPED"}
    if tankan_fixture or fetch_survey:
        try:
            url=tankan_url if tankan_fixture else tankan_latest_url(tankan_fetch(TANKAN_INDEX),today)
            candidate=parse_tankan(Path(tankan_fixture).read_text(encoding="utf-8") if tankan_fixture else tankan_fetch(url),url,today=today)
            if prior_tankan and candidate["latest_observation"]<prior_tankan["latest_observation"]:
                raise ValueError("Tankan source rolled back")
            merged={d:[prior_tankan[k][i] for k in ("lending_attitude","financial_position","loan_rate_change")] for i,d in enumerate(prior_tankan["dates"])} if prior_tankan else {}
            merged.update({d:[candidate[k][i] for k in ("lending_attitude","financial_position","loan_rate_change")] for i,d in enumerate(candidate["dates"])})
            dates=sorted(merged)[-16:]
            survey={**candidate,"dates":dates,**{k:[merged[d][i] for d in dates] for i,k in enumerate(("lending_attitude","financial_position","loan_rate_change"))}}
            tankan_status={"status":"VERIFIED","latest_observation":survey["latest_observation"]}
        except (OSError,ValueError,TypeError,KeyError,UnicodeError) as exc:
            tankan_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(exc)[:300]}
            if prior_tankan:tankan_status["retained_observation"]=prior_tankan["latest_observation"]
    require(not original or not original[0] or item["last_observation"]>=original[0][-1],
            "official BoJ credit observation rolled backward")
    current=(item["dates"],item["values"])
    changed=original!=current or survey!=prior_tankan
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
      "canon_jpy_credit_unchanged":True,"tankan":tankan_status,
      "fx_ranking_effect":"NONE","write_state":"NO_MUTATION"
    }
    if changed and apply:
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(item,today.isoformat(),survey),encoding="utf-8")
        result["write_state"]="RESEARCH_SIDECAR_ONLY"
    return result

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--candidate",type=Path,required=True)
    a.add_argument("--destination",type=Path,default=DEST)
    a.add_argument("--apply",action="store_true")
    a.add_argument("--receipt",type=Path)
    a.add_argument("--fetch-survey",action="store_true")
    args=a.parse_args()
    try:
        result=run(candidate_file=args.candidate,destination=args.destination,apply=args.apply,fetch_survey=args.fetch_survey)
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
