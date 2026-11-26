"""SNB daily nominal effective exchange rate, overall index, Dec 2000=100."""
import argparse,copy,json,math
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,fetch,need
CONFIG={"CH_NEER_NOMINAL_OVERALL_history_value":"EPB@SNB.devwkieffid{N,G,I}"}
BASE="https://data.snb.ch/api/cube/devwkieffid/data/json/en"
def prepare_row(row,now,fetcher):
    ident=next(iter(CONFIG));code=CONFIG[ident]
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="Index, Dec 2000=100" and row["frequency"]=="D","wrong identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"]),"duplicate legacy date")
    url=BASE+"?"+urlencode({"fromDate":min(old),"toDate":now.date().isoformat()})
    raw=fetcher(url);payload=json.loads(raw)
    matches=[x for x in payload["timeseries"] if x["metadata"]["key"]==code];need(len(matches)==1,"unique exact official series required")
    x=matches[0];meta=x["metadata"];need(meta.get("frequency")=="P1D_L" and meta.get("unit")=="December 2000 = 100" and meta.get("scale")=="","official unit or frequency changed")
    obs={}
    for p in x["values"]:
        d=p["date"];need(datetime.strptime(d,"%Y-%m-%d").date()<=now.date(),"future observation")
        if p.get("value") in (None,""):continue
        v=float(p["value"]);need(math.isfinite(v) and v>0 and d not in obs,"invalid observation");obs[d]=v
    ds=sorted(d for d in obs if d>=min(old));need(set(old)<=set(ds) and ds[-1]>=max(old),"history regression")
    exact=sum(round(obs[d],4)==round(v,4) for d,v in old.items());need(exact==len(old),"historical mismatch")
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    vs=[obs[d] for d in ds];changed=ds!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"SNB_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":url,"source_json_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);ident=next(iter(CONFIG))
    try:
        hits=[r for r in out["CHF"] if r["id"]==ident];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher);hits[0].update(row)
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_CHF_SNB_NEER_DAILY_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
