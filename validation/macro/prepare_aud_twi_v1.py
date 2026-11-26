"""RBA F11 monthly trade-weighted index, official current revised history."""
import argparse,copy,csv,io,json,math
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from validation.macro.prepare_aud_rba_stocks_revised_v1 import SOURCE,fetch,parse_date,need
URL="https://www.rba.gov.au/statistics/tables/csv/f11-data.csv"
CONFIG={"AU_AUD_TWI_history_value":"FXRTWI"}
def parse(raw,now):
    data=list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    meta={}
    for r in data[:30]:
        if r and r[0].strip().casefold() in ("title","description","units","frequency","series id"):
            k=r[0].strip().casefold();need(k not in meta,"duplicate metadata");meta[k]=r
    cols=[i for i,s in enumerate(meta["series id"]) if s.strip().upper()=="FXRTWI"]
    need(len(cols)==1,"expected one FXRTWI")
    i=cols[0];details={k:v[i].strip() for k,v in meta.items() if len(v)>i}
    need(details["frequency"].casefold()=="monthly" and details["units"].casefold()=="index","wrong frequency or unit")
    need(details["title"].casefold()=="trade-weighted index may 1970 = 100" and details["description"].casefold()=="australian dollar trade-weighted index","wrong index definition")
    obs={}
    for r in data:
        if len(r)<=i:continue
        d=parse_date(r[0].strip())
        if d is None or r[i].strip() in ("","..","-","NA"):continue
        v=float(r[i]);need(math.isfinite(v) and v>0 and d.strftime("%Y-%m")<now.strftime("%Y-%m") and d not in obs,"invalid observation")
        obs[d]=v
    return obs,details
def prepare_row(row,now,raw):
    ident=next(iter(CONFIG))
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["frequency"]=="M" and row["unit"]=="Index","wrong local identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old={parse_date(d):float(v) for d,v in zip(row["dates"],row["values"])}
    need(None not in old and len(old)==len(row["dates"]),"invalid or duplicate legacy dates")
    obs,details=parse(raw,now);ds=sorted(d for d in obs if d>=min(old))
    need(set(old)<=set(ds) and ds[-1]>=max(old),"history regression")
    need(all((b.year-a.year)*12+b.month-a.month==1 for a,b in zip(ds,ds[1:])),"monthly gap or duplicate")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    need(max(errors)<=.051,"historical identity mismatch")
    dates=[d.strftime("%d-%b-%Y") for d in ds];vs=[obs[d] for d in ds];before=max(old).isoformat()
    prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]=="FXRTWI","source identity changed")
    changed=dates!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!="FXRTWI"
    if changed:row.update(dates=dates,values=vs,last_date=dates[-1],last_value=vs[-1],current_vintage_provenance={"status":"RBA_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":"FXRTWI","source_url":URL,"source_metadata":details,"source_csv_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":sum(e<=1e-6 for e in errors),"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1].isoformat(),"latest":vs[-1]}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);ident=next(iter(CONFIG))
    try:
        hits=[r for r in out["AUD"] if r["id"]==ident];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher(URL));hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError,IndexError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_AUD_RBA_TWI_REVISED_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
