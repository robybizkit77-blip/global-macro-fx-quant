"""Official current-vintage DG ECFIN surveys via Eurostat. Descriptive only."""
from __future__ import annotations
import argparse,calendar,copy,json,math,statistics
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from validation.macro.prepare_eur_activity_revised_v1 import fetch
from validation.sources.eur_eurostat_core import API_BASE,extract_series
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
PREFIX="EA_ECFIN_BCS_LEAD_INDICATORS_history_"
CONFIG={PREFIX+k:v for k,v in {
"Consumer":"BS-CSMCI-BAL","Construction":"BS-CCI-BAL","ESI":"BS-ESI-I","EEI":"BS-EEI-I",
"Industry":"BS-ICI-BAL","Retail":"BS-RCI-BAL","Services":"BS-SCI-BAL"}.items()}
def need(ok,why):
    if not ok:raise ValueError(why)
def ordinal(d):return int(d[:4])*12+int(d[5:7])
def month_end(d):
    y,m=map(int,d[:7].split("-"));return f"{y:04d}-{m:02d}-{calendar.monthrange(y,m)[1]:02d}"
def query(ident,start):
    code=CONFIG[ident];eei=code=="BS-EEI-I"
    dataset="ei_bsee_m_r2" if eei else "ei_bssi_m_r2"
    filters={"freq":"M","indic":code,"s_adj":"SA","geo":"EA21"}
    if eei:filters["unit"]="INX"
    return dataset,filters,API_BASE+"/"+dataset+"?"+urlencode({"lang":"EN",**filters,"sinceTimePeriod":start})
def prepare_row(row,ident,now,fetcher):
    need(row["id"]==ident and row["source_file"]=="EA_ECFIN_BCS_LEAD_INDICATORS_history.csv" and row["unit"]=="" and row["frequency"]=="","local survey definition mismatch")
    ds0=row["dates"];vs0=row["values"]
    need(len(ds0)==len(vs0)>=36 and ds0[-1]==row["last_date"] and vs0[-1]==row["last_value"] and all(d==month_end(d) for d in ds0),"invalid archived dates")
    dataset,filters,url=query(ident,ds0[0][:7]);raw=fetcher(url);payload=json.loads(raw)
    need(set(payload["id"])==set(filters)|{"time"},"unfiltered source dimensions")
    observations=extract_series(payload,filters)
    ds=[month_end(d) for d,v in observations];vs=[v for d,v in observations]
    need(len(ds)==len(set(ds)) and ds[0]==ds0[0] and set(ds0)<=set(ds) and ds[-1]>=ds0[-1] and ds[-1][:7]<=now.date().isoformat()[:7],"source coverage or future month")
    need(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])) and ordinal(now.date().isoformat()[:7])-ordinal(ds[-1])<=2,"incomplete or stale monthly survey")
    index=CONFIG[ident] in ("BS-ESI-I","BS-EEI-I")
    need(all(math.isfinite(v) and (20<v<180 if index else -100<=v<=100) for v in vs),"survey scale mismatch")
    lookup=dict(zip(ds,vs));matched=[lookup[d] for d in ds0];errors=[abs(a-b) for a,b in zip(vs0,matched)]
    med=statistics.median(errors);mx=max(errors);corr=statistics.correlation(vs0,matched)
    audit={"count":len(errors),"exact":sum(e<=1e-8 for e in errors),"median_absolute_error":med,"max_absolute_error":mx,"correlation":corr}
    print("ECFIN_SURVEY_OVERLAP",ident,json.dumps(audit,sort_keys=True))
    need(med<=.6 and mx<=2.5 and corr>=.995,"archived survey identity not established")
    prior=row.get("current_vintage_provenance",{})
    need(not prior.get("filters") or prior["filters"]==filters,"certified survey definition changed")
    changed=ds!=ds0 or vs!=vs0 or prior.get("filters")!=filters;before=row["last_date"]
    if changed:row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"DG_ECFIN_EUROSTAT_CURRENT_REVISED_HISTORY_NOT_PIT","dataset":dataset,"filters":filters,"source_url":url,"source_json_sha256":sha256(raw).hexdigest(),"source_frequency":"M","source_units":"index long-run mean 100" if index else "balance percentage points","geography":"EA21 fixed composition","month_end_is_reference_label_not_release_date":True,"historical_overlap":audit,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"overlap":audit,"source_url":url}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);rows=[]
    for ident in CONFIG:
        try:
            hits=[r for r in out["EUR"] if r["id"]==ident];need(len(hits)==1,"unique series required")
            x=copy.deepcopy(hits[0]);result=prepare_row(x,ident,now,fetcher);hits[0].update(x);rows.append(result)
        except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
            rows.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_EUR_ECFIN_BCS_MONTHLY_V1","series":rows,"status":"READY" if any(x["status"]=="READY" for x in rows) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
