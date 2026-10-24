#!/usr/bin/env python3
"""Eurostat July-Sept 2026 flash/detailed event replay: web-attested, NOT PIT certified.

Original publisher dates are verified, not their intraday release clocks.
Conservative next-UTC-day visibility prevents date-only source lookahead but
does not establish precise intraday market knowledge. NO live scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_eurostat_hicp_component_event_replay_v1 import (
    PATH as SEPTEMBER_COMPONENTS, validate as validate_september,
)

SOURCE = ROOT / "validation/macro/fixtures/v2_eurostat_hicp_jul_sep_2026_flash_detailed_v1.json"
SCHEMA = "GMFQ_MACRO_V2_EUROSTAT_HICP_THREE_MONTH_FLASH_DETAILED_LEDGER_V1"
RECEIPT = "GMFQ_MACRO_V2_EUROSTAT_HICP_THREE_MONTH_WEB_RELEASE_REPLAY_V1"
BASE = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/"
CATEGORIES = (
    "ALL_ITEMS_HICP", "CORE_HICP", "ENERGY", "FOOD_ALCOHOL_TOBACCO",
    "NON_ENERGY_INDUSTRIAL_GOODS", "SERVICES",
)
# Independent period-specific pins: (period, flash-day, detail-day, URL slugs,
#                        paired [flash, detail] annual-rate metrics in CATEGORIES order).
PINS = (
    ("2026-07", "2026-07-31", "2026-08-19",
     "2-31072026-ap", "2-19082026-ap",
     ((2.9, 2.9), (2.5, 2.5), (10.0, 10.3), (1.2, 1.2), (0.9, 0.9), (3.3, 3.3))),
    ("2026-08", "2026-09-01", "2026-09-17",
     "2-01092026-ap", "2-17092026-ap",
     ((3.3, 3.2), (2.4, 2.4), (14.3, 14.3), (1.2, 1.1), (1.2, 1.2), (3.0, 3.0))),
    ("2026-09", "2026-10-02", "2026-10-16",
     "2-02102026-ap", "2-16102026-ap",
     ((3.8, 3.8), (2.5, 2.5), (18.8, 18.9), (1.4, 1.3), (1.1, 1.1), (3.2, 3.2))),
)

def month_index(period):
    require(isinstance(period,str) and len(period)==7 and period[4]=="-",
            "month format must be YYYY-MM")
    try:
        d=date.fromisoformat(period+"-01")
    except ValueError as e:
        raise ValueError("invalid reference period") from e
    return d.year*12+d.month-1


def release(item, published, slug):
    require(item.get("published_on")==published and
            item.get("url")==BASE+slug and
            item.get("original_clock_verified") is None,
            "official release identity/time must be preserved")
    floor=datetime.combine(date.fromisoformat(published)+timedelta(days=1),
                           datetime.min.time(),tzinfo=timezone.utc)
    require(timestamp(item.get("conservative_visible_from_utc"))==floor,
            "unverified Eurostat intraday clock must be next-day gated")
    return floor


def validate(fixture, sep_fixture, sep_headline):
    require(fixture.get("schema")==SCHEMA and fixture.get("review_as_of")=="2026-10-24"
            and fixture.get("currency")=="EUR" and fixture.get("geography")=="EA21"
            and fixture.get("publisher")=="Eurostat"
            and fixture.get("metric_unit")=="percent year-on-year (not contribution)",
            "source geography or rate metric drift")
    for k in ("original_release_day_web_bytes_preserved",
              "full_first_release_pit_chain_certified", "known_intraday_release_clocks",
              "model_promotion_allowed", "eligible_for_backtest",
              "safe_to_publish_new_D", "safe_to_update_pair_theses", "writes_live_data"):
        require(fixture.get(k) is False, "unsafe source-data promotion: "+k)
    months=fixture.get("months")
    require(isinstance(months,list) and len(months)==3, "three consecutive periods required")
    events=[]
    last_period=None
    last_publication=None
    for observed, pinned in zip(months,PINS):
        period,flash_day,detail_day,flash_slug,detail_slug,metrics=pinned
        require(observed.get("reference_period")==period,
                "period identity drift")
        if last_period is not None:
            require(month_index(period)==last_period+1,
                    "noncontiguous Eurostat HICP periods")
        last_period=month_index(period)
        flash=release(observed["flash"],flash_day,flash_slug)
        detail=release(observed["detailed"],detail_day,detail_slug)
        require(date.fromisoformat(flash_day)>=date.fromisoformat(period+"-01")
                and flash<detail, "release chronology invalid")
        if last_publication:
            require(last_publication<flash, "official publication sequence overlap")
        last_publication=detail
        rows=observed.get("components")
        require(isinstance(rows,list) and len(rows)==len(CATEGORIES),
                "six comparable HICP annual-rate metrics required")
        validated=[]
        for row,c,pair in zip(rows,CATEGORIES,metrics):
            require(row.get("component_id")==c, "component identity changed")
            for name,expected in (("flash_rate_yoy_percent",pair[0]),
                                  ("detailed_rate_yoy_percent",pair[1])):
                value=row.get(name)
                require(type(value) in (int,float) and math.isfinite(value)
                        and value==expected, "published Eurostat annual rate mismatch")
            validated.append({"component_id":c,"flash":pair[0],"detailed":pair[1]})
        events.append({"period":period,"flash_gate":flash,"detailed_gate":detail,
                       "flash_url":BASE+flash_slug,"detailed_url":BASE+detail_slug,
                       "components":validated})
    # Existing independently validated September component audit is a second
    # source contract, not silently replaced by the three-month ledger.
    require(sep_headline.get("reference_period")=="2026-09"
            and sep_headline.get("full_historical_first_release_chain_certified") is False,
            "prior September official web ledger changed")
    sep_rows=sep_fixture.get("components")
    require(isinstance(sep_rows,list) and len(sep_rows)==10,
            "separate September detail-series evidence missing")
    map_ids={"CORE_HICP":"EX_ENERGY_FOOD_ALCOHOL_TOBACCO"}
    sep_index={x["component_id"]:x for x in sep_rows}
    for x in events[-1]["components"]:
        src=sep_index[map_ids.get(x["component_id"],x["component_id"])]
        require(src["flash_percent_yoy"]==x["flash"]
                and src["detailed_percent_yoy"]==x["detailed"],
                "September pinned source diverges from earlier certified web comparison")
    require([x["components"][0]["flash"] for x in events]==[2.9,3.3,3.8],
            "flash values of July/August/September changed")
    return events


def replay(as_of, fixture=None, sep_fixture=None, sep_headline=None):
    if fixture is None:
        fixture=json.loads(SOURCE.read_text(encoding="utf-8"))
    if sep_fixture is None:
        sep_fixture=json.loads(SEPTEMBER_COMPONENTS.read_text(encoding="utf-8"))
    if sep_headline is None:
        sep_headline=json.loads((ROOT/"validation/macro/MACRO_V2_EUR_HICP_SEP_2026_RELEASE_SEQUENCE_2026-10-24.json").read_text(encoding="utf-8"))
    events=validate(fixture,sep_fixture,sep_headline)
    cutoff=timestamp(as_of)
    rows=[]
    published=0
    for event in events:
        has_flash=cutoff>=event["flash_gate"]
        has_detail=cutoff>=event["detailed_gate"]
        published+=int(has_flash)+int(has_detail)
        stage=("DETAILED_PUBLICATION" if has_detail else
               "FLASH_ESTIMATE" if has_flash else "NOT_KNOWN")
        rows.append({
            "reference_period":event["period"],
            "stage_at_cutoff":stage,
            "flash_visible":has_flash,
            "detailed_visible":has_detail,
            "visible_metric_values":{
                x["component_id"]:(x["detailed"] if has_detail else
                                   x["flash"] if has_flash else None)
                for x in event["components"]},
            "component_flash_to_detailed_change_pp":{
                x["component_id"]:round(x["detailed"]-x["flash"],1)
                for x in event["components"]} if has_detail else None,
            "original_flash_headline":event["components"][0]["flash"] if has_flash else None,
            "detailed_headline":event["components"][0]["detailed"] if has_detail else None,
            "source_web_url_known":event["detailed_url"] if has_detail else
                                   event["flash_url"] if has_flash else None,
        })
    latest=next((r for r in reversed(rows) if r["flash_visible"]),None)
    known_initial=sum(x["flash_visible"] for x in rows)
    return {
        "schema":RECEIPT,
        "as_of_utc":cutoff.isoformat(),
        "research_scope":{"reference_months":3,"source_publications":6,
                          "annual_rate_components":6,
                          "published_metric_value_records_total":36},
        "source_publications_visible":published,
        "months_with_at_least_one_publication":known_initial,
        "latest_known_reference_period":latest["reference_period"] if latest else None,
        "latest_known_headline_at_cutoff":
            latest["visible_metric_values"]["ALL_ITEMS_HICP"] if latest else None,
        "snapshot_by_reference_period":rows,
        "headline_flash_to_detailed_revisions_visible":{
            r["reference_period"]:r["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"]
            for r in rows if r["detailed_visible"]},
        "full_monthly_first_release_training_minimum":25,
        "missing_independent_monthly_first_release_periods":
            25-known_initial,
        "source_rechecked_against_original_web_at_ci_runtime":False,
        "original_release_day_immutable_bytes_certified":False,
        "complete_historical_first_and_revised_vintage_chain_certified":False,
        "actual_intraday_eurostat_release_timing_certified":False,
        "eligible_for_macro_scoring":False,
        "eligible_for_backtest":False,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "writes_live_data":False,
        "evidence_fingerprint_sha256":hashlib.sha256(
            json.dumps(fixture,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-24T00:00:00Z")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    r=replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),"research receipt restricted to /tmp")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"months_known":r["months_with_at_least_one_publication"],
                      "publications_visible":r["source_publications_visible"],
                      "latest_headline":r["latest_known_headline_at_cutoff"],
                      "macro_scoring":r["eligible_for_macro_scoring"]}))

if __name__=="__main__":
    main()
