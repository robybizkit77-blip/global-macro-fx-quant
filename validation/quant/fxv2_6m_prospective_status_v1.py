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
    policy_ok, verified_journal, verified_outcomes, read_jsonl, seal, CANDIDATES as TRIAL_CANDIDATES
)
from validation.quant.fxv2_rates_fx_temporal_readiness_v1 import (
    validate_fx, validate_macro, validate_quotes, utc_first_seen,
    MACRO_PATH, QUOTES_PATH
)

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"site/fx-quant-v2/6m-prospective-status-v1.json"
SCHEMA="GMFQ_FXV2_6M_PROSPECTIVE_STATUS_READONLY_V1"
ROME=ZoneInfo("Europe/Rome")
CANDIDATES=("EUR/USD","EUR/CHF","USD/CHF")


def need(v,reason):
    if not v:
        raise ValueError("FXV2_PROSPECTIVE_STATUS_REJECTED: "+reason)




def inspect_dated_6m_source(fx_dates, quote_rows, now):
    """Source audit only: never compute a forecast or fill missing futures.

    The newest quote's first-seen time is required to be <= actual inspection
    time. Two adjacent ECB sessions must contain exactly one identical
    listed contract per leg. This read-only audit can precede actual T0 and
    cannot create a prospective prediction.
    """
    if quote_rows is None:
        return {
            "available":False,
            "reason":"NO_FUTURES_SOURCE_INSPECTED",
            "currency_latest_market_date":{},
            "pair_recent_same_contract_source":{}
        }
    by_quote=validate_quotes(quote_rows)
    available={}
    for ccy in ("USD","EUR","CHF"):
        candidates=[
            row for (source_ccy,tenor,_),entries in by_quote.items()
            if source_ccy==ccy and tenor=="6m"
            for row in entries
            if utc_first_seen(row["first_seen_at_utc"],"source")<=now
        ]
        available[ccy]=max((r["observation_date"] for r in candidates),
                           default=None)
    pair_recent={}
    # The same 2-fixing-session lookback limit already registered in the
    # protocol, evaluated relative to latest ACTUALLY available ECB fixing.
    for pair in CANDIDATES:
        base,quote=pair.split("/")
        matched_date=None
        for lag in range(3):
            ix=len(fx_dates)-1-lag
            if ix<1:
                break
            pday,nday=fx_dates[ix-1],fx_dates[ix]
            consistent=True
            for ccy in (base,quote):
                older={r["contract"]:r for r in by_quote.get((ccy,"6m",pday),())}
                newer={r["contract"]:r for r in by_quote.get((ccy,"6m",nday),())}
                common=older.keys() & newer.keys()
                if len(common)!=1:
                    consistent=False
                    break
                contract=next(iter(common))
                if max(
                    utc_first_seen(older[contract]["first_seen_at_utc"],"old"),
                    utc_first_seen(newer[contract]["first_seen_at_utc"],"new")
                )>now:
                    consistent=False
                    break
            if consistent:
                matched_date=nday.isoformat()
                break
        pair_recent[pair]={
            "has_recent_matched_same_contract_6m_quote_change":
                matched_date is not None,
            "last_eligible_source_market_day":matched_date,
            "not_a_frozen_hypothesis":True,
            "not_an_OIS_repricing_signal":True
        }
    return {
        "available":True,
        "source_as_of_last_available_ecb_fixing":fx_dates[-1].isoformat(),
        "currency_latest_market_date":available,
        "pair_recent_same_contract_source":pair_recent,
        "no_forecast_generated":True,
        "no_automatic_core_effect":True
    }

def build(policy,fx,macro,snaps,observed,now,quote_rows=None):
    need(isinstance(now,datetime) and now.tzinfo and now.utcoffset() is not None,
         "timezone-aware status clock required")
    policy_ok(policy)
    fx_dates=validate_fx(fx)
    names=validate_macro(macro)
    registered=policy.get("preregistration_date_utc")
    need(registered=="2026-11-05","research registration date changed")
    policy_sha=seal(policy)
    verified_journal(snaps,policy_sha)
    indexed={s["rome_day"]:s for s in snaps}
    verified_outcomes(observed,indexed)
    need([s["rome_day"] for s in snaps]==sorted(indexed),
         "append-only captures out of chronological order")
    local=now.astimezone(ROME)
    current=local.date()
    need(fx_dates[-1]<=current,"future dated ECB history")
    preflight=inspect_dated_6m_source(fx_dates,quote_rows,
                                       now.astimezone(timezone.utc))
    scheduled_evening_reached=(current>=date.fromisoformat(
        policy["earliest_eligible_capture_rome"])
        and local.weekday()<5 and (local.hour,local.minute)>=(20,45))
    same_day_ecb_available=(fx_dates[-1].isoformat()==current.isoformat())
    todays_capture_exists=current.isoformat() in indexed
    capture_attention=scheduled_evening_reached and not todays_capture_exists
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
    if capture_attention:
        status=("CAPTURE_MISSED_WITH_SAME_DAY_ECB_AVAILABLE_ATTENTION"
                if same_day_ecb_available else
                "CAPTURE_BLOCKED_MISSING_SAME_DAY_ECB_FIXING_ATTENTION")
    elif not snaps:
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
        "input_readiness":{
            "capture_gate_local_time":"20:45 Europe/Rome",
            "capture_gate_reached_for_rome_business_day":scheduled_evening_reached,
            "official_ecb_t0_available_for_rome_day":same_day_ecb_available,
            "prospective_capture_already_frozen_for_rome_day":todays_capture_exists,
            "capture_due_but_missing":capture_attention,
            "last_valid_6m_source_audit":preflight,
            "preflight_is_not_an_experimental_prediction":True
        },
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
    report=build(policy,fx,macro,read_jsonl(JOURNAL),read_jsonl(OUTCOMES),
                 now,read_jsonl(QUOTES_PATH))
    if args.check:
        need(args.output.exists() and json.loads(args.output.read_text())==report,
             "published report not equal to sealed prospective journals")
        print("FXV2_PROSPECTIVE_STATUS_PARITY_PASS",report["summary"])
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
        print("FXV2_PROSPECTIVE_STATUS_BUILT",report["report_status"],report["summary"])
        if report["input_readiness"]["capture_due_but_missing"]:
            print("::warning::FXV2_6M_PROSPECTIVE_CAPTURE_BLOCKED "+
                  report["report_status"]+"; BCE as-of="+
                  report["latest_observed_ecb_fixing"]+
                  "; no fabricated or backfilled experiment observation")

if __name__=="__main__":
    main()
