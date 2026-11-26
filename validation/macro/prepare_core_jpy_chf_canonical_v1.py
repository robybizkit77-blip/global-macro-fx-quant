"""Reuse official national core CPI sources for canonical revised monthly series."""
import argparse,copy,json,math
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,need
from validation.macro.collect_g8_semaphore_gaps_v1 import JP_CORE_URL,CH_CORE_URL,parse_jp_core,parse_ch_core,fetch_issuer
CONFIG={
 "JP_CPI_CORE_YOY_history_value":("JPY",JP_CORE_URL,parse_jp_core,"ESTAT_JP_2025_CORE_0161_YOY"),
 "CH_CPI_CORE1_YOY_history_value":("CHF",CH_CORE_URL,parse_ch_core,"FSO_LIK25B25_CORE1_YOY"),
}
def prepare_row(row,ident,now,fetcher):
    ccy,url,parser,code=CONFIG[ident]
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="Percent YoY" and row["frequency"]=="M","wrong local identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"]),"duplicate legacy month")
    raw=fetcher(url);obs=dict(parser(raw,now.date()));ds=sorted(d for d in obs if d>=min(old))
    need(set(old)<=set(ds) and ds[-1]>=max(old),"history coverage regression")
    ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    need(all(math.isfinite(obs[d]) and abs(obs[d])<=50 and d<now.strftime("%Y-%m") for d in ds),"invalid monthly value")
    errors=[abs(obs[d]-v) for d,v in old.items()];exact=sum(e<=1e-8 for e in errors)
    need(max(errors)<=.05,"historical identity mismatch")
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    vs=[obs[d] for d in ds];changed=ds!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"OFFICIAL_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":url,"source_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch_issuer):
    need(now.utcoffset() is not None,"aware clock required");out=copy.deepcopy(current);receipts=[]
    for ident,(ccy,*_) in CONFIG.items():
        try:
            hits=[r for r in out[ccy] if r["id"]==ident];need(len(hits)==1,"unique row required")
            row=copy.deepcopy(hits[0]);receipt=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(receipt)
        except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as e:receipts.append({"id":ident,"status":"WITHHELD","reason":str(e)})
    return out,{"schema":"GMFQ_JPY_CHF_CORE_REVISED_V1","series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
