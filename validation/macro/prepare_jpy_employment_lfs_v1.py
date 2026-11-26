"""Japan LFS national employed persons, seasonally adjusted, current revised monthly history."""
import argparse,copy,json,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,need
from validation.macro.probe_jpy_employment_lfs_v1 import URL,fetch,parse
CONFIG={"JP_EMPLOYED_history_value":"ESTAT_LFS_1A1_EMPLOYED_BOTH_SEXES_SA"}
def prepare_row(row,now,raw):
    ident,code=next(iter(CONFIG.items()))
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="10k persons" and row["frequency"]=="M","wrong local identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"]),"duplicate dates")
    obs=parse(raw,now)["SA"];ds=sorted(d for d in obs if d>=min(old));need(set(old)<=set(ds) and ds[-1]>=max(old),"coverage regression")
    ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    errors=[abs(obs[d]-v) for d,v in old.items()];exact=sum(e==0 for e in errors)
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    if not prior.get("source_series_id"):need(exact==len(old),"initial source identity mismatch")
    else:need(statistics.median(errors)<=15 and max(errors)<=60,"historical revision exceeds tolerance")
    vs=[obs[d] for d in ds];changed=ds!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"OFFICIAL_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":URL,"source_workbook_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required");out=copy.deepcopy(current);ident=next(iter(CONFIG))
    try:
        hits=[r for r in out["JPY"] if r["id"]==ident];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher());hits[0].update(row)
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_JPY_LFS_EMPLOYMENT_SA_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
