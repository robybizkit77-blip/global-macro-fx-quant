#!/usr/bin/env python3
"""Observe matured ECB *reference returns* after genuine V2 shadow freezes.

This is NOT V2 predictive validation: the V2 candidate has no authorized
cross-currency FX score or trade side. It is an observational feature/price
panel that may enable prospective hypothesis tests after enough independent
calendar cutoffs exist. No costs, P&L, alpha or executable prices inferred.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.forward.capture_v2_research_prospective_evidence_v1 import (
    ROOT, JOURNAL as SNAPSHOTS, SCHEMA as SNAP_SCHEMA,
    sha, canonical, verify_journal
)
from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    SOURCE_URL, FX_PATH, source_map, cross, HORIZONS
)

OUTCOMES = ROOT / "validation/forward/reference_observations/V2_RESEARCH_ECB_REFERENCE_RETURNS_V1.jsonl"
SCHEMA = "GMFQ_V2_RESEARCH_ECB_REFERENCE_RETURNS_V1"
ROME = ZoneInfo("Europe/Rome")


def check(value, message):
    if not value:
        raise ValueError("V2_RESEARCH_REFERENCE_OBSERVER_REJECTED: " + message)


def read_jsonl(path):
    if not path.is_file():
        return []
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def verify_prior(items):
    keys=set()
    for item in items:
        check(item.get("schema")==SCHEMA
              and item.get("reference_return_sha256")==sha({
                  k:v for k,v in item.items() if k!="reference_return_sha256"
              }),"tampered prior reference outcome")
        key=(item.get("shadow_snapshot_id"),item.get("pair"),item.get("horizon"))
        check(key not in keys and item.get("trade_net_return") is None
              and item.get("beta_predictive_accuracy") is None
              and item.get("model_alpha_claim") is False,
              "duplicate or falsely promoted V2 reference result")
        keys.add(key)
    return keys


def compute(frozen, fx, now, prior=()):
    check(isinstance(now, datetime) and now.tzinfo is not None
          and now.utcoffset() is not None, "observer requires real aware time")
    check(isinstance(frozen,list) and isinstance(prior,(tuple,list)),
          "forward ledgers must be arrays")
    instant=now.astimezone(timezone.utc)
    local=instant.astimezone(ROME)
    historical=source_map(fx)
    verify_journal(frozen)
    prior_keys=verify_prior(prior)
    # Today's reference publication minute has no original-time archive
    # across the whole historical series. We admit a same-day fixing only
    # after local 19:00; earlier runs stop at yesterday.
    latest_allowed=local.date() if local.hour>=19 else local.date()-timedelta(days=1)
    seen=set()
    new=[]
    waits={"not_matured":0,"missing_reference_after_maturity":0,
           "source_gap":0,"already_recorded":0,"new":0}
    for snap in frozen:
        sid=snap["snapshot_id"]
        check(sid not in seen and snap["schema"]==SNAP_SCHEMA,"invalid/duplicate shadow")
        seen.add(sid)
        check(snap.get("future_outcomes_observed_at_capture") is False
              and snap.get("V2_pair_directional_predictions") is False
              and snap.get("eligible_for_real_trading_or_sizing") is False,
              "snapshot promoted into a trading claim")
        cutoff=datetime.fromisoformat(snap["capture_at_utc"].replace("Z","+00:00"))
        check(cutoff.utcoffset() is not None and cutoff <= instant,
              "unknown future or timezone-less decision cutoff")
        t0_day=cutoff.astimezone(ROME).date()
        check(snap["local_date_rome"]==t0_day.isoformat()
              and snap["official_ecb_t0_date"]==t0_day.isoformat(),
              "t0 original local date mismatch")
        source_row=historical.get(t0_day)
        check(source_row is not None and len(snap["observed_t0_ref"])==28,
              "original 28-pair ECB T0 unavailable")
        for pair, anchor in sorted(snap["observed_t0_ref"].items()):
            check(pair.count("/")==1 and anchor["date"]==t0_day.isoformat()
                  and anchor["source"]==FX_PATH.relative_to(ROOT).as_posix()
                  and anchor["trade_execution_price"] is False
                  and anchor["layer"]=="ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT",
                  "untrusted original reference price")
            a,b=pair.split("/")
            original=cross(source_row,a,b)
            check(original is not None and math.isclose(original,anchor["rate"],
                  abs_tol=1e-10,rel_tol=1e-9),
                  "historical t0 ECB fixing revised; quarantine before association")
            for horizon,duration in HORIZONS.items():
                key=(sid,pair,horizon)
                if key in prior_keys:
                    waits["already_recorded"]+=1
                    continue
                maturity=cutoff+timedelta(days=duration)
                if maturity>instant:
                    waits["not_matured"]+=1
                    continue
                target=maturity.astimezone(ROME).date()
                # Strictly AFTER the full calendar maturity day, matching
                # the original incumbent forward reference observer.
                later=[d for d in historical if target<d<=latest_allowed]
                if not later:
                    waits["missing_reference_after_maturity"]+=1
                    continue
                end_day=min(later)
                if (end_day-target).days>4:
                    waits["source_gap"]+=1
                    continue
                final=cross(historical[end_day],a,b)
                if final is None:
                    waits["source_gap"]+=1
                    continue
                record={
                    "schema":SCHEMA,
                    "shadow_snapshot_id":sid,
                    "origin_snapshot_sha256":snap["snapshot_sha256"],
                    "capture_at_utc":snap["capture_at_utc"],
                    "original_economic_asof":snap["economic_checked_as_of"],
                    "pair":pair,
                    "horizon":horizon,
                    "horizon_calendar_days":duration,
                    "t0_source_date":t0_day.isoformat(),
                    "t0_ECB_nonexecutable_rate":original,
                    "maturity_date":target.isoformat(),
                    "first_observed_ecb_date_strictly_after_maturity":end_day.isoformat(),
                    "days_after_maturity":(end_day-target).days,
                    "observed_ECB_nonexecutable_rate":final,
                    "observed_reference_return_pct":round(100*(final/original-1),8),
                    "reference_source":SOURCE_URL,
                    "reference_layer":"OFFICIAL_ECB_DAILY_REFERENCE_NOT_EXECUTION_PRICE",
                    "source_day_original_issuer_bytes_verifiable":False,
                    "trade_direction":None,
                    "trade_gross_return":None,
                    "trade_cost_bps":None,
                    "trade_net_return":None,
                    "trade_PnL":None,
                    "beta_predictive_accuracy":None,
                    "model_alpha_claim":False,
                    "beta_validation_certified":False,
                    "new_core_score_calculated":False,
                }
                record["reference_return_sha256"]=sha(record)
                new.append(record)
                waits["new"]+=1
    return {
        "schema":"GMFQ_V2_REFERENCE_OBSERVER_RECEIPT_V1",
        "status":"FEATURE_OUTCOME_ASSOCIATION_PANEL_ONLY_NO_PREDICTIVE_VALIDATION",
        "observed_at_utc":instant.isoformat().replace("+00:00","Z"),
        "source_last_observed_ecb_fixing":fx["last_as_of"],
        "frozen_snapshot_days":len(frozen),
        "new_matured_reference_rows":len(new),
        "horizons_checked":list(HORIZONS),
        "no_actual_PnL_or_beta_performance_claim":True,
        "no_new_schedules":True,
        "waiting":waits,
        "new_rows":new,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--receipt",required=True,type=Path)
    parser.add_argument("--append-journal",action="store_true")
    args=parser.parse_args()
    check(args.receipt.resolve().is_relative_to(Path("/tmp")),
          "read-only receipts only under /tmp")
    now=datetime.now(timezone.utc)
    source=json.loads(FX_PATH.read_text(encoding="utf-8"))
    result=compute(read_jsonl(SNAPSHOTS),source,now,read_jsonl(OUTCOMES))
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                             encoding="utf-8")
    if args.append_journal and result["new_rows"]:
        OUTCOMES.parent.mkdir(parents=True,exist_ok=True)
        with OUTCOMES.open("ab") as f:
            for row in result["new_rows"]:
                f.write(canonical(row))
    print(json.dumps({k:v for k,v in result.items() if k!="new_rows"},sort_keys=True))


if __name__=="__main__":
    main()
