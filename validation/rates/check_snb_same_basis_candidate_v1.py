#!/usr/bin/env python3
"""Read-only SNB CHF same-basis 2Y/10Y source candidate; never promote rates.

Uses the official SNB daily spot-yield cube, not the monthly rendoblid cube,
and compares its last certified canonical observation to guard basis drift.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
SOURCE="https://data.snb.ch/api/cube/rendeiduebd/data/json/en"
KEYS={"2Y":"EPB@SNB.rendeiduebd{CHF,2J}",
      "10Y":"EPB@SNB.rendeiduebd{CHF,10J}"}
EXPECTED_UNIT=("percent","%","prozent","pourcent","per cent")

def parse_candidate(payload:object, *, certified_date:str, certified_2y:float,
                    certified_10y:float)->dict:
    if not isinstance(payload,dict) or not isinstance(payload.get("timeseries"),list):
        raise ValueError("SNB data API did not return a timeseries collection")
    by_key={}
    for entry in payload["timeseries"]:
        if not isinstance(entry,dict):
            raise ValueError("SNB malformed timeseries entry")
        meta=entry.get("metadata")
        if not isinstance(meta,dict):
            raise ValueError("SNB missing official metadata")
        key=meta.get("key")
        if key not in KEYS.values():
            raise ValueError("SNB contains unexpected security/currency/tenor")
        if key in by_key:
            raise ValueError("SNB duplicate same-basis maturity")
        unit=str(meta.get("unit") or "").lower()
        if not any(x in unit for x in EXPECTED_UNIT):
            raise ValueError("SNB tenor unit not independently verified as percent")
        frequency=str(meta.get("frequency") or "")
        if frequency not in ("P1D","P1BD"):
            raise ValueError("SNB tenor not a daily official spot series")
        data=entry.get("values")
        if not isinstance(data,list) or not data:
            raise ValueError("SNB official tenor returned metadata without observations")
        obs={}
        for item in data:
            if not isinstance(item,dict):
                raise ValueError("SNB invalid observation")
            ds=item.get("date")
            try:
                day=dt.date.fromisoformat(ds).isoformat()
            except (TypeError,ValueError):
                raise ValueError("SNB invalid observation date")
            value=item.get("value")
            if ds!=day or type(value) not in (int,float) or not math.isfinite(value):
                raise ValueError("SNB invalid/non-numeric observation")
            if not (-5<=value<=25):
                raise ValueError("SNB spot yield outside conservative validation bounds")
            if day in obs:
                raise ValueError("SNB duplicate observation date")
            obs[day]=float(value)
        by_key[key]=obs
    if set(by_key)!=set(KEYS.values()):
        raise ValueError("SNB missing 2Y or 10Y source series")
    v2=by_key[KEYS["2Y"]]
    v10=by_key[KEYS["10Y"]]
    if certified_date not in v2 or certified_date not in v10:
        return {"status":"SOURCE_BASIS_NOT_RECONCILED","reason":"Previously certified exact-source date missing",
                "eligible_for_automatic_promotion":False}
    if abs(v2[certified_date]-certified_2y)>0.001 or abs(v10[certified_date]-certified_10y)>0.001:
        return {"status":"SOURCE_BASIS_NOT_RECONCILED","reason":"Previously certified same-date 2Y/10Y numeric values differ",
                "eligible_for_automatic_promotion":False}
    shared=sorted(set(v2)&set(v10))
    if not shared or shared[-1]<certified_date:
        raise ValueError("SNB no validated common-date spot pair")
    last=shared[-1]
    return {
        "status":"REVIEWABLE_NEW_OFFICIAL_PAIR" if last>certified_date else "CURRENT_CANONICAL_DATE_RECONCILED",
        "source_as_of":last,"last_certified_as_of":certified_date,
        "2Y":v2[last],"10Y":v10[last],"curve_bp":round((v10[last]-v2[last])*100,1),
        "common_date_observations":len(shared),
        "source":"Swiss National Bank, CHF Confederation spot rates, rend eiduebd".replace("rend eiduebd","rendeiduebd"),
        "eligible_for_automatic_promotion":False
    }

def inspect(current:dict, *, fetch=None, now:dt.date|None=None)->dict:
    now=now or dt.date.today()
    chf=current["CHF"]
    certified=dt.date.fromisoformat(chf["date"])
    start=(certified-dt.timedelta(days=5)).isoformat()
    query=urllib.parse.urlencode({"dimSel":"D0(CHF),D1(2J,10J)",
                                  "fromDate":start,"toDate":now.isoformat()})
    url=SOURCE+"?"+query
    def get(url:str):
        req=urllib.request.Request(url,headers={"User-Agent":"GMFQ-CHF-SNB-Official-Candidate/1.0",
                                                "Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=18) as res:
            if res.status!=200 or "json" not in res.headers.get("Content-Type","").lower():
                raise ValueError("SNB source returned non-JSON/HTTP 200 response")
            return json.load(res)
    try:
        obj=(fetch or get)(url)
        result=parse_candidate(obj,certified_date=chf["date"],certified_2y=chf["2Y"],
                               certified_10y=chf["10Y"])
    except (ValueError,KeyError,TypeError,urllib.error.URLError,TimeoutError,OSError) as exc:
        result={"status":"SOURCE_CANDIDATE_WITHHELD",
                "reason":f"{type(exc).__name__}: {str(exc)[:200]}",
                "eligible_for_automatic_promotion":False}
    return {"schema":"GMFQ_SNB_CHF_2Y_10Y_OFFICIAL_CANDIDATE_V1",
            "checked_at_date":now.isoformat(),
            "source_url":SOURCE,"filter":"D0(CHF),D1(2J,10J)",
            "mode":"READ_ONLY_REQUIRES_OFFICIAL_SOURCE_CERTIFICATION",
            "candidate":result,
            "changed_native_rates":False,"changed_macro":False,"auto_promotion":False}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="/tmp/snb-chf-source-candidate.json")
    args=p.parse_args()
    current=json.loads((ROOT/"live_data/sections/NATIVE_RATES_DATA.json").read_text())
    report=inspect(current)
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
