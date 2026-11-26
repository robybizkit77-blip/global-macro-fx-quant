"""Revised Eurostat industrial production and real retail volume, no PIT/FX promotion."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request,urlopen
from validation.sources.eur_eurostat_core import API_BASE, extract_series

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"live_data/sections/MACRO_SERIES.json"
CONFIG={
    "EA_IP_history_value":("EA_IP_history.csv","sts_inpr_m",{"indic_bt":"PRD","nace_r2":"B-D"}),
    "EA_RETAIL_VOL_history_value":("EA_RETAIL_VOL_history.csv","sts_trtu_m",{"indic_bt":"VOL_SLS","nace_r2":"G47"}),
}
COMMON={"freq":"M","unit":"I21","geo":"EA21","s_adj":"SCA"}
SCHEMA="GMFQ_EUROSTAT_EUR_ACTIVITY_REVISED_V1"


def require(ok,reason):
    if not ok: raise ValueError(reason)


def query(ident):
    _,dataset,extra=CONFIG[ident]
    filters={**COMMON,**extra}
    url=f"{API_BASE}/{dataset}?"+urlencode({"lang":"EN",**filters,"sinceTimePeriod":"2019-10"})
    return dataset,filters,url


def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"application/json"}),timeout=30) as response:
        require(response.status==200 and urlsplit(response.geturl()).hostname=="ec.europa.eu","Eurostat transport not verified")
        raw=response.read(4_000_001)
    require(0<len(raw)<=4_000_000,"Eurostat response size")
    return raw


def prepare(current,*,now,fetcher=fetch):
    require(now.utcoffset() is not None,"Aware timestamp required")
    out=copy.deepcopy(current)
    report={"schema":SCHEMA,"observed_at_utc":now.isoformat(),"series":[],"first_release_PIT_certified":False,"affects_fx_core":False}
    for ident,(source_file,_,_) in CONFIG.items():
        hits=[x for x in out["EUR"] if x["id"]==ident]
        require(len(hits)==1,"Unique historical series required: "+ident)
        row=hits[0]
        before=row["last_date"]
        require(row["source_file"]==source_file and row["frequency"]=="M" and row["unit"]=="Index 2021=100","Existing series definition changed: "+ident)
        require(row["dates"][-1]==before and row["values"][-1]==row["last_value"],"Existing series inconsistent")
        dataset,filters,url=query(ident)
        raw=fetcher(url)
        payload=json.loads(raw)
        require(set(payload["id"])==set(filters)|{"time"},"Unfiltered dimension in Eurostat response")
        observations=extract_series(payload,filters)
        dates=[d[:7] for d,v in observations]
        vals=[v for d,v in observations]
        start=row["dates"][0][:7]
        pairs=[(d,v) for d,v in zip(dates,vals) if d>=start]
        ds,vs=map(list,zip(*pairs))
        def ordinal(d):
            return int(d[:4])*12+int(d[5:7])
        require(ds[0]==start and ds[-1]>=before[:7] and ds[-1]<now.date().isoformat()[:7],"Source does not cover current history or includes future period")
        require(all(ordinal(b)-ordinal(a)==1 for a,b in zip(ds,ds[1:])) and all(math.isfinite(v) and v>0 for v in vs),"Incomplete or invalid revised history")
        require(set(d[:7] for d in row["dates"])<=set(ds),"Historical coverage regression")
        # Full vintage replacement: never splice a fixed-composition EA21
        # current series onto an older aggregate of unknown composition.
        prov={"status":"EUROSTAT_CURRENT_REVISED_HISTORY_NOT_PIT","dataset":dataset,"filters":filters,"source_url":url,
              "source_series_first_release_PIT_certified":False,"historical_levels_may_be_revised_again":True,
              "geography":"EA21 fixed composition","source_json_sha256":sha256(raw).hexdigest()}
        old=row.get("current_vintage_provenance",{})
        changed=row["dates"]!=ds or row["values"]!=vs or old.get("filters")!=filters
        if changed:
            row.update(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1],
                       current_vintage_provenance={**prov,"runner_first_seen_utc":now.isoformat()})
        report["series"].append({"id":ident,"before":before,"after":ds[-1],"latest":vs[-1],"changed":changed,"source":prov})
    report["status"]="READY" if any(r["changed"] for r in report["series"]) else "NO_CHANGE"
    return out,report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True,type=Path)
    p.add_argument("--receipt",required=True,type=Path)
    a=p.parse_args()
    require(all(x.resolve().is_relative_to(Path("/tmp")) for x in (a.candidate,a.receipt)),"Only temporary output permitted")
    out,receipt=prepare(json.loads(SOURCE.read_text()),now=datetime.now(timezone.utc))
    a.candidate.parent.mkdir(parents=True,exist_ok=True)
    a.candidate.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__": main()
