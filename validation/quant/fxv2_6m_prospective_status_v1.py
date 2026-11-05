#!/usr/bin/env python3
"""Read-only status of the preregistered V2 6M FX forward experiment.

Three distinct realities: source existence, prospectively frozen hypotheses,
and separately verified ECB reference outcomes. No backfilling or alpha claims.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.quant.fxv2_6m_prospective_trial_v1 import (
    FX_PATH, POLICY_PATH, JOURNAL, OUTCOMES,
    policy_ok, verified_journal, verified_outcomes, read_jsonl
)
from validation.quant.fxv2_rates_fx_temporal_readiness_v1 import (
    validate_fx, validate_macro, MACRO_PATH
)

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"site/fx-quant-v2/6m-prospective-status-v1.json"
SCHEMA="GMFQ_FXV2_6M_PROSPECTIVE_STATUS_READONLY_V1"
ROME=ZoneInfo("Europe/Rome")
CANDIDATES=("EUR/USD","EUR/CHF","USD/CHF")


def need(v,reason):
    if not v:
        raise ValueError("FXV2_PROSPECTIVE_STATUS_REJECTED: "+reason)


def build(policy,fx,macro,snaps,observed,now):
    need(isinstance(now,datetime) and now.tzinfo and now.utcoffset() is not None,
         "timezone-aware status clock required")
    policy_ok(policy)
    fx_dates=validate_fx(fx)
    names=validate_macro(macro)
    registered=policy.get("preregistration_date_utc")
    need(registered=="2026-11-05","research registration date changed")
    policy_sha=__import__("validation.quant.fxv2_6m_prospective_trial_v1",
                         fromlist=["seal"]).seal(policy)
    verified_journal(snaps,policy_sha)
    indexed={s["rome_day"]:s for s in snaps}
    verified_outcomes(observed,indexed)
    need([s["rome_day"] for s in snaps]==sorted(indexed),
         "append-only captures out of chronological order")
    current=now.astimezone(ROME).date()
    need(fx_dates[-1]<=current,"future dated ECB history")
    fx_map={d.isoformat():i for i,d in enumerate(fx_dates)}
    by_event={(r["snapshot_id"],r["pair"]):r for r in observed}
    per_pair={}
    all_eligible=[]
    pending=0
    matured_unobserved=0
    for pair in names:
        last=None
        statuses=Counter()
        frozen=0
        actual=0
        for snap in snaps:
            x=snap["pairs"][pair]
            status=x.get("status")
            need(isinstance(status,str) and
                 (status.startswith("ABSTAIN_") or status=="FROZEN_EXPERIMENTAL_DIRECTION"),
                 pair+" unrecognized frozen sample status")
            statuses[status]+=1
            last=status
            if status!="FROZEN_EXPERIMENTAL_DIRECTION":
                continue
            need(pair in CANDIDATES and x.get("experimental_rate_hypothesis_sign") in (-1,1)
                 and x.get("trade_signal") is None and x.get("expected_fx_return") is None,
                 pair+" illegal forecast promotion")
            frozen+=1
            key=(snap["rome_day"],pair)
            all_eligible.append(key)
            if key in by_event:
                actual+=1
            else:
                ix=fx_map.get(snap["rome_day"])
                # An unobserved target after 5 future ECB sessions is an
                # operational missing-outcome problem, not a pending forecast.
                if ix is not None and ix+5<len(fx_dates):
                    matured_unobserved+=1
                else:
                    pending+=1
        per_pair[pair]={
            "futures_6m_history_potentially_supported":pair in CANDIDATES,
            "frozen_capture_days":len(snaps),
            "last_capture_state":last or "NOT_YET_OBSERVED",
            "all_capture_state_counts":dict(sorted(statuses.items())),
            "frozen_experimental_directions":frozen,
            "matured_ecb_reference_outcomes":actual,
            "eligible_for_live_fx_signals":False
        }
    need(set(per_pair)==set(names),"all 28 pairs required")
    need(len(observed)+pending+matured_unobserved==len(all_eligible),
         "future reference count cannot reconcile against frozen hypotheses")
    for r in observed:
        s=indexed[r["snapshot_id"]]
        need(r["pair"] in s["pairs"] and
             s["pairs"][r["pair"]]["status"]=="FROZEN_EXPERIMENTAL_DIRECTION" and
             r["original_freeze_sha256"]==s["frozen_sha256"] and
             r["ecb_log_reference_return"] is not None and
             r["statistically_validated"] is False and
             r["no_inferred_policy_repricing"] is True and
             r["not_independent_across_pairs_or_overlapping_dates"] is True,
             "outcome not linked to its original sealed experimental direction")
        need(r["t0_fixing_date"]==s["rome_day"] and
             r["observed_at_utc"][:10]>=r["t5_fixing_date"] and
             fx_map.get(r["t0_fixing_date"]) is not None and
             fx_map.get(r["t5_fixing_date"])==
             fx_map[r["t0_fixing_date"]]+5,"nonmatured or inconsistent outcome")
    days=len({snap["rome_day"] for snap in snaps})
    weeks=((current-date.fromisoformat(snaps[0]["rome_day"])).days//7
           if snaps else 0)
    thresholds=policy["analysis_controls"]
    min_days=thresholds["minimum_distinct_capture_days_for_inferential_review"]
    min_weeks=thresholds["minimum_calendar_weeks_elapsed"]
    min_outcomes=thresholds["minimum_matured_pair_events_for_inferential_review"]
    review=(days>=min_days and weeks>=min_weeks and len(observed)>=min_outcomes
            and matured_unobserved==0)
    if not snaps:
        status=("PREREGISTERED_BEFORE_FIRST_ELIGIBLE_CAPTURE"
                if current<date.fromisoformat(policy["earliest_eligible_capture_rome"])
                else "AWAITING_FIRST_ACTUAL_EVENING_SNAPSHOT")
    elif matured_unobserved:
        status="MATURED_OUTCOMES_NOT_YET_RECORDED_ATTENTION"
    elif review:
        status="READY_FOR_INDEPENDENT_REVIEW_NOT_VALIDATED"
    else:
        status="PROSPECTIVE_COLLECTION_IN_PROGRESS_NOT_VALIDATED"
    return {
        "schema":SCHEMA,
        "as_of_rome_day":current.isoformat(),
        "report_status":status,
        "registration_date_utc":registered,
        "first_eligible_rome_date":policy["earliest_eligible_capture_rome"],
        "latest_observed_ecb_fixing":fx["last_as_of"],
        "reference_price_type":"ECB_REFERENCE_NOT_EXECUTABLE",
        "rate_instrument_type":"SECONDARY_LISTED_FUTURES_6M_NOT_OIS",
        "source_protocol":"validation/quant/FXV2_6M_PREREGISTERED_PROTOCOL_V1.json",
        "summary":{
            "pair_universe":28,
            "supported_rate_source_pair_universe":len(CANDIDATES),
            "unsupported_rate_source_pair_universe":25,
            "actual_prospective_capture_days":days,
            "frozen_28_pair_rows":days*28,
            "experimental_direction_observations":len(all_eligible),
            "outcomes_observed_after_5_future_fixings":len(observed),
            "frozen_directions_awaiting_maturity":pending,
            "matured_outcomes_not_recorded":matured_unobserved,
            "elapsed_full_weeks_since_first_capture":weeks,
            "min_distinct_days_for_review":min_days,
            "min_elapsed_weeks_for_review":min_weeks,
            "min_matured_events_for_review":min_outcomes
        },
        "pairs":per_pair,
        "pre_registered_hypothesis":"sign(delta base-minus-quote 6M listed-futures rate spread) vs 5-fixing momentum; next 5 ECB fixings",
        "no_live_fx_signals":True,
        "no_trades":True,
        "no_backfilled_decisions":True,
        "no_point_in_time_macro_validation_claimed":True,
        "no_independent_28_pair_sample_claim":True,
        "eligible_for_predictive_claim":False,
        "inference_review_threshold_reached":review,
        "predictive_skill_validated":False,
        "sharpe":None,
        "alpha":None
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUTPUT)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    policy=json.loads(POLICY_PATH.read_text())
    fx=json.loads(FX_PATH.read_text())
    macro=json.loads(MACRO_PATH.read_text())
    report=build(policy,fx,macro,read_jsonl(JOURNAL),read_jsonl(OUTCOMES),now)
    if args.check:
        need(args.output.exists() and json.loads(args.output.read_text())==report,
             "published report not equal to sealed prospective journals")
        print("FXV2_PROSPECTIVE_STATUS_PARITY_PASS",report["summary"])
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
        print("FXV2_PROSPECTIVE_STATUS_BUILT",report["report_status"],report["summary"])

if __name__=="__main__":
    main()
