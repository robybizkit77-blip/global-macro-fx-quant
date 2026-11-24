#!/usr/bin/env python3
"""Official Bank of England IADB LPMVTYI mortgage-secured credit growth.

Source contract:
  LPMVTYI = Monthly 12 month growth rate of total sterling net secured lending
  to individuals (in percent), seasonally adjusted.
  CSV export provided by the Bank of England IADB, no API token required.

Not commercial bank reserves RPWB56A, PNFC credit, mortgage origination flow,
mortgage approval counts, or a new 1-month loan growth calculation. Changes
between 12-month growth rates are percentage points, not percent changes.

Fail-closed guards: exact source code and CSV column, issuer host, monthly
chronology, overlap with canonical July 2026 3.6%, 2026 Q3 official reported
August 3.6% and September 3.4%, bounded revisions, no future periods,
no core FX/credit production writes, and no PIT/backtest eligibility.
"""
from __future__ import annotations
import argparse
import ast
import calendar
import csv
import io
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/"site/fx-quant-v2/next/gbp-boe-secured-credit-research-v1.js"
SOURCE="https://www.bankofengland.co.uk/boeapps/database/"
SERIES="LPMVTYI"
API=(SOURCE+"_iadb-fromshowcolumns.asp?"
     "csv.x=yes&Datefrom=01/Jan/2021&Dateto=now&SeriesCodes=LPMVTYI"
     "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
PUBLIC=(SOURCE+"fromshowcolumns.asp?SeriesCodes=LPMVTYI&UsingCodes=Y")
RELEASE="https://www.bankofengland.co.uk/statistics/money-and-credit/2026/september-2026"
SCHEMA="GMFQ_NEXT_GBP_BOE_SECURED_CREDIT_GROWTH_V1"
CCS_ROOT="https://www.bankofengland.co.uk/credit-conditions-survey/"
CCS_INDEX="https://www.bankofengland.co.uk/sitemap/credit-conditions-survey"
KNOWN={"2026-07":3.6,"2026-08":3.6,"2026-09":3.4}
MONTHS={s.lower():i for i,s in enumerate(
    ("","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")) if i}

def require(flag, reason):
    if not flag:
        raise ValueError("BOE_GBP_SECURED_CREDIT_WITHHELD: "+reason)

def fetch():
    req=urllib.request.Request(API,headers={
        "User-Agent":"FXQuant-Official-Macro-Research/1.0",
        "Accept":"text/csv,application/csv,text/plain"})
    with urllib.request.urlopen(req,timeout=35) as reply:
        url=urllib.parse.urlsplit(reply.geturl())
        require(url.scheme=="https" and url.hostname=="www.bankofengland.co.uk"
                and url.path.lower().startswith("/boeapps/database/"),
                "unexpected nonissuer redirect")
        content=reply.read(1_000_001)
    require(len(content)<1_000_001,"source body unexpectedly large")
    return content.decode("utf-8-sig",errors="strict")

def month_from_date(raw):
    s=str(raw).strip().strip('"')
    formats=("%d %b %Y","%d %b %y","%d-%b-%Y","%d-%b-%y",
             "%d/%b/%Y","%d/%b/%y","%Y-%m-%d","%d/%m/%Y","%d/%m/%y")
    when=None
    for f in formats:
        try:
            when=datetime.strptime(s,f).date()
            break
        except ValueError:
            pass
    require(when is not None,"unrecognized BoE IADB observation date")
    require(when.day==calendar.monthrange(when.year,when.month)[1],
            "monthly IADB period must be end-of-month")
    return when.strftime("%Y-%m")

def rows_from_csv(content):
    require(len(content)<1_000_000 and "<html" not in content.lower()
            and "<!doctype" not in content.lower(),
            "IADB returned HTML/error instead of CSV")
    require("LPMVTYI" in content.upper(),
            "exact secured lending code not present in export")
    data=list(csv.reader(io.StringIO(content),skipinitialspace=True))
    require(10<len(data)<180,"unreasonable export row count")
    header_idx=None
    date_col=None
    value_col=None
    for i,row in enumerate(data[:14]):
        norms=[v.strip().strip('"').replace("\ufeff","").upper() for v in row]
        if SERIES not in norms:continue
        vi=norms.index(SERIES)
        di=next((j for j,k in enumerate(norms)
                 if k in ("DATE","DATES","OBSERVATION_DATE","TIME_PERIOD")),None)
        if (di is None and vi>0 and len(norms)>=2 and
                (norms[0]=="" or "DATE" in norms[0])):di=0
        if di is not None:
            header_idx,date_col,value_col=i,di,vi
            break
    require(header_idx is not None,
            "exact LPMVTYI column and DATE header not uniquely identified")
    records={}
    seen=[]
    for row in data[header_idx+1:]:
        if len(row)<=max(date_col,value_col):continue
        d=row[date_col].strip()
        v=row[value_col].strip()
        if not d or v in ("",".",".."):continue
        if d.upper().startswith(("NOTES","SOURCE","DATE")):continue
        month=month_from_date(d)
        try:rate=float(v.replace(",",""))
        except ValueError as e:
            raise ValueError("BOE_GBP_SECURED_CREDIT_WITHHELD: nonnumeric credit growth") from e
        require(math.isfinite(rate) and -15<rate<25,
                "secured lending annual growth outside prudent range")
        require(month not in records,"duplicated month in official IADB export")
        records[month]=round(rate,5)
        seen.append(month)
    require(len(records)>=24,"fewer than 24 validated secured credit months")
    dates=sorted(records)
    require(seen==dates or seen==list(reversed(dates)),
            "unexpected IADB monthly chronology")
    for i in range(1,len(dates)):
        a,b=dates[i-1],dates[i]
        ay,am=int(a[:4]),int(a[5:])
        by,bm=int(b[:4]),int(b[5:])
        require((by*12+bm)-(ay*12+am)==1,
                "monthly official series has an unexpected gap")
        require(abs(records[b]-records[a])<8,
                "unexplained >8 percentage-point monthly growth-rate revision")
    for period,verified in KNOWN.items():
        require(period in records,"missing canonical or September 2026 official overlap")
        require(abs(records[period]-verified)<0.16,
                f"source level or revision variant mismatch at {period}")
    return dates,records

def parse(content,*,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    dates,records=rows_from_csv(content)
    latest=dates[-1]
    y,m=int(latest[:4]),int(latest[5:])
    period_end=date(y,m,calendar.monthrange(y,m)[1])
    require(period_end<=today,"future official observation not yet possible")
    require((today-period_end).days<=110,
            "monthly source too stale to call a successful refresh")
    recent=dates[-48:]
    return {
       "dates":recent,
       "values":[records[d] for d in recent],
       "last_observation":latest,
       "official_july_overlap_revision_pp":round(records["2026-07"]-3.6,4),
       "official_september_overlap_revision_pp":round(records["2026-09"]-3.4,4)
    }

class CCSRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table":self.table=[]
        if tag=="tr" and self.table is not None:self.row=[]
        if tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None and self.table is not None:
            self.table.append(self.row);self.row=None
        if tag=="table" and self.table is not None:
            self.tables.append(self.table);self.table=None

def ccs_fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"FXQuant-Official-Macro-Research/1.0","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=30) as response:
        require(response.geturl().startswith(CCS_ROOT) or response.geturl()==CCS_INDEX,"unexpected CCS redirect")
        raw=response.read(4000001)
    require(len(raw)<4000001,"CCS page too large")
    return raw.decode("utf-8-sig")

def ccs_latest_url(index,today):
    candidates=set(re.findall(r"/credit-conditions-survey/(20[0-9]{2})/20[0-9]{2}-q([1-4])(?=[\"'/?#<])",index,re.I))
    valid=[(int(y),int(q)) for y,q in candidates if (int(y),int(q))<=(today.year,(today.month-1)//3+1)]
    require(bool(valid),"official CCS links missing")
    year,q=max(valid)
    return f"{CCS_ROOT}{year}/{year}-q{q}"

def parse_ccs(html,url,*,today):
    m=re.fullmatch(re.escape(CCS_ROOT)+r"(20[0-9]{2})/\1-q([1-4])",url)
    require(m is not None,"CCS report URL mismatch")
    year,q=map(int,m.groups())
    require((year,q)<=(today.year,(today.month-1)//3+1),"future CCS period")
    require((today-date(year,q*3-2,1)).days<=230,"stale CCS report")
    parser=CCSRows();parser.feed(html);parser.close()
    question="how has the availability of credit provided to the corporate sector overall changed?"
    matches=[]
    for table in parser.tables:
        for i,row in enumerate(table):
            if row and question in row[0].lower() and len(row)>=3 and row[1].lower()=="past three months":
                matches.append((table,i,row))
    require(len(matches)==1,"CCS corporate actual row absent or ambiguous")
    table,i,row=matches[0]
    values=row[2:]
    require(4<=len(values)<=12,"CCS unexpected observation columns")
    require(i+1<len(table) and table[i+1][0].lower()=="next three months","CCS forecast separation not verified")
    quarter_row=next((r for r in reversed(table[:i]) if len(r)>=len(values) and all(re.fullmatch(r"Q[1-4]",x) for x in r[-len(values):])),None)
    require(quarter_row is not None,"CCS quarter header missing")
    dates=[]
    for offset in range(len(values)-1,-1,-1):
        n=year*4+q-1-offset
        dates.append(f"{n//4}-Q{n%4+1}")
    require(quarter_row[-len(values):]==[d[-2:] for d in dates],"CCS quarter chronology mismatch")
    numbers=[]
    for v in values:
        n=float(v.replace("−","-"))
        require(math.isfinite(n) and -100<=n<=100,"CCS invalid balance")
        numbers.append(n)
    if "2026-Q2" in dates:require(abs(numbers[dates.index("2026-Q2")])<.11,"CCS canonical overlap mismatch")
    return {"source_url":url,"series_id":"BOE_CCS_CORPORATE_AVAILABILITY_ACTUAL","frequency":"Q","unit":"net_percentage_balance",
            "positive_means":"increased_availability","negative_means":"decreased_availability",
            "dates":dates,"values":numbers,"latest_observation":dates[-1],
            "first_release_pit_verified":False,"eligible_for_fx_core":False,"eligible_for_backtest":False}

def existing_payload(text):
    start=text.find("const data=")
    if start!=-1:
        try:return json.JSONDecoder().raw_decode(text[start+len("const data="):])[0]
        except ValueError:pass
    return {}

def existing_values(text):
    result=[]
    for field in ("dates","values"):
        match=re.search(r"['\"]?"+field+r"['\"]?\s*:\s*(\[[^\]]*\])",text)
        if not match:return None
        try:result.append(ast.literal_eval(match.group(1)))
        except (ValueError,SyntaxError):return None
    return tuple(result)

def emit_js(parsed,checked,conditions=None):
    data={
      "schema":SCHEMA,
      "status":"VERIFIED_BOE_LPMVTYI_SECURED_GROWTH_RESEARCH_ONLY",
      "country":"GBP","publisher":"Bank of England",
      "series_id":SERIES,
      "source_url":PUBLIC,"api_url":API,
      "official_september_2026_release":RELEASE,
      "official_september_release_date":"2026-10-29",
      "source_contract":"Monthly 12 month growth rate of total sterling net secured lending to individuals, seasonally adjusted",
      "category":"secured_household_credit_yoy_growth",
      "frequency":"M","unit":"percent_yoy","seasonally_adjusted":True,
      "observation_is_not_publication_date":True,
      "first_release_pit_verified":False,
      "eligible_for_fx_core":False,"eligible_for_backtest":False,
      "last_checked_rome":checked,
      **parsed,
      "inference":"Tasso annuo crescita prestiti garantiti alle famiglie; variazioni = punti percentuali. Non nuovi prestiti, riserve BoE, credito alle imprese né trade GBP."
    }
    if conditions is not None:data['lending_conditions']=conditions
    return ("'use strict';\n"
       "/* Official BoE IADB LPMVTYI growth, not sterling reserve stock. */\n"
       "(function(root){\n const data="+json.dumps(data,ensure_ascii=False,indent=1)+";\n"
       " root.FXQuantGBPBoESecuredCreditResearch=Object.freeze(data);\n"
       " if(typeof module!=='undefined'&&module.exports)module.exports=data;\n"
       "})(typeof window!=='undefined'?window:globalThis);\n")

def run(*,destination=DEST,fixture=None,today=None,apply=False,ccs_fixture=None,ccs_url=None):
    today=today or datetime.now(ZoneInfo("Europe/Rome")).date()
    text=destination.read_text(encoding="utf-8") if destination.exists() else ""
    old=existing_values(text) if text else None
    prior=existing_payload(text)
    prior_ccs=prior.get("lending_conditions")
    conditions=prior_ccs
    ccs_status={"status":"SKIPPED_FIXTURE"}
    if ccs_fixture or not fixture:
        try:
            url=ccs_url if ccs_fixture else ccs_latest_url(ccs_fetch(CCS_INDEX),today)
            data=parse_ccs(Path(ccs_fixture).read_text(encoding="utf-8") if ccs_fixture else ccs_fetch(url),url,today=today)
            if prior_ccs and data["latest_observation"]<prior_ccs["latest_observation"]:
                raise ValueError("CCS source rolled back")
            merged=dict(zip(prior_ccs["dates"],prior_ccs["values"])) if prior_ccs else {}
            merged.update(zip(data["dates"],data["values"]))
            dates=sorted(merged)[-20:]
            conditions={**data,"dates":dates,"values":[merged[d] for d in dates]}
            ccs_status={"status":"VERIFIED","latest_observation":data["latest_observation"]}
        except (OSError,ValueError,UnicodeError,TypeError,KeyError) as error:
            ccs_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:300]}
            if prior_ccs:ccs_status["retained_observation"]=prior_ccs["latest_observation"]
    credit_status={"status":"VERIFIED"}
    try:
        parsed=parse(Path(fixture).read_text(encoding="utf-8") if fixture else fetch(),today=today)
    except (OSError,ValueError,UnicodeError) as error:
        if not (old and prior.get("schema")==SCHEMA and conditions!=prior_ccs):raise
        parsed={k:prior[k] for k in ("dates","values","last_observation","official_july_overlap_revision_pp","official_september_overlap_revision_pp")}
        credit_status={"status":"WITHHELD_INVALID_OR_INACCESSIBLE_SOURCE","reason":str(error)[:300]}
    require(old is None or not old[0] or parsed["last_observation"]>=old[0][-1],
            "IADB source unexpectedly rolled back latest release")
    modified=old!=(parsed["dates"],parsed["values"]) or conditions!=prior_ccs
    receipt={
      "schema":"GMFQ_BOE_GBP_SECURED_CREDIT_SOURCE_RECEIPT_V1",
      "status":"UPDATE_AVAILABLE" if modified else "NO_CHANGE",
      "issuer":"Bank of England","series":SERIES,"api_url":API,
      "latest_observation":parsed["last_observation"],
      "latest_growth_yoy_pct":parsed["values"][-1],
      "previous_growth_yoy_pct":parsed["values"][-2],
      "july_revision_pp":parsed["official_july_overlap_revision_pp"],
      "september_revision_pp":parsed["official_september_overlap_revision_pp"],
      "observations":len(parsed["dates"]),
      "checked_rome":today.isoformat(),
      "observed_period_is_not_release_date":True,
      "first_release_pit_verified":False,
      "canonical_liquidity_unchanged":True,
      "fx_rank_effect":"NONE","ccs":ccs_status,"credit":credit_status,
      "write_state":"NO_MUTATION"
    }
    if apply and modified:
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(emit_js(parsed,today.isoformat() if credit_status["status"]=="VERIFIED" else prior["last_checked_rome"],conditions),encoding="utf-8")
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
    except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
        result={
          "schema":"GMFQ_BOE_GBP_SECURED_CREDIT_SOURCE_RECEIPT_V1",
          "status":"WITHHELD_SOURCE_UNAVAILABLE_OR_UNVERIFIED",
          "reason":str(exc)[:340],"write_state":"NO_MUTATION",
          "canonical_liquidity_unchanged":True,"fx_rank_effect":"NONE"
        }
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        a.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"].startswith("WITHHELD"):sys.exit(2)

if __name__=="__main__":main()
