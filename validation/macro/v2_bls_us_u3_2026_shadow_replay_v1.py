#!/usr/bin/env python3
"""USD labour 2026: source-dated sparse-event replay, no live/FX scoring.

Every input is the original headline of an archived BLS Employment Situation.
The unobserved October 2025 CPS month is retained as a structural hole. Because
the 24-observation rolling window still straddles that hole, these intensities
are DESCRIPTIVE releases-based comparators, not monthly PIT-normalized scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT, period_index, require, timestamp
from validation.macro.v2_bls_us_unrate_25_release_pilot_v1 import (
    read_fixture, validate_manifest,
)
from validation.macro.v2_bls_shutdown_sparse_reentry_v1 import (
    load_evidence, validate_evidence, _snapshot,
)

SCHEMA = "GMFQ_BLS_U3_2026_FIRST_RELEASE_SHADOW_EVIDENCE_V1"
RECEIPT = "GMFQ_MACRO_V2_US_U3_2026_SPARSE_RELEASE_STUDY_V1"
PATH = ROOT / "validation/macro/fixtures/v2_bls_us_u3_2026_jan_sep_first_release_web_evidence.json"
ASOF_FLOOR = timestamp("2026-01-09T13:30:00Z")
ASOF_CEILING = timestamp("2026-10-23T23:59:59Z")
ARCHIVE = "https://www.bls.gov/bls/news-release/empsit.htm"
CALENDAR = "https://www.bls.gov/cps/publications/release-calendar.htm"
EXPECTED = (
    ("2026-01", "2026-02-11T08:30:00-05:00", 4.3,
     "https://www.bls.gov/news.release/archives/empsit_02112026.htm"),
    ("2026-02", "2026-03-06T08:30:00-05:00", 4.4,
     "https://www.bls.gov/news.release/archives/empsit_03062026.htm"),
    ("2026-03", "2026-04-03T08:30:00-04:00", 4.3,
     "https://www.bls.gov/news.release/archives/empsit_04032026.htm"),
    ("2026-04", "2026-05-08T08:30:00-04:00", 4.3,
     "https://www.bls.gov/news.release/archives/empsit_05082026.htm"),
    ("2026-05", "2026-06-05T08:30:00-04:00", 4.3,
     "https://www.bls.gov/news.release/archives/empsit_06052026.htm"),
    ("2026-06", "2026-07-02T08:30:00-04:00", 4.2,
     "https://www.bls.gov/news.release/archives/empsit_07022026.htm"),
    ("2026-07", "2026-08-07T08:30:00-04:00", 4.1,
     "https://www.bls.gov/news.release/archives/empsit_08072026.htm"),
    ("2026-08", "2026-09-04T08:30:00-04:00", 4.1,
     "https://www.bls.gov/news.release/archives/empsit_09042026.htm"),
    ("2026-09", "2026-10-02T08:30:00-04:00", 4.2,
     "https://www.bls.gov/news.release/archives/empsit_10022026.htm"),
)


def evidence() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def validate(e: dict, pre: dict, gap: dict) -> None:
    """Require original official first-release evidence, dates and immutable rules."""
    validate_manifest(pre)
    validate_evidence(gap, pre)
    require(isinstance(e, dict) and e.get("schema") == SCHEMA and
            e.get("status") ==
            "OFFICIAL_BLS_ARCHIVED_HEADLINE_READS_NOT_IMMUTABLE_BYTES_CERTIFIED",
            "unknown nine-release BLS 2026 research contract")
    require((e.get("currency"),e.get("pillar"),e.get("series_id"),
             e.get("fred_alias"),e.get("method")) ==
            ("USD","labour","LNS14000000","UNRATE",
             "BLS_CPS_U3_SEASONALLY_ADJUSTED_FIRST_PUBLICATION_HEADLINE"),
            "U3 BLS / FRED reference series mismatch")
    require(e.get("source_archive") == ARCHIVE and
            e.get("source_release_calendar") == CALENDAR and
            e.get("pre_gap_manifest") ==
            "validation/macro/fixtures/v2_bls_us_unrate_25_first_releases_2023_09_2025_09.json" and
            e.get("shutdown_manifest") ==
            "validation/macro/fixtures/v2_bls_us_unemployment_shutdown_2025_gap_resumption.json",
            "official archive/calendars or pilot provenance changed")
    require(e.get("structural_missing_cps_period") == "2025-10" and
            e.get("coverage_first_period") == "2026-01" and
            e.get("coverage_last_period") == "2026-09" and
            e.get("latest_observation_first_published_utc") ==
            "2026-10-02T12:30:00+00:00" and
            e.get("next_release_not_yet_published_at_asof") == {
                "reference_period":"2026-10",
                "scheduled":"2026-11-06T08:30:00-05:00",
            },
            "source period bounds or November scheduled release changed")
    require(e.get("evidence_independently_hashed") is False and
            e.get("full_vintage_revision_chain_certified") is False,
            "archived BLS pages are not independent hash-certified vintage bytes")
    g=e.get("governance")
    require(isinstance(g,dict) and
            g.get("model") == "SPARSE_EVENT_DESCRIPTIVE_LEVEL_ONLY" and
            type(g.get("training_window_previous_first_releases")) is int and
            g["training_window_previous_first_releases"] == 24 and
            g.get("previous_2025_10_cps_hole_imputed") is False and
            g.get("strict_monthly_macro_v2_still_fails_gap") is True and
            g.get("monthly_velocity_through_missing_period") is None and
            g.get("monthly_acceleration_through_missing_period") is None and
            g.get("current_2026_g8_macro_score_not_certified") is True and
            g.get("force_no_forex_strength") is True and
            g.get("live_data_promotion_allowed") is False and
            g.get("allow_backtest") is False and
            g.get("allow_pair_mutation") is False and
            g.get("safe_to_publish_new_D") is False and
            g.get("writes_live_data") is False,
            "research intensity may not become official current Macro/FX score")

    rows=e.get("first_release_values")
    require(isinstance(rows,list) and len(rows)==len(EXPECTED),
            "exactly nine 2026 BLS first-release headlines required")
    previous=timestamp(gap["resumed_first_releases"][-1]["released_at"])
    ny=ZoneInfo("America/New_York")
    for row,(period,when,value,url) in zip(rows,EXPECTED):
        require(isinstance(row,dict) and row.get("observation_period")==period and
                row.get("kind")=="FIRST" and type(row.get("value")) in (int,float) and
                math.isfinite(row["value"]) and
                (row["released_at"],row["value"],row["evidence_ref"]) ==
                (when,value,url),
                "BLS 2026 original headline value, date, or source drift")
        stamp=timestamp(row["released_at"])
        local=stamp.astimezone(ny)
        require(datetime.fromisoformat(row["released_at"]).utcoffset() ==
                local.utcoffset() and
                (local.hour,local.minute,local.second)==(8,30,0),
                "BLS original release violates 08:30 America/New_York/DST")
        require(urlparse(row["evidence_ref"]).hostname=="www.bls.gov" and
                row["evidence_ref"].endswith(
                    "empsit_"+local.strftime("%m%d%Y")+".htm"),
                "BLS archive URL must match original release date")
        require(stamp>previous,"first publications cannot be out of order")
        previous=stamp
    require(rows[-1]["observation_period"]=="2026-09" and
            rows[-1]["value"]==4.2 and
            timestamp(rows[-1]["released_at"]) ==
            timestamp(e["latest_observation_first_published_utc"]),
            "latest reference and release timestamp must match")


def replay(*,at: str,record: dict | None=None,
           pre_gap: dict | None=None,shutdown: dict | None=None) -> dict:
    """Versioned research-only cutoff; even one-second early means unavailable."""
    m=pre_gap if pre_gap is not None else read_fixture()
    g=shutdown if shutdown is not None else load_evidence()
    e=record if record is not None else evidence()
    validate(e,m,g)
    cutoff=timestamp(at)
    require(ASOF_FLOOR<=cutoff<=ASOF_CEILING,
            "the replay has no verified evidence after 23 Oct 2026")
    records=m["vintages"]+g["resumed_first_releases"]+e["first_release_values"]
    seen=set(); first=[]
    for row in records:
        period=row["observation_period"]
        require(period!="2025-10" and period not in seen and row["kind"]=="FIRST",
                "non-existent October 2025 release, duplicate period or revision")
        seen.add(period)
        first.append({
            "period":period,"period_index":period_index(period,"M"),
            "value":row["value"],"release_clock":timestamp(row["released_at"])
        })
    all_released=[row for row in first if row["release_clock"]<=cutoff]
    require(all(all_released[i+1]["period_index"]>all_released[i]["period_index"]
                for i in range(len(all_released)-1)),
            "release order/reference chronology broken")
    newer=[r for r in all_released if r["period"].startswith("2026-")]
    scenarios=[_snapshot(all_released,r,r["release_clock"]) for r in newer]
    last=scenarios[-1] if scenarios else None
    current=last is not None and last["reference_period"]=="2026-09"
    # The 24 FIRST releases preceding September 2026 straddle the 2025-10
    # absent CPS observation; the regular consecutive-calendar model is not
    # eligible to run even though the last few observation periods are adjacent.
    receipt={
        "schema":RECEIPT,
        "status":"DATED_BLS_2026_U3_RELEASES_SPARSE_EVENT_STUDY_ONLY",
        "as_of":cutoff.isoformat(),
        "currency":"USD","pillar":"labour","source_series_id":"LNS14000000",
        "fred_alias":"UNRATE",
        "original_2026_annual_first_release_count_verified":len(EXPECTED),
        "first_release_rows_visible_at_cutoff":len(all_released),
        "releases_2026_visible_at_cutoff":len(newer),
        "latest_reference_period":last["reference_period"] if last else None,
        "latest_released_at":last["first_published_at_utc"] if last else None,
        "latest_rate_first_release_percent":last["u3_first_release_percent"] if last else None,
        "latest_research_descriptive_labour_intensity":
            last["labour_tightness_descriptive_only"] if last else None,
        "nine_first_release_snapshots":scenarios,
        "has_2025_10_missing_CPS_observation":True,
        "October_2025_cps_value":None,
        "consecutive_month_normalizer_eligible":False,
        "calendar_month_velocity_through_gap":None,
        "calendar_month_acceleration_through_gap":None,
        "asof_contains_latest_released_2026_09":current,
        "source_evidence_archive_bytes_hashed":False,
        "independent_complete_revision_chain_certified":False,
        "no_new_macro_or_currency_score":True,
        "currency_strength_score":None,"FX_signal":None,
        "eligible_for_current_macro_scoring":False,
        "eligible_for_backtest":False,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "writes_live_data":False,
    }
    receipt["method_fingerprint_sha256"]=hashlib.sha256(json.dumps({
        "receipt":RECEIPT,"cutoff":receipt["as_of"],
        "events":[(x["period"],x["release_clock"].isoformat(),x["value"])
                  for x in all_released],
        "missing_gap":"2025-10","snapshots":scenarios,
    },sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return receipt


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--asof",default="2026-10-23T12:00:00Z")
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    result=replay(at=args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")),
                "research receipt must not be saved to a production path")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in (
        "as_of","latest_reference_period","latest_rate_first_release_percent",
        "latest_research_descriptive_labour_intensity",
        "safe_to_publish_new_D","eligible_for_backtest")},sort_keys=True))


if __name__=="__main__":
    main()
