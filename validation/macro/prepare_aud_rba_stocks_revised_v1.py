"""Official RBA stocks, current revised history; never infer break-adjusted growth."""
from __future__ import annotations
import argparse,copy,csv,json,math,re,statistics
from datetime import datetime,timezone,date
from hashlib import sha256
from io import StringIO
from pathlib import Path
from urllib.request import Request,urlopen
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
# table, exact series ID, normalized title, frequency, legacy unit, target unit
CONFIG={
 "AU_CREDIT_BUSINESS_CURRENT_SA_history_value":("d2","DLCACSFBS","credit business including select financial businesses seasonally adjusted","M","AUD billions","AUD billions"),
 "AU_MORTGAGE_RATE_OWNER_OCC_OUTSTANDING_history_value":("f6","FLRHOOTA","lending rates housing credit outstanding owner occupied all loans all institutions","M","Percent per annum","Percent per annum"),
 "AU_BUSINESS_LENDING_RATE_MEDIUM_OUTSTANDING_history_value":("f7","FLRBFOMBT","lending rates business finance outstanding medium business total","M","Percent per annum","Percent per annum"),
 "AU_CREDIT_INVESTOR_HOUSING_SA_history_value":("d2","DLCACIHS","credit investor housing seasonally adjusted","M","AUD billions","AUD billions"),
 "AU_CREDIT_OWNER_OCC_HOUSING_SA_history_value":("d2","DLCACOHS","credit owner occupier housing seasonally adjusted","M","AUD billions","AUD billions"),
 "AU_CREDIT_OTHER_PERSONAL_SA_history_value":("d2","DLCACOPS","credit other personal seasonally adjusted","M","AUD billions","AUD billions"),
 "AU_BROAD_MONEY_SA_history_value":("d3","DMABMS","broad money seasonally adjusted","M","AUD millions","AUD billions"),
 "AU_EXCHANGE_SETTLEMENT_BALANCES_history_value":("a1","ARBALESBW","exchange settlement balances","W","AUD millions","AUD millions"),
 "AU_RBA_TOTAL_ASSETS_history_value":("a1","ARBAATAW","total assets","W","AUD millions","AUD millions"),
}
BASE="https://www.rba.gov.au/statistics/tables/csv/"
def need(ok,why):
    if not ok:raise ValueError(why)
def norm(s):return re.sub(r"[^a-z0-9]+"," ",s.lower()).strip()
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0","Accept":"text/csv"}),timeout=30) as r:
        need(r.status==200 and r.geturl()==url,"RBA source redirect")
        raw=r.read(4_000_001)
    need(0<len(raw)<=4_000_000,"invalid source size")
    return raw
def parse_date(s):
    for f in ("%Y-%m-%d","%d-%b-%Y","%d/%m/%Y","%d %b %Y"):
        try:return datetime.strptime(s,f).date()
        except ValueError:pass
    return None
def parse(raw,ident,now):
    table,code,title,freq,old_unit,target=CONFIG[ident]
    rows=list(csv.reader(StringIO(raw.decode("utf-8-sig"))))
    meta={}
    for row in rows[:30]:
        if row and row[0].strip().lower() in ("title","description","units","frequency","series id"):
            label=row[0].strip().lower();need(label not in meta,"duplicate metadata");meta[label]=row
    ids=meta.get("series id",[])
    cols=[i for i,v in enumerate(ids) if v.strip().upper()==code]
    need(len(cols)==1,"RBA series ID absent/ambiguous: "+code)
    i=cols[0]
    def field(k):
        values=meta.get(k,[])
        return values[i].strip() if i<len(values) else ""
    actual_title=norm(field("title") or field("description"))
    need(actual_title==title,"RBA title mismatch: "+actual_title)
    need(field("frequency").casefold()==("monthly" if freq=="M" else "weekly"),"RBA frequency mismatch")
    unit=norm(field("units"))
    rate=target=="Percent per annum"
    if rate:
        need(unit in ("per cent per annum","percent per annum"),"RBA rate unit mismatch: "+unit)
        factor=1
    else:
        need(unit in ("billion","billions","million","millions","a billion","a billion dollars","a million","a million dollars","aud billion","aud billions","aud million","aud millions","billions of dollars","millions of dollars"),"RBA monetary unit mismatch: "+unit)
        source_billion="billion" in unit
        target_billion="billions" in target
        factor=1 if source_billion==target_billion else (1000 if source_billion else .001)
    obs={}
    for row in rows:
        if not row or len(row)<=i:continue
        d=parse_date(row[0].strip())
        if d is None or row[i].strip() in ("","..","-","na","NA"):continue
        need(d<=now.date() and d not in obs,"future or duplicate date")
        v=float(row[i].strip().replace(",",""))*factor
        need(math.isfinite(v) and (0<v<=30 if rate else v>0),"invalid RBA observation")
        obs[d]=v
    need(len(obs)>=24,"short RBA history")
    return obs,field("units")
