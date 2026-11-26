"""RBNZ official revised quarterly context, never first-release or FX-core inputs."""
import argparse,copy,io,json,math,statistics
from datetime import date,datetime,timezone
from hashlib import sha256
from pathlib import Path
from openpyxl import load_workbook
from validation.macro.probe_nzd_rbnz_employment_sfm_v1 import PAGES,fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "NZ_CORE_INFLATION_SFM_Q_history_value":("M1 Prices","CPI.Q.ZC43.iay","Sectoral factor model","(y/y%)","%","percent y/y",.2,.4),
 "NZ_EMPLOYED_history_value":("M9 Labour Market","HLFS.Q.L01G001.ns","Labour force","Employed (000s s.a.)","000s","thousand persons, seasonally adjusted",3.,12.),
}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def rows(book,name):
    ws=book[name]
    if ws.max_row==1 and ws.max_column==1:ws.reset_dimensions()
    rr=list(ws.iter_rows(values_only=True))
    need(sum(map(len,rr))<=500000,"oversized worksheet")
    return rr
def parse(ident,raw,now):
    table,code,group,series,unit,*_=CONFIG[ident]
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        meta={r[0]:r[1] for r in rows(book,"Table Description") if len(r)>1}
        need(meta.get("Published By")=="Reserve Bank of New Zealand" and meta.get("Table")==table,"wrong publisher or table")
        published=meta.get("Published Date");need(isinstance(published,(date,datetime)) and published.strftime("%Y-%m-%d")<=now.strftime("%Y-%m-%d"),"invalid release date")
        defs=rows(book,"Series Definitions")
        need(sum(tuple(r[:4])==(group,series,code,unit) for r in defs)==1,"wrong series definition")
        data=rows(book,"Data");hits=[i for i,v in enumerate(data[4]) if v==code]
        need(len(hits)==1,"nonunique series");k=hits[0]
        need((data[0][k],data[1][k],data[3][k])==(group,series,unit),"header mismatch")
        obs={}
        for row in data[5:]:
            if len(row)<=k or row[k] in (None,""):continue
            d=row[0];v=row[k]
            need(isinstance(d,(date,datetime)) and d.month in (3,6,9,12),"invalid quarter")
            key=d.strftime("%Y-%m")
            need(key<now.strftime("%Y-%m") and key not in obs,"duplicate or future quarter")
            need(isinstance(v,(int,float)) and math.isfinite(v) and (0<v<10000 if unit=="000s" else -20<v<30),"invalid value")
            obs[key]=float(v)
        return obs,published.strftime("%Y-%m-%d")
    finally:book.close()
def reconcile(row,obs,released,raw,now):
    ident=row["id"];_,code,_,_,_,unit,median_cap,max_cap=CONFIG[ident]
    ds=row["dates"];vs=row["values"];old=dict(zip(ds,vs))
    need(row["unit"]==unit and row["frequency"]=="Q" and row["source_file"]==ident.removesuffix("_value")+".csv","local identity mismatch")
    need(len(old)==len(ds)==len(vs)>=24 and ds==sorted(ds) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid local history")
    need(set(old)<=set(obs),"missing overlap")
    dates=sorted(d for d in obs if d>=ds[0]);ordq=lambda d:int(d[:4])*12+int(d[5:7])
    need(dates[-1]>=ds[-1] and all(ordq(b)-ordq(a)==3 for a,b in zip(dates,dates[1:])),"quarterly gap or regression")
    errors=[abs(obs[d]-v) for d,v in old.items()];med=statistics.median(errors);mx=max(errors)
    need(med<=median_cap+1e-8 and mx<=max_cap+1e-8,f"revision above guard: {med}, {mx}")
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    values=[obs[d] for d in dates]
    changed=ds!=dates or vs!=values or prior.get("source_series_id")!=code
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"RBNZ_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":PAGES[ident],"source_workbook_sha256":sha256(raw).hexdigest(),"release_date":released,"historical_overlap":len(old),"median_absolute_revision":med,"max_absolute_revision":mx,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":ds[-1],"after":dates[-1],"latest":values[-1],"overlap":len(old),"median_absolute_revision":med,"max_absolute_revision":mx}
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["NZD"] if r["id"]==ident];need(len(hits)==1,"unique row required")
            row=copy.deepcopy(hits[0]);raw=fetcher(PAGES[ident]);obs,released=parse(ident,raw,now);rec=reconcile(row,obs,released,raw,now);hits[0].update(row)
        except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError) as e:rec={"id":ident,"status":"WITHHELD","reason":str(e)}
        receipts.append(rec)
    return out,{"schema":"GMFQ_NZD_RBNZ_EMPLOYMENT_SFM_V1","series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
