"""Official SNB M2/M3 current revised monthly macro histories, not first-release PIT."""
import argparse,copy,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
BASE="https://data.snb.ch/api/cube/snbmonagg/data/json/en"
CONFIG={"CH_M2_history_value":"GM2","CH_M3_history_value":"GM3"}
def need(ok,why):
    if not ok:raise ValueError(why)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"application/json"}),timeout=40) as r:
        need(r.status==200 and r.geturl()==url,"SNB unexpected response")
        raw=r.read(5_000_001)
    need(0<len(raw)<=5_000_000,"SNB response size")
    return raw
def prepare_row(row,ident,now,fetcher):
    key=CONFIG[ident];series="EPB@SNB.snbmonagg{B,"+key+"}"
    need(row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="CHF millions" and row["frequency"]=="M","local identity mismatch")
    need(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"invalid local history")
    url=BASE+"?"+urlencode({"dimSel":"D0(B),D1("+key+")","fromDate":row["dates"][0],"toDate":now.strftime("%Y-%m")})
    raw=fetcher(url);payload=json.loads(raw)
    matches=[x for x in payload["timeseries"] if x.get("metadata",{}).get("key")==series]
    need(len(matches)==1,"SNB exact series not unique")
    x=matches[0];meta=x["metadata"]
    need(meta.get("frequency")=="P1M" and meta.get("unit") in ("In CHF millions","In CHF millions / In percent") and meta.get("scale")=="","SNB metadata mismatch: "+str(meta))
    # The cube-level unit combines levels and percent changes. Exact B (level),
    # GM2/GM3 keys above, the full-window value guard below and the official
    # published level definition exclude any growth-rate variant.
    obs={}
    for p in x["values"]:
        d=p["date"];v=p.get("value")
        if v is None or v=="":continue
        need(bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",d)) and d<now.strftime("%Y-%m"),"invalid or future observation")
        need(d not in obs,"duplicate observation")
        v=float(v);need(math.isfinite(v) and v>0,"invalid monetary level");obs[d]=v
    old=dict(zip(row["dates"],row["values"]));ds=sorted(d for d in obs if d>=row["dates"][0])
    need(len(ds)>=24 and set(old)<=set(ds) and ds[0]==row["dates"][0] and ds[-1]>=row["last_date"],"source coverage regression")
    ord=lambda m:int(m[:4])*12+int(m[5:7])
    need(all(ord(b)-ord(a)==1 for a,b in zip(ds,ds[1:])),"noncontiguous monthly history")
    errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in old.items()]
    need(statistics.median(errors)<=.005 and max(errors)<=.03,"SNB historical identity unproven")
    vs=[obs[d] for d in ds];before=row["last_date"];exact=sum(abs(obs[d]-v)<=1e-6 for d,v in old.items())
    changed=row["dates"]!=ds or row["values"]!=vs or row.get("current_vintage_provenance",{}).get("source_series_id")!=series
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={
         "status":"SNB_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"source_series_id":series,"source_metadata":meta,
         "source_json_sha256":sha256(raw).hexdigest(),"historical_overlap_exact":exact,
         "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"source_url":url,"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["CHF"] if r["id"]==ident];need(len(hits)==1,"unique source row required")
            row=copy.deepcopy(hits[0]);result=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_CHF_SNB_MONTHLY_REVISED_V1","observed_at_utc":now.isoformat(),"series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
