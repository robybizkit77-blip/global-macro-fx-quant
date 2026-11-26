"""BoE DMP monthly current-revised histories; exact semantic columns and full overlap."""
import argparse,calendar,copy,io,json,math,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from validation.macro.probe_gbp_dmp_monthly_v1 import fetch,month,need,SOURCE
PREFIX="UK_BOE_DMP_LEAD_INDICATORS_history_"
CONFIG={PREFIX+k:v for k,v in {
    "HighVeryHighUncertainty":("Overall uncertainty",5,6),
    "EmploymentExpected":("Employment growth",13),
    "EmploymentRealised":("Employment growth",2),
    "PriceExpected":("Price growth",13),
    "PriceRealised":("Price growth",2),
    "SalesExpected":("Sales growth",15),
    "SalesRealised":("Sales growth",3),
}.items()}
def discover(now,fetcher):
    for lag in range(1,5):
        ordinal=now.year*12+now.month-1-lag
        year,m=divmod(ordinal,12);m+=1
        name=calendar.month_name[m];period=f"{year:04}-{m:02}"
        page=f"https://www.bankofengland.co.uk/decision-maker-panel/{year}/{name.lower()}-{year}"
        try:raw,final=fetcher(page)
        except HTTPError as e:
            if e.code==404:continue
            raise
        soup=BeautifulSoup(raw,"html.parser")
        links=set()
        for a in soup.find_all("a",href=True):
            label=" ".join(a.get_text(" ",strip=True).casefold().split())
            if "monthly aggregate-level data" in label and f"{name.lower()} {year}" in label:
                links.add(urljoin(final,a["href"]))
        need(len(links)<=1,"ambiguous official workbook")
        if not links:continue
        url=links.pop();u=urlsplit(url)
        need(u.scheme=="https" and u.hostname in ("www.bankofengland.co.uk","bankofengland.co.uk") and u.path.lower().endswith(".xlsx"),"unexpected workbook link")
        raw,final=fetcher(url);need(raw.startswith(b"PK"),"not XLSX")
        return load_workbook(io.BytesIO(raw),read_only=True,data_only=True),final,period,sha256(raw).hexdigest()
    raise ValueError("no recent official monthly DMP workbook")
def observations(book,ident,period):
    tab,*cols=CONFIG[ident];rows=list(book[tab].iter_rows(values_only=True))
    first=next((i for i,row in enumerate(rows) if month(row[0])),None)
    need(first is not None,"no monthly dates")
    if len(cols)==2:
        need(any(tuple(row[4:6])==("High","Very high") for row in rows[:first]),"uncertainty header mismatch")
    else:
        headers=[str(row[cols[0]-1]) for row in rows[:first] if len(row)>=cols[0] and row[cols[0]-1] is not None]
        kind="expected" if ident.endswith("Expected") else "realised"
        need("Single month" in headers and any(kind in h.casefold() for h in headers),"monthly semantic header mismatch")
    obs={}
    for row in rows[first:]:
        d=month(row[0])
        if not d:continue
        vs=[row[c-1] for c in cols]
        if all(v is None for v in vs):continue
        need(all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in vs),"invalid monthly value")
        need(d<=period and d not in obs,"future or duplicate month")
        if len(cols)==2:
            need(all(0<=v<=100 for v in vs) and sum(vs)<=100,"invalid uncertainty share")
            obs[d]=round(sum(vs),3)
        else:obs[d]=float(vs[0])
    need(obs and max(obs)==period,"workbook period mismatch")
    return obs
def prepare_row(row,ident,obs,period,url,digest,now):
    need(row["id"]==ident and row["source_file"]=="UK_BOE_DMP_LEAD_INDICATORS_history.csv","local source mismatch")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid legacy history")
    old={month(d):float(v) for d,v in zip(row["dates"],row["values"])}
    need(None not in old and len(old)==len(row["dates"]) and set(old)<=set(obs),"incomplete overlap")
    ds=sorted(d for d in obs if d>=min(old));ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(ds and ds[-1]==period and period>=max(old) and all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"non-contiguous or regressed history")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    changes=[{"month":d,"old":v,"official":obs[d]} for d,v in sorted(old.items()) if abs(obs[d]-v)>.00051]
    # Original seven-series live proof: max revision 0.036 percentage points.
    # Fail closed if a later vintage materially diverges from the certified series.
    need(statistics.median(errors)<=.001 and max(errors)<=.05,"historical revision exceeds validated guard")
    dates=[datetime.strptime(d,"%Y-%m").strftime("%b-%y") for d in ds];vs=[obs[d] for d in ds]
    prior=row.get("current_vintage_provenance",{});source_id="BOE_DMP_MONTHLY:"+ident.removeprefix(PREFIX)
    need(not prior.get("source_series_id") or prior["source_series_id"]==source_id,"certified identity changed")
    changed=dates!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=source_id
    before=max(old)
    if changed:
        row.update(dates=dates,values=vs,last_date=dates[-1],last_value=vs[-1],current_vintage_provenance={
            "status":"BOE_DMP_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":source_id,"source_url":url,
            "source_workbook_sha256":digest,"historical_overlap":len(old),"historical_revisions":changes,
            "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":period,"latest":vs[-1],"overlap":len(old),"max_abs_revision":max(errors),"revisions":changes}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    try:book,url,period,digest=discover(now,fetcher)
    except (OSError,ValueError,KeyError,TypeError) as e:
        book=None;reason=str(e)
    for ident in CONFIG:
        try:
            need(book is not None,reason if book is None else "")
            hits=[z for z in out["GBP"] if z["id"]==ident];need(len(hits)==1,"unique source required")
            row=copy.deepcopy(hits[0]);receipt=prepare_row(row,ident,observations(book,ident,period),period,url,digest,now);hits[0].update(row);receipts.append(receipt)
        except (OSError,ValueError,KeyError,TypeError,IndexError) as e:receipts.append({"id":ident,"status":"WITHHELD","reason":str(e)})
    if book is not None:book.close()
    return out,{"schema":"GMFQ_GBP_BOE_DMP_REVISED_V1","series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
