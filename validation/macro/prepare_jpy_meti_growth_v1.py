"""Exact METI e-Stat monthly industrial production and retail current revised histories."""
import argparse,copy,io,json,math,re,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from openpyxl import load_workbook
from validation.macro.probe_jpy_meti_growth_v1 import PAGES,fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={"JP_IIP_history_value":"ESTAT_METI_IIP_1000000000_SA_2020","JP_RETAIL_history_value":"ESTAT_METI_RETAIL_SA_2020"}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def period(s):
    m=re.fullmatch(r"(20\d{2})(0[1-9]|1[0-2])",str(s))
    return f"{m[1]}-{m[2]}" if m else None
def parse(ident,raw,now):
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        if ident=="JP_IIP_history_value":
            rows=list(book["生産"].iter_rows(values_only=True))
            need(rows[0][0]=="項目：総合季節調整済指数【月次】付加価値額生産（2020＝100.0）" and str(rows[3][0])=="1000000000" and rows[3][1]=="鉱工業","wrong IIP scope")
            pairs=zip(rows[2][3:],rows[3][3:])
        else:
            rows=list(book["季調済指数(Seasonaly adjusted)（月次M）"].iter_rows(values_only=True))
            need(rows[2][1]=="(2) Seasonal adjustment indices" and rows[5][20]=="C.Y.2020=100" and rows[7][20]=="Retail" and rows[6][20]=="小売業計","wrong retail scope")
            pairs=((str(x[0])[:4]+str(x[0])[6:8],x[20]) for x in rows[8:] if re.fullmatch(r"20\d{2}00(0[1-9]|1[0-2])\1",str(x[0])))
        out={}
        for d,v in pairs:
            d=period(d)
            if not d or v is None or v in ("***","X","-"):continue
            need(isinstance(v,(int,float)) and math.isfinite(v) and 0<v<500 and d<now.strftime("%Y-%m") and d not in out,"invalid observation")
            out[d]=float(v)
        return out
    finally:book.close()
def reconcile(row,obs,now,raw):
    ident=row["id"];code=CONFIG[ident]
    ds=row["dates"];vs=row["values"];old=dict(zip(ds,vs))
    need(row["unit"]=="Index 2020=100" and row["frequency"]=="M" and row["source_file"]==ident.removesuffix("_value")+".csv","wrong local identity")
    need(len(old)==len(ds)==len(vs)>=36 and ds==sorted(ds) and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"invalid local history")
    need(set(old)<=set(obs),"coverage regression")
    dates=sorted(d for d in obs if d>=ds[0]);ordm=lambda d:int(d[:4])*12+int(d[5:7])
    need(all(ordm(b)-ordm(a)==1 for a,b in zip(dates,dates[1:])) and dates[-1]>=ds[-1],"gap or stale")
    errors=[abs(obs[d]-v) for d,v in old.items()];exact=sum(e<1e-8 for e in errors)
    prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source changed")
    if not prior.get("source_series_id"):need(exact==len(old),"initial historical identity mismatch")
    else:need(statistics.median(errors)<=.5 and max(errors)<=4,"revision beyond tolerance")
    values=[obs[d] for d in dates];changed=ds!=dates or vs!=values or prior.get("source_series_id")!=code
    if changed:row.update(dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance={"status":"METI_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":PAGES[ident],"source_workbook_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"exact_overlap":exact,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":ds[-1],"after":dates[-1],"latest":values[-1],"exact_overlap":exact}
def prepare(current,*,now,fetcher=fetch):
    out=copy.deepcopy(current);receipts=[]
    for ident in CONFIG:
        try:
            hits=[x for x in out["JPY"] if x["id"]==ident];need(len(hits)==1,"unique row required")
            row=copy.deepcopy(hits[0]);raw,_=fetcher(PAGES[ident]);r=reconcile(row,parse(ident,raw,now),now,raw);hits[0].update(row)
        except (OSError,ValueError,KeyError,TypeError,IndexError) as e:r={"id":ident,"status":"WITHHELD","reason":str(e)}
        receipts.append(r)
    return out,{"schema":"GMFQ_JPY_METI_GROWTH_V1","series":receipts,"status":"READY" if any(x["status"]=="READY" for x in receipts) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
