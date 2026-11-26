"""StatCan real retail, chained 2017 dollars, current revised research only."""
import argparse,copy,csv,io,json,math,statistics,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from validation.sources.cad_statcan_core import download_csv,StatCanTransportUnavailable,norm
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
ID="CA_RETAIL_VOLUME_history_value"
PID="20100067"
CONFIG={ID:PID}
def need(ok,why):
    if not ok:raise ValueError(why)
def prepare_row(row,now,raw):
    need(row["id"]==ID and row["source_file"]=="CA_RETAIL_VOLUME_history.csv" and row["unit"]=="million chained 2017 CAD SA" and row["frequency"]=="M","canonical identity mismatch")
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds==sorted(set(ds)) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid history")
    reader=csv.DictReader(io.StringIO(raw))
    need({"REF_DATE","GEO","UOM","SCALAR_FACTOR","VECTOR","VALUE","Sales, price and volume"}<=set(reader.fieldnames or []),"unexpected header")
    candidates={}
    for r in reader:
        if norm(r["GEO"])!="canada":continue
        industry=next((norm(v) for k,v in r.items() if "industry classification" in k.casefold()),"")
        if industry not in ("retail trade [44-45]","retail trade","total retail trade"):continue
        measure=norm(r["Sales, price and volume"])
        if norm(r["UOM"])!="dollars" or norm(r["SCALAR_FACTOR"])!="millions":continue
        key=(r["VECTOR"],measure)
        obs=candidates.setdefault(key,{})
        if r["VALUE"] in ("",None):continue
        d=r["REF_DATE"];v=float(r["VALUE"])
        need(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",d) and d not in obs and math.isfinite(v) and v>0,"invalid retail observation")
        obs[d]=v
    old=dict(zip(ds,vs));matches=[]
    for (vector,measure),obs in candidates.items():
        if not set(old)<=set(obs):continue
        err=[abs(obs[d]-v)/abs(v) for d,v in old.items()]
        print("CAD_RETAIL_CANDIDATE",json.dumps({"vector":vector,"measure":measure,"count":len(err),"median":statistics.median(err),"max":max(err),"latest":obs[max(obs)],"date":max(obs)}))
        if "chained" not in measure or "unchained" in measure or "2017" not in measure:continue
        if statistics.median(err)<=.015 and max(err)<=.04:matches.append((vector,measure,obs,err))
    need(len(matches)==1,"unique chained-dollar history not proven")
    vector,measure,obs,err=matches[0]
    # Independently published September 2026 release, revised vintages may change later.
    if now.strftime("%Y-%m")=="2026-11":need(abs(obs.get("2026-09",0)-61362)<=1,"September release anchor mismatch")
    dates=sorted(d for d in obs if d>=ds[0])
    need(dates[-1]>=ds[-1] and dates[-1]<now.strftime("%Y-%m"),"source regression or incomplete month")
    ordinal=lambda d:int(d[:4])*12+int(d[5:])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(dates,dates[1:])),"monthly gap")
    prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_vector") or prior["source_vector"]==vector,"source changed")
    values=[obs[d] for d in dates];before=ds[-1]
    changed=ds!=dates or vs!=values or prior.get("source_vector")!=vector
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"STATCAN_CURRENT_REVISED_HISTORY_NOT_PIT","source_table":PID,"source_vector":vector,"source_measure":measure,"source_url":"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010006701","source_csv_sha256":sha256(raw.encode()).hexdigest(),"historical_overlap":len(old),"median_relative_revision":statistics.median(err),"max_relative_revision":max(err),"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":before,"after":dates[-1],"latest":values[-1],"vector":vector}
def prepare(current,*,now,fetcher=download_csv):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current)
    try:
        hits=[r for r in out["CAD"] if r["id"]==ID];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher(PID));hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError,StatCanTransportUnavailable) as exc:receipt={"id":ID,"status":"WITHHELD","reason":str(exc)}
    return out,{"schema":"GMFQ_CAD_RETAIL_VOLUME_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
