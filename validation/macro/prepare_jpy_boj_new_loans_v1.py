"""BoJ IR04 total new loans and discounts rate; current revised monthly history."""
import argparse,copy,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.prepare_jpy_boj_base_revised_v1 import SOURCE,BASE,fetch,need
CONFIG={"JP_NEW_LOANS_RATE_history_value":"DLLR2CIDBNL1"}
def prepare_row(row,now,fetcher):
    ident,code=next(iter(CONFIG.items()))
    need(row["id"]==ident and row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="Percent per annum" and row["frequency"]=="M","wrong local identity")
    need(len(row["dates"])==len(row["values"])>=36 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"]),"duplicate dates")
    url=BASE+"?"+urlencode({"format":"json","lang":"en","db":"IR04","startDate":min(old).replace("-",""),"endDate":now.strftime("%Y%m"),"code":code})
    raw=fetcher(url);p=json.loads(raw)
    need(p.get("STATUS")==200 and len(p.get("RESULTSET") or [])==1,"source unavailable")
    x=p["RESULTSET"][0];meta={k:x.get(k) for k in ("SERIES_CODE","UNIT","FREQUENCY","NAME_OF_TIME_SERIES")}
    print("BOJ_IR04_METADATA",json.dumps(meta,sort_keys=True))
    need(meta["SERIES_CODE"]==code and meta["FREQUENCY"]=="MONTHLY","wrong source code or frequency")
    unit=(meta["UNIT"] or "").casefold().strip()
    need(unit in ("percent per annum","percent per year","percent p.a.","% per annum","% p.a.","percent","%","annual percent","% per year"),"wrong source unit: "+unit)
    title=(meta["NAME_OF_TIME_SERIES"] or "").casefold()
    need("new loans" in title and "total" in title and "domestically licensed banks" in title,"wrong rate definition: "+title)
    dates=x["VALUES"]["SURVEY_DATES"];vs=x["VALUES"]["VALUES"];need(len(dates)==len(vs),"invalid source arrays")
    obs={};seen=set()
    for d,v in zip(dates,vs):
        d=str(d);need(bool(re.fullmatch(r"\d{4}(0[1-9]|1[0-2])",d)),"invalid period")
        m=d[:4]+"-"+d[4:];need(m not in seen,"duplicate month");seen.add(m)
        if v is None:continue
        v=float(v);need(math.isfinite(v) and -5<=v<=25 and m<now.strftime("%Y-%m"),"invalid rate/date");obs[m]=v
    ds=sorted(d for d in obs if d>=min(old));need(set(old)<=set(ds) and ds[-1]>=max(old),"coverage regression")
    ordinal=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"monthly gap")
    exact=sum(abs(obs[d]-v)<=1e-8 for d,v in old.items());need(exact==len(old),"historical source identity unproven: "+str(exact))
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source identity changed")
    vs=[obs[d] for d in ds];changed=ds!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"BOJ_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_database":"IR04","source_url":url,"source_metadata":meta,"source_json_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":max(old),"after":ds[-1],"latest":vs[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required");out=copy.deepcopy(current);ident=next(iter(CONFIG))
    try:
        hits=[r for r in out["JPY"] if r["id"]==ident];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher);hits[0].update(row)
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,IndexError) as e:receipt={"id":ident,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_JPY_BOJ_NEW_LOANS_V1","series":[receipt],"status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
