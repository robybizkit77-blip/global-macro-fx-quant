#!/usr/bin/env python3
"""G8 source adapters for already-attested latest official publisher web releases.

A latest first-web-release page supplies ONE observation, not a 25-month monthly
or 13-quarterly vintage chain. The source-attestation contract, index/rate units
and date-only conservative availability are independently pinned here.

All evidence is from the existing reviewed CORE/GROWTH registries; no network
requests, fake publisher hours, historical extrapolation or live feed changes.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_pit_g8_evidence_adapters_v1 import event, source

CORE_FILE = ROOT / "validation/macro/CORE_G8_OFFICIAL_RELEASE_WEB_ATTESTATIONS_2026-10-22.json"
GROWTH_FILE = ROOT / "validation/macro/GROWTH_FIRST_RELEASE_OFFICIAL_WEB_ATTESTATIONS_2026-10-20.json"
REGISTRY_FILE = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"

# Independently pinned web-attested source facts, not generated from mutable
# fixture rows; exact candidate identity, metric, value and release date matter.
# GBP.labour already has three vetted ONS rolling-window events in PR #589.
# The external GBP latest-only anchor is crosschecked below, not duplicated.
CORE_PINS = {
    "USD.inflation": ("2026-09", "2026-10-14", 336.298, "CPIAUCSL", "M",
                      "SA CPI-U index, September 2026", "U.S. Bureau of Labor Statistics",
                      "https://www.bls.gov/news.release/archives/realer_10142026.htm",
                      "yoy_pct_from_index"),
    "CAD.inflation": ("2026-09", "2026-10-19", 3.092783505154628,
                      "CA_CPI_HEADLINE_YOY", "M",
                      "percent YoY, computed 170.0 / 164.9 - 1, not published rounded 3.1",
                      "Statistics Canada",
                      "https://www150.statcan.gc.ca/n1/daily-quotidien/261019/t001a-eng.htm",
                      "derived_yoy_from_index"),
    "AUD.labour": ("2026-09", "2026-10-15", 4.7, "AU_UNEMP_RATE", "M",
                   "percent SA unemployment headline",
                   "Australian Bureau of Statistics",
                   "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/sep-2026",
                   "level"),
    "CAD.labour": ("2026-09", "2026-10-09", 6.5, "CA_UNEMP_RATE", "M",
                   "percent unemployment SA", "Statistics Canada",
                   "https://www150.statcan.gc.ca/n1/daily-quotidien/261009/dq261009a-eng.htm",
                   "level"),
    "JPY.labour": ("2026-08", "2026-10-02", 2.5, "JP_UNEMP_RATE", "M",
                   "percent SA unemployment, basic tabulation",
                   "Statistics Bureau of Japan",
                   "https://www.stat.go.jp/data/roudou/sokuhou/tsuki/", "level"),
    "GBP.inflation": ("2026-09", "2026-10-21", 3.5, "D7G7", "M",
                      "percent YoY UK CPI, NOT CPIH", "UK Office for National Statistics",
                      "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026",
                      "reported_yoy_rate"),
    "NZD.inflation": ("2026Q3", "2026-10-22", 3.7, "NZ_CPI_HEADLINE_YOY", "Q",
                      "percent YoY for September 2026 quarter, NOT quarter-on-quarter",
                      "Stats NZ",
                      "https://www.stats.govt.nz/news/annual-inflation-at-3-7-percent-in-september-2026/",
                      "reported_yoy_rate"),
}
CORE_REFERENCE = {
    "USD.inflation": ("2026-09", 3.7172508442689933, "2026-10-14T08:30:00-04:00",
                      324.245, 336.298),
    "CAD.inflation": ("2026-09", 3.092783505154628, None, 164.9, 170.0),
    "AUD.labour": ("2026-09", 4.7, "2026-10-15T11:30:00+11:00", None, None),
    "CAD.labour": ("2026-09", 6.5, None, None, None),
    "JPY.labour": ("2026-08", 2.5, None, None, None),
    "GBP.inflation": ("2026-09", 3.5, None, None, None),
    "NZD.inflation": ("2026-09", 3.7, None, None, None),
}
SKIPPED_GBP_LABOUR = (
    "2026-08", "2026-10-20", 4.7,
    "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/"
    "employmentandemployeetypes/bulletins/uklabourmarket/october2026"
)
GROWTH_PINS = {
    "AUD": ("AU_REAL_GDP_QOQ_ABS_history_value", "2026Q2", "2026-06",
            "2026-09-02", "2026-09-02T11:30:00+10:00", 0.4,
            "% QoQ, seasonally adjusted chain volume",
            "Australian Bureau of Statistics",
            "https://www.abs.gov.au/statistics/economy/national-accounts/"
            "australian-national-accounts-national-income-expenditure-and-product/jun-2026"),
    "NZD": ("NZ_REAL_GDP_Q_history_value", "2026Q2", "2026-06",
            "2026-09-17", None, 2.6, "percent y/y",
            "Stats NZ",
            "https://www.stats.govt.nz/information-releases/"
            "gross-domestic-product-june-2026-quarter/"),
}
EXPECTED_KEYS = {
    "USD.inflation", "CAD.inflation", "AUD.labour", "CAD.labour",
    "JPY.labour", "GBP.labour", "GBP.inflation", "NZD.inflation",
}
SOURCE_WEB_CLASS = "OFFICIAL_PUBLISHER_RELEASE_WEB_VALUE_DATE_NOT_IMMUTABLE_BYTES"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def observed_gate(day, published_at_local):
    published = date.fromisoformat(day)
    if published_at_local is None:
        # No independently verified original publisher intraday time. This is
        # a conservative simulation gate, NOT market's real release timestamp.
        return datetime.combine(published + timedelta(days=1),
                                datetime.min.time(),tzinfo=timezone.utc).isoformat()
    local = datetime.fromisoformat(published_at_local)
    require(local.date() == published and local.tzinfo is not None
            and local.utcoffset() is not None,
            "verified publisher local clock date/offset mismatch")
    return timestamp(published_at_local).isoformat()


def _canonical_registry():
    registry = load_json(REGISTRY_FILE)
    require(registry.get("schema") == "GMFQ_MACRO_SOURCE_REGISTRY_V1"
            and len(registry.get("series", {})) == 16,
            "canonical G8 macro source registry drift")
    return registry["series"]


def latest_core():
    d = load_json(CORE_FILE)
    require(d.get("schema") == "GMFQ_G8_CORE_OFFICIAL_WEB_RELEASE_ATTESTATIONS_V1"
            and d.get("evidence_class") == SOURCE_WEB_CLASS
            and d.get("historical_full_PIT_vintage_certified") is False
            and d.get("review_as_of") == "2026-10-22",
            "official latest core source limitations altered")
    anchors=d.get("attestations")
    require(isinstance(anchors,list) and len(anchors)==8
            and {a["key"] for a in anchors}==EXPECTED_KEYS,
            "eight exact latest official Core source anchors required")
    reg=_canonical_registry()
    new=[]
    for a in anchors:
        key=a["key"]
        if key=="GBP.labour":
            p,day,value,url=SKIPPED_GBP_LABOUR
            require(a.get("observation_period")==p and a.get("release_date")==day
                    and a.get("raw_series_value")==value and a.get("publisher")==
                    "Office for National Statistics" and a.get("url")==url,
                    "existing GBP LFS three-window evidence conflicts with latest ONS bulletin")
            continue
        (period,day,metric,sid,freq,unit,publisher,url,transform)=CORE_PINS[key]
        source_period,reported,clock,denominator,numerator=CORE_REFERENCE[key]
        require(a.get("observation_period")==source_period
                and a.get("release_date")==day
                and a.get("raw_series_value")==metric
                and a.get("published_value")==reported
                and a.get("release_timestamp_local")==clock
                and a.get("transform")==transform
                and a.get("url")==url,
                "latest official first-web value/date/unit/URL drift: "+key)
        require(a.get("publisher")==(
            "Office for National Statistics" if key=="GBP.inflation"
            else publisher),
            "official publisher identity changed: "+key)
        if numerator is not None:
            require(a.get("numerator_index")==numerator
                    and a.get("denominator_index")==denominator,
                    "index-derived official inflation transformation drift: "+key)
            derived=(numerator/denominator-1.0)*100.0
            require(abs(derived-reported)<1e-9,
                    "derived inflation annual rate disagrees with two publisher index levels")
        else:
            require(a.get("numerator_index") is None and
                    a.get("denominator_index") is None,
                    "indexed inflation conversion leaked into a rate or unemployment series")
        r=reg[key]
        ccy,pillar=key.split(".")
        require(r.get("series_id")==sid and r.get("frequency")==freq
                and r.get("currency")==ccy and r.get("dimension")==pillar,
                "latest official source identity or frequency differs from canonical registry")
        e=event(period,"FIRST_WEB",observed_gate(day,clock),metric,url)
        new.append(source(ccy,pillar,sid,freq,unit,publisher,
                          period_semantics=(
                              "SEPTEMBER_2026_QUARTER" if freq=="Q" else
                              "MONTHLY_OBSERVATION_ATTESTED_ONE_PERIOD_ONLY"),
                          evidence="CORE_G8_LATEST_OFFICIAL_WEB_ATTESTATIONS_2026_10_22",
                          notes=[
                              "This is ONE latest official web release, not a historical PIT chain",
                              "No archived original publication-day page bytes or subsequent revisions",
                              "Canonical registry name match alone does not establish metric transform, vintage or scoring approval",
                              "Source transformation: "+transform,
                              "Publisher intraday clock independently unavailable: date-only next UTC day gate"
                              if clock is None else
                              "Source release clock explicitly recorded with UTC offset",
                          ],events=[e]))
    require(len(new)==7 and len({(x["currency"],x["pillar"]) for x in new})==7,
            "seven new core source slots after deduplicating GBP labour required")
    return new


def latest_growth():
    d=load_json(GROWTH_FILE)
    require(d.get("schema")=="GMFQ_G8_GROWTH_FIRST_RELEASE_ATTESTATIONS_V1"
            and d.get("review_as_of")=="2026-10-20"
            and d.get("attestation_does_not_certify_historical_vintage") is True
            and d.get("attestation_does_not_recalculate_macro_scores") is True,
            "source-reported Growth data not a certified historical time series")
    a=d.get("attestations")
    require(isinstance(a,list) and len(a)==2
            and {x.get("currency") for x in a}=={"AUD","NZD"},
            "exact two original GDP official web attestations required")
    growth=[]
    for x in a:
        ccy=x["currency"]
        (series,period,observed,day,clock,value,unit,publisher,url)=GROWTH_PINS[ccy]
        require(x.get("series_id")==series
                and x.get("observation_period")==observed
                and x.get("release_date")==day
                and x.get("release_timestamp_local")==clock
                and x.get("first_release_value")==value
                and x.get("units")==unit
                and x.get("publisher")==publisher
                and x.get("official_source_url")==url
                and x.get("source_artifact_sha256") is None
                and x.get("provenance_level")==
                "OFFICIAL_WEB_PAGE_DATE_VALUE_VERIFIED_NO_ARCHIVED_BYTES",
                "source-specific GDP date/value/series/format drift: "+ccy)
        require((ccy=="AUD" and "quarter-on-quarter" in x["metric_definition"])
                or (ccy=="NZD" and "SAME quarter of previous year" in x["metric_definition"]),
                "AUD and NZD GDP are economically different QoQ vs YoY drivers")
        growth.append(source(ccy,"growth",series,"Q",unit,publisher,
                 period_semantics=("GDP_QUARTERLY_QOQ_SA_CHAIN_VOLUME" if ccy=="AUD"
                                   else "GDP_QUARTERLY_SAME_QUARTER_YOY_NOT_ANNUAL_AVERAGE"),
                 evidence="GROWTH_FIRST_RELEASE_OFFICIAL_WEB_ATTESTATIONS_2026_10_20",
                 notes=[
                     "Only one period-specific official GDP release; series is not selected in canonical Growth registry",
                     "AUD GDP QoQ and NZD GDP same-quarter YoY cannot be pooled as identical percentage transforms",
                     "No 13-quarter original first-release chain or verified historical revisions",
                     "Source publication clock independently unavailable; date-only next UTC day gate"
                     if clock is None else
                     "Release clock recorded with local UTC offset",
                 ],
                 events=[event(period,"FIRST_WEB",observed_gate(day,clock),value,url)]))
    require(len(growth)==2, "two audited GDP source adapters expected")
    return growth


def collect_latest():
    """Expand G8 control plane with nine source-specific, strictly bounded adapters."""
    return latest_core()+latest_growth()
