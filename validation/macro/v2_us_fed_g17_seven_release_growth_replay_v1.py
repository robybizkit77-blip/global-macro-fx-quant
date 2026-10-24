#!/usr/bin/env python3
"""2026 Fed G.17 total industrial production: 7 actual dated-publisher tables.

The March–September *first preliminary published rounded* G.17 index values
are one-per-observation; later dated G.17 tables show changes in the SAME
earlier observation months. We replay these vintages as-of original publisher
scheduled 09:15 EDT release instants (Fed calendar). Dated webpages as served
today are NOT immutable page bytes captured on their original release date.
The source's 0.1 index precision cannot be silently equated to exact INDPRO.

Strict research-only; no automatic source acquisition, FX model, live feeds,
PIT-trained normalizer or historical score approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp, period_index
from validation.macro.v2_g8_growth_transform_proposal_gate_v1 import (
    FILE as PROPOSALS_FILE, shadow_math,
)

SCHEMA="GMFQ_MACRO_V2_US_FED_G17_SEVEN_DATED_PUBLISHER_TABLE_SNAPSHOTS_V1"
FILE=ROOT/"validation/macro/fixtures/v2_us_fed_g17_seven_dated_total_ip_2026_v1.json"
FIRST_PERIODS=("2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09")
# Pinned independently from the publisher-dated G17 HTML row "Total index"
# rather than trusting changing fixture values as source of truth.
TABLE_ROWS=(
    ("2026-04-16","2026-03",(101.8,)),
    ("2026-05-15","2026-04",(101.8,102.5)),
    ("2026-06-15","2026-05",(101.6,102.5,102.6)),
    ("2026-07-17","2026-06",(101.6,102.4,102.6,102.6)),
    ("2026-08-18","2026-07",(101.8,102.5,102.5,102.8,103.0)),
    ("2026-09-18","2026-08",(101.7,102.6,102.6,102.8,103.0,103.1)),
    # The October 16 publisher table starts at Apr 2026; the earlier March
    # figure is not erased from our September publisher-asof evidence.
    ("2026-10-16","2026-09",(102.6,102.7,103.0,103.2,103.3,104.0)),
)


def validate(fixture):
    require(isinstance(fixture,dict) and fixture.get("schema")==SCHEMA
            and fixture.get("review_as_of")=="2026-10-24"
            and fixture.get("publisher")=="Federal Reserve Board"
            and fixture.get("metric")=="Seasonally adjusted industrial production Total index"
            and fixture.get("unit")=="index 2017=100 rounded to 1 decimal by dated G.17 HTML summary"
            and fixture.get("observation_series_candidate_id")==
              "US_G17_IP_2017_BASE_PUBLISHED_ONE_DECIMAL",
            "G.17 industrial production source/metric/base or fixture version drift")
    require(fixture.get("canonical_G8_growth_series_selected") is False
            and fixture.get("archived_release_day_original_page_bytes_verified") is False
            and fixture.get("publisher_dated_pages_retrieved_after_publication_not_immutable_release_day_bytes") is True
            and fixture.get("exact_unrounded_original_indpro_transport_verified") is False
            and fixture.get("complete_historical_revision_chain_certified") is False
            and fixture.get("research_only") is True,
            "web-dated G17 observations cannot self certify immutable PIT input")
    snaps=fixture.get("snapshots")
    require(isinstance(snaps,list) and len(snaps)==7,
            "seven monthly original Fed G17 publisher tables required")
    timeline=[]
    for idx,(s,(release,first,values)) in enumerate(zip(snaps,TABLE_ROWS)):
        expected_periods=FIRST_PERIODS[:idx+1] if idx<6 else FIRST_PERIODS[1:]
        got=s.get("total_index_sa_2017_100_by_observation_period")
        require(isinstance(got,dict) and list(got)==list(expected_periods)
                and list(got.values())==list(values)
                and all(type(v) in (int,float) and v>0
                        and round(v,1)==v for v in got.values()),
                "official published Total index rounded one-decimal row altered: "+release)
        url="https://www.federalreserve.gov/releases/g17/"+release.replace("-","")+"/table0.htm"
        assert_url=urlsplit(s.get("publisher_url",""))
        require(assert_url.scheme=="https"
                and assert_url.hostname=="www.federalreserve.gov"
                and assert_url.path.lower()==urlsplit(url).path.lower()
                and not assert_url.username and not assert_url.password
                and not assert_url.query and not assert_url.fragment
                and s.get("publisher_url")==url,
                "official date-specific Federal Reserve source URL changed")
        utc=release+"T13:15:00Z"
        local=release+"T09:15:00-04:00"
        require(s.get("release_date")==release
                and s.get("new_preliminary_period")==first
                and s.get("release_clock_et")==local
                and s.get("release_utc")==utc
                and timestamp(local)==timestamp(utc)
                and date.fromisoformat(release).year==2026,
                "Federal Reserve G17 scheduled 9:15 EDT release clock drift")
        require(s.get("source_table")==
                "G.17 Summary | Industrial production | Total index | first six monthly levels, 2017=100, SA"
                and s.get("all_table_values_from_dated_publisher_page_not_first_releases") is True,
                "publisher latest table's older revised values are NOT new first-releases")
        timeline.append((utc,first,got,url))
    return timeline


def build_events(timeline):
    events=[]
    last={}
    first_seen=set()
    for utc,new_period,observations,url in timeline:
        require(new_period not in first_seen,
                "duplicate first event for same economic reference month")
        for period,value in observations.items():
            require(period_index(period,"M")<=period_index(new_period,"M"),
                    "future economic period included in older publisher table")
            if period not in first_seen:
                require(period==new_period,
                        "older reported month cannot be labeled first after unseen original")
                kind="FIRST_WEB"
                first_seen.add(period)
            elif last[period]!=value:
                kind="REVISION_WEB"
            else:
                continue
            events.append({
                "reference_period":period,"kind":kind,
                "published_at_utc":utc,
                "value":value,
                "official_publisher_url":url,
            })
            last[period]=value
    require(tuple(sorted(first_seen))==FIRST_PERIODS,
            "exactly seven first-preliminary Fed IP months required")
    require(len(events)==20
            and sum(e["kind"]=="FIRST_WEB" for e in events)==7
            and sum(e["kind"]=="REVISION_WEB" for e in events)==13,
            "original Fed seven first + thirteen value-changing subsequent publisher statements required")
    return events


def read_fixture():
    return json.loads(FILE.read_text(encoding="utf-8"))


def research_proposal():
    r=json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
    rows=[x for x in r.get("feature_proposals",[]) if x.get("currency")=="USD"]
    require(len(rows)==1 and rows[0].get("observed_series_id")==
            "US_INDPRO_history_value" and rows[0].get("proposal_transform")=="LEVEL_3M3M"
            and rows[0].get("canonical_growth_source_selected") is False
            and rows[0].get("training_window_certified") is False,
            "US GDP Growth canonical source or 3m3m definition unexpectedly changed")
    return rows[0]


def replay(as_of, fixture=None):
    if fixture is None:
        fixture=read_fixture()
    tl=validate(fixture)
    events=build_events(tl)
    cutoff=timestamp(as_of)
    visible=[e for e in events if timestamp(e["published_at_utc"])<=cutoff]
    # Do not equate older revised report cells to *new* economic months.
    first=[e for e in visible if e["kind"]=="FIRST_WEB"]
    revised=[e for e in visible if e["kind"]=="REVISION_WEB"]
    known={}
    for e in visible:
        known[e["reference_period"]]=e["value"]
    feat=shadow_math(research_proposal(),[
        {k:e[k] for k in ("reference_period","kind","published_at_utc","value")}
        for e in events
    ],as_of=as_of)
    first_only=shadow_math(research_proposal(),[
        {k:e[k] for k in ("reference_period","kind","published_at_utc","value")}
        for e in events if e["kind"]=="FIRST_WEB"
    ],as_of=as_of)
    if feat["research_feature_percent"] is not None:
        require(len(first)>=6 and len(feat["underlying_periods_in_formula"])==6,
                "3m3m requires six actual visible source observation months")
    result={
        "schema":"GMFQ_MACRO_V2_US_FED_G17_SEVEN_PUBLISHER_VINTAGES_ASOF_REPLAY_V1",
        "as_of_utc":cutoff.isoformat(),
        "source":"Federal Reserve Board G.17 dated publisher Total index table",
        "unit":"2017=100 SA index as reported to ONE decimal",
        "first_months_in_full_dossier":7,
        "distinct_first_economic_months_visible":len(first),
        "value_changing_revisions_visible":len(revised),
        "first_visible_month":first[0]["reference_period"] if first else None,
        "latest_first_published_reference_month":
            first[-1]["reference_period"] if first else None,
        "asof_last_reported_rounded_levels_by_month":{
            p:known[p] for p in sorted(known)},
        "asof_value_changing_revision_events":[{
            "reference_period":e["reference_period"],"value":e["value"],
            "released_at_utc":e["published_at_utc"],"source_url":e["official_publisher_url"],
        } for e in revised],
        "growth_3m3m_asof_revised_publisher_rounded_pct":
            feat["research_feature_percent"],
        "growth_3m3m_only_first_rounded_publication_pct":
            first_only["research_feature_percent"],
        "growth_3m3m_status":feat["status"],
        "source_current_dated_pages_not_original_day_hashed_archive":True,
        "source_rounded_one_decimal_not_unrounded_INDPRO":True,
        "has_source_asof_archived_monthly_revision_claims_but_not_full_historical_PIT":True,
        "g8_growth_training_first_releases_target":25,
        "source_first_releases_short_of_25":18,
        "prior_frozen_feature_training_history_ready":False,
        "no_historical_normalized_zscore":True,
        "source_has_complete_25month_first_release_history":False,
        "publisher_original_release_day_bytes_hash_verified":False,
        "canonical_growth_series_mapping_certified":False,
        "model_growth_score_permitted":False,"fx_pair_ranking_permitted":False,
        "safe_to_publish_new_D":False,"writes_live_data":False,
        "fixture_sha256_as_reviewed_today_not_publish_day":
            hashlib.sha256(json.dumps(fixture,sort_keys=True,
                separators=(",",":")).encode()).hexdigest(),
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-24T00:00:00Z")
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    r=replay(a.asof)
    if a.out is not None:
        require(a.out.resolve().is_relative_to(Path("/tmp")),
                "research replay outputs restricted to /tmp")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "asof":r["as_of_utc"],"first_releases":r["distinct_first_economic_months_visible"],
        "revisions":r["value_changing_revisions_visible"],
        "research_3m3m":r["growth_3m3m_asof_revised_publisher_rounded_pct"],
        "safe_to_publish_new_D":False,
    }))


if __name__=="__main__":
    main()
