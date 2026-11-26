"""SNB MONA bank-office credit balances in CHF millions; exact historical identity."""
import argparse,copy,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,fetch,need
CONFIG={
 "CH_MORTGAGE_CREDIT_DOMESTIC_history_value":("BSTA.SNB.MONA_B.BIL.AKT.HYP","B,I,T,T,A40","CHF millions","KONSOLIDIERUNGSSTUFE(B),INLANDAUSLAND(I),WAEHRUNG(T),FAELLIGKEIT(T),BANKENGRUPPE(A40)"),
 "CH_BANK_CREDIT_CUSTOMERS_history_value":("BSTA.SNB.MONA_B.BIL.AKT.FKU","B,T,T,T,T,T,A40","CHF millions","KONSOLIDIERUNGSSTUFE(B),INLANDAUSLAND(T),WAEHRUNG(T),FAELLIGKEIT(T),DECKUNG(T),SEKTORDECKUNG(T),BANKENGRUPPE(A40)"),
}
def prepare_row(row,ident,now,fetcher):
    cube,key,unit,dims=CONFIG[ident];code="BSTA@"+cube.removeprefix("BSTA.")+"{"+key+"}"
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]==unit and row["frequency"]=="M","wrong local identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"]),"duplicate local date")
    url="https://data.snb.ch/api/warehouse/cube/"+cube+"/data/json/en?"+urlencode({"dimSel":dims,"fromDate":min(old),"toDate":now.strftime("%Y-%m")})
    raw=fetcher(url);payload=json.loads(raw);matches=[x for x in payload["timeseries"] if x["metadata"]["key"]==code]
    need(len(matches)==1,"unique source identity")
    x=matches[0];meta=x["metadata"];need(meta.get("frequency")=="P1M" and meta.get("scale")=="3" and meta.get("unit")=="CHF","wrong source unit or scale")
    obs={}
    for p in x["values"]:
        d=p["date"];v=p.get("value")
        if v in (None,""):continue
        need(bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",d)) and d<now.strftime("%Y-%m") and d not in obs,"invalid or duplicated observation period")
        v=float(v)/1000;need(math.isfinite(v) and v>0,"invalid observation value");obs[d]=v
    ds=sorted(d for d in obs if d>=min(old));need(set(old)<=set(ds) and ds[-1]>=max(old),"coverage regression")
    ordinal=lambda m:int(m[:4])*12+int(m[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    exact=sum(math.isclose(obs[d],v,rel_tol=1e-12,abs_tol=1e-7) for d,v in old.items());need(exact==len(old),"historical identity mismatch")
    vs=[obs[d] for d in ds];prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    changed=ds!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"SNB_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":url,"source_metadata":meta,"source_to_CHF_millions_factor":0.001,"source_json_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required");out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["CHF"] if r["id"]==ident];need(len(hits)==1,"unique row required")
            row=copy.deepcopy(hits[0]);receipt=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(receipt)
        except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as e:receipts.append({"id":ident,"status":"WITHHELD","reason":str(e)})
    return out,{"schema":"GMFQ_CHF_MONA_CREDIT_V1","series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
