#!/usr/bin/env python3
"""Eurostat HICP March–September 2026 7-month shadow event replay.

Two March/April reference months add to the prior 5-month research replay.
March Services later retrospective values have a separate *publication* clock,
never backdated to the original March release. Conservative next-UTC-day
visibility is NOT the true Eurostat intraday release clock or certifiable PIT.
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
from validation.macro.v2_eurostat_hicp_five_month_replay_v1 import replay as previous_replay

EVIDENCE = ROOT / "validation/macro/fixtures/v2_eurostat_hicp_mar_apr_2026_release_addendum_v1.json"
SCHEMA = "GMFQ_MACRO_V2_EUROSTAT_MAR_APR_2026_HICP_AND_MARCH_SERVICES_LINEAGE_V1"
OUTPUT = "GMFQ_MACRO_V2_EUROSTAT_HICP_SEVEN_MONTH_WEB_RELEASE_REPLAY_V1"
BASE = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/"
# Independent, hard-pinned to period-specific official publisher tables.
# One pair each for CATEGORIES:
# headline, core, energy, food+alcohol+tobacco, non-energy goods, services.
PINS = (
    ("2026-03", "2026-03-31", "2-31032026-ap", "2026-04-16", "2-16042026-ap",
     ((2.5, 2.6), (2.3, 2.3), (4.9, 5.1), (2.4, 2.4), (0.5, 0.5), (3.2, 3.2))),
    ("2026-04", "2026-04-30", "2-30042026-ap", "2026-05-20", "2-20052026-ap",
     ((3.0, 3.0), (2.2, 2.2), (10.9, 10.8), (2.5, 2.4), (0.8, 0.8), (3.0, 3.0))),
)
SERVICE_HISTORY = (
    ("2026-03", "DETAILED", "2026-04-16", "2-16042026-ap", 3.2, False),
    ("2026-04", "DETAILED", "2026-05-20", "2-20052026-ap", 3.3, False),
    ("2026-05", "DETAILED", "2026-06-17", "2-17062026-ap", 3.3, False),
    ("2026-06", "FLASH", "2026-07-01", "2-01072026-ap", 3.2, True),
)


def visible_floor(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                            datetime.min.time(),tzinfo=timezone.utc)


def official_gate(item, date_s, slug):
    require(item.get("release_date")==date_s and
            item.get("source_url")==BASE+slug and
            item.get("confirmed_intraday_clock") is None,
            "Eurostat date-only source/clock contract invalid")
    stamp=visible_floor(date_s)
    require(timestamp(item.get("conservative_visible_from_utc"))==stamp,
            "cannot introduce invented same-day Eurostat publication clock")
    return stamp


def validate(evidence):
    require(evidence.get("schema")==SCHEMA and evidence.get("reviewed_on")=="2026-10-24"
            and (evidence.get("publisher"),evidence.get("currency"),evidence.get("region"))==
            ("Eurostat","EUR","EA21") and
            evidence.get("annual_rate_unit")==
            "percent YoY (one decimal) NOT index level or contribution" and
            evidence.get("source_class")==
            "PERIOD_SPECIFIC_OFFICIAL_WEB_PAGES_NO_RELEASE_DAY_BYTE_CERTIFICATION",
            "noncanonical Eurostat HICP original web source or economic metric")
    for k in ("publication_day_byte_archive_certified","actual_intraday_release_times_verified",
              "full_historical_vintage_chain_certified","backtest_eligible",
              "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
        require(evidence.get(k) is False,
                "research-only original-source limitations cannot be promoted "+k)
    months=evidence.get("months")
    require(isinstance(months,list) and len(months)==2,"two May–September precursor HICP months required")
    audited=[]
    previous_period=None
    previous_detail=None
    for row,(period,fd,fs,dd,ds,metrics) in zip(months,PINS):
        require(row.get("reference_period")==period,"HICP reference month drift")
        current=month_index(period)
        if previous_period is not None:
            require(current==previous_period+1,"missing consecutive month")
        previous_period=current
        f=official_gate(row.get("flash",{}),fd,fs)
        d=official_gate(row.get("detailed",{}),dd,ds)
        require(f<d and (previous_detail is None or previous_detail<f),
                "publication chronology or ordering invalid")
        previous_detail=d
        rates=row.get("rate_components")
        require(isinstance(rates,list) and len(rates)==len(CATEGORIES),
                "six comparable HICP annual-rate components required")
        values={}
        for metric,cat,(flash,detailed) in zip(rates,CATEGORIES,metrics):
            require(metric.get("component_id")==cat,
                    "annual-rate metric identity or order changed")
            for field,expected in (("flash_percent_yoy",flash),
                                   ("detailed_percent_yoy",detailed)):
                actual=metric.get(field)
                require(type(actual) in (float,int) and math.isfinite(actual)
                        and actual==expected,
                        "publisher annual-rate value altered from independently pinned figure")
            values[cat]=(flash,detailed)
        audited.append({"reference_period":period,"flash_gate":f,"detail_gate":d,
                        "flash_url":BASE+fs,"detailed_url":BASE+ds,"metrics":values})
    require(audited[0]["detail_gate"]<audited[1]["flash_gate"],
            "March/April flash detail events overlap")
    service=evidence.get("march_services_cross_report_history")
    require(isinstance(service,list) and len(service)==len(SERVICE_HISTORY),
            "four separate source-vintage March-services citations required")
    out=[]
    for row,(report,stage,day,slug,val,revised_marker) in zip(service,SERVICE_HISTORY):
        require(row.get("reference_period")=="2026-03" and
                row.get("report_period")==report and row.get("publication_stage")==stage
                and row.get("release_day")==day and
                row.get("source_url")==BASE+slug and
                row.get("reported_services_percent_yoy")==val and
                type(row.get("reported_services_percent_yoy")) in (int,float),
                "March services historical cross-report source/figure changed")
        require(timestamp(row.get("conservative_visible_from_utc"))==visible_floor(day),
                "retrospective release value backdated")
        if revised_marker:
            require(row.get("revision_marker_on_source") is True,
                    "source's explicit later revised marker is missing")
        else:
            require(row.get("revision_marker_on_source") is None,
                    "revision marker has been invented on historical source")
        require(row.get("role") in (
            "ORIGINAL_MARCH_DETAILED_SERVICES_RATE_NOT_PROVEN_FIRST_PUBLISHED_RELEASE_WEB_BYTES",
            "LATER_APRIL_DETAILED_REPORTED_MARCH_SERVICES_RATE",
            "LATER_MAY_DETAILED_REPORTED_MARCH_SERVICES_RATE",
            "LATER_JUNE_FLASH_REPORTED_MARCH_SERVICES_RATE_WITH_R_MARKER",
        ),"historical statement must remain a later publication, not a first-release override")
        out.append({"report_period":report,"publication_stage":stage,
                    "visible_from":visible_floor(day),"value":val,
                    "source_url":BASE+slug,"revised_marker":revised_marker})
    require(out[0]["visible_from"]==audited[0]["detail_gate"]
            and out[1]["visible_from"]==audited[1]["detail_gate"]
            and all(a["visible_from"]<b["visible_from"]
                    for a,b in zip(out,out[1:])),
            "March retrospective vintage chronology mismatch")
    return audited,out


def replay(as_of,evidence=None):
    if evidence is None:
        evidence=json.loads(EVIDENCE.read_text(encoding="utf-8"))
    first,service=validate(evidence)
    cutoff=timestamp(as_of)
    older=previous_replay(as_of)
    require(older["research_scope"]["reference_months"]==5
            and older["research_scope"]["distinct_publisher_publications"]==10
            and older["eligible_for_backtest"] is False
            and older["safe_to_publish_new_D"] is False
            and older["writes_live_data"] is False,
            "previous May–September source contract changed or promoted")
    rows=[]
    for e in first:
        flash=cutoff>=e["flash_gate"]
        final=cutoff>=e["detail_gate"]
        rows.append({
            "reference_period":e["reference_period"],
            "stage_at_cutoff":"DETAILED_PUBLICATION" if final else "FLASH_ESTIMATE" if flash else "NOT_KNOWN",
            "flash_visible":flash,"detailed_visible":final,
            "visible_metric_values":{k:(pair[1] if final else pair[0] if flash else None)
                                     for k,pair in e["metrics"].items()},
            "component_flash_to_detailed_change_pp":{
                k:round(pair[1]-pair[0],1) for k,pair in e["metrics"].items()
            } if final else None,
            "original_flash_headline":e["metrics"]["ALL_ITEMS_HICP"][0] if flash else None,
            "detailed_headline":e["metrics"]["ALL_ITEMS_HICP"][1] if final else None,
            "source_web_url_known":e["detailed_url"] if final else
                                   e["flash_url"] if flash else None,
        })
    rows+=older["snapshot_by_reference_period"]
    require([r["reference_period"] for r in rows]==[
        "2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09"],
        "seven distinct economic months must remain separate")
    service_visible=[s for s in service if cutoff>=s["visible_from"]]
    latest=next((r for r in reversed(rows) if r["flash_visible"]),None)
    known=sum(r["flash_visible"] for r in rows)
    publications=sum(r["flash_visible"]+r["detailed_visible"] for r in rows)
    historical={
        "reference_month":"2026-03","metric":"SERVICES_ANNUAL_RATE_PERCENT_YOY",
        "known_publication_values":[
            {"report_period":s["report_period"],
             "report_stage":s["publication_stage"],
             "reported_value":s["value"],
             "known_from_utc":s["visible_from"].isoformat(),
             "source_url":s["source_url"],
             "report_has_revised_marker":s["revised_marker"]}
            for s in service_visible],
        "earliest_sampled_value":service_visible[0]["value"] if service_visible else None,
        "latest_sampled_value":service_visible[-1]["value"] if service_visible else None,
        "full_march_vintage_chain_certified":False,
        "exact_revision_effective_timestamp_certified":False,
        "historical_month_counts_as_extra_first_release":False,
    }
    return {
        "schema":OUTPUT,"as_of_utc":cutoff.isoformat(),
        "research_scope":{"reference_months":7,"publisher_release_events":14,
                          "annual_rate_components_per_stage":6,
                          "report_value_observations":84,
                          "march_services_retrospective_statement_count":4},
        "publisher_events_visible":publications,
        "monthly_first_publication_periods_visible":known,
        "latest_reference_month_visible":latest["reference_period"] if latest else None,
        "latest_headline_percent_yoy":
            latest["visible_metric_values"]["ALL_ITEMS_HICP"] if latest else None,
        "snapshot_by_reference_period":rows,
        "headline_flash_detailed_changes_visible":{
            r["reference_period"]:r["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"]
            for r in rows if r["detailed_visible"]},
        "component_rate_differences_nonzero_visible":sum(
            sum(abs(change)>0 for change in r["component_flash_to_detailed_change_pp"].values())
            for r in rows if r["detailed_visible"]),
        "march_services_cross_report_history":historical,
        "months_short_of_25_release_research_minimum":25-known,
        "original_release_day_bytes_archived":False,
        "true_intraday_eurostat_release_times_certified":False,
        "full_pit_revisions_certified":False,
        "eligible_for_macro_scoring":False,
        "eligible_for_backtest":False,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "writes_live_data":False,
        "fixture_sha256":hashlib.sha256(json.dumps(
            evidence,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-24T00:00:00Z")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    r=replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),"receipts only /tmp")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"months":r["monthly_first_publication_periods_visible"],
                      "revisions":r["headline_flash_detailed_changes_visible"],
                      "historical_services_reports":len(r["march_services_cross_report_history"]["known_publication_values"]),
                      "scoring":r["eligible_for_macro_scoring"]}))


if __name__=="__main__":
    main()
