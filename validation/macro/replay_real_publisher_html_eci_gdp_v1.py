#!/usr/bin/env python3
"""Real publisher source replay, read-only and intentionally historical.

The live GH runner attempts two actual past BLS/StatCan HTTP documents
dated before the evaluation day, using the SAME parser as next Friday.
No user/model data are changed. A blocked publisher source FAILS the live
reachability gate rather than being disguised as a successful end-to-end test.
"""
from __future__ import annotations
import argparse
import hashlib
import json

from validation.macro.capture_official_postrelease_actuals_v1 import (
    ECI,GDP,parse_issuer_page,retrieve,need,Pending,PlainText
)

SAMPLES=[
    {
       "key":ECI,
       "source_url":"https://www.bls.gov/news.release/archives/eci_07312026.htm",
       "host":"www.bls.gov",
       "release":"Friday, July 31, 2026",
       "period":"June",
       "published_value":0.9,
       "scope":"2026Q2_US_BLS_CIVILIAN_ECI_TOTAL_3_MONTH_SA"
    },
    {
       "key":GDP,
       "source_url":"https://www150.statcan.gc.ca/n1/daily-quotidien/260929/dq260929a-eng.htm",
       "host":"www150.statcan.gc.ca",
       "release":"2026-09-29",
       "period":"July",
       "published_value":0.0,
       "scope":"2026_07_CANADA_REAL_GDP_ALL_INDUSTRIES_MOM_SA"
    },
]

def audit(get=retrieve):
    output=[]
    for sample in SAMPLES:
        body,final=get(sample["source_url"],sample["host"])
        need(final==sample["source_url"],
             "published source redirected from declared historical location")
        try:
            number=parse_issuer_page(sample["key"],body,
                    expected_release=sample["release"],
                    expected_period=sample["period"])
        except Pending:
            # First-party real page only. Print short debugging fragments
            # to distinguish missing genuine headline from HTML spacing.
            h=PlainText();h.feed(body.decode("utf-8",errors="replace"))
            content=h.value()
            for key in ("Real GDP by industry","was essentially unchanged in","Released:"):
                i=content.find(key)
                if i>=0:print("ISSUER_PARSER_DIAGNOSTIC",sample["host"],key,
                              repr(content[max(0,i-80):i+260]),flush=True)
            raise
        need(abs(number-sample["published_value"])<1e-9,
             sample["scope"]+": parser does not match original publisher actual")
        output.append({
            "source_url":sample["source_url"],
            "publisher_host":sample["host"],
            "source_raw_html_sha256":hashlib.sha256(body).hexdigest(),
            "source_bytes":len(body),
            "issuer_series":sample["scope"],
            "parsed_actual_percent":number,
            "reference_period":sample["period"]+" 2026",
            "recorded_at_original_release_day":False,
            "news_event_fx_causal_claim":False,
        })
    return {
        "status":"HISTORICAL_OFFICIAL_PUBLISHER_HTML_SOURCE_REPLAY_PASSED",
        "historical_documents_downloaded":len(output),
        "frozen_oct30_actuals_written":0,
        "FX_or_CB_rate_repricing_certified":False,
        "records":output,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out")
    args=p.parse_args()
    report=audit()
    if args.out:
        from pathlib import Path
        dest=Path(args.out)
        need(dest.resolve().is_relative_to(Path("/tmp")),
             "historical receipt must be in /tmp")
        dest.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":main()
