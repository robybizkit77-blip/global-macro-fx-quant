#!/usr/bin/env python3
"""Preflight official BLS CPI metric parser, NOT an actual/surprise ledger.

Safe behavior:
- Prior to the exact BLS 2026-11-10 08:30 ET release: absolutely no fetch.
- After release: require exact target publication header and month.
- Four distinctly defined metrics (headline/core, m/m SA vs y/y NSA).
- The source HTTP capture time is not the first public publication time.
- Output is only a research preview in /tmp; it never modifies frozen
  forecasts, official actual ledger, live_data, site, or FX signals.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import re
from pathlib import Path

from validation.macro.capture_official_postrelease_actuals_v1 import (
    PlainText,Pending,retrieve
)
from validation.macro.freeze_pre_release_consensus_v1 import scheduled
from validation.macro.g8_metric_issuer_contract_v8 import metrics_for

ROOT=Path(__file__).resolve().parents[2]
SOURCE="https://www.bls.gov/news.release/cpi.htm"
TARGET={
 "ccy":"USD","date":"2026-11-10","event_type":"INFLATION",
 "title":"Consumer Price Index","reference_period":"October 2026",
 "time_local":"08:30","timezone":"America/New_York",
}
REPORT_SCHEMA="GMFQ_BLS_CPI_SOURCE_METRIC_PREFLIGHT_ONLY_V8"
HEADER="CONSUMER PRICE INDEX - OCTOBER 2026"
RELEASE_LABEL="Tuesday, November 10, 2026"
MONTH="October"
YEAR=2026
# Supported keys reflect the official BLS CPI-U news release's headline text.
KEYS=("US_CPI_U_HEADLINE_MOM_SA","US_CPI_U_HEADLINE_YOY_NSA",
      "US_CPI_U_CORE_MOM_SA","US_CPI_U_CORE_YOY_NSA")

def require(ok,msg):
    if not ok:
        raise ValueError("BLS_CPI_PREFLIGHT_REJECTED: "+msg)

def rate(verb,raw):
    v=verb.strip().lower()
    zero=v in ("was unchanged","were unchanged","remained unchanged")
    if zero:
        if raw is not None:
            raise Pending("UNCHANGED_WITH_CONTRADICTORY_NUMBER")
        return 0.
    if not raw:
        raise Pending("RATE_MISSING_FOR_DIRECTION")
    value=float(raw)
    require(math.isfinite(value) and 0<=value<40,
            "rate magnitude outside BLS CPI headline plausible bounds")
    return -value if v in ("declined","decreased","fell") else value

def sole(pattern,text,which):
    matches=list(re.finditer(pattern,text,flags=re.I))
    if len(matches)!=1:
        raise Pending(which+"_NOT_SINGLE_UNAMBIGUOUS_MATCH")
    return rate(matches[0].group("verb"),matches[0].groupdict().get("value"))

def parse(*,raw,month=MONTH,year=YEAR,release_label=RELEASE_LABEL):
    require(type(raw) is bytes and 10<len(raw)<=2_000_000,
            "HTML bytes required with bounded length")
    decoded=raw.decode("utf-8",errors="replace")
    # do not treat arbitrary untrusted HTML as the source; caller must verify
    # TLS issuer host, and this parser still checks the exact dated issue.
    obj=PlainText()
    obj.feed(decoded)
    text=obj.value()
    required=f"CONSUMER PRICE INDEX - {month.upper()} {year}"
    if len(re.findall(re.escape(required),text,flags=re.I))!=1:
        raise Pending("ISSUER_RELEASE_MONTH_HEADER_NOT_TARGET")
    embargo=(r"Transmission of material in this release is embargoed until"
             r".{0,240}8:30 a\.m\.\s*\(ET\)\s*"+re.escape(release_label))
    if not re.search(embargo,text,re.I):
        raise Pending("ISSUER_EMBARGO_RELEASE_DATE_NOT_TARGET")
    def positive_or_negative():
        return r"(?P<verb>increased|rose|went up|declined|decreased|fell|was unchanged|were unchanged|remained unchanged)"
    quantity=r"(?:by\s+)?(?P<value>\d+(?:\.\d+)?)?\s*(?:percent)?"
    heading=re.escape(month)+r"\s+"+str(year)
    lead=(
      r"The Consumer Price Index for All Urban Consumers\s*\(CPI-U\)\s+"
      +positive_or_negative()+r"\s+"+quantity+
      r"\s+on a seasonally adjusted basis in\s+"+re.escape(month)+r"\b"
    )
    # BLS reports the unadjusted 12-month all-items rate in the opening
    # paragraph. Restrict to the same target release header's lead.
    headline_yoy_pattern=(
      r"Over the last 12 months,?\s+the all items index\s+"
      +positive_or_negative()+r"\s+"+quantity+
      r"\s+before seasonal adjustment"
    )
    core_m=(
      r"The index for all items less food and energy\s+"
      +positive_or_negative()+r"\s+"+quantity+
      r"\s+in\s+"+re.escape(month)+r"\b"
    )
    core_y_patterns=[
      r"The all items less food and energy index\s+"
      +positive_or_negative()+r"\s+"+quantity+
      r"\s+over the year",
      r"The index for all items less food and energy\s+"
      +positive_or_negative()+r"\s+"+quantity+
      r"\s+over the past 12 months"
    ]
    # The news release's lead starts AFTER the exact heading, not the menu
    # or a future release mentioned in boilerplate.
    lead_text=text.split(required,1)[1].split("Table A. Percent changes",1)[0][:3300]
    # BLS repeats the annual core rate in later narrative sections.
    # Match only the introductory summary BEFORE Table A; the source's
    # repeated prose must not create an artificial ambiguous annual actual.
    core_year_matches=[]
    for pat in core_y_patterns:
        core_year_matches.extend(re.finditer(pat,lead_text,flags=re.I))
    if len(core_year_matches)!=1:
        raise Pending("CORE_YOY_NOT_SINGLE_UNAMBIGUOUS_VALUE")
    core_yr=rate(core_year_matches[0].group("verb"),
                 core_year_matches[0].groupdict().get("value"))
    metrics={
      "US_CPI_U_HEADLINE_MOM_SA":sole(lead,lead_text,"HEADLINE_MOM"),
      "US_CPI_U_HEADLINE_YOY_NSA":sole(headline_yoy_pattern,lead_text,"HEADLINE_YOY"),
      "US_CPI_U_CORE_MOM_SA":sole(core_m,lead_text,"CORE_MOM"),
      "US_CPI_U_CORE_YOY_NSA":core_yr,
    }
    require(set(metrics)==set(KEYS),"lost BLS metric identity")
    return {
      "reference_period":f"{month} {year}",
      "issuer_release_label":release_label,
      "metric_actual_pct":metrics,
      "surprise_vs_frozen_consensus_pp":None,
      "actual_is_first_publisher_delivery_PIT":False,
      "source_page_can_change_after_capture":True,
      "eligible_for_live_fx_signal":False,
    }

def inspect(*,now,fetch=retrieve):
    require(isinstance(now,datetime) and now.tzinfo is not None,
            "UTC clock with offset mandatory")
    now=now.astimezone(timezone.utc)
    release=scheduled(TARGET)
    require(release is not None,"official 2026-11-10 CPI clock required")
    base={
        "schema":REPORT_SCHEMA,
        "event_key":"USD|2026-11-10|INFLATION|Consumer Price Index",
        "issuer_url":SOURCE,
        "issuer_release_scheduled_utc":release.isoformat().replace("+00:00","Z"),
        "checked_at_utc":now.isoformat().replace("+00:00","Z"),
        "expected_metric_ids":list(KEYS),
        "actual_pct":None,
        "source_html_sha256":None,
        "source_first_publication_PIT_verified":False,
        "actual_not_promoted_to_live_data":True,
        "frozen_consensus_available":False,
        "surprise_pp":None,
        "fx_signal":None,
    }
    if now<release:
        return {**base,"status":"BEFORE_RELEASE_NO_HTTP"}
    if now>release+timedelta(days=7):
        return {**base,"status":"OUTSIDE_FIRST_OBSERVATION_REVIEW_WINDOW_NO_HTTP"}
    try:
        data,url=fetch(SOURCE,"www.bls.gov")
        require(url.startswith("https://www.bls.gov/news.release/") and
                "cpi.htm" in url.lower(),
                "verified issuer URL expected")
        values=parse(raw=data)
    except (Pending,OSError,TimeoutError,UnicodeError) as exc:
        return {**base,"status":"ISSUER_SOURCE_PENDING_OR_UNPARSABLE",
                "reason":type(exc).__name__}
    # The successful read is a first observation by THIS runner only.
    return {**base,
            "status":"BLS_TARGET_CPI_METRICS_PARSED_RESEARCH_ONLY_NOT_PIT",
            "issuer_url":url,
            "actual_pct":values["metric_actual_pct"],
            "source_html_sha256":hashlib.sha256(data).hexdigest(),
            "source_first_publication_PIT_verified":False,
            "frozen_consensus_available":False,
            "surprise_pp":None,
            "eligible_for_macro_event_causality":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    p.add_argument("--check-issuer",action="store_true")
    a=p.parse_args()
    require(a.output is None or a.output.resolve().is_relative_to(Path("/tmp")),
            "preflight only /tmp")
    now=datetime.now(timezone.utc)
    r=inspect(now=now) if a.check_issuer else inspect(
        now=now,fetch=lambda u,h: (_ for _ in ()).throw(Pending("FETCH_DISABLED")))
    # When check-issuer disabled and after the release, no network is
    # attempted; it explicitly cannot be called an observation.
    if not a.check_issuer and r["status"]=="ISSUER_SOURCE_PENDING_OR_UNPARSABLE":
        r["status"]="HTTP_DISABLED_NO_ACTUAL_OBSERVED"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
