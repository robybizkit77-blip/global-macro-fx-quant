#!/usr/bin/env python3
"""V2 Forward research cohort-quality audit: 28 pairs are NOT 28 independent trials.

Read ONLY immutable contemporaneous V2 shadows and later non-tradable ECB
reference comparisons; no trading signal, performance estimate, OOS success
claim, weight search, historical backfill, or scheduled job. The unit of
observation for chronology is a captured Rome DATE. Multiple FX crosses on
that day share the same seven EUR-base reference rates and overlapping G8
drivers, so pair-row counts cannot be used as statistical sample size.
A day cluster is not guaranteed statistically independent of other days,
either. Report that caveat explicitly and do not calculate naive p-values.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import itertools
import json
import math

from validation.forward.capture_v2_research_prospective_evidence_v1 import (
    JOURNAL, SCHEMA as FREEZE_SCHEMA, G8, sha, verify_journal
)
from validation.forward.observe_v2_research_ecb_reference_returns_v1 import (
    OUTCOMES, SCHEMA as RETURN_SCHEMA, read_jsonl, verify_prior, HORIZONS, SOURCE_URL
)

ROME = ZoneInfo("Europe/Rome")
SCHEMA = "GMFQ_V2_PROSPECTIVE_FX_COHORT_DEPENDENCE_AUDIT_V1"
EXPECTED_UNORDERED = {
    frozenset((a,b)) for a,b in itertools.combinations(G8,2)
}
REFERENCE_LAYER = "OFFICIAL_ECB_DAILY_REFERENCE_NOT_EXECUTION_PRICE"


def require(ok, message):
    if not ok:
        raise ValueError("V2_COHORT_INDEPENDENCE_AUDIT_REJECTED: "+message)


def positive(v):
    return type(v) in (float,int) and math.isfinite(v) and v>0


def stamp(raw):
    require(isinstance(raw,str), "missing frozen capture instant")
    try:
        value=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid frozen capture instant") from exc
    require(value.tzinfo is not None and value.utcoffset() is not None,
            "frozen capture must have explicit timezone")
    return value.astimezone(timezone.utc)


def inspect(frozen, outcomes, now):
    require(isinstance(now,datetime) and now.tzinfo is not None
            and now.utcoffset() is not None, "actual aware inspection clock")
    require(isinstance(frozen,list) and isinstance(outcomes,list),
            "expected complete immutable journal arrays")
    utc=now.astimezone(timezone.utc)
    local=utc.astimezone(ROME)
    # The ECB release instant is not independently attested in this archive.
    # A current-day EOD reference is eligible for this audit only after 19:00.
    latest_allowed=local.date() if local.hour>=19 else local.date()-timedelta(days=1)
    verify_journal(frozen)
    verify_prior(outcomes)
    snapshots={}
    for item in frozen:
        sid=item.get("snapshot_id")
        require(isinstance(sid,str) and len(sid)==64 and sid not in snapshots,
                "duplicate or missing frozen snapshot identity")
        cutoff=stamp(item.get("capture_at_utc"))
        require(cutoff<=utc, "future frozen snapshot cannot be counted")
        d=cutoff.astimezone(ROME).date().isoformat()
        require(d==item.get("local_date_rome")==item.get("official_ecb_t0_date")
                and item.get("schema")==FREEZE_SCHEMA
                and item.get("future_outcomes_observed_at_capture") is False
                and item.get("V2_pair_directional_predictions") is False
                and item.get("core_D_recalculated") is False,
                "incorrect research-only original-day snapshot provenance")
        anchors=item.get("observed_t0_ref")
        domestic=item.get("domestic_v2_features")
        require(isinstance(anchors,dict) and len(anchors)==28
                and isinstance(domestic,dict) and set(domestic)==set(G8),
                "all 8 evidence legs and all 28 T0 pairs must be retained")
        orientations=[]
        for pair, anchor in anchors.items():
            require(isinstance(pair,str) and pair.count("/")==1,
                    "malformed pair orientation")
            a,b=pair.split("/")
            require(a in G8 and b in G8 and a!=b
                    and isinstance(anchor,dict)
                    and anchor.get("date")==d
                    and anchor.get("layer")=="ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT"
                    and anchor.get("trade_execution_price") is False
                    and positive(anchor.get("rate")),
                    "an original ECB T0 anchor is missing/invalid")
            orientations.append(frozenset((a,b)))
        require(len(set(orientations))==28
                and set(orientations)==EXPECTED_UNORDERED,
                "28 correlated original currency crosses required, no missing losers")
        for ccy, feat in domestic.items():
            require(feat.get("FX_signal") is None
                    and feat.get("trade_entry") is None
                    and feat.get("cb_CAN_not_calibrated") is True,
                    ccy+" V2 no-score/nontrading condition violated")
        snapshots[sid]=(item,cutoff)
    result_rows={}
    for item in outcomes:
        sid=item.get("shadow_snapshot_id")
        require(sid in snapshots, "orphan V2 return without first-live frozen features")
        snap,cutoff=snapshots[sid]
        pair=item.get("pair")
        horizon=item.get("horizon")
        require(pair in snap["observed_t0_ref"] and horizon in HORIZONS,
                "unknown outcome pair or horizon")
        require(item.get("schema")==RETURN_SCHEMA
                and item.get("origin_snapshot_sha256")==snap["snapshot_sha256"]
                and item.get("capture_at_utc")==snap["capture_at_utc"]
                and item.get("original_economic_asof")==snap.get("economic_checked_as_of")
                and item.get("t0_source_date")==snap["local_date_rome"]
                and item.get("reference_source")==SOURCE_URL
                and item.get("reference_layer")==REFERENCE_LAYER
                and item.get("source_day_original_issuer_bytes_verifiable") is False,
                "outcome source chain is not original frozen feature chain")
        t0=snap["observed_t0_ref"][pair]["rate"]
        end=item.get("observed_ECB_nonexecutable_rate")
        require(positive(end) and positive(item.get("t0_ECB_nonexecutable_rate"))
                and math.isclose(item["t0_ECB_nonexecutable_rate"],t0,
                                 rel_tol=1e-9,abs_tol=1e-10),
                "outcome T0 must equal its immutable original reference")
        due=cutoff+timedelta(days=HORIZONS[horizon])
        due_day=due.astimezone(ROME).date()
        observed=item.get("first_observed_ecb_date_strictly_after_maturity")
        try:
            observed_day=datetime.strptime(observed,"%Y-%m-%d").date()
        except (TypeError,ValueError) as exc:
            raise ValueError("invalid observed ECB outcome civil date") from exc
        gap=(observed_day-due_day).days
        require(item.get("horizon_calendar_days")==HORIZONS[horizon]
                and item.get("maturity_date")==due_day.isoformat()
                and 0<gap<=4 and item.get("days_after_maturity")==gap
                and due<=utc and observed_day<=latest_allowed,
                "future/out-of-window/misaligned ECB reference outcome")
        expected=round(100*(end/t0-1),8)
        require(type(item.get("observed_reference_return_pct")) in (int,float)
                and math.isclose(item["observed_reference_return_pct"],expected,
                                 abs_tol=1e-8,rel_tol=0),
                "return arithmetic disagrees with original ECB ratio")
        require(item.get("trade_direction") is None
                and item.get("trade_gross_return") is None
                and item.get("trade_cost_bps") is None
                and item.get("trade_net_return") is None
                and item.get("trade_PnL") is None
                and item.get("beta_predictive_accuracy") is None
                and item.get("model_alpha_claim") is False
                and item.get("beta_validation_certified") is False
                and item.get("new_core_score_calculated") is False,
                "reference-only result must not become a trading outcome")
        key=(sid,pair,horizon)
        require(key not in result_rows, "duplicate pair/horizon outcome")
        result_rows[key]=item
    horizon_report={}
    for horizon,days in HORIZONS.items():
        mature=[sid for sid,(_,cutoff) in snapshots.items()
                if cutoff+timedelta(days=days)<=utc]
        counts={sid:sum((sid,p,horizon) in result_rows
                         for p in snapshots[sid][0]["observed_t0_ref"]) for sid in mature}
        eligible=28*len(mature)
        observed=sum(counts.values())
        horizon_report[horizon]={
            "horizon_calendar_days":days,
            "capture_date_clusters_with_elapsed_horizon":len(mature),
            "possible_reference_pair_rows_at_matured_dates":eligible,
            "recorded_reference_pair_rows":observed,
            "not_observed_yet_pair_rows":eligible-observed,
            "complete_28_cross_capture_dates":sum(x==28 for x in counts.values()),
            "partial_capture_dates":sum(0<x<28 for x in counts.values()),
            "no_observed_return_capture_dates":sum(x==0 for x in counts.values()),
            "observed_capture_date_clusters":sum(x>0 for x in counts.values()),
            "28_pairs_are_statistically_independent":False,
            "capture_days_are_not_guaranteed_serially_independent":True,
            "statistical_predictive_skill_certified":False,
        }
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_COHORT_COVERAGE_ONLY_PREDICTIVE_SKILL_NOT_EVALUABLE",
        "as_of_utc":utc.isoformat().replace("+00:00","Z"),
        "total_frozen_capture_date_clusters":len(snapshots),
        "total_G8_currency_dimensions":8,
        "number_of_independent_EUR_base_FX_quote_levels_per_date_at_most":7,
        "canonical_28_pair_crosses_per_snapshot":28,
        "total_reference_outcome_rows":len(result_rows),
        "per_horizon":horizon_report,
        "source_survivorship_audit_includes_missing_unobserved_rows":True,
        "no_cross_pair_independence_assumption":True,
        "no_multiple_horizon_winner_selection":True,
        "no_naive_pair_level_p_values":True,
        "true_historical_PIT_backtest_certified":False,
        "real_FX_positioning_or_PnL_certified":False,
        "new_candidate_predictive_accuracy_or_alpha_claimed":False,
        "allowed_to_promote_D_or_28_pairs":False,
        "writes_live_data":False,
    }


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--receipt",required=True,type=Path)
    a=cli.parse_args()
    require(a.receipt.resolve().is_relative_to(Path("/tmp")),
            "audit receipt must be /tmp only")
    now=datetime.now(timezone.utc)
    r=inspect(read_jsonl(JOURNAL),read_jsonl(OUTCOMES),now)
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",
                         encoding="utf-8")
    print(json.dumps({
        "status":r["status"],"capture_date_clusters":r["total_frozen_capture_date_clusters"],
        "observed_reference_pair_rows":r["total_reference_outcome_rows"],
        "predictive_skill_certified":False,
        "per_horizon":{h:{"matured_date_clusters":v["capture_date_clusters_with_elapsed_horizon"],
                           "observed_pair_rows":v["recorded_reference_pair_rows"],
                           "missing_pair_rows":v["not_observed_yet_pair_rows"]}
                       for h,v in r["per_horizon"].items()}
    },sort_keys=True))


if __name__=="__main__":
    main()
