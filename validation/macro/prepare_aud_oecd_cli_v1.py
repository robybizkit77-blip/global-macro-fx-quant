"""Official OECD amplitude-adjusted Australia CLI; revised context only, not PIT."""
import argparse,copy,csv,io,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.probe_aud_oecd_cli_v1 import ID,BASE,fetch

SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
EXACT_BASE=BASE.rsplit("/",1)[0]+"/AUS.M.LI.IX._Z.AA.IX._Z.H"
CONFIG={ID:EXACT_BASE}
META={"DATAFLOW":"OECD.SDD.STES:DSD_STES@DF_CLI(4.1)","REF_AREA":"AUS","FREQ":"M","MEASURE":"LI","UNIT_MEASURE":"IX","ACTIVITY":"_Z","ADJUSTMENT":"AA","TRANSFORMATION":"IX","TIME_HORIZON":"_Z","METHODOLOGY":"H","UNIT_MULT":"0","BASE_PER":""}
SERIES_KEY="DSD_STES@DF_CLI(4.1)/AUS.M.LI.IX._Z.AA.IX._Z.H"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def parse(raw,now):
    rd=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    # Normalize only whitespace/BOM in column labels; never infer missing dimensions.
    fields=rd.fieldnames or []
    normalized=[v.strip().lstrip("\ufeff") for v in fields]
    need(len(set(normalized))==len(normalized),"duplicate source columns")
    rd.fieldnames=normalized
    required=set(META)|{"TIME_PERIOD","OBS_VALUE"}
    missing=required-set(normalized)
    need(not missing,"missing source metadata: "+",".join(sorted(missing))+"; actual columns: "+repr(fields))
    obs={}
    for r in rd:
        if not all(r[k]==v for k,v in META.items()):continue
        d=r["TIME_PERIOD"]
        need(bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",d)) and d<now.strftime("%Y-%m"),"invalid or future period")
        need(d not in obs,"duplicate observation")
        v=float(r["OBS_VALUE"])
        need(math.isfinite(v) and 70<v<130,"invalid CLI level")
        obs[d]=v
    need(bool(obs),"empty source")
    return obs
def reconcile(row,obs,url,raw,now):
    ds=row["dates"];vs=row["values"];old={d[:7]:v for d,v in zip(ds,vs)}
    need(row["id"]==ID and row["source_file"]=="AU_OECD_CLI_LEAD_INDICATOR_history.csv","local identity mismatch")
    need(len(old)==len(ds)==len(vs)>=24 and ds==sorted(ds) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid local history")
    need(all(d==d[:7]+"-01T00:00:00Z" for d in ds),"unexpected date format")
    need(set(old)<=set(obs),"missing overlap")
    dates=sorted(d for d in obs if d>=min(old));ordm=lambda d:int(d[:4])*12+int(d[5:7])
    need(dates[-1]>=max(old) and all(ordm(b)-ordm(a)==1 for a,b in zip(dates,dates[1:])),"monthly gap or regression")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    med=statistics.median(errors);mx=max(errors)
    need(med<=.05 and mx<=.10,"revisions above guard")
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==SERIES_KEY,"source identity changed")
    newds=[d+"-01T00:00:00Z" for d in dates];values=[obs[d] for d in dates]
    changed=ds!=newds or vs!=values or prior.get("source_series_id")!=SERIES_KEY
    if changed:row.update(dates=newds,values=values,last_date=newds[-1],last_value=values[-1],current_vintage_provenance={"status":"OECD_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":SERIES_KEY,"source_url":url,"source_payload_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"median_absolute_revision":med,"max_absolute_revision":mx,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":ds[-1],"after":newds[-1],"latest":values[-1],"overlap":len(old),"median_absolute_revision":med,"max_absolute_revision":mx}
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current)
    try:
        hits=[r for r in out["AUD"] if r["id"]==ID];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0])
        query="?"+urlencode({"startPeriod":min(d[:7] for d in row["dates"]),"dimensionAtObservation":"AllDimensions","format":"csvfile"})
        # Use the proven wildcard response first, selecting only the full exact metadata tuple.
        # Never infer an absent dimension, even when an exact URL was requested.
        errors=[]
        for endpoint in (BASE,EXACT_BASE):
            url=endpoint+query
            try:
                raw=fetcher(url);obs=parse(raw,now);break
            except (OSError,ValueError,AssertionError) as exc:
                errors.append(str(exc))
        else:raise ValueError("; ".join(errors))
        rec=reconcile(row,obs,url,raw,now);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError) as e:rec={"id":ID,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_AUD_OECD_CLI_V1","series":[rec],"status":"READY" if rec["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
