#!/usr/bin/env python3
"""Audit ECB EUR2Y entire official AAA spot curve against existing mirror.

Fail closed on any mismatch; report all dates and basis discrepancies. This
code never promotes values, modifies live_data, or feeds original Core.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import math
from statistics import median

from validation.beta import weekly_fx_2y_shadow_oos_v1 as beta
from validation.beta.eurjpy_ecb_2y_official_bridge_v1 import (
    ECB_SERIES, parse_ecb_sdmx_original_csv
)

SCHEMA="GMFQ_ECB_EUR2Y_ORIGINAL_2Y_SOURCE_PARITY_AUDIT_V1"
END="2026-10-22"
START="2025-09-16"
OFFICIAL_URL=("https://data-api.ecb.europa.eu/service/data/YC/"
              "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?"
              "startPeriod=2025-09-16&endPeriod=2026-10-22&format=csvdata")


def audit_eur_original(rates,raw):
    original,err=beta.rate_history("EUR",rates,date.fromisoformat(END))
    if err:
        raise ValueError("original EUR 2Y mirror invalid: "+err)
    official=parse_ecb_sdmx_original_csv(raw,start=START,end=END)
    latest=date.fromisoformat(END)
    if not official or max(official)!=latest:
        raise ValueError("official ECB full historical series missing expected 2026-10-22")
    overlap=sorted(set(original)&set(official))
    if len(overlap)<200:
        raise ValueError("insufficient source overlap to reconcile series")
    diffs=[{"date":d.isoformat(),"stored_pct":original[d],
            "official_pct":official[d],
            "difference_bp":round((original[d]-official[d])*100,5)}
           for d in overlap
           if abs(original[d]-official[d])>0.000005]
    dvals=[abs(x["difference_bp"]) for x in diffs]
    missing_original=sorted(d.isoformat() for d in set(official)-set(original))
    missing_official=sorted(d.isoformat() for d in set(original)-set(official))
    return {
        "schema":SCHEMA,
        "status":"SOURCE_DEFINITION_MATCHES_CURRENT_PUBLISHER" if not diffs
            else "RATE_EUR2Y_CURRENT_MIRROR_DIFFERS_FROM_OFFICIAL_SERIES",
        "source":"ECB AAA spot curve via SDMX",
        "official_series_key":ECB_SERIES,
        "official_url":OFFICIAL_URL,
        "official_payload_sha256":hashlib.sha256(raw).hexdigest(),
        "original_mirror_as_of":rates["EUR"]["date"],
        "original_mirror_source":rates["EUR"]["source"],
        "official_rows":len(official),
        "stored_rows":len(original),
        "overlap_rows":len(overlap),
        "mismatching_same_day_yield_rows":len(diffs),
        "max_absolute_difference_bp":max(dvals,default=0.0),
        "median_absolute_difference_bp":median(dvals) if dvals else 0.0,
        "missing_from_mirror_dates":missing_original,
        "stored_dates_missing_from_current_official":missing_official,
        "overlap_sample_first":diffs[:7],
        "overlap_sample_last":diffs[-7:],
        "september_21_22_exact_differences":[x for x in diffs if x["date"] in
                                              ("2026-09-21","2026-09-22")],
        "official_current_latest_2y_pct":official[latest],
        "stored_latest_2y_pct":original[latest],
        "source_grade_comparable":False if diffs else True,
        "historic_first_release_pit_verified":False,
        "research_only":True,
        "production_history_modified":False,
        "beta_promoted":False,
        "core_recomputed":False,
        "new_data_estimated":False,
    }


def shadow_full_publisher_eurjpy_oos(fx,rates,original_ecb_bytes,
                                     mof_historical_bytes,mof_current_bytes,
                                     *,as_of="2026-10-26"):
    """Replace entire mismatched mirror EUR2Y with verified ECB official BYTES,
    but ONLY in a deep-copied research input. The current live source
    remains untouched and must be repaired at its actual producer.
    """
    import copy
    forensic=audit_eur_original(rates,original_ecb_bytes)
    latest=forensic["original_mirror_as_of"]
    official=parse_ecb_sdmx_original_csv(
        original_ecb_bytes,start=START,end=END)
    if max(official).isoformat()!=latest:
        raise ValueError("official current period not aligned with stored as-of")
    if any(day.weekday()>=5 for day in official):
        raise ValueError("ECB daily government curve has a weekend observation")
    # Require an independently observed historical publication series of at
    # least 200 actual rates; no interpolation or backfill guesses.
    if len(official)<200 or forensic["overlap_rows"]<200:
        raise ValueError("insufficient exact official ECB 2Y coverage")
    shadow=copy.deepcopy(rates)
    ordered=sorted(official.items())
    shadow["EUR"]["history2"]["dates"]=[d.isoformat() for d,v in ordered]
    shadow["EUR"]["history2"]["values"]=[v for d,v in ordered]
    # We did NOT advance the dataset as-of; all observations remain known
    # official latest publisher values, not certified as first-release PIT.
    shadow["EUR"]["date"]=ordered[-1][0].isoformat()
    full=beta.audit_with_official_jpy_source(
        fx,shadow,mof_historical_bytes,mof_current_bytes,as_of=as_of)
    eurjpy=next(x for x in full["pairs"] if x["pair"]=="EURJPY")
    return {
        "schema":"GMFQ_EURJPY_FULL_ORIGINAL_ECB_2Y_SHADOW_RESULT_V1",
        "status":"ORIGINAL_ECB_LATEST_PUBLISHER_PSEUDO_OOS_RESEARCH_ONLY",
        "source_parity":forensic,
        "used_official_ecb_days":len(official),
        "original_eur2y_mirror_replaced_only_in_memory":True,
        "eurjpy_historical_oos_rows":eurjpy["historical_oos_observations"],
        "eurjpy_beta_status":eurjpy["status"],
        "pair_count_with_some_historical_oos":full["pairs_with_any_oos"],
        "pair_count_with_descriptive_variance":full["pairs_with_descriptive_variance_measure"],
        "missing_week_eur_jpy_still_inferred":False,
        "publisher_current_latest_not_first_release_pit":True,
        "benchmark_instrument_basis_comparability_certified":False,
        "b1_b2_rule_validated":False,
        "beta_promoted":False,
        "live_data_modified":False,
        "core_recomputed":False,
    }
