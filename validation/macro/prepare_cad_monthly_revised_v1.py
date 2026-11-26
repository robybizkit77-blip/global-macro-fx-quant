"""Recurring current-vintage StatCan monthly research histories, not PIT/FX signals."""
from __future__ import annotations
import argparse,copy,csv,io,json,math,re
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from validation.sources.cad_statcan_core import download_csv,StatCanTransportUnavailable,norm

SOURCE=Path(__file__).resolve().parents[2]/"live_data/sections/MACRO_SERIES.json"
CONFIG={
 "CA_CPI_MEDIAN_YOY_history_value":("18100256","CA_CPI_MEDIAN_YOY_history.csv","percent YoY","median"),
 "CA_CPI_TRIM_YOY_history_value":("18100256","CA_CPI_TRIM_YOY_history.csv","percent YoY","trim"),
 "CA_EMPLOYMENT_history_value":("14100287","CA_EMPLOYMENT_history.csv","thousand persons SA","employment"),
 "CA_REAL_GDP_M_history_value":("36100434","CA_REAL_GDP_M_history.csv","million chained 2017 CAD SAAR","gdp"),
}
SCHEMA="GMFQ_CAD_STATCAN_MONTHLY_REVISED_RESEARCH_V1"
def require(ok,reason):
    if not ok:raise ValueError(reason)
def matches(row,kind):
    if norm(row.get("GEO"))!="canada":return False
    unit=norm(row.get("UOM"));scale=norm(row.get("SCALAR_FACTOR"))
    if kind in ("median","trim"):
        # Table 18-10-0256 includes both index levels and YoY measures.
        # Select only CPI-median or CPI-trim expressed in percent.
        expected={"median":("v108785714","measure of core inflation based on a weighted median approach, cpi-median (year-over-year percent change)"),"trim":("v108785715","measure of core inflation based on a trimmed mean approach, cpi-trim (year-over-year percent change)")}
        vector,title=expected[kind]
        return row.get("VECTOR")==vector and norm(row.get("Alternative measures"))==title and unit=="percent" and scale=="units"
    if kind=="employment":
        return (row.get("VECTOR")=="v2062811" and norm(row.get("Labour force characteristics"))=="employment" and
                norm(row.get("Gender") or row.get("Sex")) in ("total - gender","both sexes","total, gender") and
                norm(row.get("Age group"))=="15 years and over" and norm(row.get("Statistics"))=="estimate" and
                norm(row.get("Data type"))=="seasonally adjusted" and unit=="persons in thousands" and scale=="thousands")
    if kind=="gdp":
        industry=next((norm(v) for k,v in row.items() if "industry classification" in k.casefold()),"")
        return (industry in ("all industries","all industries [t001]") and
                norm(row.get("Seasonal adjustment"))=="seasonally adjusted at annual rates" and
                norm(row.get("Prices"))=="chained (2017) dollars" and unit=="dollars" and scale=="millions")
    raise ValueError("unknown series")
def parse(text,kind):
    obs={};vectors=set()
    reader=csv.DictReader(io.StringIO(text))
    require({"REF_DATE","GEO","UOM","SCALAR_FACTOR","VECTOR","VALUE"}<=set(reader.fieldnames or []),"StatCan table header mismatch")
    for row in reader:
        if not matches(row,kind):continue
        if row["VALUE"] in (None,""):continue
        stamp=row["REF_DATE"]
        require(bool(re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])",stamp)),"nonmonthly reference period")
        require(stamp not in obs,"duplicate exact source period")
        v=float(row["VALUE"])
        require(math.isfinite(v) and (kind in ("median","trim") or v>0),"invalid source value")
        obs[stamp]=v;vectors.add(row["VECTOR"])
    if len(vectors)!=1 or len(obs)<24:
        # Report source metadata only, to diagnose exact dimension mismatches.
        examples={}
        for row in csv.DictReader(io.StringIO(text)):
            if norm(row.get("GEO"))!="canada":continue
            if kind in ("median","trim"):
                if not any("cpi-"+kind in norm(v) or "cpi "+kind in norm(v) for v in row.values()):continue
            elif kind=="employment":
                if norm(row.get("Labour force characteristics"))!="employment":continue
                if norm(row.get("Age group"))!="15 years and over":continue
            else:continue
            key=row.get("VECTOR")
            if key not in examples and len(examples)<12:
                examples[key]={k:v for k,v in row.items() if k not in ("REF_DATE","VALUE","STATUS","SYMBOL","DECIMALS","DGUID","TERMINATED","COORDINATE") and not k.endswith("_ID")}
        raise ValueError("unique exact StatCan series not identified: "+kind+"; observations="+str(len(obs))+"; observed dimensions="+json.dumps(examples,ensure_ascii=False))
    return obs,next(iter(vectors))
