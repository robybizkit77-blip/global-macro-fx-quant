"""Daily/weekly US descriptive histories from FRED, not canonical rates or FX Core."""
from __future__ import annotations
import argparse,copy,csv,json,math,re
from datetime import date,datetime,timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from bs4 import BeautifulSoup
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch

SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
# local id -> FRED ID, title token, units token, cadence, adjustment, old unit
CONFIG={
 "US_CCSA_history_CCSA":("CCSA","Continued Claims (Insured Unemployment)","Number","W","seasonally adjusted",""),
 "US_MORTGAGE30US_history_MORTGAGE30US":("MORTGAGE30US","30-Year Fixed Rate Mortgage Average","Percent","W","not seasonally adjusted",""),
 "US_TOTBKCR_history_value":("TOTBKCR","Bank Credit, All Commercial Banks","Billions of U.S. Dollars","W","seasonally adjusted","Billions of U.S. Dollars"),
 "US_WALCL_history_value":("WALCL","Total Assets (Less Eliminations from Consolidation): Wednesday Level","Millions of U.S. Dollars","W","not seasonally adjusted","Millions of U.S. Dollars"),
 "US_WRESBAL_history_value":("WRESBAL","Reserve Balances with Federal Reserve Banks","Millions of U.S. Dollars","W","not seasonally adjusted","Millions of U.S. Dollars"),
 "US_NFCI_history_value":("NFCI","Chicago Fed National Financial Conditions Index","Index","W","not seasonally adjusted","Index"),
 "US_DTWEXBGS_history_value":("DTWEXBGS","Nominal Broad U.S. Dollar Index","Index Jan 2006=100","D","not seasonally adjusted","Index Jan 2006=100"),
 "US_T10YIE_history_T10YIE":("T10YIE","10-Year Breakeven Inflation Rate","Percent","D","not seasonally adjusted",""),
 "US_DFII10_history_DFII10":("DFII10","Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity, Quoted on an Investment Basis, Inflation-Indexed","Percent","D","not seasonally adjusted",""),
 **{f"US_DGS{n}_history_DGS{n}":(f"DGS{n}",f"Market Yield on U.S. Treasury Securities at {n}-Year Constant Maturity, Quoted on an Investment Basis","Percent","D","not seasonally adjusted","") for n in (2,5,10,30)},
}
SCHEMA="GMFQ_US_MARKET_WEEKLY_REVISED_FRED_RESEARCH_V1"
def need(ok,reason):
    if not ok:raise ValueError(reason)
def norm(s):return " ".join(s.replace("–","-").replace("’","'").split()).casefold()
def metadata(raw,fred,title,unit,freq,adjustment):
    soup=BeautifulSoup(raw,"html.parser")
    heading=norm(soup.title.get_text(" ",strip=True) if soup.title else "")
    need(norm(title) in heading and fred.casefold() in heading,"FRED series title mismatch: "+heading[:180])
    text=norm(soup.get_text(" ",strip=True))
    units=re.search(r"units:\s*(.*?)\s*frequency:",text)
    actual=units.group(1) if units else ""
    need(norm(unit) in actual and adjustment in actual and
         (adjustment!="seasonally adjusted" or "not seasonally adjusted" not in actual),"FRED unit/adjustment mismatch: "+actual[:180])
    need(re.search(r"frequency:\s*"+("weekly" if freq=="W" else "daily")+r"\b",text),"FRED cadence mismatch")
    return actual
def csv_rows(raw,fred,now):
    reader=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    need(reader.fieldnames in (["observation_date",fred],["DATE",fred]),"FRED CSV identity mismatch")
    out={}
    for r in reader:
        stamp=r[reader.fieldnames[0]]
        d=date.fromisoformat(stamp)
        need(stamp==d.isoformat() and d<=now,"invalid/future source date")
        need(stamp not in out,"duplicate date")
        if r[fred] in ("","."):continue
        v=float(r[fred]);need(math.isfinite(v),"nonfinite source value")
        out[stamp]=v
    need(len(out)>=20 and list(out)==sorted(out),"source window too short or unsorted")
    return out
def prepare_row(row,ident,now,fetcher):
    fred,title,unit,freq,adjustment,old_unit=CONFIG[ident]
    new_unit=old_unit or unit
    need(row["source_file"]=="US_"+fred+"_history.csv" and row.get("unit") in (old_unit,new_unit)
         and row.get("frequency") in ("",freq),"canonical series identity mismatch")
    need(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"canonical history inconsistent")
    url="https://fred.stlouisfed.org/series/"+fred
    raw,final=fetcher(url);need(urlsplit(final).path=="/series/"+fred,"metadata redirect")
    verified=metadata(raw,fred,title,unit,freq,adjustment)
    csv_url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":fred,"cosd":row["dates"][0]})
    raw_csv,final=fetcher(csv_url);need(urlsplit(final).path=="/graph/fredgraph.csv","CSV redirect")
    obs=csv_rows(raw_csv,fred,now.date())
    ds=[d for d in obs if d>=row["dates"][0]]
    vs=[obs[d] for d in ds]
    need(ds and ds[0]==row["dates"][0] and ds[-1]>=row["last_date"] and set(row["dates"])<=set(ds),"source does not cover canonical dates; do not relabel or fill gaps")
    if freq=="W":
        gaps=[(date.fromisoformat(b)-date.fromisoformat(a)).days for a,b in zip(ds,ds[1:])]
        # Freddie Mac can publish on a different weekday around holidays.
        # Preserve actual dates; do not synthesize or shift observations.
        if fred=="MORTGAGE30US":
            need(all(5<=g<=9 for g in gaps),"mortgage weekly source cadence incompatible")
            need(len({d.isocalendar()[:2] for d in map(date.fromisoformat,ds)})==len(ds),"duplicate mortgage ISO week")
        else:
            need(all(g==7 for g in gaps),"weekly source cadence not contiguous")
    before=row["last_date"]
    changed=row["dates"]!=ds or row["values"]!=vs or row.get("frequency")!=freq or row.get("unit")!=new_unit or row.get("current_vintage_provenance",{}).get("source_series_id")!=fred
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],frequency=freq,unit=new_unit,
          current_vintage_provenance={"status":"FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":fred,"source_url":url,"source_csv_url":csv_url,
           "source_csv_sha256":sha256(raw_csv).hexdigest(),"source_metadata_sha256":sha256(raw).hexdigest(),"source_units_verified":verified,
           "source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat(),"historical_levels_may_be_revised_again":True})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1]}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current); receipts=[]
    for ident in CONFIG:
        try:
            rows=[r for r in out["USD"] if r["id"]==ident];need(len(rows)==1,"unique series required")
            candidate=copy.deepcopy(rows[0]);receipt=prepare_row(candidate,ident,now,fetcher);rows[0].update(candidate);receipts.append(receipt)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":SCHEMA,"observed_at_utc":now.isoformat(),"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD",
                "series":receipts,"first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",required=True,type=Path);p.add_argument("--receipt",required=True,type=Path);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
