"""Exact BoE IADB histories with full overlap, no PIT or FX promotion."""
import argparse,calendar,copy,csv,io,json,math,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
BASE="https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
CONFIG={
 "UK_MORTGAGE_RATE_2Y_75LTV_history_value":("IUMBV34","Percent","M",0,20,.005,.03,"%d %b %Y"),
 "UK_SECURED_LENDING_YOY_history_value":("LPMVTYI","Percent","M",-15,25,.12,.6,"%d %b %Y"),
 "UK_MORTGAGE_APPROVALS_HOUSE_PURCHASE_SA_history_value":("LPMVTVX","Number","M",0,150000,.005,.03,"%d %b %Y"),
 "UK_M4_SA_history_value":("LPMAUYN","GBP millions","M",1000000,6000000,.005,.03,"%Y-%m-%d"),
 "UK_BOE_RESERVE_BALANCES_history_value":("RPWB56A","GBP millions","W",300000,1400000,.001,.01,"%Y-%m-%d"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def day(s):
    for fmt in ("%d %b %Y","%d %b %y","%d-%b-%Y","%d-%b-%y","%d/%b/%Y","%d/%b/%y","%Y-%m-%d","%d/%m/%Y","%d/%m/%y"):
        try:return datetime.strptime(s.strip(),fmt).date()
        except ValueError:pass
    raise ValueError("unrecognized IADB date: "+s)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"text/csv,application/csv,text/plain"}),timeout=35) as response:
        final=urlsplit(response.geturl())
        need(response.status==200 and final.scheme=="https" and final.hostname=="www.bankofengland.co.uk" and final.path.lower().startswith("/boeapps/database/"),"unexpected IADB response")
        raw=response.read(2_000_001)
    need(0<len(raw)<=2_000_000,"invalid response size")
    return raw
def query(code,start):
    return BASE+"?"+urlencode({"csv.x":"yes","Datefrom":start.strftime("%d/%b/%Y"),"Dateto":"now","SeriesCodes":code,"CSVF":"TN","UsingCodes":"Y","VPD":"Y","VFD":"N"})
def observations(raw,code,f,lo,hi,now):
    txt=raw.decode("utf-8-sig")
    need("<html" not in txt.lower() and "<!doctype" not in txt.lower(),"IADB returned HTML")
    rows=list(csv.reader(io.StringIO(txt),skipinitialspace=True));header=None
    for i,row in enumerate(rows[:14]):
        names=[x.strip().upper() for x in row]
        if code not in names:continue
        need(names.count(code)==1,"duplicate series column")
        v=names.index(code);d=next((j for j,k in enumerate(names) if k in ("DATE","DATES","OBSERVATION_DATE","TIME_PERIOD")),None)
        if d is None and v>0 and names[0]=="":d=0
        if d is not None:header=(i,d,v);break
    need(header is not None,"exact IADB series column missing")
    h,d,v=header;obs={}
    for row in rows[h+1:]:
        if len(row)<=max(d,v) or not row[d].strip() or row[v].strip() in ("",".",".."):continue
        if row[d].upper().startswith(("NOTES","SOURCE","DATE")):continue
        date=day(row[d]);value=float(row[v].replace(",",""))
        need(date<=now.date() and date not in obs and math.isfinite(value) and lo<value<hi,"future duplicate or out of range")
        if f=="M":need(date.day==calendar.monthrange(date.year,date.month)[1] and date.strftime("%Y-%m")<now.strftime("%Y-%m"),"not a closed month end")
        else:need(date.weekday()==2,"not a Wednesday weekly stock")
        obs[date]=value
    return obs
def prepare_row(row,ident,now,fetcher):
    code,unit,f,lo,hi,med_limit,max_limit,fmt=CONFIG[ident]
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]==unit and row["frequency"]==f,"local identity mismatch")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old={day(d):v for d,v in zip(row["dates"],row["values"])}
    need(len(old)==len(row["dates"]),"duplicate local period")
    url=query(code,min(old));raw=fetcher(url);obs=observations(raw,code,f,lo,hi,now)
    ds=sorted(d for d in obs if d>=min(old))
    need(ds and ds[0]==min(old) and set(old)<=set(ds) and ds[-1]>=max(old),"official history coverage regression")
    if f=="M":need(all((b.year-a.year)*12+b.month-a.month==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    else:need(all((b-a).days==7 for a,b in zip(ds,ds[1:])),"weekly gap")
    errors=[abs(obs[d]-v) if unit=="Percent" else abs(obs[d]-v)/max(abs(v),1) for d,v in old.items()]
    audit={"count":len(old),"exact":sum(abs(obs[d]-v)<=1e-6 for d,v in old.items()),"median_error":statistics.median(errors),"max_error":max(errors),"error_units":"percentage points" if unit=="Percent" else "relative"}
    print("BOE_IADB_HISTORICAL_OVERLAP",ident,json.dumps(audit,sort_keys=True))
    need(audit["median_error"]<=med_limit and audit["max_error"]<=max_limit,"historical identity unproven")
    vs=[obs[d] for d in ds];dates=[d.strftime(fmt) for d in ds];before=row["last_date"];prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==code,"certified source changed")
    changed=dates!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=dates,values=vs,last_date=dates[-1],last_value=vs[-1],current_vintage_provenance={"status":"BOE_IADB_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":url,"source_csv_sha256":sha256(raw).hexdigest(),"historical_overlap":audit,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":day(before).isoformat(),"after":ds[-1].isoformat(),"latest":vs[-1],"source_series_id":code,"overlap":audit}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);rows=[]
    for ident in CONFIG:
        try:
            hits=[x for x in out["GBP"] if x["id"]==ident];need(len(hits)==1,"unique source required")
            x=copy.deepcopy(hits[0]);result=prepare_row(x,ident,now,fetcher);hits[0].update(x);rows.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:rows.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_GBP_BOE_IADB_REVISED_V1","series":rows,"status":"READY" if any(x["status"]=="READY" for x in rows) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