def prepare_row(row,ident,now,raw):
    pid,source,unit,kind=CONFIG[ident]
    require(row["source_file"]==source and row["unit"]==unit and row["frequency"]=="M","local series identity mismatch")
    require(len(row["dates"])==len(row["values"]) and row["dates"][-1]==row["last_date"] and row["values"][-1]==row["last_value"],"inconsistent local row")
    obs,vector=parse(raw,kind)
    start=row["dates"][0][:7];ds=sorted(d for d in obs if d>=start);vs=[obs[d] for d in ds]
    require(ds and ds[0]==start and ds[-1]>=row["last_date"][:7] and ds[-1]<now.date().isoformat()[:7],"history regression or future observation")
    require(set(d[:7] for d in row["dates"])<=set(ds),"historical coverage regression")
    def ordinal(d):return int(d[:4])*12+int(d[5:7])
    require(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])),"noncontiguous monthly history")
    old=row.get("current_vintage_provenance",{})
    before=row["last_date"]
    changed=row["dates"]!=ds or row["values"]!=vs or old.get("source_vector")!=vector
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid="+pid+"01"
    if changed:
        row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],
          current_vintage_provenance={"status":"STATCAN_CURRENT_REVISED_HISTORY_NOT_PIT","source_url":url,
           "source_table":pid,"source_vector":vector,"source_csv_sha256":sha256(raw.encode()).hexdigest(),
           "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,
           "runner_first_seen_utc":now.isoformat()})
    return {"id":ident,"status":"READY" if changed else "NO_CHANGE","before":before,"after":ds[-1],"latest":vs[-1],"vector":vector,"source_url":url}
def prepare(current,*,now,fetcher=download_csv):
    require(now.utcoffset() is not None,"aware clock required")
    out=copy.deepcopy(current);receipts=[];cache={}
    for ident,(pid,*_) in CONFIG.items():
        try:
            if pid not in cache:
                try:cache[pid]=fetcher(pid)
                except (OSError,ValueError,StatCanTransportUnavailable) as exc:cache[pid]=exc
            raw=cache[pid]
            if isinstance(raw,Exception):raise raw
            rows=[r for r in out["CAD"] if r["id"]==ident];require(len(rows)==1,"unique canonical series required")
            candidate=copy.deepcopy(rows[0]);receipt=prepare_row(candidate,ident,now,raw);rows[0].update(candidate);receipts.append(receipt)
        except (OSError,ValueError,KeyError,TypeError,StatCanTransportUnavailable) as exc:
            receipts.append({"id":ident,"status":"WITHHELD","reason":str(exc)})
    return out,{"schema":SCHEMA,"observed_at_utc":now.isoformat(),"series":receipts,
                "status":"READY" if any(r["status"]=="READY" for r in receipts) else "NO_CHANGE_OR_WITHHELD",
                "first_release_PIT_certified":False,"affects_fx_core":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--candidate",required=True,type=Path);p.add_argument("--receipt",required=True,type=Path);a=p.parse_args()
    require(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"temporary output only")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n");a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
