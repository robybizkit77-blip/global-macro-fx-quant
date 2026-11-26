"""Refresh explicitly mapped US weekly research histories; no PIT or FX score promotion."""
from __future__ import annotations
import argparse, copy, csv, json, math, re
from datetime import datetime, timezone, date
from hashlib import sha256
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from bs4 import BeautifulSoup
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"live_data/sections/MACRO_SERIES.json"
SCHEMA="GMFQ_US_WEEKLY_REVISED_FRED_RESEARCH_V1"
# FRED IDs, source identity, unit, seasonal convention and exact weekday.
# ICSA is not included: existing imports end on Friday, not the issuer's Saturday.
CONFIG={
 "US_CCSA_history_CCSA":("CCSA","Continued Claims (Insured Unemployment)","Number","Seasonally Adjusted",5,""),
 "US_MORTGAGE30US_history_MORTGAGE30US":("MORTGAGE30US","30-Year Fixed Rate Mortgage Average in the United States","Percent","Not Seasonally Adjusted",3,""),
 "US_TOTBKCR_history_value":("TOTBKCR","Bank Credit, All Commercial Banks","Billions of U.S. Dollars","Seasonally Adjusted",2,"Billions of U.S. Dollars"),
 "US_WALCL_history_value":("WALCL","Assets: Total Assets: Total Assets","Millions of U.S. Dollars","Not Seasonally Adjusted",2,"Millions of U.S. Dollars"),
 "US_WRESBAL_history_value":("WRESBAL","Reserve Balances with Federal Reserve Banks","Millions of U.S. Dollars","Not Seasonally Adjusted",2,"Millions of U.S. Dollars"),
 "US_NFCI_history_value":("NFCI","Chicago Fed National Financial Conditions Index","Index","Not Seasonally Adjusted",4,"Index"),
}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def verify_metadata(raw,fred,title,unit,adjustment):
    soup=BeautifulSoup(raw,"html.parser")
    norm=lambda s:" ".join(s.replace("’","'").replace("–","-").split()).casefold()
    heading=norm(soup.title.get_text(" ",strip=True) if soup.title else "")
    require(norm(title) in heading and fred.casefold() in heading,"FRED series title mismatch")
    text=norm(soup.get_text(" ",strip=True))
    m=re.search(r"units:\s*(.*?)\s*frequency:",text)
    require(m is not None,"missing FRED units")
    u=m.group(1)
    require(norm(unit) in u and norm(adjustment) in u and
            ("not seasonally adjusted" in u)==(adjustment=="Not Seasonally Adjusted"),
            "FRED unit/adjustment mismatch: "+u)
    require(re.search(r"frequency:\s*weekly\b",text),"not weekly frequency")
    return u
def parse_weekly(raw,fred,weekday,today):
    reader=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    require(reader.fieldnames in (["DATE",fred],["observation_date",fred]),"CSV source identity mismatch")
    rows=[]
    for r in reader:
        dt=date.fromisoformat(r[reader.fieldnames[0]])
        require(dt<=today and dt.weekday()==weekday,"future or inconsistent observation weekday")
        if r[fred] in ("","."): continue
        n=float(r[fred])
        require(math.isfinite(n),"nonfinite observation")
        require(fred=="NFCI" or n>0,"nonpositive level")
        rows.append((dt,n))
    require(len(rows)>=24,"insufficient weekly history")
    require(all((b[0]-a[0]).days==7 for a,b in zip(rows,rows[1:])),"weekly history gap or duplicate")
    return rows
def prepare_row(row,ident,now,fetcher):
    fred,title,unit,adj,weekday,old_unit=CONFIG[ident]
    new_unit=old_unit or unit
    require(row["source_file"]=="US_"+fred+"_history.csv" and row.get("unit") in (old_unit,new_unit)
            and row.get("frequency") in ("","W"),"canonical source/unit mismatch")
    require(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"inconsistent canonical row")
    old_dates=[date.fromisoformat(d) for d in row["dates"]]
    require(all(d.weekday()==weekday for d in old_dates),"canonical weekday differs from publisher")
    meta_url="https://fred.stlouisfed.org/series/"+fred
    raw_meta,final=fetcher(meta_url)
    require(urlsplit(final).scheme=="https" and urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path.rstrip("/")=="/series/"+fred,"metadata URL mismatch")
    verified=verify_metadata(raw_meta,fred,title,unit,adj)
    csv_url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":fred,"cosd":old_dates[0].isoformat()})
    raw,final=fetcher(csv_url)
    require(urlsplit(final).scheme=="https" and urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path=="/graph/fredgraph.csv","CSV URL mismatch")
    observations=[(d,v) for d,v in parse_weekly(raw,fred,weekday,now.date()) if d>=old_dates[0]]
    ds=[d.isoformat() for d,v in observations];vs=[v for d,v in observations]
    require(ds and ds[0]==row["dates"][0] and ds[-1]>=row["last_date"] and set(row["dates"])<=set(ds),"weekly history coverage regression")
    before=row["last_date"]
    changed=(row["dates"]!=ds or row["values"]!=vs or row.get("unit")!=new_unit or row.get("frequency")!="W" or row.get("current_vintage_provenance",{}).get("source_series_id")!=fred)
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],unit=new_unit,frequency="W",
            current_vintage_provenance={"status":"FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":fred,
            "source_url":meta_url,"source_csv_url":csv_url,"source_csv_sha256":sha256(raw).hexdigest(),
            "source_metadata_sha256":sha256(raw_meta).hexdigest(),"source_units_verified":verified,
            "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,
            "runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"fred_id":fred,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1]}
def prepare(current,*,now,fetcher=fetch):
    require(now.utcoffset() is not None,"aware capture clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["USD"] if r["id"]==ident]
            require(len(hits)==1,"unique historical source required")
            candidate=copy.deepcopy(hits[0])
            result=prepare_row(candidate,ident,now,fetcher)
            hits[0].update(candidate);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":SCHEMA,"observed_at_utc":now.isoformat(),"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","series":receipts,"first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True)
    a=p.parse_args()
    require(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary outputs only")
    out,r=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    a.receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(r,sort_keys=True))
if __name__=="__main__":main()
