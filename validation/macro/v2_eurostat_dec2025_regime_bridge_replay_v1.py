#!/usr/bin/env python3
"""Eurostat December 2025 EA20 -> January 2026 EA21 HICP: research-only PIT bridge.

The December flash/detailed *source publications* disagree with a later
retrospective December headline in Jan 2026 publisher pages. Preserve all
dated web statements as separate records; never auto-rewrite December's 1.9
detailed reading using a later 2.0 retrospective reference. Only the
next-UTC-day date gate is known, NOT the real intraday publication timestamp.

Do not conflate the membership change with ECOICOP v2 reclassification:
Eurostat asserts historical all-items HICP is unchanged *by ECOICOP alone*.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_eurostat_hicp_three_month_replay_v1 import CATEGORIES
from validation.macro.v2_eurostat_hicp_nine_month_corrigendum_replay_v1 import (
    replay as nine_month_replay,
)

SOURCE = ROOT / "validation/macro/fixtures/v2_eurostat_hicp_dec2025_ea20_transition_v1.json"
SCHEMA = "GMFQ_MACRO_V2_EUROSTAT_DEC_2025_EA20_TRANSITION_ADDENDUM_V1"
RECEIPT = "GMFQ_MACRO_V2_EUROSTAT_HICP_DEC2025_SEP2026_REGIME_BRIDGE_REPLAY_V1"
BASE = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/"
PINNED_STAGES = (
    ("FLASH", "2026-01-07", "2-07012026-ap"),
    ("DETAILED", "2026-01-19", "2-19012026-ap"),
)
PINNED_COMPONENTS = (
    ("ALL_ITEMS_HICP", 2.0, 1.9),
    ("CORE_HICP", 2.3, 2.3),
    ("ENERGY", -1.9, -1.9),
    ("FOOD_ALCOHOL_TOBACCO", 2.6, 2.5),
    ("NON_ENERGY_INDUSTRIAL_GOODS", 0.4, 0.4),
    ("SERVICES", 3.4, 3.4),
)
PINNED_LATER = (
    ("2026-01", "FLASH_POST_CORRIGENDUM_AS_CURRENTLY_SERVED",
     "2026-02-04", "2-04022026-ap", 2.0),
    ("2026-01", "DETAILED",
     "2026-02-25", "2-25022026-ap", 2.0),
)
METHOD_URL = ("https://ec.europa.eu/eurostat/documents/272892/11336726/"
              "HICP%2Bimprovements%2B-%2BQuestions%2Band%2BAnswers-2026-EN.pdf/"
              "dff14a89-9f65-8371-e143-488231305710?t=1766052045691")
MEMBERSHIP_URL = "https://economy-finance.ec.europa.eu/euro/eu-countries-and-euro/bulgaria-and-euro_en"


def floor_after(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=1),
                            datetime.min.time(),tzinfo=timezone.utc)


def validate(data):
    require(data.get("schema")==SCHEMA and data.get("reviewed_on")=="2026-10-24"
            and data.get("publisher")=="Eurostat"
            and data.get("reference_period")=="2025-12"
            and data.get("period_geography")=="EA20"
            and data.get("source_metric")=="HICP_ANNUAL_RATE_PERCENT_YOY_ONE_DECIMAL"
            and data.get("source_component_classification")=="PRE_ECOICOP_V2"
            and data.get("source_index_reference_period")=="2015=100"
            and data.get("source_vintage_status")==
            "PERIOD_SPECIFIC_PUBLISHER_WEB_PAGES_NO_IMMUTABLE_RELEASE_DAY_BYTES",
            "2025 HICP reference series or original web evidence identity changed")
    for k in ("original_december_flash_html_release_day_bytes_certified",
              "intraday_publication_time_certified",
              "december_historical_retroactive_2point0_causal_reason_certified",
              "complete_first_release_pit_training_certified","backtest_eligible",
              "score_eligible","safe_to_publish_new_D","safe_to_update_pair_theses",
              "writes_live_data"):
        require(data.get(k) is False, "research-only evidence gate promoted: "+k)
    regime=data.get("transition",{})
    require(regime.get("membership_change_effective")=="2026-01-01"
            and regime.get("membership_2025")=="EA20"
            and regime.get("membership_2026")=="EA21"
            and regime.get("newly_joined_country")=="Bulgaria"
            and regime.get("technical_method_2025")=="ECOICOP_V1_BASE_2015_100"
            and regime.get("technical_method_2026")=="ECOICOP_V2_BASE_2025_100"
            and regime.get("hicp_first_ecoicop_v2_publication")=="2026-02-04"
            and regime.get("eurostat_all_items_historical_unaffected_by_ecoicop_reclassification_alone") is True
            and regime.get("eurostat_chain_index_for_evolving_member_states") is True
            and regime.get("no_assumption_aggregate_components_weights_homogeneous") is True
            and regime.get("no_automatic_cross_regime_normalized_macro_signal") is True
            and regime.get("eurostat_methodology_url")==METHOD_URL
            and regime.get("eurostat_membership_url")==MEMBERSHIP_URL,
            "geographic or ECOICOP change boundary is not independently pinned")
    stages=data.get("stage_publications")
    require(isinstance(stages,list) and len(stages)==len(PINNED_STAGES),
            "December flash and detailed events are required")
    stage_gates=[]
    for item,(stage,day,slug) in zip(stages,PINNED_STAGES):
        require(item.get("stage")==stage and item.get("published_on")==day
                and item.get("source_url")==BASE+slug
                and item.get("independent_intraday_clock_certified") is False
                and timestamp(item.get("conservative_visible_from_utc"))==floor_after(day),
                "official December publication date/URL or availability changed")
        stage_gates.append(floor_after(day))
    require(stage_gates[0]<stage_gates[1], "flash must precede detailed")
    comp=data.get("components")
    require(isinstance(comp,list) and len(comp)==len(CATEGORIES),
            "six comparable annual rates required")
    paired=[]
    for item,(cat,f,d),known_cat in zip(comp,PINNED_COMPONENTS,CATEGORIES):
        require(cat==known_cat and item.get("component_id")==cat,
                "same selected HICP annual-rate category set required")
        for field,val in (("flash_percent_yoy",f),("detailed_percent_yoy",d)):
            v=item.get(field)
            require(type(v) in (int,float) and math.isfinite(v) and v==val,
                    "published December component rate disagrees with pinned source")
        paired.append((cat,f,d))
    later=data.get("later_2026_report_references")
    require(isinstance(later,list) and len(later)==len(PINNED_LATER),
            "two retrospective December headline references required")
    earlier_time=stage_gates[1]
    later_rows=[]
    for item,(report,stage,day,slug,val) in zip(later,PINNED_LATER):
        at=floor_after(day)
        require(item.get("report_reference_period")==report and
                item.get("report_stage")==stage and
                item.get("report_date")==day and
                item.get("source_url")==BASE+slug and
                type(item.get("publisher_reported_december_2025_headline_percent")) in (int,float)
                and item.get("publisher_reported_december_2025_headline_percent")==val
                and item.get("original_2026_flash_page_immutable") is False
                and timestamp(item.get("report_conservative_visible_from_utc"))==at,
                "later December reference source/time or numerical value drift")
        require(at>earlier_time, "later reported December figure cannot precede source")
        earlier_time=at
        later_rows.append({"report_reference_period":report,
                           "report_stage":stage,"reported_at":at,
                           "reported_december_headline":val,
                           "source_url":BASE+slug})
    return stage_gates,paired,later_rows


def replay(as_of,data=None):
    if data is None:
        data=json.loads(SOURCE.read_text(encoding="utf-8"))
    (flash_time,detail_time),component_pairs,later=validate(data)
    cutoff=timestamp(as_of)
    old=nine_month_replay(as_of)
    require(old["scope"]["reference_months"]==9
            and old["scope"]["ordinary_flash_and_detailed_events"]==18
            and old["scope"]["separate_corrigendum_events"]==2
            and old["eligible_for_macro_scoring"] is False
            and old["safe_to_publish_new_D"] is False
            and old["writes_live_data"] is False,
            "January–September pre-existing research scope or restrictions modified")
    flash=cutoff>=flash_time
    detailed=cutoff>=detail_time
    dec={
        "reference_period":"2025-12","geography":"EA20",
        "economic_classification":"PRE_ECOICOP_V2_2025",
        "stage_at_cutoff":"DETAILED" if detailed else "FLASH" if flash else "NOT_KNOWN",
        "flash_visible":flash,"detailed_visible":detailed,
        "visible_metric_values":{
            code:(d if detailed else f if flash else None)
            for code,f,d in component_pairs},
        "original_flash_headline":2.0 if flash else None,
        "detailed_headline":1.9 if detailed else None,
        "component_flash_to_detailed_change_pp":{
            code:round(d-f,1) for code,f,d in component_pairs
        } if detailed else None,
        "source_web_url_known":BASE+("2-19012026-ap" if detailed else
                                      "2-07012026-ap") if flash else None,
        "original_release_day_bytes_archived":False,
    }
    rows=[dec]+old["snapshot_by_reference_period"]
    require([r["reference_period"] for r in rows]==[
        "2025-12","2026-01","2026-02","2026-03","2026-04","2026-05",
        "2026-06","2026-07","2026-08","2026-09"],
        "ten separately attributable economic reference months required")
    retros=[{
        "reference_period":"2025-12","reported_in_reference_period":event["report_reference_period"],
        "reported_in_publication_stage":event["report_stage"],
        "publication_gate_utc":event["reported_at"].isoformat(),
        "value_reported_percent_yoy":event["reported_december_headline"],
        "source_url":event["source_url"],
        "overwrites_december_detailed_1point9":False,
        "cause_of_discrepancy_verified":False,
    } for event in later if cutoff>=event["reported_at"]]
    known=sum(x["flash_visible"] for x in rows)
    finished=sum(x["detailed_visible"] for x in rows)
    latest=next((x for x in reversed(rows) if x["flash_visible"]),None)
    january=rows[1]
    bridge_visible=dec["detailed_visible"] and january["flash_visible"]
    return {
        "schema":RECEIPT,"as_of_utc":cutoff.isoformat(),
        "research_scope":{"reference_months":10,"ordinary_release_events":20,
                          "separate_correction_events":2,
                          "year_on_year_metric_stage_values":120,
                          "sampled_later_december_references":2},
        "ordinary_publications_visible":known+finished,
        "correction_events_visible":old["corrigenda_visible"],
        "months_with_initial_web_publication_visible":known,
        "months_short_of_25":25-known,
        "latest_visible_reference_month":latest["reference_period"] if latest else None,
        "latest_visible_headline_percent_yoy":latest["visible_metric_values"]["ALL_ITEMS_HICP"] if latest else None,
        "vintage_by_economic_reference_month":rows,
        "headline_flash_to_detailed_changes_visible":{
            x["reference_period"]:x["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"]
            for x in rows if x["detailed_visible"]},
        "retrospective_december_headline_in_2026_reports":retros,
        "regime_transition":{
            "previous_reference_month":"2025-12","previous_region":"EA20",
            "next_reference_month":"2026-01","next_region":"EA21",
            "classification_change":"ECOICOP_TO_ECOICOP_V2",
            "index_reference_change":"2015_100_TO_2025_100",
            "chain_index_context_from_eurostat":True,
            "historical_all_items_unchanged_due_to_ECOICOP_alone":True,
            "has_both_month_values":bridge_visible,
            "last_december_detailed_percent_yoy":1.9 if dec["detailed_visible"] else None,
            "january_first_web_headline_percent_yoy":
                january["original_flash_headline"] if january["flash_visible"] else None,
            "automatic_cross_regime_headline_delta_pp":None,
            "automatic_cross_regime_weighted_component_comparison":None,
            "cross_regime_model_normalization_certified":False,
            "regime_bridge_independent_evidence_review_required":True,
        },
        "release_day_original_bytes_verified":False,
        "full_historical_pit_revision_matrix_certified":False,
        "intraday_eurostat_publisher_clock_certified":False,
        "eligible_for_macro_scoring":False,
        "eligible_for_backtest":False,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "writes_live_data":False,
        "source_fingerprint_sha256":hashlib.sha256(
            json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-24T00:00:00Z")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    data=replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),"research receipts only /tmp")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"months":data["months_with_initial_web_publication_visible"],
                      "retrospectives":len(data["retrospective_december_headline_in_2026_reports"]),
                      "regime_bridge_approved":data["regime_transition"]["cross_regime_model_normalization_certified"],
                      "scoring":data["eligible_for_macro_scoring"]}))


if __name__=="__main__":
    main()
