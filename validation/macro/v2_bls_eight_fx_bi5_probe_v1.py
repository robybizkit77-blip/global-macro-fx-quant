#!/usr/bin/env python3
"""Read-only eight-event Dukascopy FX hour probe, strictly release-timed."""
import argparse,json
from datetime import timezone
from pathlib import Path
from validation.macro.v2_shadow_features_v1 import require,timestamp
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence,validate
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import read_fixture
from validation.macro.v2_bls_shutdown_sparse_reentry_v1 import load_evidence
from validation.macro.v2_dukascopy_bi5_hour_probe_v1 import fetch,summarize,source_clock

def event_url(release):
    instant=timestamp(release).astimezone(timezone.utc)
    return ("https://datafeed.dukascopy.com/datafeed/EURUSD/"
            f"{instant.year}/{instant.month-1:02}/{instant.day:02}/{instant.hour:02}h_ticks.bi5")

def run(*, downloader=fetch, max_attempts=2,timeout=20):
    bls=evidence()
    validate(bls,read_fixture(),load_evidence())
    require(max_attempts in (1,2) and 1<=timeout<=60,"bounded retry contract")
    reports=[]
    for event in bls["first_release_values"][:-1]:
        at=timestamp(event["released_at"]).astimezone(timezone.utc)
        require(at.minute==30 and at.second==0,"noncanonical BLS release second")
        url=event_url(event["released_at"])
        base,parts=source_clock(url)
        require(base==at.replace(minute=0,second=0,microsecond=0),"BI5 UTC hour mismatch")
        outcome={"period":event["observation_period"],"release_at":at.isoformat(),
                 "source_url":url,"status":"NOT_ACQUIRED","attempts":0,
                 "error_type":None,"receipt":None}
        for i in range(max_attempts):
            outcome["attempts"]=i+1
            try:
                data,transport=downloader(url,timeout)
                receipt=summarize(data,source_url=url,transport_receipt=transport)
                require(receipt["fx_window_complete"] is True,"missing before/after ticks")
                pre=receipt["pre_0825_new_york"];post=receipt["post_0835_new_york"]
                require(pre["observed_at_utc"]<at.isoformat()<post["observed_at_utc"],
                        "pre/post observations must bracket original BLS second")
                # Avoid misleading hard-coded Oct 2 timestamp in legacy single-hour probe.
                receipt["release_at"]=at.isoformat()
                outcome.update(status="ACQUIRED_VALIDATED",receipt=receipt,error_type=None)
                break
            except Exception as exc:
                outcome["error_type"]=type(exc).__name__
        reports.append(outcome)
    successful=sum(r["status"]=="ACQUIRED_VALIDATED" for r in reports)
    return {"schema":"GMFQ_BLS_EIGHT_FX_BI5_EVENT_WINDOW_PROBE_V1",
       "attempted_events":8,"validated_source_hours":successful,
       "unavailable_hours":8-successful,"events":reports,
       "license_independently_certified":False,"causality_claimed":False,
       "complete_cross_asset_windows":0,"eligible_for_backtest":False,
       "safe_to_publish_new_D":False,"safe_to_update_pair_theses":False,
       "writes_live_data":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=20)
    p.add_argument("--attempts",type=int,default=2)
    x=p.parse_args()
    require(x.out.resolve().is_relative_to(Path("/tmp")),"temporary receipt only")
    p.error("Automated Dukascopy eight-event acquisition is disabled without independently verified prior written consent; synthetic in-memory tests are permitted")
    x.out.parent.mkdir(parents=True,exist_ok=True)
    x.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"attempted":8,"validated":result["validated_source_hours"],
      "unavailable":result["unavailable_hours"]}))
if __name__=="__main__":main()
