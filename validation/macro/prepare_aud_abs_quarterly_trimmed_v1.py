"""ABS quarterly trimmed mean annual growth, legacy pre-October 2025 method."""
import argparse,copy,io,json,math,statistics
from datetime import date,datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from openpyxl import load_workbook
from validation.macro.probe_aud_abs_quarterly_trimmed_v1 import fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
ID="AU_CPI_TRIMMED_MEAN_Q_YOY_history_value"
CODE="A3604511X"
CONFIG={ID:CODE}
TITLE="Percentage Change from Corresponding Quarter of Previous Year ;  Trimmed Mean ;  Australia ;"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def get_workbook(now,fetcher):
    q=now.year*4+(now.month-1)//3-1
    for i in range(3):
        y,k=divmod(q-i,4);month=("mar","jun","sep","dec")[k];period=f"{y}-{3*(k+1):02d}"
        url=f"https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/{month}-{y}/64010Appendix1a.xlsx"
        try:raw=fetcher(url)
        except HTTPError as e:
            if e.code==404:continue
            raise
        need(raw.startswith(b"PK"),"not an XLSX")
        return raw,url,period
    raise ValueError("no official quarterly appendix available")
def parse(raw,period):
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        ws=book["Data1"]
        if ws.max_row==1 and ws.max_column==1:ws.reset_dimensions()
        rows=list(ws.iter_rows(values_only=True))
        need(sum(map(len,rows))<=200000,"oversized workbook")
        hits=[i for i,v in enumerate(rows[9]) if v==CODE]
        need(len(hits)==1,"source identity not unique")
        k=hits[0]
        need([rows[i][k] for i in range(5)]==[TITLE,"Percent","Seasonally Adjusted","PERCENT","Quarter"],"wrong source definition")
        end=rows[7][k];need(isinstance(end,(date,datetime)) and end.strftime("%Y-%m")==period,"header period mismatch")
        obs={}
        for row in rows[10:]:
            if len(row)<=k or row[k] in (None,""):continue
            d,v=row[0],row[k]
            need(isinstance(d,(date,datetime)) and d.month in (3,6,9,12),"invalid quarter")
            key=d.strftime("%Y-%m")
            need(key<=period and key not in obs and isinstance(v,(int,float)) and math.isfinite(v) and -20<v<30,"invalid observation")
            obs[key]=float(v)
        need(bool(obs) and max(obs)==period,"source not reaching latest quarter")
        return obs
    finally:book.close()
def reconcile(row,obs,url,raw,now):
    ds=row["dates"];vs=row["values"];old=dict(zip(ds,vs))
    need(row["id"]==ID and row["unit"]=="percent YoY SA" and row["frequency"]=="Q" and row["source_file"]=="AU_CPI_TRIMMED_MEAN_Q_YOY_history.csv","local identity mismatch")
    need(len(old)==len(ds)==len(vs)>=24 and ds==sorted(ds) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid local history")
    need(set(old)<=set(obs),"missing overlap")
    dates=sorted(d for d in obs if d>=ds[0]);ordq=lambda d:int(d[:4])*12+int(d[5:7])
    need(dates[-1]>=ds[-1] and all(ordq(b)-ordq(a)==3 for a,b in zip(dates,dates[1:])),"quarterly gap or regression")
    errors=[abs(obs[d]-v) for d,v in old.items()]
    need(statistics.median(errors)<=.1+1e-8 and max(errors)<=.3+1e-8,"revision above guard")
    prior=row.get("current_vintage_provenance",{});need(not prior.get("source_series_id") or prior["source_series_id"]==CODE,"source identity changed")
    values=[obs[d] for d in dates];changed=ds!=dates or vs!=values or prior.get("source_series_id")!=CODE
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"ABS_LEGACY_QUARTERLY_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":CODE,"source_url":url,"source_workbook_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"median_absolute_revision":statistics.median(errors),"max_absolute_revision":max(errors),"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":ds[-1],"after":dates[-1],"latest":values[-1],"overlap":len(old),"median_absolute_revision":statistics.median(errors),"max_absolute_revision":max(errors)}
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current)
    try:
        hits=[r for r in out["AUD"] if r["id"]==ID];need(len(hits)==1,"unique row required")
        row=copy.deepcopy(hits[0]);raw,url,period=get_workbook(now,fetcher);rec=reconcile(row,parse(raw,period),url,raw,now);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError) as e:rec={"id":ID,"status":"WITHHELD","reason":str(e)}
    return out,{"schema":"GMFQ_AUD_ABS_QUARTERLY_TRIMMED_V1","series":[rec],"status":"READY" if rec["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