def prepare_row(row,ident,now,raw):
    table,code,title,freq,old_unit,target=CONFIG[ident]
    need(row["source_file"]==ident.removesuffix("_value")+".csv" and row["frequency"]==freq and row["unit"] in (old_unit,target),"canonical identity mismatch")
    need(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"inconsistent canonical row")
    obs,source_unit=parse(raw,ident,now)
    old_dates=[parse_date(x) for x in row["dates"]]
    need(all(x is not None for x in old_dates),"legacy date parsing failed")
    ds=sorted(d for d in obs if d>=old_dates[0])
    need(ds and ds[0]==old_dates[0] and ds[-1]>=old_dates[-1] and set(old_dates)<=set(ds),"history regression or incompatible period semantics")
    if freq=="W":
        need(all((b-a).days==7 for a,b in zip(ds,ds[1:])),"weekly cadence mismatch")
    else:
        need(all((b.year-a.year)*12+b.month-a.month==1 for a,b in zip(ds,ds[1:])),"monthly cadence mismatch")
    strict=table in ("f6","f7") or code=="DLCACSFBS"
    overlap=list(zip(old_dates,row["values"]))
    if not strict:overlap=overlap[-12:]
    errors=[abs(obs[d]-float(v))/max(abs(float(v)),1) for d,v in overlap]
    if strict:
        need(len(overlap)>=12 and statistics.median(errors)<=.002 and max(errors)<=.02,"legacy source identity/revision mismatch")
        need((now.date()-ds[-1]).days<=125,"stale RBA monthly series")
    else:
        need(statistics.median(errors)<=.1,"legacy value scale or definition incompatible")
    vs=[obs[d] for d in ds]
    dates=[d.strftime("%d/%m/%Y") if freq=="M" else d.isoformat() for d in ds]
    before=row["last_date"];old=row.get("current_vintage_provenance",{})
    changed=row["dates"]!=dates or row["values"]!=vs or row["unit"]!=target or old.get("source_series_id")!=code
    url=BASE+table+"-data.csv"
    if changed:
        row.update(dates=dates,values=vs,last_date=dates[-1],last_value=vs[-1],unit=target,
         current_vintage_provenance={"status":"RBA_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"source_series_id":code,
           "source_unit":source_unit,"source_csv_sha256":sha256(raw).hexdigest(),"runner_first_seen_utc":now.isoformat(),
           "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,
           "stock_level_not_break_adjusted_growth":target!="Percent per annum",
           "historical_overlap_count":len(overlap),"historical_overlap_exact":sum(abs(obs[d]-v)<=1e-8 for d,v in overlap),
           "historical_overlap_median_relative_error":statistics.median(errors),"historical_overlap_max_relative_error":max(errors),
           "source_title":title})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":old_dates[-1].isoformat(),"after":ds[-1].isoformat(),"latest":vs[-1],"unit":target,"source_url":url,"historical_overlap":len(overlap),"exact_overlap":sum(abs(obs[d]-v)<=1e-8 for d,v in overlap)}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[];cache={}
    for ident,(table,*_) in CONFIG.items():
        try:
            if table not in cache:
                try:cache[table]=fetcher(BASE+table+"-data.csv")
                except (OSError,ValueError) as exc:cache[table]=exc
            raw=cache[table]
            if isinstance(raw,Exception):raise raw
            rows=[r for r in out["AUD"] if r["id"]==ident];need(len(rows)==1,"unique row required")
            candidate=copy.deepcopy(rows[0]);receipt=prepare_row(candidate,ident,now,raw);rows[0].update(candidate);receipts.append(receipt)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_AUD_RBA_STOCKS_REVISED_V1","observed_at_utc":now.isoformat(),"series":receipts,
     "status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
