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
