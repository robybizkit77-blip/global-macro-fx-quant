"""Refresh US monthly descriptive histories from FRED's published revised vintage.
No first-release PIT claim, heatmap mutation or FX score promotion.
Each source fails independently and retains the prior verified row.
"""
from __future__ import annotations
import argparse, copy, json, math, re
from datetime import datetime, timezone, date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from bs4 import BeautifulSoup
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch,fred_monthly_csv

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"live_data/sections/MACRO_SERIES.json"
# Exact local import identity, FRED series ID, metadata title and unit tokens,
# expected canonical unit (blank only for previously unannotated imports).
CONFIG={
 "US_INDPRO_history_value":("INDPRO","US_INDPRO_history.csv","Industrial Production", "Index 2017=100","Index 2017=100"),
 "US_CPILFESL_history_value":("CPILFESL","US_CPILFESL_history.csv","Consumer Price Index for All Urban Consumers: All Items Less Food and Energy","Index 1982-1984=100","Index 1982-1984=100"),
 "US_PCEPILFE_history_value":("PCEPILFE","US_PCEPILFE_history.csv","Personal Consumption Expenditures Excluding Food and Energy","Index 2017=100","Index 2017=100"),
 "US_PCEPI_history_value":("PCEPI","US_PCEPI_history.csv","Personal Consumption Expenditures: Chain-type Price Index","Index 2017=100","Index 2017=100 SA"),
 "US_JTSJOL_history_value":("JTSJOL","US_JTSJOL_history.csv","Job Openings: Total Nonfarm","Thousands of Levels","Thousands of job openings, seasonally adjusted"),
 "US_PAYEMS_history_value":("PAYEMS","US_PAYEMS_history.csv","All Employees, Total Nonfarm","Thousands of Persons","Thousands of persons"),
 "US_M2SL_history_value":("M2SL","US_M2SL_history.csv","M2","Billions of Dollars","Billions of U.S. dollars, seasonally adjusted"),
 "US_AHE_TOTAL_PRIVATE_history_value":("CES0500000003","US_AHE_TOTAL_PRIVATE_history.csv","Average Hourly Earnings of All Employees, Total Private","Dollars per Hour","U.S. dollars per hour, seasonally adjusted"),
 "US_NEWORDER_history_NEWORDER":("NEWORDER","US_NEWORDER_history.csv","Manufacturers' New Orders: Nondefense Capital Goods Excluding Aircraft","Millions of Dollars",""),
 "US_PI_history_PI":("PI","US_PI_history.csv","Personal Income","Billions of Dollars",""),
 "US_PSAVERT_history_PSAVERT":("PSAVERT","US_PSAVERT_history.csv","Personal Saving Rate","Percent",""),
 "US_JTSHIR_history_JTSHIR":("JTSHIR","US_JTSHIR_history.csv","Hires: Total Nonfarm","Thousands of Levels",""),
 "US_JTSQUR_history_JTSQUR":("JTSQUR","US_JTSQUR_history.csv","Quits: Total Nonfarm","Thousands of Levels",""),
 "US_HOUST_history_HOUST":("HOUST","US_HOUST_history.csv","New Privately-Owned Housing Units Started: Total Units","Thousands of Units",""),
 "US_PERMIT_history_PERMIT":("PERMIT","US_PERMIT_history.csv","New Privately-Owned Housing Units Authorized","Thousands of Units",""),
 "US_HSN1F_history_HSN1F":("HSN1F","US_HSN1F_history.csv","New One Family Houses Sold","Thousands of Units",""),
}
SCHEMA="GMFQ_US_MONTHLY_REVISED_FRED_RESEARCH_V1"
def require(ok,message):
    if not ok: raise ValueError(message)