# Read-only discovery: metadata and measured historical overlap, never a
# source admission or an automatic mutation of the canonical archive.
def probe_missing(current,now,fetcher=fetch):
    targets={
      "AU_CREDIT_BUSINESS_CURRENT_SA_history_value":"d2",
      "AU_MORTGAGE_RATE_OWNER_OCC_OUTSTANDING_history_value":"f6",
      "AU_BUSINESS_LENDING_RATE_MEDIUM_OUTSTANDING_history_value":"f7",
    }
    for ident,table in targets.items():
        try:
            row=next(x for x in current["AUD"] if x["id"]==ident)
            old={parse_date(d):v for d,v in zip(row["dates"],row["values"])}
            need(None not in old and len(old)==len(row["dates"]) and len(old)>=12,"invalid canonical history")
            raw=fetcher(BASE+table+"-data.csv")
            rows=list(csv.reader(StringIO(raw.decode("utf-8-sig"))))
            meta={r[0].strip().lower():r for r in rows[:30] if r and r[0].strip().lower() in ("title","description","units","frequency","series id")}
            ids=meta.get("series id",[]);candidates=[]
            for i,code in enumerate(ids[1:],1):
                def field(k):
                    r=meta.get(k,[])
                    return r[i].strip() if i<len(r) else ""
                if not code.strip() or field("frequency").casefold()!="monthly":continue
                obs={}
                for rec in rows:
                    if len(rec)<=i:continue
                    d=parse_date(rec[0].strip())
                    if d is None or d>now.date():continue
                    try:v=float(rec[i].strip().replace(",",""))
                    except ValueError:continue
                    if math.isfinite(v):obs[d]=v
                unit=norm(field("units"))
                if table=="d2":
                    if "million" in unit:obs={d:v/1000 for d,v in obs.items()}
                    elif "billion" not in unit:continue
                elif "percent" not in unit and "per cent" not in unit:continue
                overlap=sorted(set(old)&set(obs))
                if len(overlap)<12:continue
                errors=[abs(obs[d]-old[d])/max(abs(old[d]),1) for d in overlap]
                candidates.append({"code":code.strip(),"title":field("title"),"description":field("description"),"unit":field("units"),"frequency":field("frequency"),"overlap":len(overlap),"exact":sum(abs(obs[d]-old[d])<=1e-8 for d in overlap),"median_relative_error":statistics.median(errors),"max_relative_error":max(errors),"latest_date":max(obs).isoformat(),"latest_value":obs[max(obs)],"tail":[[d.isoformat(),obs[d]] for d in sorted(obs)[-5:]]})
            candidates.sort(key=lambda x:(x["median_relative_error"],x["max_relative_error"],-x["exact"]))
            print("RBA_SOURCE_IDENTITY_PROBE",json.dumps({"id":ident,"table":table,"source_sha256":sha256(raw).hexdigest(),"canonical_last_date":row["last_date"],"candidate_count":len(candidates),"closest":candidates[:8],"canonical_modified":False},sort_keys=True))
        except (OSError,ValueError,KeyError,TypeError,StopIteration) as exc:
            print("RBA_SOURCE_IDENTITY_PROBE_WITHHELD",ident,str(exc))
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path);p.add_argument("--receipt",type=Path);p.add_argument("--probe-missing",action="store_true");a=p.parse_args()
    if a.probe_missing:
        need(a.candidate is None and a.receipt is None,"read-only probe accepts no output paths")
        probe_missing(json.loads(SOURCE.read_text()),datetime.now(timezone.utc));return
    need(a.candidate is not None and a.receipt is not None,"candidate and receipt required")
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
