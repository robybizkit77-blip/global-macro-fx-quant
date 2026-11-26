"""Exact official ECB daily research series, without fill or PIT claims."""
import argparse,copy,csv,io,json,math,statistics
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from validation.liquidity.refresh_ecb_eur_nfc_credit_v1 import fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "EA_EXCESS_LIQUIDITY_history_value":("ILM.D.U2.C.EXLIQ.U2.EUR","EUR millions","T00:00:00Z","6",-1000000,10000000,.002,.02),
 "EA_CISS_history_value":("CISS.D.U2.Z0Z.4F.EC.SS_CIN.IDX","Index"," 00:00:00+00:00","0",0,1,.001,.015),
 "EA_EER40_NOMINAL_history_value":("EXR.D.E03.EUR.EN00.A","Index"," 00:00:00+00:00","0",50,250,.001,.01),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def prepare_row(row,ident,now,fetcher):
    key,unit,suffix,mult,lo,hi,median_limit,max_limit=CONFIG[ident]
    need(row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]==unit and row["frequency"]=="D","local identity mismatch")
    need(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"invalid local history")
    old={date.fromisoformat(d[:10]):v for d,v in zip(row["dates"],row["values"])}
    need(len(old)==len(row["dates"]),"duplicate local date")
    dataset,series=key.split(".",1)
    url="https://data-api.ecb.europa.eu/service/data/"+dataset+"/"+series+"?format=csvdata&startPeriod="+min(old).isoformat()
    raw=fetcher(url);reader=csv.DictReader(io.StringIO(raw));fields=set(reader.fieldnames or [])
    need({"TIME_PERIOD","OBS_VALUE","UNIT_MULT"}<=fields and bool(fields&{"KEY","SERIES_KEY"}),"ECB columns missing")
    obs={}
    for rec in reader:
        need((rec.get("KEY") or rec.get("SERIES_KEY"))==key,"wrong exact ECB series")
        if rec.get("OBS_VALUE") in (None,"","."):continue
        need(rec.get("UNIT_MULT")==mult,"ECB unit multiplier mismatch")
        d=date.fromisoformat(rec["TIME_PERIOD"]);v=float(rec["OBS_VALUE"])
        need(d<=now.date() and d not in obs and math.isfinite(v) and lo<=v<=hi,"invalid or duplicated daily observation")
        obs[d]=v
    ds=sorted(d for d in obs if d>=min(old))
    need(len(ds)>=40 and set(old)<=set(ds) and ds[0]==min(old) and ds[-1]>=max(old),"missing old dates or history regression")
    need((now.date()-ds[-1]).days<=10 and all((b-a).days<=5 for a,b in zip(ds,ds[1:])),"stale daily source or large gap")
    errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in old.items()]
    need(statistics.median(errors)<=median_limit and max(errors)<=max_limit,"historical identity unproven")
    exact=sum(abs(obs[d]-v)<=1e-6 for d,v in old.items())
    overlap_audit={"count":len(old),"exact":exact,"median_scaled_error":statistics.median(errors),"max_scaled_error":max(errors)}
    if ident=="EA_CISS_history_value":
        # The ECB publishes both legacy CISS and New CISS. A close value
        # range alone is insufficient to prove the archived variant.
        alternative=key.replace("SS_CIN","SS_CI")
        alt_url=url.replace("SS_CIN","SS_CI")
        alt_raw=fetcher(alt_url);alt={}
        for rec in csv.DictReader(io.StringIO(alt_raw)):
            need((rec.get("KEY") or rec.get("SERIES_KEY"))==alternative,"wrong alternative CISS identity")
            if rec.get("OBS_VALUE") in (None,"","."):continue
            day=date.fromisoformat(rec["TIME_PERIOD"]);v=float(rec["OBS_VALUE"])
            need(day not in alt and math.isfinite(v) and 0<=v<=1,"invalid alternative CISS observation")
            alt[day]=v
        need(set(old)<=set(alt),"cannot compare historical CISS variants")
        alt_errors=[abs(alt[d]-v) for d,v in old.items()]
        overlap_audit["alternative_median_abs_error"]=statistics.median(alt_errors)
        overlap_audit["alternative_max_abs_error"]=max(alt_errors)
        print("CISS_VARIANT_COMPARISON",json.dumps(overlap_audit,sort_keys=True))
        need(statistics.median(errors)<=.001 and statistics.median(alt_errors)>max(3*statistics.median(errors),.0001),"New CISS historical variant not uniquely established")
    vs=[obs[d] for d in ds];ds=[d.isoformat()+suffix for d in ds];before=row["last_date"]
    changed=row["dates"]!=ds or row["values"]!=vs or row.get("current_vintage_provenance",{}).get("source_series_id")!=key
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={
         "status":"ECB_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"source_series_id":key,"source_csv_sha256":sha256(raw.encode()).hexdigest(),
         "historical_overlap_exact":exact,"historical_overlap_audit":overlap_audit,"no_synthetic_dates":True,"source_series_first_release_PIT_certified":False,
         "historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"source_url":url,"exact_overlap":exact,"overlap_audit":overlap_audit}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["EUR"] if r["id"]==ident];need(len(hits)==1,"unique source row required")
            row=copy.deepcopy(hits[0]);result=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_EUR_ECB_DAILY_REVISED_V1","observed_at_utc":now.isoformat(),"series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
