"""BoJ reserve balances, average amounts outstanding, official revised monthly history."""
import argparse,copy,io,json,math
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from openpyxl import load_workbook
from validation.macro.prepare_jpy_boj_base_revised_v1 import SOURCE,need
from validation.estimated.refresh_jpy_reserve_balances_proxy_v1 import _fetch_workbook,_row_period,_number,WORKBOOK_URL
CONFIG={"JP_BOJ_RESERVE_BALANCES_history_value":"BOJ_MBLONG_AVERAGE_RESERVE_BALANCES"}
def parse(raw,now):
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        sheets=[ws for ws in book.worksheets if "Average amounts outstanding" in ws.title]
        need(len(sheets)==1,"unique average balance sheet required")
        rows=list(sheets[0].iter_rows(values_only=True))
        cols=[i for i in range(max(map(len,rows))) if any(len(r)>i and isinstance(r[i],str) and " ".join(r[i].split()).casefold()=="reserve balances" for r in rows[:20])]
        need(len(cols)==1,"unique reserve balance header required")
        need(any("100 million yen" in str(v) for r in rows[:20] for v in r),"unit header missing")
        obs={};col=cols[0]
        for r in rows:
            if len(r)<=col:continue
            d=_row_period(r);v=_number(r[col])
            if not d or v is None:continue
            need(d<now.strftime("%Y-%m") and d not in obs and math.isfinite(v) and v>0,"invalid month or value")
            obs[d]=v
        return obs
    finally:book.close()
def prepare_row(row,now,raw):
    ident=next(iter(CONFIG));code=CONFIG[ident]
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="100 million yen" and row["frequency"]=="M","wrong identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local row")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"]),"duplicate legacy month")
    obs=parse(raw,now);ds=sorted(d for d in obs if d>=min(old))
    need(set(old)<=set(ds) and ds[-1]>=max(old),"history regression")
    ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in old.items()]
    exact=sum(abs(obs[d]-v)<=1e-6 for d,v in old.items())
    need(exact/len(old)>=.8 and max(errors)<=.01,"historical identity mismatch")
    vs=[obs[d] for d in ds];prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    changed=ds!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"BOJ_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":WORKBOOK_URL,"source_workbook_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=_fetch_workbook):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);ident=next(iter(CONFIG))
    try:
        hits=[r for r in out["JPY"] if r["id"]==ident];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher());hits[0].update(row)
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_JPY_BOJ_RESERVE_AVERAGE_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
