#!/usr/bin/env python3
"""Settle frozen G8 forecasts against later *first seen in FX Quant* values.

No revised/latest series is substituted for the earliest post-capture snapshot.
Outputs are create-only research receipts. This is NOT issuer first-release PIT.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.capture_g8_prospective_v1 import (
    ROOT, DIRECTORY, FX, github_json
)

OUTCOMES="research/g8-growth-prospective/outcomes"
SCHEMA="GMFQ_G8_GROWTH_FIRST_SEEN_OUTCOME_V1"


def valid_receipt(r: dict) -> bool:
    try:
        return (r["schema"]=="GMFQ_G8_GROWTH_PROSPECTIVE_CAPTURE_V1"
                and r["issuer_release_vintage_verified"] is False
                and r["affects_fx_rankings_or_signals"] is False
                and isinstance(r["captured_at_utc"],str)
                and r["captured_at_utc"].endswith("Z")
                and set(r["selected_macro_vintage"])==set(FX)
                and set(r["forecast_evidence"]["currencies"])==set(FX))
    except (KeyError,TypeError,AttributeError):
        return False


def observation(receipt:dict,ccy:str,period:str):
    meta=receipt["selected_macro_vintage"][ccy]
    return next((r["value"] for r in meta["observations"] if r["period"]==period),None)


def score_pair(issue: dict, seen: dict, ccy: str) -> dict | None:
    if not valid_receipt(issue) or not valid_receipt(seen):
        return None
    if not issue["captured_at_utc"] < seen["captured_at_utc"]:
        return None
    prediction=issue["forecast_evidence"]["currencies"][ccy]
    if prediction.get("candidate") is not True or not isinstance(prediction.get("forecast"),dict):
        return None
    target=prediction.get("nextObservationPeriod")
    prev=issue["selected_macro_vintage"][ccy]["latest_observation_period"]
    if not isinstance(target,str) or target<=prev:
        return None
    if observation(issue,ccy,target) is not None:
        return None
    actual_target=observation(seen,ccy,target)
    later_prev=observation(seen,ccy,prev)
    original_prev=observation(issue,ccy,prev)
    if any(not isinstance(x,(int,float)) or isinstance(x,bool)
           for x in (actual_target,later_prev,original_prev)):
        return None
    f=prediction["forecast"].get("nextChange")
    if not isinstance(f,(int,float)) or isinstance(f,bool):
        return None
    if prediction["forecast"].get("unit")=="punti percentuali":
        actual=actual_target-later_prev
        revision_of_baseline=later_prev-original_prev
    elif prediction["forecast"].get("unit")=="%":
        if later_prev==0 or original_prev==0:
            return None
        actual=(actual_target/later_prev-1)*100
        revision_of_baseline=(later_prev/original_prev-1)*100
    else:
        return None
    if not all(__import__("math").isfinite(x) for x in (actual,f,revision_of_baseline)):
        return None
    return {
        "schema":SCHEMA,
        "currency":ccy,
        "series_id":issue["selected_macro_vintage"][ccy]["series_id"],
        "target_observation_period":target,
        "forecast_created_at_utc":issue["captured_at_utc"],
        "first_seen_in_fx_quant_at_utc":seen["captured_at_utc"],
        "forecast_source_commit":issue["source_main_commit"],
        "first_seen_source_commit":seen["source_main_commit"],
        "forecast_source_sha256":issue["source_macro_sha256"],
        "first_seen_source_sha256":seen["source_macro_sha256"],
        "model_sha256":issue["source_model_sha256"],
        "forecast_change":f,
        "observed_change_first_seen":actual,
        "unit":prediction["forecast"]["unit"],
        "baseline_zero_change":0,
        "model_absolute_error":abs(f-actual),
        "baseline_absolute_error":abs(actual),
        "correct_direction":(1 if f*actual>0 else 0 if f*actual<0 else None),
        "prior_baseline_value_at_forecast":original_prev,
        "prior_baseline_value_at_first_seen":later_prev,
        "baseline_revision_during_window":revision_of_baseline,
        "first_seen_target_value":actual_target,
        "status":"FIRST_SEEN_AFTER_FROZEN_FORECAST",
        "issuer_first_release_verified":False,
        "historical_pit_certified":False,
        "fx_signal_generated":False,
        "note":"Evaluates an earlier immutable model output using the earliest subsequent FX Quant snapshot with the target observation; not proof that the issuer had not already published it before the forecast."
    }


def evaluate(receipts: list[dict]) -> list[dict]:
    snapshots=sorted((x for x in receipts if valid_receipt(x)),
                     key=lambda x:x["captured_at_utc"])
    candidates=[]
    for ccy in FX:
        pairs_seen=set()
        for i,issue in enumerate(snapshots):
            f=issue["forecast_evidence"]["currencies"][ccy]
            if f.get("candidate") is not True or not f.get("forecast"):
                continue
            target=f.get("nextObservationPeriod")
            if not target or (ccy,target) in pairs_seen:
                continue
            # First valid forecast for a target is frozen; never cherry-pick
            # an improved model output from a later forecast date.
            pairs_seen.add((ccy,target))
            for seen in snapshots[i+1:]:
                if observation(seen,ccy,target) is None:
                    continue
                outcome=score_pair(issue,seen,ccy)
                if outcome:
                    candidates.append(outcome)
                break
    return sorted(candidates,key=lambda o:(o["currency"],o["target_observation_period"]))


def read_git_receipts(root:Path,revision:str)->tuple[str,list[dict]]:
    commit=subprocess.check_output(["git","rev-parse",revision+"^{commit}"],
                                   cwd=root,text=True).strip()
    paths=subprocess.check_output(
        ["git","ls-tree","-r","--name-only",commit,"--",DIRECTORY],
        cwd=root,text=True).splitlines()
    seen={}
    for path in paths:
        if not path.endswith(".json") or not path.startswith(DIRECTORY+"/"):
            continue
        raw=subprocess.check_output(["git","show",f"{commit}:{path}"],cwd=root)
        val=json.loads(raw)
        if not valid_receipt(val):
            raise ValueError("Malformed frozen G8 research entry: "+path)
        day=val["capture_rome_date"]
        if day in seen:
            raise ValueError("Duplicate research capture day "+day)
        if path!=f"{DIRECTORY}/{day}.json":
            raise ValueError("Capture filename and frozen Rome day disagree: "+path)
        seen[day]=val
    return commit,list(seen.values())


def publish_outcome(ou:dict,token:str,repo:str)->dict:
    if ou.get("schema")!=SCHEMA or ou.get("issuer_first_release_verified") is not False:
        raise ValueError("Cannot promote an unqualified settlement")
    ccy=ou["currency"]
    period=ou["target_observation_period"]
    if ccy not in FX or not isinstance(period,str) or len(period)!=7 or period[4]!="-":
        raise ValueError("Invalid target path")
    relative=f"{OUTCOMES}/{ccy}-{period}.json"
    url=f"https://api.github.com/repos/{repo}/contents/{relative}"
    status,item=github_json("GET",url,token)
    if status==200:
        return {"status":"ALREADY_SETTLED_IMMUTABLE","path":relative,"wrote":False}
    if status!=404:
        raise RuntimeError(f"Failed outcome existence guard: {status}")
    raw=json.dumps(ou,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    for attempt in range(3):
        status,item=github_json("PUT",url,token,{
            "message":f"Freeze G8 first-seen forecast outcome {ccy} {period} [skip ci]",
            "content":base64.b64encode(raw.encode("utf-8")).decode("ascii"),
            "branch":"main"})
        if status in (200,201):
            return {"status":"CREATED_IMMUTABLE","path":relative,"wrote":True}
        if status not in (409,422):
            raise RuntimeError(f"Outcome immutable append failed: {status}")
        status,item=github_json("GET",url,token)
        if status==200:
            return {"status":"ALREADY_SETTLED_IMMUTABLE","path":relative,"wrote":False}
        if status!=404:
            raise RuntimeError(f"Unsafe settlement retry GET {status}")
        __import__("time").sleep(1+attempt)
    raise RuntimeError("Repeated settlement write conflict")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--revision",default="origin/main")
    ap.add_argument("--output",required=True)
    ap.add_argument("--publish",action="store_true")
    a=ap.parse_args()
    commit,snapshots=read_git_receipts(ROOT,a.revision)
    outcomes=evaluate(snapshots)
    result={"schema":"GMFQ_G8_FIRST_SEEN_SCORE_AUDIT_V1",
            "evaluated_at_utc":datetime.now(timezone.utc).isoformat(),
            "snapshot_repository_commit":commit,
            "frozen_capture_count":len(snapshots),
            "realized_count":len(outcomes),
            "outcomes":outcomes,
            "official_release_pit_validation":False,
            "fx_signal_generated":False}
    output=Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("G8_FIRST_SEEN_OUTCOME_AUDIT captures=",len(snapshots),"outcomes=",len(outcomes))
    if a.publish:
        if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_REPOSITORY"):
            raise ValueError("GitHub token/repository required for settlement")
        published=[publish_outcome(o,os.environ["GITHUB_TOKEN"],os.environ["GITHUB_REPOSITORY"])
                   for o in outcomes]
        print("G8_FIRST_SEEN_OUTCOME_PUBLISH",json.dumps(published))
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
                f.write("\n### First-seen G8 shadow forecast outcomes\n")
                f.write("- Frozen captures inspected: "+str(len(snapshots))+"\n")
                f.write("- Realized target periods: "+str(len(outcomes))+"\n")
                f.write("- **Issuer first-release PIT remains unverified; no FX signal.**\n")


if __name__=="__main__":
    main()
