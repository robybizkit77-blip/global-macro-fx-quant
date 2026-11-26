"""Current revised BoC monthly research histories; not native liquidity or FX Core."""
import argparse,copy,json,math,re,statistics
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
BASE="https://www.bankofcanada.ca/valet/observations/"
CONFIG={
 "CA_BOC_TOTAL_ASSETS_history_value":("V36651","total assets"),
 "CA_SETTLEMENT_BALANCES_history_value":("V41886561","members of payments canada"),
 "CA_M2PP_SA_history_value":("V41552801","m2++"),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"application/json"}),timeout=35) as r:
        need(r.status==200 and r.geturl()==url,"BoC unexpected response")
        raw=r.read(5_000_001)
    need(0<len(raw)<=5_000_000,"invalid BoC response size")
    return raw
def prepare_row(row,ident,now,fetcher):
    code,title=CONFIG[ident]
    need(row["source_file"]==ident.removesuffix("_value")+".csv" and row["unit"]=="CAD millions" and row["frequency"]=="M","local identity mismatch")
    need(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"local history inconsistent")
    url=BASE+code+"/json?"+urlencode({"start_date":row["dates"][0][:7]+"-01"})
    raw=fetcher(url);j=json.loads(raw)
    need(set(j.get("seriesDetail",{}))=={code},"wrong BoC Valet series")
    meta=j["seriesDetail"][code]
    label=str(meta.get("label",""));desc=str(meta.get("description",""))
    need(title in (label+" "+desc).casefold(),"BoC series label mismatch: "+str(meta))
    if ident=="CA_M2PP_SA_history_value":
        text=(label+" "+desc).casefold()
        need("seasonally adjusted" in text and "unadjusted" not in text,"M2++ adjustment mismatch")
    obs={}
    for x in j["observations"]:
        d=date.fromisoformat(x["d"]);m=d.isoformat()[:7]
        need(m not in obs,"duplicate monthly observation")
        v=x.get(code,{}).get("v")
        if v in (None,""):continue
        need(m<now.strftime("%Y-%m"),"unclosed month")
        v=float(v);need(math.isfinite(v) and v>=0,"invalid BoC level")
        obs[m]=v
    old={d[:7]:float(v) for d,v in zip(row["dates"],row["values"])}
    start=row["dates"][0][:7];ds=sorted(m for m in obs if m>=start)
    need(len(ds)>=24 and ds[0]==start and ds[-1]>=row["last_date"][:7] and set(old)<=set(ds),"source history regression")
    ordinal=lambda m:int(m[:4])*12+int(m[5:7])
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"noncontiguous months")
    errors=[abs(obs[m]-v)/max(abs(v),1) for m,v in old.items()]
    exact=sum(abs(obs[m]-v)<=1e-6 for m,v in old.items())
    if ident=="CA_M2PP_SA_history_value":
        need(statistics.median(errors)<=.01 and max(errors)<=.03,"M2++ historical identity unproven")
    else:
        need(exact/len(old)>=.95 and statistics.median(errors)<=.001,"balance sheet historical identity unproven")
    vs=[obs[m] for m in ds];ds=[m+"-01" for m in ds]
    before=row["last_date"]
    changed=row["dates"]!=ds or row["values"]!=vs or row.get("current_vintage_provenance",{}).get("source_series_id")!=code
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={
          "status":"BOC_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"source_series_id":code,"source_metadata":meta,
          "source_json_sha256":sha256(raw).hexdigest(),"historical_overlap_exact":exact,
          "period_semantics":"CALENDAR_MONTH_STORED_FIRST_DAY","source_series_first_release_PIT_certified":False,
          "historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"source_url":url}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["CAD"] if r["id"]==ident];need(len(hits)==1,"unique source row required")
            row=copy.deepcopy(hits[0]);result=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_CAD_BOC_MONTHLY_REVISED_V1","observed_at_utc":now.isoformat(),"series":receipts,
       "status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD",
       "first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
