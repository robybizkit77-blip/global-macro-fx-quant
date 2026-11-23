#!/usr/bin/env python3
"""Supplemental G8 economic traffic-light research, never FX Core or canonical Macro.
Seven explicit OECD/BIS/issuer series via FRED and Eurostat building permits.
Fails closed on stale, missing, changed-source or ambiguous observations.
All data are current revised vintages, not point-in-time historical releases.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, timezone
from io import StringIO
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
TARGET=ROOT/"site/fx-quant-v2/next/semaphore-supplement-v1.json"
SCHEMA="GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1"
FRED="https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MAX_BYTES=3_000_000
# Definitions and transformations deliberately fixed and source-identifiable.
# Several historical OECD/BIS feeds have stopped updating: retain status WITHHELD;
# never use today's fetch time to make an old observation look current.
REGISTRY=[
 dict(ccy="EUR",area="house",key="EA20_STS_COBP_M",method="eurostat",
      name="Permessi edilizi area euro (abitazioni)",unit="indice 2021=100",
      frequency="M",kind="percent",max_age_days=115,
      source_page="https://ec.europa.eu/eurostat/databrowser/view/sts_cobp_m/default/table?lang=en",
      origin="Eurostat / sts_cobp_m"),
 dict(ccy="JPY",area="house",key="JPNWSCNDW01MLSAM",method="fred",
      name="Nuove costruzioni residenziali",unit="abitazioni SA",frequency="M",
      kind="percent",max_age_days=110,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/JPNWSCNDW01MLSAM"),
 dict(ccy="AUD",area="industry",key="PRMNTO01AUQ657S",method="fred",
      name="Manifattura: crescita trimestrale SA",unit="% QoQ",frequency="Q",
      kind="points",max_age_days=250,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/PRMNTO01AUQ657S"),
 dict(ccy="NZD",area="house",key="NZLPERMITMISMEI",method="fred",
      name="Permessi residenziali",unit="indice 2015=100 SA",frequency="M",
      kind="percent",max_age_days=110,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/NZLPERMITMISMEI"),
 dict(ccy="NZD",area="industry",key="PRMNTO01NZQ657S",method="fred",
      name="Manifattura: crescita trimestrale SA",unit="% QoQ",frequency="Q",
      kind="points",max_age_days=250,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/PRMNTO01NZQ657S"),
 dict(ccy="NZD",area="leading",key="NZLLOLITOAASTSAM",method="fred",
      name="OECD CLI Nuova Zelanda",unit="indice SA",frequency="M",
      kind="points",max_age_days=115,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/NZLLOLITOAASTSAM"),
 dict(ccy="NZD",area="credit",key="QNZPBMXDCA",method="fred",
      name="Credito bancario settore privato, corretto per rotture",unit="mld NZD NSA",frequency="Q",
      kind="percent",max_age_days=250,origin="BIS tramite FRED",
      source_page="https://fred.stlouisfed.org/series/QNZPBMXDCA"),
 dict(ccy="CAD",area="industry",key="CANSLMNTO02MLSAM",method="fred",
      name="Vendite manifatturiere SA",unit="CAD SA",frequency="M",
      kind="percent",max_age_days=110,origin="OECD tramite FRED",
      source_page="https://fred.stlouisfed.org/series/CANSLMNTO02MLSAM"),
]
assert len(REGISTRY)==8 and len({(s["ccy"],s["area"]) for s in REGISTRY})==8

def fetch(url:str)->bytes:
    host=urlsplit(url).hostname
    if host not in {"fred.stlouisfed.org","ec.europa.eu"} or not url.startswith("https://"):
        raise ValueError("source host outside immutable allowlist")
    req=Request(url,headers={"User-Agent":"GMFQ-Economic-Research/1.0",
                              "Accept":"text/csv,application/json"})
    with urlopen(req,timeout=18) as response:
        final=response.geturl()
        if urlsplit(final).hostname!=host or not final.startswith("https://"):
            raise ValueError("untrusted redirect")
        data=response.read(MAX_BYTES+1)
        if not data or len(data)>MAX_BYTES:
            raise ValueError("oversized/empty source")
    return data

def period(date_string, frequency):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date_string):
        raise ValueError("unrecognized observation date")
    x=date.fromisoformat(date_string)
    if frequency=="Q":
        return f"{x.year}-Q{(x.month-1)//3+1}"
    return f"{x.year}-{x.month:02d}"

def period_end(p):
    if m:=re.fullmatch(r"(\d{4})-Q([1-4])",p):
        year=int(m[1]); month=int(m[2])*3
    elif m:=re.fullmatch(r"(\d{4})-(\d{2})",p):
        year=int(m[1]);month=int(m[2])
        if not 1<=month<=12:raise ValueError("invalid monthly period")
    else: raise ValueError("invalid period")
    if month==12: return date(year,12,31)
    return date.fromordinal(date(year,month+1,1).toordinal()-1)

def parse_fred(raw:bytes,key:str,frequency:str,now:date):
    rdr=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    if rdr.fieldnames not in (["observation_date",key],["DATE",key]):
        raise ValueError("FRED header/source ID changed")
    result={}
    for row in rdr:
        p=period(row[rdr.fieldnames[0]],frequency)
        if period_end(p)>now: continue
        raw_value=row[key]
        if raw_value in {"", "."}: continue
        value=float(raw_value)
        if not math.isfinite(value) or abs(value)>1e15: raise ValueError("nonfinite/implausible value")
        if p in result: raise ValueError("duplicate official period")
        result[p]=value
    if len(result)<12: raise ValueError("insufficient history")
    return sorted(result.items())

def parse_eurostat(raw:bytes,now:date):
    """JSON-stat v2: accept only *one exact* EA20 / permits-dwellings / adjusted index.
    Do not collapse multiple dimensions or select a convenient value implicitly.
    """
    payload=json.loads(raw.decode("utf-8"))
    if payload.get("class")!="dataset" or not isinstance(payload.get("value"),dict):
        raise ValueError("Eurostat JSON-stat identity changed")
    dims=payload.get("dimension",{})
    ids=payload.get("id",[])
    sizes=payload.get("size",[])
    if len(ids)!=len(sizes) or not ids or "time" not in ids:
        raise ValueError("invalid Eurostat shape")
    allowed={"freq":{"M"},"geo":{"EA20","EA21"},"indic_bt":{"BPRM_DW"},
             "s_adj":{"SCA"},"unit":{"I21"}}
    selected={}
    for k in ids:
        index=dims.get(k,{}).get("category",{}).get("index",{})
        if not isinstance(index,dict):raise ValueError("invalid Eurostat category map")
        choices=[v for v in allowed.get(k,set()) if v in index]
        if k!="time":
            if len(choices)!=1:raise ValueError("missing/ambiguous Eurostat dimension "+k)
            selected[k]=index[choices[0]]
    if payload.get("size",[0])[ids.index("time")]<12:raise ValueError("too few periods")
    vals=payload["value"]
    out={}
    for period_raw,pos in dims["time"]["category"]["index"].items():
        if not re.fullmatch(r"\d{4}-\d{2}",period_raw):continue
        stamp=period_raw+"-01"
        p=period(stamp,"M")
        if period_end(p)>now:continue
        coords={**selected,"time":pos}
        i=0
        for k,n in zip(ids,sizes):
            i=i*n+coords[k]
        v=vals.get(str(i))
        if v is None:continue
        f=float(v)
        if not math.isfinite(f):raise ValueError("nonfinite Eurostat observation")
        out[p]=f
    if len(out)<12:raise ValueError("insufficient Eurostat observations")
    return sorted(out.items())

def contiguous_last_two(obs,frequency):
    a,b=obs[-2:]
    left,right=a[0],b[0]
    if frequency=="M":
        y,m=map(int,left.split("-")); ny,nm=map(int,right.split("-"))
        if ny*12+nm-y*12-m !=1:raise ValueError("monthly gap in latest observations")
    else:
        y=int(left[:4]);q=int(left[-1]);ny=int(right[:4]);nq=int(right[-1])
        if ny*4+nq-y*4-q!=1:raise ValueError("quarterly gap in latest observations")
    return [list(a),list(b)]

def candidate(spec,observations,now):
    newest=observations[-1][0]
    age=(now-period_end(newest)).days
    if age>spec["max_age_days"]:
        return None,{"status":"WITHHELD_STALE","last_observation":newest,"days_since_period_end":age}
    if age<0:raise ValueError("future period")
    points=contiguous_last_two(observations,spec["frequency"])
    payload={"ccy":spec["ccy"],"area":spec["area"],
      "id":"SEM_G8_"+spec["ccy"]+"_"+spec["area"].upper(),
      "label":spec["name"],"frequency":spec["frequency"],"unit":spec["unit"],
      "dates":[x[0] for x in points],"values":[x[1] for x in points],
      "category":"Semaforo supplementare","source_file":spec["origin"],
      "source_page":spec["source_page"],"source_series_id":spec["key"],
      "metric_kind":spec["kind"],"observation_as_of":newest,
      "quality":"SOURCE_REVISED_RESEARCH_NOT_PIT"}
    return payload,{"status":"READY_DESCRIPTIVE_REVISED","last_observation":newest,"days_since_period_end":age}

def collect(now=None,fetcher=fetch):
    now=now or datetime.now(timezone.utc).date()
    out={"schema":SCHEMA,"as_of":now.isoformat(),"source_count":len(REGISTRY),
      "series":[],"audit":{},"notes":"Latest revised observations, not PIT, no FX score."}
    for spec in REGISTRY:
        code=spec["ccy"]+"_"+spec["area"]
        url=(FRED+spec["key"]) if spec["method"]=="fred" else (
          "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_cobp_m?"
          "geo=EA20&indic_bt=BPRM_DW&s_adj=SCA&unit=I21&lang=EN")
        try:
            raw=fetcher(url)
            observations=(parse_fred(raw,spec["key"],spec["frequency"],now)
                          if spec["method"]=="fred" else parse_eurostat(raw,now))
            item,status=candidate(spec,observations,now)
            if item is not None:out["series"].append(item)
            out["audit"][code]={"...":None,**status,"source_page":spec["source_page"],
                                 "origin":spec["origin"]}
            out["audit"][code].pop("...")
        except (ValueError,KeyError,IndexError,UnicodeError,TimeoutError,OSError) as exc:
            out["audit"][code]={"status":"WITHHELD_FETCH_OR_VALIDATION","reason":str(exc)[:180],
                                 "source_page":spec["source_page"],"origin":spec["origin"]}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default=str(TARGET))
    ap.add_argument("--dry-run",action="store_true")
    x=ap.parse_args()
    out=collect()
    content=json.dumps(out,ensure_ascii=False,indent=2)+"\n"
    if not x.dry_run: Path(x.output).write_text(content,encoding="utf-8")
    print(json.dumps({"status":"CAPTURED_REVISED_NOT_PIT",
      "ready":len(out["series"]),"total":len(REGISTRY),
      "audit":{k:v["status"] for k,v in out["audit"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
