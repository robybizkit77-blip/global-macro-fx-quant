"""Exact FRED productivity, unit labor costs, SLOOS and CFNAI, revised research only."""
import argparse,copy,csv,io,json,math,re,statistics
from datetime import datetime,timezone,date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from bs4 import BeautifulSoup
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch
SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "US_ULCNFB_history_ULCNFB":("ULCNFB","unit labor costs","Q","",1,300,.005,.03),
 "US_OPHNFB_history_OPHNFB":("OPHNFB","labor productivity","Q","",1,300,.005,.03),
 "US_SLOOS_CI_LARGE_MIDDLE_history_value":("DRTSCILM","net percentage of domestic banks tightening standards","Q","Percent, not seasonally adjusted",-100,100,.15,1),
 "US_CFNAI_LEAD_INDICATOR_history_CFNAI":("CFNAI","chicago fed national activity index","M","",-30,30,.15,.7),
}
def need(ok,why):
    if not ok:raise ValueError(why)
def norm(s):return " ".join(s.casefold().split())
def prepare_row(row,ident,now,fetcher):
    code,title,f,unit,lo,hi,med_limit,max_limit=CONFIG[ident]
    need(row["id"]==ident and row["unit"]==unit and row["frequency"] in ("",f),"local identity mismatch")
    need(len(row["dates"])==len(row["values"])>=24 and row["last_date"]==row["dates"][-1] and row["last_value"]==row["values"][-1],"invalid local history")
    segments=[{}]
    for d,v in zip(row["dates"],row["values"]):
        d=date.fromisoformat(d[:10])
        if segments[-1] and d<=next(reversed(segments[-1])):segments.append({})
        segments[-1][d]=v
    mixed=len(segments)>1
    if mixed:
        need(code=="DRTSCILM" and len(segments)==2,"ambiguous duplicate local dates")
        need(all(len(seg)>=24 and all(d.day==1 and d.month in (1,4,7,10) for d in seg) and all((b.year-a.year)*12+b.month-a.month==3 for a,b in zip(seg,list(seg)[1:])) for seg in segments),"invalid legacy SLOOS segment")
        need(len(set(segments[0]) & set(segments[1]))>=24,"insufficient shared SLOOS history")
    old={d:v for seg in reversed(segments) for d,v in seg.items()}
    meta_url="https://fred.stlouisfed.org/series/"+code
    meta,final=fetcher(meta_url);need(urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path.rstrip("/")=="/series/"+code,"wrong metadata endpoint")
    soup=BeautifulSoup(meta,"html.parser");head=norm(soup.title.get_text(" ",strip=True) if soup.title else "")
    need(title in head and code.casefold() in head,"metadata title mismatch: "+head)
    txt=norm(soup.get_text(" ",strip=True));units=re.search(r"units:\s*(.*?)\s*frequency:",txt)
    need(units and re.search(r"frequency:\s*"+("quarterly" if f=="Q" else "monthly")+r"\b",txt),"metadata unit/frequency missing")
    u=units.group(1)
    if code in ("ULCNFB","OPHNFB"):
        need("index" in u and "seasonally adjusted" in u and "not seasonally adjusted" not in u,"index unit mismatch")
        need("nonfarm business" in head,"wrong business sector")
    elif code=="DRTSCILM":need("percent" in u and "not seasonally adjusted" in u and "large and middle-market" in head,"survey definition mismatch")
    else:need("index" in u,"CFNAI index unit mismatch")
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"id":code,"cosd":min(old).isoformat()})
    raw,final=fetcher(url);need(urlsplit(final).hostname=="fred.stlouisfed.org" and urlsplit(final).path=="/graph/fredgraph.csv","wrong CSV endpoint")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")));need(reader.fieldnames in (["observation_date",code],["DATE",code]),"wrong FRED CSV series")
    obs={};seen=set()
    for r in reader:
        d=date.fromisoformat(r[reader.fieldnames[0]]);need(d.day==1 and d not in seen and (f!="Q" or d.month in (1,4,7,10)),"invalid source date")
        seen.add(d)
        if r[code] in ("","."):continue
        v=float(r[code]);need(d<=now.date() and math.isfinite(v) and lo<v<hi,"invalid source value")
        if d>=min(old):obs[d]=v
    ds=sorted(obs);need(ds and ds[0]==min(old) and set(old)<=set(ds) and ds[-1]>=max(old),"source history coverage regression")
    need(all((b.year-a.year)*12+b.month-a.month==(3 if f=="Q" else 1) for a,b in zip(ds,ds[1:])),"source cadence gap")
    if mixed:
        comparisons=[]
        for i,seg in enumerate(segments):
            errors=[abs(obs[d]-v) for d,v in seg.items()]
            comparisons.append({"column":i,"count":len(seg),"first":min(seg).isoformat(),"last":max(seg).isoformat(),"median":statistics.median(errors),"max":max(errors),"exact":sum(e<=1e-6 for e in errors)})
        print("SLOOS_LEGACY_DUPLICATE_COLUMN_PROOF",json.dumps(comparisons,sort_keys=True))
        matched=[a for a in comparisons if a["median"]<=med_limit and a["max"]<=max_limit and a["exact"]>=.9*a["count"]]
        need(len(matched)==1,"cannot uniquely identify historical SLOOS column")
        old=segments[matched[0]["column"]]
    errors=[abs(obs[d]-v)/max(abs(v),1) if code in ("ULCNFB","OPHNFB") else abs(obs[d]-v) for d,v in old.items()]
    audit={"count":len(old),"exact":sum(abs(obs[d]-v)<=1e-6 for d,v in old.items()),"median_error":statistics.median(errors),"max_error":max(errors)}
    print("US_RESEARCH_HISTORICAL_OVERLAP",ident,json.dumps(audit,sort_keys=True))
    need(audit["median_error"]<=med_limit and audit["max_error"]<=max_limit,"historical identity mismatch")
    suffix="T00:00:00Z" if "T" in row["dates"][0] else ""
    dates=[d.isoformat()+suffix for d in ds];vs=[obs[d] for d in ds];before=row["last_date"];prior=row.get("current_vintage_provenance",{})
    need(not prior.get("source_series_id") or prior["source_series_id"]==code,"source changed")
    changed=dates!=row["dates"] or vs!=row["values"] or prior.get("source_series_id")!=code
    if changed:row.update(dates=dates,values=vs,last_date=dates[-1],last_value=vs[-1],current_vintage_provenance={"status":"FRED_PUBLISHED_CURRENT_REVISED_HISTORY_NOT_PIT","source_series_id":code,"source_url":meta_url,"source_csv_url":url,"source_csv_sha256":sha256(raw).hexdigest(),"source_units_verified":u,"source_frequency":f,"legacy_duplicate_column_repair":mixed,"historical_overlap":audit,"legacy_segment_comparisons":comparisons if mixed else None,"source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,"runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":dates[-1],"latest":vs[-1],"source_series_id":code,"overlap":audit}
def prepare(current,*,now,fetcher=fetch):
    need(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);rows=[]
    for ident in CONFIG:
        try:
            hits=[x for x in out["USD"] if x["id"]==ident];need(len(hits)==1,"unique source required")
            x=copy.deepcopy(hits[0]);result=prepare_row(x,ident,now,fetcher);hits[0].update(x);rows.append(result)
        except (OSError,ValueError,KeyError,TypeError) as exc:rows.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":"GMFQ_US_QUARTERLY_CFNAI_REVISED_V1","series":rows,"status":"READY" if any(x["status"]=="READY" for x in rows) else "NO_CHANGE_OR_WITHHELD","first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
    need(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True);a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,sort_keys=True)+"\n");print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
