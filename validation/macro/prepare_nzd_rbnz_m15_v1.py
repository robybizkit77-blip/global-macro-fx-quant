"""RBNZ M15 official aggregate business expectations, current-vintage context only."""
import argparse,copy,io,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from openpyxl import load_workbook
from validation.macro.probe_nzd_rbnz_employment_sfm_v1 import fetch as fetch_workbook
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
URL="https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m15/hm15.xlsx"
PREFIX="NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_"
COLS=("CPI_1Y","CPI_2Y","CPI_5Y","CPI_10Y","Wage_1Y","Wage_2Y","Unemp_1Y","Unemp_2Y")
CONFIG={PREFIX+k:i for i,k in enumerate(COLS)}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def fetch(url):
    return fetch_workbook(url)
KEYS=(("CPI inflation","1 year"),("CPI inflation","2 years"),("CPI inflation","5 years"),("CPI inflation","10 years"),("Wage inflation","1 year"),("Wage inflation","2 years"),("Unemployment","1 year"),("Unemployment","2 years"))
HEAD=("time_period","statistic","horizon","business_size","industry","item_response_count","weighted_mean","standard_error_wtd_mean","lower_confidence_interval_wtd_mean","upper_confidence_interval_wtd_mean","relative_standard_error_wtd_mean","moderate_uncertainty_flag_wtd_mean","high_uncertainty_flag_wtd_mean","weighted_median","suppression_required","series_name")
def parse(raw,now):
    need(now.utcoffset() is not None,"aware clock required")
    wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    obs={}
    try:
        need(wb.sheetnames==["Sheet1"],"unexpected M15 workbook layout")
        ws=wb["Sheet1"]
        if ws.max_row==1 and ws.max_column==1:ws.reset_dimensions()
        rr=ws.iter_rows(values_only=True)
        need(tuple(next(rr))==HEAD,"M15 schema changed")
        for i,row in enumerate(rr):
            need(i<100000,"oversized M15 workbook")
            if len(row)!=16 or row[3:5]!=("All","All") or tuple(row[1:3]) not in KEYS:continue
            period=row[0]
            if hasattr(period,"strftime"):period=period.strftime("%Y-%m-%d")
            need(isinstance(period,str) and bool(re.fullmatch(r"\d{4}-(03-31|06-30|09-30|12-31)",period)),"invalid M15 quarter")
            d=period[:7]
            quarter=f"{now.year:04d}-{((now.month-1)//3+1)*3:02d}"
            need(d<=quarter,"future survey quarter")
            if str(row[14]) not in ("0","0.0","False"):continue
            v=row[6]
            need(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) and -10<v<30,"invalid weighted mean")
            need(isinstance(row[5],(int,float)) and row[5]>0 and bool(row[15]),"invalid survey metadata")
            k=KEYS.index(tuple(row[1:3]));slot=obs.setdefault(d,{})
            need(k not in slot,"duplicate M15 aggregate")
            slot[k]=float(v)
        need(bool(obs) and all(len(x)==8 for x in obs.values()),"incomplete aggregate survey quarter")
        return {d:[x[k] for k in range(8)] for d,x in obs.items()},now.date().isoformat()
    finally:wb.close()
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current);rows=[]
    try:
        raw=fetcher(URL);obs,available_by=parse(raw,now)
        for ident,col in CONFIG.items():
            hits=[r for r in out["NZD"] if r["id"]==ident]
            need(len(hits)==1,"nonunique M15 row")
            row=hits[0];ds=row["dates"];vs=row["values"]
            need(row["source_file"]=="NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv" and len(ds)==len(vs)==len(set(ds)) and ds==sorted(ds) and row["last_date"]==ds[-1] and row["last_value"]==vs[-1],"local identity mismatch")
            old=dict(zip(ds,vs));overlap=sorted(set(old)&set(obs))
            need(len(overlap)>=3 and ds[-1] in overlap and all(abs(old[d]-obs[d][col])<.005 for d in overlap),"published summary historical overlap mismatch")
            new=sorted(d for d in obs if d>ds[-1])
            ordinal=lambda d:int(d[:4])*12+int(d[5:])
            need(max(obs)>=ds[-1] and all(ordinal(b)-ordinal(a)==3 for a,b in zip([ds[-1]]+new,new)),"missing new quarter or regression")
            prior=row.get("current_vintage_provenance",{})
            code="RBNZ_M15_AGGREGATE_WEIGHTED_MEAN_"+COLS[col]
            need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source changed")
            if new:
                row.update(dates=ds+new,values=vs+[obs[d][col] for d in new],last_date=new[-1],last_value=obs[new[-1]][col],current_vintage_provenance={"status":"RBNZ_M15_CURRENT_PUBLISHED_SURVEY_NOT_PIT","source_series_id":code,"source_url":URL,"available_by_date":available_by,"reference_period_semantics":"survey quarter; observed availability upper bound, not certified release date","source_payload_sha256":sha256(raw).hexdigest(),"historical_overlap":len(overlap),"source_series_first_release_PIT_certified":False,"methodology_note":"Wage question wording revised starting December 2026 quarter","runner_first_seen_utc":now.isoformat()})
            rows.append({"id":ident,"status":"READY" if new else "NO_CHANGE","before":ds[-1],"after":row["last_date"],"latest":row["last_value"],"overlap":len(overlap),"available_by_date":available_by})
    except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError) as e:
        out=copy.deepcopy(current);rows=[{"id":k,"status":"WITHHELD","reason":str(e)} for k in CONFIG]
    return out,{"schema":"GMFQ_NZD_RBNZ_M15_V1","series":rows,"status":"READY" if any(r["status"]=="READY" for r in rows) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
