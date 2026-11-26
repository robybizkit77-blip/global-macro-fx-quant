"""Recover exact ECB BSI monthly current-vintage macro histories, not PIT."""
import argparse,copy,csv,io,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from validation.liquidity.refresh_ecb_eur_nfc_credit_v1 import fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "EA_HH_LOANS_history_value":("BSI.M.U2.N.A.A20.A.1.U2.2250.Z01.E","BSI.M.U2.Y.U.A20.A.1.U2.2250.Z01.E",3000000,12000000),
 "EA_NFC_LOANS_history_value":("BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E","BSI.M.U2.Y.U.A20.A.1.U2.2240.Z01.E",2000000,10000000),
 "EA_M3_history_value":("BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E","BSI.M.U2.N.V.M30.X.1.U2.2300.Z01.E",7000000,30000000),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def ordinal(d):return int(d[:4])*12+int(d[5:7])
def observations(key,start,now,fetcher,lo,hi):
    url="https://data-api.ecb.europa.eu/service/data/BSI/"+key.split(".",1)[1]+"?format=csvdata&startPeriod="+start
    raw=fetcher(url);reader=csv.DictReader(io.StringIO(raw));cols=set(reader.fieldnames or [])
    need({"TIME_PERIOD","OBS_VALUE","UNIT_MULT"}<=cols and bool(cols&{"KEY","SERIES_KEY"}),"ECB BSI fields missing")
    obs={}
    for rec in reader:
        need((rec.get("KEY") or rec.get("SERIES_KEY"))==key,"wrong ECB BSI series")
        if rec.get("OBS_VALUE") in (None,"","."):continue
        d=rec["TIME_PERIOD"];v=float(rec["OBS_VALUE"])
        need(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",d) and d<now.date().isoformat()[:7] and d not in obs,"invalid future/duplicate period")
        need(rec["UNIT_MULT"]=="6" and math.isfinite(v) and lo<v<hi,"wrong units or scale")
        obs[d]=v
    ds=sorted(obs)
    need(len(ds)>=36 and ds[0]==start and all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"incomplete BSI history")
    return obs,url,sha256(raw.encode()).hexdigest()
def prepare_row(row,ident,now,fetcher):
    primary,alternate,lo,hi=CONFIG[ident]
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="" and row["frequency"]=="","local BSI identity mismatch")
    ds0=row["dates"];vs0=row["values"]
    need(len(ds0)==len(vs0)>=36 and ds0[-1]==row["last_date"] and vs0[-1]==row["last_value"] and all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds0,ds0[1:])),"invalid local history")
    candidates=[]
    for key in (primary,alternate):
        obs,url,digest=observations(key,ds0[0],now,fetcher,lo,hi)
        need(set(ds0)<=set(obs),"missing archived BSI periods")
        e=[abs(obs[d]-v)/abs(v) for d,v in zip(ds0,vs0)]
        candidates.append((statistics.median(e),max(e),key,obs,url,digest,sum(abs(obs[d]-v)<=1e-6 for d,v in zip(ds0,vs0))))
    candidates.sort(key=lambda x:(x[0],x[1]))
    med,mx,key,obs,url,digest,exact=candidates[0];other=candidates[1]
    audit=[{"series":x[2],"median_relative_error":x[0],"max_relative_error":x[1],"exact_overlap":x[6]} for x in candidates]
    print("ECB_BSI_VARIANT_DIAGNOSTIC",ident,json.dumps(audit,sort_keys=True))
    need(med<=.002 and mx<=.01 and other[0]>max(med*2,.0001),"BSI variant ambiguous or historical mismatch")
    ds=sorted(obs);vs=[obs[d] for d in ds]
    need(ds[-1]>=ds0[-1] and ordinal(now.date().isoformat()[:7])-ordinal(ds[-1])<=3,"stale BSI source")
    need(all(abs(b/a-1)<.1 for a,b in zip(vs,vs[1:])),"unexpected stock change")
    before=row["last_date"];prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==key,"certified source identity changed")
    changed=ds!=ds0 or vs!=vs0 or prior.get("source_series_id")!=key
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"ECB_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":key,"source_url":url,"source_csv_sha256":digest,"source_units":"EUR millions","source_frequency":"M","variant_comparison":audit,"historical_overlap_count":len(ds0),"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"source_series_id":key,"variant_comparison":audit}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);rows=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["EUR"] if r["id"]==ident];need(len(hits)==1,"unique target required")
            x=copy.deepcopy(hits[0]);result=prepare_row(x,ident,now,fetcher);hits[0].update(x);rows.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            rows.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_EUR_ECB_BSI_MONTHLY_REVISED_V1","series":rows,"status":"READY" if any(x["status"]=="READY" for x in rows) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