def metadata(raw,fred,title,unit):
    soup=BeautifulSoup(raw,"html.parser")
    def norm(x):
        return " ".join(x.replace("’","'").replace("–","-").split()).casefold()
    heading=norm(soup.title.get_text(" ",strip=True) if soup.title else "")
    require(norm(title) in heading and fred.casefold() in heading,"FRED title or series identity mismatch")
    text=norm(soup.get_text(" ",strip=True))
    # FRED labels are part of the source metadata; never infer cadence from numbers.
    units=re.search(r"units:\s*(.*?)\s*frequency:",text)
    require(units and norm(unit) in units.group(1) and "seasonally adjusted" in units.group(1)
            and "not seasonally adjusted" not in units.group(1),"FRED unit or seasonal adjustment mismatch: "+str(units.group(1) if units else None))
    require(re.search(r"frequency:\s*monthly\b",text),"FRED frequency mismatch")
    return units.group(1)

def prepare_row(row,ident,now,fetcher):
    fred,source,title,unit,old_unit=CONFIG[ident]
    require(row["source_file"]==source and row.get("frequency") in ("","M")
            and row.get("unit") in (old_unit,unit),"canonical source/unit/frequency mismatch")
    require(row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"inconsistent local latest")
    metadata_url="https://fred.stlouisfed.org/series/"+fred
    raw_meta,final=fetcher(metadata_url)
    require(urlsplit(final).path.rstrip("/")=="/series/"+fred,"unexpected FRED metadata redirect")
    verified_units=metadata(raw_meta,fred,title,unit)
    csv_url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":fred,"cosd":str(row["dates"][0])[:7]+"-01"})
    raw_csv,final=fetcher(csv_url)
    require(urlsplit(final).path=="/graph/fredgraph.csv","unexpected FRED CSV redirect")
    parsed=fred_monthly_csv(raw_csv,fred,now.date())
    # Source helper's complete window begins 2019-10, sufficient for these imports.
    lookup={r["date"][:7]:r["value"] for r in parsed["revised_vintage_monthly_history"]}
    start=str(row["dates"][0])[:7]
    months=sorted(m for m in lookup if m>=start)
    require(months and months[0]==start and months[-1]>=str(row["last_date"])[:7],"source does not cover canonical window")
    require(set(str(x)[:7] for x in row["dates"])<=set(months),"source history loses existing periods")
    def ordinal(m):return int(m[:4])*12+int(m[5:7])
    require(all(ordinal(b)-ordinal(a)==1 for a,b in zip(months,months[1:])),"noncontiguous revised history")
    # Keep existing storage precision so the page adapters continue to work.
    ds=[m+"-01" if len(str(row["dates"][0]))==10 else m for m in months]
    vs=[lookup[m] for m in months]
    new_unit=old_unit or unit
    provenance={"status":"FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT",
        "source_series_id":fred,"source_url":metadata_url,"source_csv_url":csv_url,
        "source_csv_sha256":sha256(raw_csv).hexdigest(),"source_metadata_sha256":sha256(raw_meta).hexdigest(),
        "source_units_verified":verified_units,"source_series_first_release_PIT_certified":False,
        "historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()}
    before=row["last_date"]
    changed=(row["dates"]!=ds or row["values"]!=vs or row.get("unit")!=new_unit or row.get("frequency")!="M"
             or row.get("current_vintage_provenance",{}).get("source_series_id")!=fred)
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],unit=new_unit,frequency="M",
                   current_vintage_provenance=provenance)
    return {"id":ident,"fred_id":fred,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1]}

def prepare(current,*,now,fetcher=fetch):
    require(now.utcoffset() is not None,"aware observation clock required")
    out=copy.deepcopy(current); receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["USD"] if r["id"]==ident]
            require(len(hits)==1,"unique source row required")
            candidate=copy.deepcopy(hits[0])
            result=prepare_row(candidate,ident,now,fetcher)
            hits[0].update(candidate)
            receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":SCHEMA,"observed_at_utc":now.isoformat(),
        "status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD",
        "series":receipts,"first_release_PIT_certified":False,"affects_fx_core":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True,type=Path);p.add_argument("--receipt",required=True,type=Path)
    a=p.parse_args()
    require(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary outputs only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
