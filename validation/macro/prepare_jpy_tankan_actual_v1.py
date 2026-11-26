"""BoJ Tankan actual DIs, revised research only; forecasts unchanged."""
import argparse,copy,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.prepare_jpy_boj_revised_v1 import BASE,fetch,need
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
PREFIX="JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_"
CONFIG={
 "JP_TANKAN_LENDING_ATTITUDE_history_value":("TK99F0000612GCQ00000","D.I./Lending Attitude/All Enterprises/All industries/Actual result","Q"),
 PREFIX+"Manufacturing_Actual":("TK99F1000601GCQ01000","D.I./Business Conditions/Large Enterprises/Manufacturing/Actual result","slash"),
 PREFIX+"Nonmanufacturing_Actual":("TK99F2000601GCQ01000","D.I./Business Conditions/Large Enterprises/Nonmanufacturing/Actual result","slash"),
}
def prepare_row(row,ident,now,fetcher):
    code,title,style=CONFIG[ident]
    need(row["id"]==ident and ((row["unit"],row["frequency"],row["source_file"])==("% points","Q","JP_TANKAN_LENDING_ATTITUDE_history.csv") if style=="Q" else (row["unit"],row["frequency"],row["source_file"])==("","","JP_BOJ_TANKAN_LEAD_INDICATORS_history.csv")),"canonical identity mismatch")
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds==sorted(set(ds)) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid local history")
    def parse(d):
        m=re.fullmatch(r"(\d{4})-Q([1-4])" if style=="Q" else r"(\d{4})/(03|06|09|12)",d)
        need(m is not None,"invalid canonical quarter")
        return int(m[1])*4+(int(m[2]) if style=="Q" else int(m[2])//3)-1
    def label(q):
        y,k=divmod(q,4)
        return f"{y}-Q{k+1}" if style=="Q" else f"{y}/{(k+1)*3:02d}"
    old={parse(d):v for d,v in zip(ds,vs)};start=min(old);y,k=divmod(start,4)
    qnow=(now.month-1)//3+1
    url=BASE+"?"+urlencode({"format":"json","lang":"en","db":"CO","startDate":f"{y}{k+1:02d}","endDate":f"{now.year}{qnow:02d}","code":code})
    raw=fetcher(url);payload=json.loads(raw)
    need(payload.get("STATUS")==200 and len(payload.get("RESULTSET") or [])==1,"BoJ source unavailable")
    x=payload["RESULTSET"][0]
    need(x.get("SERIES_CODE")==code and x.get("UNIT") in ("% points","0 points") and x.get("FREQUENCY")=="QUARTERLY" and x.get("NAME_OF_TIME_SERIES")==title,"wrong BoJ metadata: "+str({k:x.get(k) for k in ("SERIES_CODE","UNIT","FREQUENCY","NAME_OF_TIME_SERIES")}))
    dates=x["VALUES"]["SURVEY_DATES"];values=x["VALUES"]["VALUES"];need(len(dates)==len(values),"source arrays unequal")
    obs={};seen=set()
    for d,v in zip(dates,values):
        m=re.fullmatch(r"(\d{4})0([1-4])",str(d));need(m is not None,"invalid API quarter")
        q=int(m[1])*4+int(m[2])-1;need(q not in seen,"duplicate quarter");seen.add(q)
        if v is None:continue
        v=float(v);need(q<now.year*4+qnow-1 and math.isfinite(v) and -100<=v<=100 and v.is_integer(),"future or invalid DI")
        obs[q]=v
    need(set(old)<=set(obs) and max(obs)>=max(old),"coverage mismatch")
    err=[abs(obs[q]-v) for q,v in old.items()];exact=sum(e==0 for e in err)
    print("BOJ_TANKAN_OVERLAP",ident,json.dumps({"count":len(err),"exact":exact,"max":max(err)}))
    need(exact/len(err)>=.9 and max(err)<=2,"full historical identity unproven")
    qs=sorted(q for q in obs if q>=start)
    need(qs[0]==start and all(b-a==1 for a,b in zip(qs,qs[1:])),"quarter gap")
    labels=[label(q) for q in qs];vals=[obs[q] for q in qs];before=ds[-1]
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source changed")
    changed=ds!=labels or vs!=vals or prior.get("source_series_id")!=code
    if changed:row.update(dates=labels,values=vals,last_date=labels[-1],last_value=vals[-1],current_vintage_provenance={"status":"BOJ_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_title":title,"source_url":url,"source_json_sha256":sha256(raw).hexdigest(),"historical_overlap":len(err),"historical_overlap_exact":exact,"max_absolute_revision":max(err),"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":labels[-1],"latest":vals[-1],"source_series_id":code,"overlap":len(err)}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["JPY"] if r["id"]==ident];need(len(hits)==1,"unique row required")
            row=copy.deepcopy(hits[0]);receipt=prepare_row(row,ident,now,fetcher);hits[0].update(row)
        except (OSError,ValueError,KeyError,TypeError) as exc:receipt={"id":ident,"status":"WITHHELD","reason":str(exc)}
        receipts.append(receipt)
    return out,{"schema":"GMFQ_JPY_TANKAN_ACTUAL_V1","series":receipts,"status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
