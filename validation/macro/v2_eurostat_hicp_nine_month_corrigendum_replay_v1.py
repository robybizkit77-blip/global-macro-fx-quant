#!/usr/bin/env python3
"""Eurostat January–September HICP publisher-event replay: bounded research only.

January/February flash webpages were CORRIGENDED after initial publication.
Their current contents do not prove original uncorrected published bytes. Keep
these as distinct dated events without manufacturing original component values,
weights or intraday clocks. Compose existing seven-month research replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_eurostat_hicp_three_month_replay_v1 import CATEGORIES, month_index
from validation.macro.v2_eurostat_hicp_seven_month_replay_v1 import replay as seven_month_replay

EVIDENCE = ROOT / "validation/macro/fixtures/v2_eurostat_hicp_jan_feb_2026_corrigenda_v1.json"
SCHEMA = "GMFQ_MACRO_V2_EUROSTAT_JAN_FEB_2026_FLASH_CORRIGENDA_DETAILED_V1"
RECEIPT = "GMFQ_MACRO_V2_EUROSTAT_HICP_NINE_MONTH_CORRIGENDUM_REPLAY_V1"
BASE = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/"
# Independently pinned selected annual YoY rates from period-specific official
# web pages (already incorporating amendments), in CATEGORIES order.
PINS = (
    ("2026-01", "2026-02-04", "2-04022026-ap",
     "2026-02-05", "2026-02-25", "2-25022026-ap",
     ((1.7, 1.7), (2.2, 2.2), (-4.1, -4.0),
      (2.7, 2.6), (0.4, 0.4), (3.2, 3.2))),
    ("2026-02", "2026-03-03", "2-03032026-ap",
     "2026-03-04", "2026-03-18", "2-18032026-ap",
     ((1.9, 1.9), (2.4, 2.4), (-3.2, -3.1),
      (2.6, 2.5), (0.7, 0.7), (3.4, 3.4))),
)
CORRECTIONS = (
    ("11:00 AM", "PROCESSING_ERROR", "UNPROCESSED_FOOD", 1, 4, None),
    ("6:00 PM", "COMPONENT_WEIGHT_TECHNICAL_ERROR",
     "COMPONENT_WEIGHTS_NOT_SIX_ANNUAL_RATE_HEADLINES", None, None, 1.4),
)


def floor(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                            datetime.min.time(), tzinfo=timezone.utc)


def dated(item, day, url, stage):
    require(item.get("publication_day") == day
            and item.get("source_url") == url
            and item.get("intraday_release_hour_independently_certified") is False
            and timestamp(item.get("conservative_visible_from_utc")) == floor(day),
            "dated "+stage+" Eurostat source contract/timing drift")
    return floor(day)


def validate(data):
    require(data.get("schema") == SCHEMA and data.get("review_as_of") == "2026-10-24"
            and (data.get("publisher"),data.get("currency"),data.get("coverage")) ==
            ("Eurostat","EUR","EA21")
            and data.get("classification") == "ECOICOP_V2_FROM_2026-02-04"
            and data.get("index_reference_period") == "2025=100"
            and data.get("metric") ==
            "Annual inflation percentage YoY, not HICP index or contributions",
            "HICP identity / EA21 / ECOICOP regime drift")
    require(data.get("source_evidence_quality") ==
            "PERIOD_SPECIFIC_OFFICIAL_WEB_PAGES_ALREADY_CORRIGENDED_NOT_ORIGINAL_PUBLICATION_BYTES",
            "cannot certify uncorrected originals from amended web pages")
    for k in ("publisher_flash_pages_might_be_edited_after_publication",
              ):
        require(data.get(k) is True, "publication amendment provenance changed: "+k)
    for k in ("original_page_bytes_archived_at_release",
              "first_uncorrected_all_metrics_certified",
              "full_revision_history_certified",
              "backtest_ready","macro_score_ready",
              "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
        require(data.get(k) is False, "unverified score/backtest certification "+k)
    observed=data.get("months")
    require(isinstance(observed,list) and len(observed)==2, "two monthly HICP source packages required")
    events=[]
    last_detail=None
    for item, pinned, correction in zip(observed,PINS,CORRECTIONS):
        (period, fday, fslug, cday, dday, dslug, expected)=pinned
        (wall, incident, corrected, nannual, nmonthly, weight_error)=correction
        require(item.get("reference_period")==period, "HICP economic month identity drift")
        flash=dated(item.get("flash",{}),fday,BASE+fslug,"flash")
        official_corrigendum=dated(item.get("corrigendum",{}),cday,BASE+fslug,"corrigendum")
        detailed=dated(item.get("detailed",{}),dday,BASE+dslug,"detailed")
        require(flash<official_corrigendum<detailed and
                (last_detail is None or last_detail<flash),
                "publication/corrigendum chronology impossible")
        last_detail=detailed
        require(item["flash"].get("current_web_page_contains_subsequent_corrigendum") is True,
                "do not treat post-correction webpage as immutable flash vintage")
        corr=item["corrigendum"]
        require(corr.get("publisher_reported_wall_clock")==wall and
                corr.get("publisher_wall_clock_timezone_certified") is False
                and corr.get("incident")==incident
                and corr.get("headline_yoy_changed") is False,
                "original correction note identity or non-headline character changed")
        if period=="2026-01":
            require(corr.get("affected_annual_rate_component_count")==nannual
                    and corr.get("affected_monthly_rate_component_count")==nmonthly
                    and corr.get("corrected_annual_component_outside_selected_six")==corrected,
                    "do not attribute January correction to headline/selected six")
        else:
            require(corr.get("maximum_absolute_weight_correction_per_thousand")==weight_error
                    and corr.get("corrected_metric")==corrected,
                    "February correction was of WEIGHTS not headline YoY rates")
        require(item.get("original_uncorrected_component_monthly_data_available") is False,
                "cannot claim original pre-correction body was acquired")
        measures=item.get("annual_rate_components")
        require(isinstance(measures,list) and len(measures)==len(CATEGORIES),
                "six comparable HICP annual-rate metrics required")
        validated=[]
        for row,category,(first,final) in zip(measures,CATEGORIES,expected):
            require(row.get("component_id")==category,
                    "HICP selected category code drift")
            for field,number in (("flash_percent_yoy",first),
                                 ("detailed_percent_yoy",final)):
                value=row.get(field)
                require(type(value) in (int,float) and math.isfinite(value) and value==number,
                        "official page rate changed without independent re-audit")
            validated.append((category,first,final))
        events.append({"reference_period":period,"flash":flash,"corrigendum":official_corrigendum,
                       "detailed":detailed,"flash_url":BASE+fslug,"detailed_url":BASE+dslug,
                       "annual_rate_metrics":validated,
                       "correction_kind":incident})
    require(events[0]["detailed"]<events[1]["flash"], "January/February ordinary releases overlap")
    require(month_index("2026-02")==month_index("2026-01")+1,
            "nonconsecutive new Eurostat reference months")
    return events


def replay(as_of, data=None):
    if data is None:
        data=json.loads(EVIDENCE.read_text(encoding="utf-8"))
    events=validate(data)
    cutoff=timestamp(as_of)
    prior=seven_month_replay(as_of)
    require(prior["research_scope"]["reference_months"]==7
            and prior["research_scope"]["publisher_release_events"]==14
            and prior["eligible_for_backtest"] is False
            and prior["safe_to_publish_new_D"] is False
            and prior["writes_live_data"] is False,
            "previous 7-month research-only source contract changed")
    early=[]
    corrections=[]
    for event in events:
        has_flash=cutoff>=event["flash"]
        has_corr=cutoff>=event["corrigendum"]
        has_detail=cutoff>=event["detailed"]
        early.append({
            "reference_period":event["reference_period"],
            "stage_at_cutoff":"DETAILED_PUBLICATION" if has_detail else
                "POST_FLASH_CORRIGENDUM" if has_corr else
                "FLASH_WEB_REPORT_WITH_UNCERTIFIED_ORIGINAL_BODY" if has_flash else "NOT_KNOWN",
            "flash_visible":has_flash,
            "corrigendum_visible":has_corr,
            "detailed_visible":has_detail,
            "visible_metric_values":{
                code:final if has_detail else first if has_flash else None
                for code,first,final in event["annual_rate_metrics"]},
            "component_flash_to_detailed_change_pp":{
                code:round(final-first,1)
                for code,first,final in event["annual_rate_metrics"]} if has_detail else None,
            "original_flash_headline":event["annual_rate_metrics"][0][1] if has_flash else None,
            "detailed_headline":event["annual_rate_metrics"][0][2] if has_detail else None,
            "source_web_url_known":event["detailed_url"] if has_detail else
                                   event["flash_url"] if has_flash else None,
            "uncorrected_flash_page_bytes_certified":False,
        })
        corrections.append({
            "reference_period":event["reference_period"],
            "correction_type":event["correction_kind"],
            "official_corrigendum_web_note_visible":has_corr,
            "publisher_correction_visible_from_conservative_utc":
                event["corrigendum"].isoformat() if has_corr else None,
            "actual_correction_instant_timezone_certified":False,
            "pre_corrigendum_corrected_values_reconstructible":False,
        })
    rows=early+prior["snapshot_by_reference_period"]
    require([r["reference_period"] for r in rows]==[
        "2026-01","2026-02","2026-03","2026-04","2026-05",
        "2026-06","2026-07","2026-08","2026-09"],
        "nine separately dated observed HICP reference months required")
    known=sum(r["flash_visible"] for r in rows)
    detail=sum(r["detailed_visible"] for r in rows)
    corrected=sum(x["official_corrigendum_web_note_visible"] for x in corrections)
    latest=next((r for r in reversed(rows) if r["flash_visible"]),None)
    return {
        "schema":RECEIPT,"as_of_utc":cutoff.isoformat(),
        "scope":{"reference_months":9,"ordinary_flash_and_detailed_events":18,
                 "separate_corrigendum_events":2,
                 "all_publisher_publication_or_correction_events":20,
                 "selected_annual_rate_metrics_per_release":6,
                 "ordinary_metric_event_observations":108},
        "ordinary_publications_visible":known+detail,
        "corrigenda_visible":corrected,
        "months_with_first_web_release_available":known,
        "latest_visible_reference_period":latest["reference_period"] if latest else None,
        "latest_headline_yoy_percent":
            latest["visible_metric_values"]["ALL_ITEMS_HICP"] if latest else None,
        "snapshot_by_reference_period":rows,
        "corrigenda":corrections,
        "headline_flash_to_detailed_changes_visible":{
            r["reference_period"]:r["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"]
            for r in rows if r["detailed_visible"]},
        "nonzero_flash_to_detailed_component_comparisons_visible":sum(
            sum(v!=0 for v in r["component_flash_to_detailed_change_pp"].values())
            for r in rows if r["detailed_visible"]),
        "march_services_cross_report_history":prior["march_services_cross_report_history"],
        "remaining_independent_monthly_first_release_periods_for_25":25-known,
        "jan_feb_flash_original_uncorrected_full_bytes_certified":False,
        "actual_eurostat_intraday_release_hour_certified":False,
        "complete_pit_revision_archive_certified":False,
        "source_release_day_original_bytes_archived":False,
        "eligible_for_macro_scoring":False,"eligible_for_backtest":False,
        "safe_to_publish_new_D":False,"safe_to_update_pair_theses":False,
        "writes_live_data":False,
        "source_manifest_sha256":hashlib.sha256(
            json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-24T00:00:00Z")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    r=replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),"research receipt only /tmp")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"months":r["months_with_first_web_release_available"],
                      "official_corrigenda":r["corrigenda_visible"],
                      "headline_revisions":r["headline_flash_to_detailed_changes_visible"],
                      "backtest":r["eligible_for_backtest"]}))

if __name__=="__main__":
    main()
