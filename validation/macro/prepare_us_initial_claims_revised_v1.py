"""FRED ICSA weekly initial claims. Prove legacy Friday labels represent
Saturday-ended weeks before adopting official Saturday period labels.
Never infer release dates or point-in-time availability from period labels.
"""
import argparse,copy,json,math,statistics
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from validation.macro.prepare_us_weekly_daily_revised_v1 import metadata,csv_rows,fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
IDENT="US_ICSA_history_value"
CONFIG={IDENT:"ICSA"}
URL="https://fred.stlouisfed.org/series/ICSA"
def need(ok,why):
    if not ok:raise ValueError(why)
def prepare_row(row,now,fetcher):
    need(row["id"]==IDENT and row["unit"] in ("Persons","Number") and row["frequency"]=="W" and row["source_file"]=="US_ICSA_history.csv","local series identity mismatch")
    ds0=row["dates"];vs0=row["values"]
    need(len(ds0)==len(vs0)>=24 and ds0[-1]==row["last_date"] and vs0[-1]==row["last_value"],"invalid local history")
    dates=[date.fromisoformat(d) for d in ds0];weekdays={d.weekday() for d in dates}
    need(weekdays in ({4},{5}) and all((b-a).days==7 for a,b in zip(dates,dates[1:])),"legacy calendar not contiguous Friday or Saturday")
    shift=1 if weekdays=={4} else 0
    raw,final=fetcher(URL);need(urlsplit(final).path=="/series/ICSA","metadata redirect")
    verified=metadata(raw,"ICSA","Initial Claims","Number","W","seasonally adjusted")
    csv_url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":"ICSA","cosd":ds0[0]})
    raw_csv,final=fetcher(csv_url);need(urlsplit(final).path=="/graph/fredgraph.csv","CSV redirect")
    obs=csv_rows(raw_csv,"ICSA",now.date())
    mapped=[(d+timedelta(days=shift)).isoformat() for d in dates]
    need(set(mapped)<=set(obs),"official calendar does not cover all archived weeks")
    ds=sorted(d for d in obs if d>=mapped[0]);vs=[obs[d] for d in ds]
    need(all(date.fromisoformat(d).weekday()==5 for d in ds) and all((date.fromisoformat(b)-date.fromisoformat(a)).days==7 for a,b in zip(ds,ds[1:])),"official weekly calendar has gaps")
    need(all(0<v<10000000 and v.is_integer() for v in vs),"invalid claims counts")
    errors=[abs(obs[d]-v)/max(abs(v),1) for d,v in zip(mapped,vs0)]
    exact=sum(abs(obs[d]-v)<=1e-6 for d,v in zip(mapped,vs0))
    audit={"exact":exact,"count":len(mapped),"median_relative_error":statistics.median(errors),"max_relative_error":max(errors),"comparisons":[]}
    for lag in (-14,-7,0,7,14):
        pairs=[(obs[(date.fromisoformat(d)+timedelta(days=lag)).isoformat()],v) for d,v in zip(mapped,vs0) if (date.fromisoformat(d)+timedelta(days=lag)).isoformat() in obs]
        if pairs:audit["comparisons"].append({"lag_days":lag,"count":len(pairs),"exact":sum(abs(x-y)<=1e-6 for x,y in pairs),"median_relative_error":statistics.median(abs(x-y)/max(abs(y),1) for x,y in pairs)})
    print("ICSA_CALENDAR_DIAGNOSTIC",json.dumps(audit,sort_keys=True))
    need(exact/len(mapped)>=.7 and statistics.median(errors)<=.003 and max(errors)<=.05,"weekly history mapping not established: "+json.dumps(audit,sort_keys=True))
    if shift:
        # Check competing adjacent-week hypotheses against real source dates.
        for lag in (-7,7):
            pairs=[(obs[(date.fromisoformat(d)+timedelta(days=lag)).isoformat()],v) for d,v in zip(mapped,vs0) if (date.fromisoformat(d)+timedelta(days=lag)).isoformat() in obs]
            need(len(pairs)>=24,"insufficient adjacent week comparison")
            alt_exact=sum(abs(a-b)<=1e-6 for a,b in pairs)/len(pairs)
            need(exact/len(mapped)>alt_exact+.2,"adjacent week mapping ambiguous")
    before=row["last_date"];prior=row.get("current_vintage_provenance",{})
    changed=ds!=ds0 or vs!=vs0 or prior.get("source_series_id")!="ICSA"
    if changed:
        migration=prior.get("legacy_calendar_migration") or {"legacy_weekday":"Friday" if shift else "Saturday","official_weekday":"Saturday","label_shift_days":shift,"overlap_count":len(mapped),"exact_overlap":exact,"old_first":ds0[0],"old_last":before}
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],current_vintage_provenance={"status":"FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":"ICSA","source_url":URL,"source_csv_url":csv_url,"source_csv_sha256":sha256(raw_csv).hexdigest(),"source_units_verified":verified,"legacy_calendar_migration":migration,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":IDENT,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"exact_overlap":exact,"overlap_count":len(mapped),"shift_days":shift}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current)
    try:
        hits=[r for r in out["USD"] if r["id"]==IDENT];need(len(hits)==1,"unique local series required")
        row=copy.deepcopy(hits[0]);receipt=prepare_row(row,now,fetcher);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError) as exc:receipt={"id":IDENT,"status":"WITHHELD","reason":str(exc)}
    return out,{"schema":"GMFQ_US_ICSA_WEEKLY_REVISED_V1","status":"READY" if receipt["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","series":[receipt],"first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
