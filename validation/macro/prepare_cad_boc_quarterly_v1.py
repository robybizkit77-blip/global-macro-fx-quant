"""Reconcile five existing quarterly BoC survey series; revised research only."""
import argparse,copy,json,math,re,statistics
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.prepare_cad_boc_revised_v1 import fetch,need,BASE
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Price_Indicator":("BOS_PRICE_INDICATOR","Price indicator","", "", "CA_BOC_BOS_LEAD_INDICATORS_history.csv"),
 "CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Activity_Indicator":("BOS_ACTIVITY_INDICATOR","Activity indicator","", "", "CA_BOC_BOS_LEAD_INDICATORS_history.csv"),
 "CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Indicator":("PC1","BOS Indicator","", "", "CA_BOC_BOS_LEAD_INDICATORS_history.csv"),
 "CA_SLOS_MORTGAGE_LENDING_history_value":("SLOS_ML_LEND","Mortgage lending conditions","Q","Balance of opinion","CA_SLOS_MORTGAGE_LENDING_history.csv"),
 "CA_SLOS_BUSINESS_LENDING_history_value":("SLOS_BUS_LEND","Overall business lending conditions","Q","Balance of opinion","CA_SLOS_BUSINESS_LENDING_history.csv"),
}
def quarter(d):
    m=re.fullmatch(r"(\d{4})Q([1-4])",d)
    if m: return f"{m[1]}-{int(m[2])*3-2:02d}-01"
    dt=date.fromisoformat(d)
    need(dt.day==1 and dt.month in (1,4,7,10),"invalid quarter start")
    return dt.isoformat()
def ordinal(d):return int(d[:4])*4+(int(d[5:7])-1)//3
def prepare_row(row,ident,now,fetcher):
    code,label,freq,unit,file=CONFIG[ident]
    need(row["source_file"]==file and row["unit"]==unit and row["frequency"]==freq,"canonical identity mismatch")
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and row["last_date"]==ds[-1] and row["last_value"]==vs[-1],"invalid canonical history")
    old={quarter(d):float(v) for d,v in zip(ds,vs)}
    need(len(old)==len(ds) and list(old)==sorted(old) and all(math.isfinite(v) for v in old.values()),"bad historical order or value")
    start=min(old);url=BASE+code+"/json?"+urlencode({"start_date":start})
    raw=fetcher(url);j=json.loads(raw)
    need(set(j.get("seriesDetail",{}))=={code},"wrong BoC series")
    meta=j["seriesDetail"][code]
    need(meta.get("label","").casefold()==label.casefold() and meta.get("dateFormat")=="quarterly","BoC identity or cadence mismatch")
    obs={};seen=set();current_q=now.year*4+(now.month-1)//3
    for item in j["observations"]:
        d=quarter(item["d"])
        need(d not in seen,"duplicate source quarter");seen.add(d)
        v=item.get(code,{}).get("v")
        if v in (None,""):continue
        n=float(v)
        need(math.isfinite(n) and abs(n)<=100 and ordinal(d)<current_q,"invalid or unclosed source quarter")
        obs[d]=n
    dates=sorted(d for d in obs if d>=start)
    need(set(old)<=set(obs) and dates and dates[-1]>=max(old),"source history regression")
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(dates,dates[1:])),"quarterly gap")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    if code.startswith("SLOS"):
        need(sum(e<=.011 for e in errors)/len(errors)>=.95 and max(errors)<=.1,"SLOS overlap mismatch")
    else:
        # The issuer explicitly re-estimates these survey indicators; do not splice vintages.
        need(statistics.median(errors)<=.2 and max(errors)<=.8,"BOS revised history identity unproven")
    values=[obs[d] for d in dates]
    if not freq:dates=[f"{d[:4]}Q{(int(d[5:7])-1)//3+1}" for d in dates]
    before=row["last_date"];previous=row.get("current_vintage_provenance",{})
    changed=dates!=ds or values!=vs or previous.get("source_series_id")!=code
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={
      "status":"BOC_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,"source_series_id":code,"source_metadata":meta,
      "source_json_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"median_absolute_revision":statistics.median(errors),
      "max_absolute_revision":max(errors),"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":dates[-1],"latest":values[-1],"source_url":url}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["CAD"] if r["id"]==ident];need(len(hits)==1,"unique source row required")
            row=copy.deepcopy(hits[0]);result=prepare_row(row,ident,now,fetcher);hits[0].update(row);receipts.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_CAD_BOC_QUARTERLY_V1","observed_at_utc":now.isoformat(),"series":receipts,
      "status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD",
      "first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
