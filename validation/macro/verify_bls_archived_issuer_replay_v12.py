#!/usr/bin/env python3
"""Optional live historical BLS CPI source replay: NOT future October actuals.

This diagnostic downloads the archived September 2026 bulletin, if accessible.
It never mutates archives, models or live data; if HTTP is blocked it prints an
explicit UNAVAILABLE (not PASS) result. If HTML is fetched but wrong, it FAILS.
"""
from __future__ import annotations
import hashlib
import json
from validation.macro.capture_official_postrelease_actuals_v1 import retrieve
from validation.macro.preflight_us_cpi_official_actual_v8 import parse

ARCHIVE="https://www.bls.gov/news.release/archives/cpi_10142026.htm"
EXPECTED={
 "US_CPI_U_HEADLINE_MOM_SA":0.6,
 "US_CPI_U_HEADLINE_YOY_NSA":3.7,
 "US_CPI_U_CORE_MOM_SA":0.3,
 "US_CPI_U_CORE_YOY_NSA":2.6,
}

def run(fetch=retrieve):
    try:
        raw, final=fetch(ARCHIVE, "www.bls.gov")
    except (OSError, TimeoutError) as exc:
        return {
            "status":"HISTORICAL_BLS_ARCHIVE_HTTP_UNAVAILABLE_NO_VALIDATION_CLAIM",
            "reason_type":type(exc).__name__,
            "verified_historical_issuer_html":False,
            "October_2026_actual_observed":False,
        }
    if final != ARCHIVE:
        raise ValueError("unexpected BLS archived source final URL")
    parsed=parse(raw=raw, month="September",
        release_label="Wednesday, October 14, 2026")
    actual=parsed["metric_actual_pct"]
    if actual!=EXPECTED:
        raise AssertionError("BLS historical archived actual four measures differ")
    return {
        "status":"HISTORICAL_BLS_ARCHIVE_FOUR_EXACT_ACTUALS_VERIFIED",
        "source_url":ARCHIVE,
        "source_html_sha256":hashlib.sha256(raw).hexdigest(),
        "source_length_bytes":len(raw),
        "historical_reference_period":"September 2026",
        "metric_actual_percent":actual,
        "verified_historical_issuer_html":True,
        "October_2026_actual_observed":False,
    }


if __name__=="__main__":
    print(json.dumps(run(),ensure_ascii=False,sort_keys=True))
