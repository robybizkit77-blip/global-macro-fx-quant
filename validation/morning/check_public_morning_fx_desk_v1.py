#!/usr/bin/env python3
"""Independently classify the public Morning Macro/FX edition at observation time.

A late HTTP check can prove present-now but NOT a publication before 08:00.
No inferred delivery timestamp from JSON creation time or GitHub job success.
"""
import argparse
from datetime import datetime, time, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SCHEMA="GMFQ_MORNING_MACRO_FX_V1"
URL=("https://robybizkit77-blip.github.io/global-macro-fx-quant/"
     "site/fx-quant-v2/next/morning-desk-current.json")
ROME=ZoneInfo("Europe/Rome")

def assess(payload,now):
    local=now.astimezone(ROME)
    today=local.date().isoformat()
    before=local.time()<time(8,0)
    details={"expected_date":today,"observed_at_rome":local.isoformat(),
             "public_delivery_by_0800_proven":False}
    if not isinstance(payload,dict):
        status="PREDEADLINE_UNREACHABLE" if before else "MISSING_AFTER_0800"
        return {**details,"status":status}
    edition=payload.get("edition_date")
    if payload.get("schema")!=SCHEMA or payload.get("observation_cutoff_exclusive")!=edition:
        return {**details,"status":"INVALID_PUBLIC_CONTRACT"}
    if not isinstance(edition,str) or edition>today:
        return {**details,"status":"INVALID_FUTURE_EDITION"}
    if not isinstance(payload.get("charts"),list) or len(payload["charts"])!=2:
        return {**details,"status":"INVALID_CHART_EVIDENCE"}
    for chart in payload["charts"]:
        if chart.get("as_of","")>=edition or any(
            x.get("date","")>=edition for x in chart.get("points",[])):
            return {**details,"status":"POST_EVENT_LOOKAHEAD_REJECTED"}
    if edition!=today:
        return {**details,"status":"ARCHIVED_AWAITING_MORNING" if before else "STALE_AFTER_0800",
                "public_edition_date":edition}
    if payload.get("edition_status") not in ("MORNING_SNAPSHOT","LATE_MORNING_SNAPSHOT"):
        return {**details,"status":"RECONSTRUCTION_NOT_LIVE_MORNING","public_edition_date":edition}
    return {**details,"status":"VERIFIED_ON_PUBLIC_SITE_BEFORE_0800" if before
            else "PRESENT_NOW_BUT_ON_TIME_DELIVERY_NOT_PROVEN",
            "public_edition_date":edition,"public_delivery_by_0800_proven":before}

def load_public(url,now):
    token=now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
    sep="&" if "?" in url else "?"
    req=Request(url+sep+"morning_audit="+token,headers={"Cache-Control":"no-cache",
        "User-Agent":"FXQuantMorningDeskPublicAudit/1.0"})
    with urlopen(req,timeout=18) as res:
        if res.status!=200:raise OSError("Morning feed HTTP "+str(res.status))
        return json.loads(res.read().decode("utf-8"))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--url",default=URL)
    p.add_argument("--local-file",type=Path)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    now=datetime.now(timezone.utc)
    try:
        payload=json.loads(a.local_file.read_text(encoding="utf-8")) if a.local_file else load_public(a.url,now)
    except (OSError,ValueError,TimeoutError):
        payload=None
    report=assess(payload,now)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    if report["status"] in ("VERIFIED_ON_PUBLIC_SITE_BEFORE_0800",
                            "PRESENT_NOW_BUT_ON_TIME_DELIVERY_NOT_PROVEN",
                            "ARCHIVED_AWAITING_MORNING","PREDEADLINE_UNREACHABLE"):
        return 0
    return 1

if __name__=="__main__":
    raise SystemExit(main())
