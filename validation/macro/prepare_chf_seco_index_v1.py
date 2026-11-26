"""SECO consumer sentiment quarterly index, seasonally/calendar adjusted, revised research only."""
import argparse,copy,csv,io,json,math,statistics
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch
from validation.macro.prepare_us_quarterly_cfna_revised_v1 import need
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
ID="CH_SECO_CONSUMER_SENTIMENT_LEAD_history_SECO_Consumer_Sentiment"
CODE="ks_i63_index_q:index:csa"
CONFIG={ID:CODE}
META="https://scheduler.swissdatas.ch/scheduled/ch-seco-ks.json"
CSV="https://scheduler.swissdatas.ch/scheduled/ks-seco.csv"
def prepare_row(row,now,fetcher):
    need(row["id"]==ID and row["unit"]=="" and row["frequency"]=="" and row["source_file"]=="CH_SECO_CONSUMER_SENTIMENT_LEAD_history.csv","canonical identity mismatch")
    ds=row["dates"];vs=row["values"]
    need(len(ds)==len(vs)>=24 and ds[-1]==row["last_date"] and vs[-1]==row["last_value"],"bad local history")
    segments=[{}]
    for d,v in zip(ds,vs):
        dt=date.fromisoformat(d[:10])
        need(d==dt.isoformat()+"T00:00:00Z" and dt.month in (1,4,7,10) and dt.day==1 and math.isfinite(v),"invalid quarterly date/value")
        if segments[-1] and dt<=next(reversed(segments[-1])):segments.append({})
        segments[-1][dt]=v
    ordq=lambda d:d.year*4+(d.month-1)//3
    need(len(segments) in (1,2) and all(len(s)>=24 and all(ordq(b)-ordq(a)==1 for a,b in zip(s,list(s)[1:])) for s in segments),"unrecognized legacy segments")
    raw,final=fetcher(META);need(final==META,"wrong SECO metadata endpoint")
    meta=json.loads(raw)
    need(meta["title"]["en"]=="Consumer sentiment index" and meta["dim_order"]==["type","structure","seas_adj"] and meta["units"]["type"]["index"]["en"]=="Index" and meta["units"]["type"]["sd"]["en"]=="Standard deviation" and meta["labels"]["structure"]["ks_i63_index_q"]["en"]=="6.3 Consumer sentiment index" and meta["labels"]["seas_adj"]["csa"]["en"]=="Seasonally and calendar adjusted","wrong SECO metadata")
    raw,final=fetcher(CSV);need(final==CSV,"wrong SECO CSV endpoint")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    need(reader.fieldnames==["structure","type","seas_adj","date","value"],"unexpected CSV header")
    variants={}
    for x in reader:
        if x["structure"]!="ks_i63_index_q":continue
        key=(x["type"],x["seas_adj"]);obs=variants.setdefault(key,{})
        if x["value"] in ("",None):continue
        d=date.fromisoformat(x["date"]);v=float(x["value"])
        need(d.day==1 and d.month in (1,4,7,10) and d<=now.date() and math.isfinite(v) and abs(v)<200 and d not in obs,"invalid or duplicate SECO observation")
        obs[d]=v
    target=variants[("index","csa")]
    def errors(obs,old):
        need(set(old)<=set(obs),"history coverage mismatch")
        return [abs(obs[d]-v) for d,v in old.items()]
    candidates=[]
    for i,s in enumerate(segments):
        if set(s)<=set(target):
            err=errors(target,s)
            if statistics.median(err)<=.2 and max(err)<=.5:candidates.append(i)
    need(len(candidates)==1,"ambiguous or nonmatching index segment")
    old=segments[candidates[0]]
    if len(segments)==2:
        other=segments[1-candidates[0]]
        err=errors(variants[("sd","na")],other)
        need(max(err)<=1e-8,"discarded segment not uniquely proven as SD")
        need(min(old)<=min(other) and max(old)>=max(other),"index does not cover full legacy window")
    start=min(old);dates=sorted(d for d in target if d>=start)
    need(dates and dates[0]==start and dates[-1]>=max(old) and all(ordq(b)-ordq(a)==1 for a,b in zip(dates,dates[1:])),"quarter coverage regression")
    err=errors(target,old);values=[target[d] for d in dates];labels=[d.isoformat()+"T00:00:00Z" for d in dates]
    before=ds[-1];prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==CODE,"source changed")
    changed=ds!=labels or vs!=values or prior.get("source_series_id")!=CODE
    if changed:row.update(dates=labels,values=values,last_date=labels[-1],last_value=values[-1],current_vintage_provenance={"status":"SECO_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":CODE,"source_url":META,"source_csv_url":CSV,"source_csv_sha256":sha256(raw).hexdigest(),"historical_overlap":len(old),"max_absolute_revision":max(err),"median_absolute_revision":statistics.median(err),"legacy_sd_segment_removed":len(segments)==2,"period_label_not_release_date":True,"current_quarter_may_be_provisional":True,"source_series_first_release_PIT_certified":False,"runner_first_seen_utc":now.isoformat()})
    return {"id":ID,"status":"READY" if changed else "NO_CHANGE","before":before,"after":labels[-1],"latest":values[-1],"source_series_id":CODE,"overlap":len(old),"legacy_segments":len(segments)}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current)
    try:
        hits=[x for x in out["CHF"] if x["id"]==ID];need(len(hits)==1,"unique source required")
        row=copy.deepcopy(hits[0]);r=prepare_row(row,now,fetcher);hits[0].update(row)
    except (OSError,ValueError,KeyError,TypeError) as exc:r={"id":ID,"status":"WITHHELD","reason":str(exc)}
    return out,{"schema":"GMFQ_CHF_SECO_INDEX_V1","series":[r],"status":"READY" if r["status"]=="READY" else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
