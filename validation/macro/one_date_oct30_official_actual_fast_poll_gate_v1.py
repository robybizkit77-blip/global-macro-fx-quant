#!/usr/bin/env python3
"""Strict UTC gate for the two *already frozen* 30-Oct-2026 official releases.

This is a ONE-DATE fast-check activation guard, not a replacement for routine
Calendar/News, not a 24/7 polling service and not an event-market reaction gate.
The check must not fetch official actuals before 12:30 UTC Oct 30; the
scheduled workflow can be delayed by GitHub Actions.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime,timezone,date

from validation.macro.capture_official_postrelease_actuals_v1 import (
    ECI,GDP,LEDGER,OUT,validate_actual_log,
)
from validation.macro.freeze_pre_release_consensus_v1 import (
    read_existing,utc_iso,validate_existing
)

RELEASE_DAY=date(2026,10,30)
SCHEDULED_UTC="2026-10-30T12:30:00Z"
EXPECTED=(ECI,GDP)
SCHEMA="GMFQ_20261030_OFFICIAL_RELEASE_FAST_POLL_GATE_V1"

def gate(forecasts,actuals,now):
    validate_existing(forecasts)
    validate_actual_log(actuals,forecasts)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("POST_RELEASE_FAST_POLL_REQUIRES_AWARE_CLOCK")
    now=now.astimezone(timezone.utc)
    signed={x["event_key"]:x for x in forecasts}
    stored={x["event_key"]:x for x in actuals}
    have_both=all(k in signed and
                  signed[k]["official_scheduled_release_utc"]==SCHEDULED_UTC
                  for k in EXPECTED)
    missing=[k for k in EXPECTED if k not in stored]
    if now.date()!=RELEASE_DAY:
        status="OUTSIDE_ONCE_ONLY_RELEASE_DAY"
    elif not have_both:
        status="MISSING_BOTH_OFFICIALLY_SCHEDULED_FROZEN_FORECASTS"
    elif now < utc_iso(SCHEDULED_UTC):
        status="BEFORE_RELEASE_TIME_DO_NOT_FETCH"
    elif not missing:
        status="ALL_OFFICIAL_ACTUALS_ALREADY_CAPTURED"
    else:
        status="POLL_MISSING_ISSUER_ACTUALS_NOW"
    return {
        "schema":SCHEMA,
        "status":status,
        "should_poll":status=="POLL_MISSING_ISSUER_ACTUALS_NOW",
        "evaluated_at_utc":now.isoformat(timespec="seconds").replace("+00:00","Z"),
        "original_official_scheduled_release_utc":SCHEDULED_UTC,
        "forecasts_prior_to_release_valid":have_both,
        "expected_events":list(EXPECTED),
        "already_captured_events":[k for k in EXPECTED if k in stored],
        "missing_events":missing,
        "no_pre_scheduled_issuer_fetch":True,
        "first_report_is_runner_observation_not_publisher_first_release":True,
        "no_automatic_attribution_to_ois_2y_or_fx":True,
        "no_Core_Beta_Forward_or_28pair_mutation":True,
        "recurrent_schedule_after_2026_oct30_has_no_active_polls":True,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--github-output")
    parser.add_argument("--github-summary")
    a=parser.parse_args()
    forecasts=read_existing(LEDGER);actuals=read_existing(OUT)
    result=gate(forecasts,actuals,datetime.now(timezone.utc))
    if a.github_output:
        with open(a.github_output,"a",encoding="utf-8") as f:
            f.write("should_poll="+str(result["should_poll"]).lower()+"\n")
            f.write("poll_status="+result["status"]+"\n")
    if a.github_summary:
        with open(a.github_summary,"a",encoding="utf-8") as f:
            f.write("### 30 October issuer macro actual release check\n")
            f.write("- UTC scheduled release: 2026-10-30 12:30Z = 13:30 CET (Rome)\n")
            f.write("- Actual workflow execution: "+result["evaluated_at_utc"]+"\n")
            f.write("- Decision: **"+result["status"]+"**\n")
            f.write("- Frozen forecasts are secondary B-grade. No release-market causal inference.\n")
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
