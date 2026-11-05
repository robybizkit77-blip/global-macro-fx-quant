#!/usr/bin/env python3
"""Resolve Rome Rates observation by scheduled UTC cron, never runner clock."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
EXPECTED_CRONS = {"10 4 * * 1-5", "40 4 * * 1-5", "10 5 * * 1-5",
                  "40 5 * * 1-5", "10 6 * * 1-5"}
ACTIVE_ROME_SLOTS = {(6, 10), (6, 40), (7, 10)}

def decide(event: str, cron: str, now: dt.datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware UTC/local time required")
    local = now.astimezone(ROME)
    result = {"event":event, "cron":cron,
              "date_rome":local.date().isoformat(),
              "actual_started_at_rome":local.isoformat(timespec="seconds"),
              "should_run":False, "reason":"UNRECOGNIZED_EVENT",
              "slot_rome":None, "execution_delay_minutes":None,
              "proves_delivery_at_0800":False}
    if event=="pull_request":
        result["reason"]="PR_CONTRACT_ONLY"
        return result
    if event in {"push", "workflow_dispatch"}:
        result.update(should_run=True,reason="EXPLICIT_SOURCE_AUDIT")
        return result
    if event!="schedule" or cron not in EXPECTED_CRONS:
        result["reason"]="UNKNOWN_OR_UNAUTHORIZED_SCHEDULE"
        return result
    minutes, hours = [int(x) for x in cron.split()[:2]]
    offset=int(local.utcoffset().total_seconds()//3600)
    local_hour=hours+offset
    result["slot_rome"]=f"{local_hour:02d}:{minutes:02d}"
    if (local_hour,minutes) not in ACTIVE_ROME_SLOTS:
        result["reason"]="INACTIVE_CET_CEST_DUPLICATE_SLOT"
        return result
    target=dt.datetime.combine(local.date(), dt.time(local_hour,minutes),tzinfo=ROME)
    delayed=int((local-target).total_seconds()//60)
    result["execution_delay_minutes"]=delayed
    result["should_run"]=True
    result["reason"]="VALID_SLOT_QUEUED_LATE" if delayed>5 else "VALID_SLOT"
    return result

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--event",required=True)
    p.add_argument("--cron",default="")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--summary",type=Path,required=True)
    args=p.parse_args()
    r=decide(args.event,args.cron,dt.datetime.now(dt.timezone.utc))
    with args.output.open("a",encoding="utf-8") as out:
        out.write("should_run="+str(r["should_run"]).lower()+"\n")
        out.write("local_time="+r["actual_started_at_rome"]+"\n")
        out.write("retry_key=rates-daily-"+r["date_rome"]+"\n")
    with args.summary.open("a",encoding="utf-8") as out:
        out.write("\n### Rates Daily Operational source check\n")
        out.write("- Gate: **"+r["reason"]+"**; source audit runs: "+str(r["should_run"])+"\n")
        out.write("- Scheduled local slot: "+str(r["slot_rome"])+"; actual: "+r["actual_started_at_rome"]+"\n")
        out.write("- Delay from intended cron: "+str(r["execution_delay_minutes"])+" minutes\n")
        out.write("- A successful cron gate does not certify new rates or published data.\n")
    print("RATES_DAILY_OPERATIONAL_GATE "+json.dumps(r,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
