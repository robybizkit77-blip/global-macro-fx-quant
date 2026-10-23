#!/usr/bin/env python3
"""Read-only official SNB/RBNZ accessibility check for missing G8 Rates.

IMPORTANT: A reachable source is NOT proof of a same-date 2Y+10Y observation.
No downloaded rates or model inputs are written; only minimal transport evidence.
SNB advises using lastUpdate (instead of polling the large cube).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROME=ZoneInfo("Europe/Rome")
SOURCES={
    "CHF_SNB_LATEST_UPDATE":(
        "https://data.snb.ch/api/cube/rendeiduebd/lastUpdate","metadata"),
    "NZD_RBNZ_B2_OFFICIAL_XLSX":(
        "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx",
        "xlsx"),
    "NZD_RBNZ_B2_PUBLIC_TABLE":(
        "https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates",
        "html"),
}

def classify(*,code:int|None,content_type:str="",prefix:bytes=b"",error:str|None=None,kind:str)->str:
    if code in (401,403):
        return "ACCESS_BLOCKED"
    if code==404:
        return "OFFICIAL_RESOURCE_NOT_FOUND"
    if code in (408,429,500,502,503,504) or (code is None and error):
        return "SOURCE_UNREACHABLE_OR_THROTTLED"
    if code!=200:
        return "UNEXPECTED_HTTP_STATUS"
    ct=content_type.lower()
    if kind=="xlsx":
        return "REACHABLE_UNVERIFIED_CONTENT" if prefix.startswith(b"PK\\x03\\x04") else "UNEXPECTED_FORMAT"
    if kind=="metadata":
        return ("REACHABLE_UNVERIFIED_CONTENT"
                if ("json" in ct or "xml" in ct or "text/plain" in ct) and prefix.strip() else "UNEXPECTED_FORMAT")
    if kind=="html":
        return ("REACHABLE_UNVERIFIED_CONTENT"
                if "html" in ct and (b"<html" in prefix.lower() or b"<!doctype" in prefix.lower())
                else "UNEXPECTED_FORMAT")
    raise ValueError(kind)

def probe(name:str,url:str,kind:str,opener=None)->dict:
    opener=opener or urllib.request.urlopen
    req=urllib.request.Request(url,headers={
        "User-Agent":"GMFQ-Official-Rates-Source-Diagnostics/1.0 (non-commercial research)",
        "Accept":"application/json,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/html,*/*",
        "Range":"bytes=0-127",
    })
    try:
        with opener(req,timeout=12) as response:
            code=response.status
            ct=response.headers.get("Content-Type","")
            prefix=response.read(128)
        state=classify(code=code,content_type=ct,prefix=prefix,kind=kind)
        err=None
    except urllib.error.HTTPError as exc:
        code=exc.code;ct=exc.headers.get("Content-Type","")
        state=classify(code=code,content_type=ct,kind=kind)
        err=f"HTTP_{code}"
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        code=None;ct=""
        state=classify(code=None,error=type(exc).__name__,kind=kind)
        err=type(exc).__name__
    return {"authority":name.split("_")[1],"url":url,"http_status":code,
            "content_type":ct[:110],"access":state,"error_type":err,
            "source_2y_10y_verified":False,"eligible_for_automatic_promotion":False,
            "effect_on_rates":"NONE","effect_on_macro":"NONE"}

def build(opener=None,now:dt.datetime|None=None)->dict:
    now=(now or dt.datetime.now(ROME)).astimezone(ROME)
    rows={name:probe(name,url,kind,opener) for name,(url,kind) in SOURCES.items()}
    return {"schema":"GMFQ_OFFICIAL_BLOCKED_RATES_ACCESS_V1",
            "checked_at_rome":now.isoformat(timespec="seconds"),"probe_status":"EVIDENCE_ONLY",
            "results":rows,
            "caveat":"Transport availability only. Neither fresh CHF spot curve nor NZD RBNZ B2 closes may be published without a separately validated same-day official source and project certification.",
            "core_model_effect":"NONE"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="/tmp/blocked-rates-source-access.json")
    args=parser.parse_args()
    result=build()
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
