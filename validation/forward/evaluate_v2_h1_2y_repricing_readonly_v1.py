#!/usr/bin/env python3
"""Preregistered V2 H1 sovereign-2Y repricing versus FX momentum.

READ-ONLY evaluation of the existing prospective V2 snapshot and ECB outcome
journals. Outputs /tmp receipts, never a trade, refreshed Core or prediction.
Do not score any snapshot captured before the H1 protocol reached main.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
import statistics
from zoneinfo import ZoneInfo

from validation.forward import audit_v2_prospective_cohort_independence_v1 as audit
from validation.forward import capture_v2_research_prospective_evidence_v1 as cap
from validation.forward import observe_v2_research_ecb_reference_returns_v1 as obs

ROME = ZoneInfo("Europe/Rome")
PROTOCOL_ID = "V2-H1-2Y-REPRICING-1W-V1"
PROTOCOL_MERGE = "b9f28a130c069616af849156c6f5d14566220d4b"
# The PR #766 protocol merged at 2026-10-28T22:43:56Z.
REGISTERED_AT = datetime(2026, 10, 28, 22, 43, 56, tzinfo=timezone.utc)
PRIMARY_HORIZON = "1W"
MIN_DATES = 120
REASONS = ("missing_prior_T0", "missing_rate", "stale_rate",
           "unchanged_bond_date", "noncomparable_source", "zero_signal",
           "not_matured", "missing_future_fixing", "evaluated")


def require(ok, why):
    if not ok:
        raise ValueError("V2_H1_READONLY_REJECTED: " + why)


def parse_utc(value):
    require(isinstance(value, str), "missing UTC timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("bad timestamp") from exc
    require(result.tzinfo is not None and result.utcoffset() is not None,
            "timezone-less timestamp")
    return result.astimezone(timezone.utc)


def prev_business_day(day):
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def business_age(day, source):
    """Conservative weekday count; no speculative country holiday calendars."""
    require(source <= day, "future bond date")
    n = 0
    d = source
    while d < day:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def sign(value):
    return (value > 0) - (value < 0)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def source_pair(now_snap, before_snap, ccy):
    now = now_snap["domestic_v2_features"].get(ccy)
    before = before_snap["domestic_v2_features"].get(ccy)
    if not isinstance(now, dict) or not isinstance(before, dict):
        return "missing_rate", None
    values = (now.get("two_year_observed_yield_pct"),
              before.get("two_year_observed_yield_pct"))
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        return "missing_rate", None
    dates = []
    for snap, leg in ((now_snap, now), (before_snap, before)):
        try:
            bond = date.fromisoformat(leg["bond_date"])
        except (KeyError, TypeError, ValueError):
            return "missing_rate", None
        day = date.fromisoformat(snap["local_date_rome"])
        if bond > day:
            # Reject an impossible PIT feature, not merely omit the pair.
            raise ValueError("V2_H1_READONLY_REJECTED: future dated 2Y "+ccy)
        if business_age(day, bond) > 2:
            return "stale_rate", None
        dates.append(bond)
    if dates[0] <= dates[1]:
        return "unchanged_bond_date", None
    ids = (now.get("two_year_instrument_identity"),
           before.get("two_year_instrument_identity"))
    if not all(isinstance(x, str) and len(x.strip()) > 12 for x in ids):
        return "noncomparable_source", None
    if ids[0] != ids[1]:
        return "noncomparable_source", None
    return None, values[0] - values[1]


def confidence_interval_by_block(daily, block=10, seed=11029, repeats=500):
    """Only after enough dates, preserves short-run serial dependence."""
    require(len(daily) >= MIN_DATES, "bootstrap on insufficient dates")
    require(block in (10, 20), "unregistered block length")
    rng = random.Random(seed + block)
    length = len(daily)
    candidates = [daily[i:i + block] for i in range(length - block + 1)]
    means = []
    for _ in range(repeats):
        draws = []
        while len(draws) < length:
            draws.extend(candidates[rng.randrange(len(candidates))])
        means.append(statistics.mean(draws[:length]))
    means.sort()
    return [means[int((repeats - 1) * .025)],
            means[int((repeats - 1) * .975)]]


def inspect(frozen, outcomes, now):
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() is not None, "aware real evaluation instant")
    now = now.astimezone(timezone.utc)
    # Reuse the existing complete integrity and source/clock checks.
    cohort = audit.inspect(frozen, outcomes, now)
    by_day = {date.fromisoformat(x["local_date_rome"]): x for x in frozen}
    by_id = {(r["shadow_snapshot_id"], r["pair"], r["horizon"]): r
             for r in outcomes}
    diagnostics = Counter({reason: 0 for reason in REASONS})
    paired = []
    rows = []
    valid_date_pairs = 0
    eligible = [x for x in frozen if parse_utc(x["capture_at_utc"]) > REGISTERED_AT]
    eligible.sort(key=lambda x: x["local_date_rome"])
    for snap in eligible:
        day = date.fromisoformat(snap["local_date_rome"])
        previous = by_day.get(prev_business_day(day))
        daily = []
        day_detail = Counter()
        due = parse_utc(snap["capture_at_utc"]) + timedelta(days=7)
        for pair in sorted(snap["observed_t0_ref"]):
            reason = None
            if previous is None or pair not in previous["observed_t0_ref"]:
                reason = "missing_prior_T0"
            else:
                base, quote = pair.split("/")
                a_reason, a_move = source_pair(snap, previous, base)
                b_reason, b_move = source_pair(snap, previous, quote)
                reason = a_reason or b_reason
                if reason is None:
                    x = 100 * (a_move - b_move)
                    p = snap["observed_t0_ref"][pair]["rate"]
                    prev_p = previous["observed_t0_ref"][pair]["rate"]
                    require(positive(p) and positive(prev_p),
                            "invalid frozen T0 price")
                    momentum = math.log(p / prev_p)
                    if x == 0 or momentum == 0:
                        reason = "zero_signal"
                    elif due > now:
                        reason = "not_matured"
                    else:
                        outcome = by_id.get((snap["snapshot_id"], pair,
                                             PRIMARY_HORIZON))
                        if outcome is None:
                            reason = "missing_future_fixing"
                        else:
                            future = outcome["observed_ECB_nonexecutable_rate"]
                            require(positive(future), "invalid future fixing")
                            forward = math.log(future / p)
                            if forward == 0:
                                reason = "zero_signal"
                            else:
                                relative_accuracy = (
                                    int(sign(x) == sign(forward)) -
                                    int(sign(momentum) == sign(forward))
                                )
                                daily.append(relative_accuracy)
                                reason = "evaluated"
            diagnostics[reason] += 1
            day_detail[reason] += 1
        if daily:
            valid_date_pairs += 1
            paired.append(statistics.mean(daily))
        rows.append({
            "capture_date": day.isoformat(),
            "horizon_matured": due <= now,
            "possible_pairs": 28,
            "evaluated_pairs": len(daily),
            "unscored_by_reason": {r: day_detail.get(r, 0)
                                  for r in REASONS if r != "evaluated"},
            # A date is one cluster; 28 crosses are not independent.
            "paired_accuracy_difference_for_date": (
                statistics.mean(daily) if daily else None),
        })
    n_days = len(paired)
    formal = n_days >= MIN_DATES
    return {
        "protocol": PROTOCOL_ID,
        "preregistration_merge_commit": PROTOCOL_MERGE,
        "registration_cutoff_utc": REGISTERED_AT.isoformat(),
        "status": ("RESEARCH_DESCRIPTIVE_120_DATES_NOT_PREDICTIVE_VALIDATION"
                   if formal else "INSUFFICIENT_VALID_PIT_COHORT"),
        "reference_only_not_trade_pnl": True,
        "horizon": PRIMARY_HORIZON,
        "frozen_dates_all": len(frozen),
        "eligible_H1_capture_dates": len(eligible),
        "possible_H1_pairs": len(eligible)*28,
        "paired_evaluable_dates": valid_date_pairs,
        "evaluated_pair_rows_correlated": diagnostics["evaluated"],
        "reason_counts": dict(diagnostics),
        "daily_date_clusters": rows,
        "mean_paired_accuracy_difference_descriptive": (
            statistics.mean(paired) if paired else None),
        "block_confidence_intervals_95": (
            {"10_days": confidence_interval_by_block(paired, 10),
             "20_days": confidence_interval_by_block(paired, 20)}
            if formal else None),
        "minimum_formal_dates": MIN_DATES,
        "no_naive_pair_level_inference": True,
        "not_a_v2_signal_or_predictive_validation": True,
        "writes_live_data": False,
        "v2_observed_reference_rows_all_horizons": cohort["total_reference_outcome_rows"]
    }



def operational_2y_readiness(live_rates, now):
    """Current-source diagnostic ONLY; not a historical H1 signal or T0.

    Publication date, not a static quality string, controls freshness.
    Weekdays are a conservative proxy, not a verified local holiday calendar.
    Source identity alone cannot prove two consecutive frozen observations.
    """
    require(isinstance(live_rates, dict), "missing operational Rates map")
    require(now.tzinfo is not None and now.utcoffset() is not None,
            "operational readiness needs aware date")
    day = now.astimezone(ROME).date()
    countries = {}
    fresh = []
    def finite_yield(v):
        return type(v) in (int, float) and math.isfinite(v)
    for ccy in cap.G8:
        row = live_rates.get(ccy)
        state = "MISSING_RATE"
        age = None
        stamp = None
        instrument_id = None
        value = None
        if isinstance(row, dict):
            stamp = row.get("date")
            value = row.get("2Y")
            if isinstance(stamp, str):
                try:
                    source_day = date.fromisoformat(stamp)
                except ValueError:
                    source_day = None
            else:
                source_day = None
            if source_day is not None and finite_yield(value):
                if source_day > day:
                    state = "FUTURE_SOURCE_REJECTED"
                else:
                    age = business_age(day, source_day)
                    instrument_id = cap.two_year_instrument_identity(
                        live_rates, ccy, value)
                    if age > 2:
                        state = "STALE_FOR_H1"
                    elif not instrument_id:
                        state = "MISSING_COMPARABLE_2Y_IDENTITY"
                    else:
                        state = "POTENTIALLY_FRESH_NOT_YET_H1_ELIGIBLE"
                        fresh.append(ccy)
        countries[ccy] = {
            "source_date": stamp,
            "source_age_weekdays": age,
            "two_year_yield_pct": value if finite_yield(value) else None,
            "source_quality_label_untrusted_for_freshness": (
                row.get("quality") if isinstance(row, dict) else None),
            "state": state,
            "instrument_metadata_available": instrument_id is not None,
        }
    return {
        "as_of_rome_date": day.isoformat(),
        "diagnostic_scope": "OPERATIONAL_CURRENT_SOURCE_NOT_FROZEN_T0",
        "does_not_certify_H1_pair_or_outcome": True,
        "potentially_fresh_currencies": fresh,
        "potential_pairs_upper_bound_not_scored": (
            len(fresh)*(len(fresh)-1)//2),
        "currency_status": countries,
        "all_G8_checked": len(countries)==8,
        "no_rates_or_forward_journal_mutation": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    require(args.receipt.resolve().is_relative_to(Path("/tmp")),
            "research receipts only under /tmp")
    now = datetime.now(timezone.utc)
    result = inspect(obs.read_jsonl(cap.JOURNAL), obs.read_jsonl(obs.OUTCOMES), now)
    # Operational diagnostics are explicitly separate from the frozen PIT
    # evaluation cohort and are NEVER used to calculate H1 outcomes.
    source = cap.ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
    result["operational_2y_source_readiness"] = operational_2y_readiness(
        json.loads(source.read_text(encoding="utf-8")), now)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n",
                            encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="daily_date_clusters"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
