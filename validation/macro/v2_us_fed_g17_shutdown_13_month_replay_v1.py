#!/usr/bin/env python3
"""Fed G17 fall-2025 shutdown to Sep-2026: source-edition vintage replay.

Publisher-dated G17 HTML release tables were checked on 2026-10-24; this
cannot prove the source HTML bytes were archived on the release days.

The 2025 G17 disruption is NOT a normal monthly release calendar:
  - September 2025 was initially published 2025-12-03, 09:15 EST.
  - October AND November 2025 were first published together 2025-12-23.
Neither October nor November is invented as a Nov 18/Dec 16 event.
Data is rounded one decimal in official dated summary row and cannot
silently replace unrounded present-day INDPRO source transport.

Only selected period cells with FIRST publisher release provenance are used;
older periods appearing in a later table can change but do NOT count again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp, period_index
from validation.macro.v2_g8_growth_transform_proposal_gate_v1 import shadow_math
from validation.macro.v2_us_fed_g17_seven_release_growth_replay_v1 import (
    research_proposal, replay as seven_replay,
)

SOURCE=ROOT/"validation/macro/fixtures/v2_us_fed_g17_2025_shutdown_2026_12_editions_v1.json"
SCHEMA="GMFQ_MACRO_V2_US_FED_G17_SHUTDOWN_AND_2026_TWELVE_DATED_EDITION_SOURCE_TABLES_V1"

# Independently pinned source-page facts, separate from JSON evidence.
# Format: publisher edition date, FIRST newly released economic months,
# total-index (period, rounded one-decimal value) in the named G17 table.
PINNED=(
 ("2025-12-03",("2025-09",),(
    ("2025-09",101.4),)),
 ("2025-12-23",("2025-10","2025-11"),(
    ("2025-09",101.7),("2025-10",101.6),("2025-11",101.8))),
 ("2026-01-16",("2025-12",),(
    ("2025-09",101.8),("2025-10",101.5),("2025-11",102.0),("2025-12",102.3))),
 ("2026-02-18",("2026-01",),(
    ("2025-09",101.7),("2025-10",101.3),("2025-11",101.4),
    ("2025-12",101.6),("2026-01",102.3))),
 ("2026-03-16",("2026-02",),(
    ("2025-09",101.7),("2025-10",101.2),("2025-11",101.4),
    ("2025-12",101.7),("2026-01",102.4),("2026-02",102.6))),
 ("2026-04-16",("2026-03",),(
    ("2025-10",101.2),("2025-11",101.1),("2025-12",101.6),
    ("2026-01",101.6),("2026-02",102.3),("2026-03",101.8))),
 ("2026-05-15",("2026-04",),(
    ("2025-11",101.0),("2025-12",101.5),("2026-01",101.5),
    ("2026-02",102.1),("2026-03",101.8),("2026-04",102.5))),
 ("2026-06-15",("2026-05",),(
    ("2025-12",101.5),("2026-01",101.1),("2026-02",101.9),
    ("2026-03",101.6),("2026-04",102.5),("2026-05",102.6))),
 ("2026-07-17",("2026-06",),(
    ("2026-01",101.0),("2026-02",101.9),("2026-03",101.6),
    ("2026-04",102.4),("2026-05",102.6),("2026-06",102.6))),
 ("2026-08-18",("2026-07",),(
    ("2026-02",101.9),("2026-03",101.8),("2026-04",102.5),
    ("2026-05",102.5),("2026-06",102.8),("2026-07",103.0))),
 ("2026-09-18",("2026-08",),(
    ("2026-03",101.7),("2026-04",102.6),("2026-05",102.6),
    ("2026-06",102.8),("2026-07",103.0),("2026-08",103.1))),
 ("2026-10-16",("2026-09",),(
    ("2026-04",102.6),("2026-05",102.7),("2026-06",103.0),
    ("2026-07",103.2),("2026-08",103.3),("2026-09",104.0))),
)
PERIODS=tuple(f"{y:04d}-{m:02d}" for y,m in
    [(2025,m) for m in range(9,13)]+[(2026,m) for m in range(1,10)])


def load():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def validate(data):
    require(isinstance(data,dict) and data.get("schema")==SCHEMA
            and data.get("reviewed_at")=="2026-10-24"
            and data.get("metric")==
               "Federal Reserve G17 industrial production TOTAL index SA 2017=100 published one decimal"
            and data.get("source_precision_decimals")==1
            and data.get("official_dated_publisher_webpage_attestation") is True
            and data.get("historical_publish_day_source_bytes_archived_and_verified") is False
            and data.get("canonical_unrounded_US_INDPRO_history_value_matched") is False
            and data.get("historical_full_PIT_certified") is False
            and data.get("model_score_eligible") is False
            and "October and November both first released December 23 2025"
               in data.get("release_context",""),
            "2025 shutdown G17 evidence, rounded metric or PIT limitations drift")
    editions=data.get("release_editions")
    require(isinstance(editions,list) and len(editions)==12,
            "12 actual source-edition dates required, not 13 synthetic report dates")
    out=[]
    total_cells=0
    first_periods=[]
    for edition,(day,firsts,rows) in zip(editions,PINNED):
        expected_offset="-05:00" if day in (
            "2025-12-03","2025-12-23","2026-01-16","2026-02-18"
        ) else "-04:00"
        expected_utc=("14:15:00" if expected_offset=="-05:00" else "13:15:00")
        local=f"{day}T09:15:00{expected_offset}"
        utc=f"{day}T{expected_utc}Z"
        url=f"https://www.federalreserve.gov/releases/g17/{day.replace('-','')}/table0.htm"
        got=edition.get("total_index_sa_2017_100_rounded_table_subset")
        expected=dict(rows)
        require(isinstance(got,dict) and list(got)==list(expected)
                and list(got.values())==list(expected.values())
                and all(type(value) in (int,float) and value>0 and
                        round(value,1)==value for value in got.values()),
                "publisher summary table total index value/period/order changed: "+day)
        require(edition.get("date")==day
                and edition.get("publisher_release_local")==local
                and edition.get("release_utc")==utc
                and timestamp(local)==timestamp(utc)
                and edition.get("official_url")==url
                and edition.get("new_preliminary_economic_periods")==list(firsts)
                and edition.get("historical_table_older_month_cells_are_revision_stage_not_first_release") is True,
                "original published release time, URL or first-month sequence drift: "+day)
        url_data=urlsplit(url)
        require(url_data.hostname=="www.federalreserve.gov" and
                url_data.scheme=="https" and not url_data.query and not url_data.fragment,
                "publisher domain is not the Federal Reserve")
        # All observed cells on a given table cannot be later than the last
        # economic period first released by that edition.
        require(max(period_index(p,"M") for p in got)<=
                max(period_index(p,"M") for p in firsts),
                "new economic month appears before first official release")
        total_cells+=len(rows)
        first_periods.extend(firsts)
        out.append({"day":day,"utc":utc,"new_first_periods":firsts,
                    "rows":got,"url":url})
    require(total_cells==61 and tuple(first_periods)==PERIODS,
            "13 contiguous first-release months and 61 original publisher table cells required")
    require([x["day"] for x in out[:2]]==["2025-12-03","2025-12-23"]
            and out[1]["new_first_periods"]==("2025-10","2025-11"),
            "shutdown delayed October and November must share one publisher event")
    return out


def build_events(editions):
    last={}
    first=set()
    events=[]
    for release in editions:
        expected=set(release["new_first_periods"])
        seen_first=set()
        for p,value in release["rows"].items():
            if p not in first:
                require(p in expected,
                        "cannot claim late edition's already-existing older month as first release")
                kind="FIRST_WEB"
                first.add(p)
                seen_first.add(p)
            elif value != last[p]:
                kind="REVISION_WEB"
            else:
                continue
            events.append({
                "reference_period":p,"kind":kind,
                "published_at_utc":release["utc"],"value":value,
                "official_publisher_url":release["url"],
            })
            last[p]=value
        require(seen_first==expected,
                "one publisher edition first published a different set of months than documented")
    require(tuple(sorted(first))==PERIODS
            and len(events)==48
            and sum(e["kind"]=="FIRST_WEB" for e in events)==13
            and sum(e["kind"]=="REVISION_WEB" for e in events)==35,
            "first-release/revision event accounting changed, including shutdown double-first")
    return events


def calculate(as_of,events):
    raw=[{k:x[k] for k in ("reference_period","kind","published_at_utc","value")}
         for x in events]
    r=shadow_math(research_proposal(),raw,as_of=as_of)
    original=shadow_math(research_proposal(),[
        e for e in raw if e["kind"]=="FIRST_WEB"],as_of=as_of)
    return r,original


def replay(as_of, data=None):
    if data is None:
        data=load()
    editions=validate(data)
    events=build_events(editions)
    cutoff=timestamp(as_of)
    visible=[e for e in events if timestamp(e["published_at_utc"])<=cutoff]
    first=[e for e in visible if e["kind"]=="FIRST_WEB"]
    revisions=[e for e in visible if e["kind"]=="REVISION_WEB"]
    current={}
    for event in visible:
        current[event["reference_period"]]=event["value"]
    latest,prelim=calculate(as_of,events)
    # Freeze features at each original publisher-edition cutoff. NEVER refit
    # historical feature cutoffs using later revisions.
    frozen=[]
    for edition in editions:
        if timestamp(edition["utc"])>cutoff:
            break
        value,_=calculate(edition["utc"],events)
        if value["research_feature_percent"] is not None:
            frozen.append({
                "publisher_released_at_utc":timestamp(edition["utc"]).isoformat(),
                "latest_reference_period":value["latest_period_known"],
                "feature_3m3m_from_rounding_and_asof_known_revisions_pct":
                    value["research_feature_percent"],
                "frozen_at_own_publisher_cutoff_not_recomputed_later":True,
            })
    require(len(first)<=13 and len(revisions)<=35,
            "source release accounting exceeds verified evidence")
    baseline=None
    if cutoff>=timestamp("2026-09-18T13:15:00Z"):
        # Existing March–September dated publisher tables remain a separately
        # audited comparable six-month 3m/3m window; the extended dossier must
        # reproduce them exactly (without assuming all earlier months have 25
        # separate vintage source reports).
        baseline=seven_replay(as_of)
        for key,new in (
            ("growth_3m3m_asof_revised_publisher_rounded_pct",
             latest["research_feature_percent"]),
            ("growth_3m3m_only_first_rounded_publication_pct",
             prelim["research_feature_percent"]),
        ):
            prior=baseline[key]
            if prior is not None:
                require(new is not None and abs(new-prior)<1e-12,
                        "extended 13-month source vintage replay disagrees with prior 7-month pilot")
    return {
        "schema":"GMFQ_MACRO_V2_US_FED_G17_2025_SHUTDOWN_13_FIRST_MONTH_PIT_RESEARCH_V1",
        "as_of_utc":cutoff.isoformat(),
        "source_editions_in_verified_dossier":len(editions),
        "source_last_calendar_edition":editions[-1]["day"],
        "first_periods_in_full_dossier":13,
        "first_periods_visible":len(first),
        "revised_source_value_events_visible":len(revisions),
        "first_publications_with_shared_release_day":[
            {"release_day":"2025-12-23",
             "economic_reference_months":["2025-10","2025-11"],
             "publisher_time_utc":"2025-12-23T14:15:00+00:00",
             "normal_november_december_release_schedule_was_delayed":True,
            }
        ],
        "first_periods_missing_to_research_minimum_25":12,
        "last_first_economic_month_visible":first[-1]["reference_period"] if first else None,
        "asof_known_publisher_rounded_2017_index_levels":{
            p:current[p] for p in sorted(current)},
        "asof_last_known_3m3m_rounded_pct":latest["research_feature_percent"],
        "asof_initial_first_release_3m3m_rounded_pct":prelim["research_feature_percent"],
        "latest_feature_status":latest["status"],
        "frozen_asof_release_features":frozen,
        "source_one_decimal_is_not_current_four_decimal_INDPRO":True,
        "official_webpages_checked_later_not_original_day_archive_bytes":True,
        "full_25month_original_release_PIT_chain_ready":False,
        "valid_25_previous_feature_vintages_for_rolling_z":False,
        "unobserved_pre_2025_september_source_first_release_values_not_backfilled":True,
        "no_automatic_updating_old_frozen_features_after_later_releases":True,
        "historical_publisher_edition_receipt_sha_today_not_original_day_hash":
            hashlib.sha256(json.dumps(data,sort_keys=True,
                separators=(",",":")).encode()).hexdigest(),
        "canonical_G8_growth_series_source_mapping_certified":False,
        "model_score_permitted":False,
        "fx_pair_rank_change_permitted":False,
        "backtest_permitted":False,
        "safe_to_publish_new_D":False,"writes_live_data":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-24T00:00:00Z")
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    result=replay(a.asof)
    if a.out:
        require(a.out.resolve().is_relative_to(Path("/tmp")),
                "research receipt destination must stay under /tmp")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "first_periods":result["first_periods_visible"],
        "revisions":result["revised_source_value_events_visible"],
        "asof_3m3m":result["asof_last_known_3m3m_rounded_pct"],
        "safe_to_publish_new_D":False,
    }))


if __name__=="__main__":
    main()
