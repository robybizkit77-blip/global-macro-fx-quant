"""BoJ official average monetary base and current-account balances; research only."""
import argparse,copy,json,math,statistics,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"live_data/sections/MACRO_SERIES.json"
BASE="https://www.stat-search.boj.or.jp/api/v1/getDataCode"
CONFIG={
 "JP_MONETARY_BASE_history_value":("MD01","MABS1AN11","Monetary Base/Average Amounts Outstanding"),
 "JP_BOJ_CURRENT_ACCOUNT_BALANCES_history_value":("MD01","MABS1AN113","Monetary Base/Current Account Balances/Average Amounts Outstanding"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"application/json"}),timeout=45) as r:
        need(r.status==200 and r.geturl()==url,"BoJ source redirect")
        raw=r.read(5_000_001)
    need(0<len(raw)<=5_000_000,"BoJ response size")
    return raw
def prepare_row(row,ident,now,fetcher):
    db,code,title=CONFIG[ident]
    need(row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="100 million yen" and row["frequency"]=="M","local identity mismatch")
    need(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"local terminal mismatch")
    url=BASE+"?"+urlencode({"format":"json","lang":"en","db":db,"startDate":row["dates"][0].replace("-",""),"endDate":now.strftime("%Y%m"),"code":code})
    raw=fetcher(url);payload=json.loads(raw)
    need(payload.get("STATUS")==200 and len(payload.get("RESULTSET") or [])==1,"BoJ API source not available")
    x=payload["RESULTSET"][0]
    need(x.get("SERIES_CODE")==code and x.get("UNIT")=="100 million yen" and x.get("FREQUENCY")=="MONTHLY","BoJ exact metadata mismatch: "+str({k:x.get(k) for k in ("SERIES_CODE","UNIT","FREQUENCY","NAME_OF_TIME_SERIES")}))
    name=x.get("NAME_OF_TIME_SERIES") or ""
    if title:need(name==title,"BoJ title mismatch: "+name)
    else:need(bool(name),"BoJ credit title missing")
    dates=x["VALUES"]["SURVEY_DATES"];values=x["VALUES"]["VALUES"];need(len(dates)==len(values),"source arrays unequal")
    obs={};seen=set()
    for d,v in zip(dates,values):
        d=str(d);need(bool(re.fullmatch(r"\d{4}(0[1-9]|1[0-2])",d)),"invalid monthly date")
        m=d[:4]+"-"+d[4:];need(m not in seen,"duplicate month");seen.add(m)
        if v is None:continue
        need(m<now.strftime("%Y-%m"),"unclosed monthly observation with actual value")
        v=float(v);need(math.isfinite(v) and v>0,"invalid BoJ level");obs[m]=v
    ds=sorted(obs);need(len(ds)>=24 and set(row["dates"])<=set(ds) and ds[0]==row["dates"][0] and ds[-1]>=row["last_date"],"source coverage regression")
    ord=lambda m:int(m[:4])*12+int(m[5:7])
    need(all(ord(b)-ord(a)==1 for a,b in zip(ds,ds[1:])),"noncontiguous source")
    # Historical identity is especially important for domestic-bank credit:
    # the existing official candidate uses this exact MD11 code; do not
    # replace a different balance-sheet concept just because its label fits.
    old=list(zip(row["dates"],row["values"]))
    exact=sum(abs(obs[d]-v)<=1e-6 for d,v in old)
    errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in old]
    audit={"overlap_count":len(old),"exact":exact,"median_relative_error":statistics.median(errors),"max_relative_error":max(errors)}
    need(exact/len(old)>=.8 and statistics.median(errors)<=.001 and max(errors)<=.01,"historical series identity unproven: "+json.dumps(audit,sort_keys=True))
    vs=[obs[d] for d in ds];before=row["last_date"]
    changed=row["dates"]!=ds or row["values"]!=vs or row.get("current_vintage_provenance",{}).get("source_series_id")!=code
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={
          "status":"BOJ_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"source_database":db,"source_series_id":code,
          "source_title":name,"source_json_sha256":sha256(raw).hexdigest(),"historical_overlap_exact":exact,"historical_overlap_audit":audit,
          "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"source_url":url,"overlap_audit":audit}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["JPY"] if r["id"]==ident];need(len(hits)==1,"unique series required")
            row=copy.deepcopy(hits[0]);result=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_JPY_BOJ_BASE_REVISED_V1","observed_at_utc":now.isoformat(),"series":receipts,
      "status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
