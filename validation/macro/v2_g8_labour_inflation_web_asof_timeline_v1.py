#!/usr/bin/env python3
"""G8 inflation/labour issuer-web release timeline, strictly research-only.

Build *one* dated event ledger for all 16 candidate publisher streams using
already audited adapters and independent canonical registry entries. Replay
daily as-of UTC snapshots plus exact before/at-publication gates, preserving
first vs detailed/revised web values. Never convert observation months into
release timestamps; never treat a retrospective page as immutable original
release-day bytes. Candidate-to-canonical source mapping is NOT certified.

No longitudinal macro model or FX backtest is permitted by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_pit_g8_control_plane_v1 import (
    normalize, SOURCE_KINDS
)
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect

SCHEMA = "GMFQ_MACRO_V2_G8_LABOUR_INFLATION_ISSUER_WEB_ASOF_TIMELINE_V1"
COUNTRIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PILLARS = ("inflation", "labour")
REGISTRY = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"
DEFAULT_START = "2026-07-01"


def fail_if(condition, message):
    if not condition:
        raise ValueError("MACRO_V2_16_SOURCE_TIMELINE_REJECTED: " + message)


def iso_day(raw):
    fail_if(isinstance(raw, str), "explicit YYYY-MM-DD date required")
    return date.fromisoformat(raw)


def daily_end(day):
    return datetime.combine(day, time(23, 59, 59, 999999), tzinfo=timezone.utc)


def qualified_canonical(source, canonical):
    same_id = source["source_series_id"] == canonical["series_id"]
    same_frequency = source["frequency"] == canonical["frequency"]
    return {
        "source_id_matches_registry": same_id,
        "frequency_matches_registry": same_frequency,
        "series_and_frequency_match": same_id and same_frequency,
        "candidate_source_canonical_mapping_certified": False,
        "eligible_for_live_macro_score": False,
        "source_alignment": ("MATCHED_IDS_FREQUENCY_BUT_VINTAGE_NOT_CERTIFIED"
                             if same_id and same_frequency else
                             "CANDIDATE_NOT_IDENTICAL_TO_CORE_SOURCE"),
    }


def visible_candidates(events, cutoff):
    """Selection has exactly one time axis: the documented publisher gate."""
    fail_if(isinstance(events, list) and
            isinstance(cutoff, datetime) and cutoff.tzinfo is not None
            and cutoff.utcoffset() == timedelta(0),
            "UTC cutoff and publisher events required")
    return [x for x in events if timestamp(x["visible_from_utc"]) <= cutoff]


def asof_source(source, cutoff):
    """Pick the most recent economic period with a known INITIAL web statement.

    A revision to a previous period never becomes a new economic month.
    The first and last known values for the selected period are retained.
    """
    events = visible_candidates(source["all_documented_publication_events"], cutoff)
    first = [x for x in events if x["stage"] == "FIRST_WEB"]
    base = {
        "currency": source["currency"], "pillar": source["pillar"],
        "candidate_series_id": source["source_series_id"],
        "candidate_frequency": source["frequency"],
        "candidate_metric_unit": source["metric_unit"],
        "candidate_period_semantics": source["period_semantics"],
        "first_issuer_web_releases_seen": len(first),
        "all_issuer_web_events_seen": len(events),
        "complete_historical_first_day_bytes_verified": False,
        "historical_revision_chain_complete": False,
        "live_source_approved": False,
        "FX_score_eligible": False,
    }
    if not first:
        return {**base, "status": "NOT_YET_VISIBLE_IN_THIS_BOUNDED_PUBLISHER_LEDGER",
                "latest_reference_period": None, "first_web_value": None,
                "asof_known_value": None, "known_revision_count_for_latest": 0,
                "first_gate_utc": None, "last_gate_utc": None}
    latest_first = max(first, key=lambda e: e["reference_period_index"])
    period = latest_first["reference_period"]
    same_period = [x for x in events if x["reference_period"] == period]
    # Same period can have flash/detail/revision, possibly all later than the
    # latest first event: sort by actual *available* gate, not fixture order.
    latest = max(same_period, key=lambda e: timestamp(e["visible_from_utc"]))
    return {
        **base,
        "status": "OFFICIAL_WEB_CANDIDATE_VISIBLE_NOT_FULL_PIT_ARCHIVE",
        "latest_reference_period": period,
        "first_web_value": latest_first["reported_value"],
        "asof_known_value": latest["reported_value"],
        "known_revision_count_for_latest":
            sum(x["stage"] in ("DETAILED_WEB", "REVISION_WEB")
                for x in same_period),
        "first_gate_utc": latest_first["visible_from_utc"],
        "last_gate_utc": latest["visible_from_utc"],
        "first_source_url": latest_first["source_url"],
        "asof_source_url": latest["source_url"],
        "last_visible_publication_stage": latest["stage"],
        "selected_reference_period_is_release_period_not_current_calendar": True,
    }


def catalogue(raw_candidates, registry):
    fail_if(isinstance(registry, dict) and
            registry.get("schema") == "GMFQ_MACRO_SOURCE_REGISTRY_V1"
            and set(registry.get("series", {})) ==
            {f"{c}.{p}" for c in COUNTRIES for p in PILLARS},
            "exact G8 canonical 16-slot source registry expected")
    fail_if(isinstance(raw_candidates, list), "publisher source adapters missing")
    index = {}
    for raw in raw_candidates:
        stream = normalize(raw)  # existing publisher/semantic/source-clock guard
        key = f"{stream['currency']}.{stream['pillar']}"
        fail_if(key in registry["series"] and key not in index,
                "missing or repeated/foreign 16-slot issuer-web candidate")
        fail_if(stream.get("original_release_day_immutable_bytes_verified") is False and
                stream.get("complete_revision_history_verified") is False and
                stream.get("canonical_series_mapping_independently_certified") is False,
                "unapproved source PIT/canonical upgrade")
        index[key] = stream
    fail_if(set(index) == set(registry["series"]),
            "not all 16 G8 labour/inflation publication streams covered")
    return index


def check_event_boundaries(sources):
    """Every asserted historical release is absent at -1 microsecond."""
    tested = 0
    for key, stream in sources.items():
        ev = stream["all_documented_publication_events"]
        for e in ev:
            gate = timestamp(e["visible_from_utc"])
            before = visible_candidates(ev, gate - timedelta(microseconds=1))
            after = visible_candidates(ev, gate)
            selector = lambda rows: any(
                x is e for x in rows)
            fail_if(not selector(before) and selector(after),
                    "pre-release event leak at " + key)
            tested += 1
    return tested


def compile_timeline(registry, candidates, *, start=DEFAULT_START, end=None):
    begin = iso_day(start)
    finish = iso_day(end or datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    fail_if(finish >= begin and
            finish <= datetime.now(ZoneInfo("Europe/Rome")).date() and
            (finish - begin).days <= 450, "research daily replay horizon must be bounded")
    sources = catalogue(candidates, registry)
    boundary_count = check_event_boundaries(sources)
    full = {}
    for key, source in sources.items():
        canonical = registry["series"][key]
        full[key] = {
            "currency": source["currency"], "pillar": source["pillar"],
            "registered_core_series_id": canonical["series_id"],
            "registered_core_frequency": canonical["frequency"],
            "candidate_series_id": source["source_series_id"],
            "candidate_frequency": source["frequency"],
            "candidate_metric_unit": source["metric_unit"],
            "candidate_period_semantics": source["period_semantics"],
            "official_publisher": source["publisher"],
            "evidence_contract": source["evidence_contract"],
            "known_first_web_events_in_full_bounded_dossier":
                source["first_reference_months_total"],
            "known_stage_events_in_full_bounded_dossier":
                len(source["all_documented_publication_events"]),
            "missing_first_reference_periods_inside_dossier":
                source["missing_reference_periods_inside_candidate_range"],
            "claimed_archival_first_release_dataset_certified": False,
            **qualified_canonical(source, canonical),
        }
    snapshots = []
    for ordinal in range((finish - begin).days + 1):
        day = begin + timedelta(days=ordinal)
        rows = {}
        for key, src in sources.items():
            # This source ledger has a strict separation between availability
            # of evidence and the country/pillar canonical model.
            rows[key] = asof_source(src, daily_end(day))
        snapshots.append({"as_of_end_utc": daily_end(day).isoformat(),
                          "slots": rows})
    latest = snapshots[-1]["slots"]
    same = sum(x["series_and_frequency_match"] for x in full.values())
    visible = sum(x["first_web_value"] is not None for x in latest.values())
    first_total = sum(x["known_first_web_events_in_full_bounded_dossier"]
                      for x in full.values())
    results = {
        "schema": SCHEMA,
        "status": "16_WEB_RELEASE_STREAMS_TIME_GATED_NOT_HISTORIC_PIT_CERTIFIED",
        "window": {"start_day_utc": start, "end_day_utc": finish.isoformat(),
                   "daily_snapshots": len(snapshots),
                   "policy": "DOCUMENTED_SOURCE_EVENT_GATE_NOT_ECONOMIC_OBSERVATION_MONTH"},
        "source_catalogue": full,
        "daily_web_release_snapshots": snapshots,
        "current_latest_web_publisher_observations": latest,
        "summary": {
            "G8_currencies": 8, "inflation_labour_source_slots": len(full),
            "slots_with_candidate_publisher_web_research": len(full),
            "series_frequency_exact_candidate_matches": same,
            "candidate_source_mismatches_or_frequency_mismatches": 16 - same,
            "slots_with_visible_first_web_on_end_date": visible,
            "first_publisher_web_periods_in_bounded_dossiers": first_total,
            "independent_event_boundaries_checked": boundary_count,
            "joint_PIT_training_histories_certified": 0,
            "live_macro_scores_created": 0,
            "FX_backtests_performed": 0,
        },
        "observed_period_is_not_publication_day": True,
        "later_revisions_never_retroactively_substituted_into_earlier_snapshots": True,
        "matching_source_id_and_frequency_does_not_certify_first_release_archive": True,
        "official_web_pages_are_not_immutable_original_day_source_bytes": True,
        "cross_country_macro_currency_strength_rankings_forbidden": True,
        "historic_macro_snapshot_on_days_without_event_not_interpolated": True,
        "safe_to_publish_new_D": False, "safe_to_change_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False,
        "writes_live_data": False,
    }
    results["evidence_fingerprint_sha256"] = hashlib.sha256(json.dumps(
        {"catalogue": full, "daily": snapshots},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return results


def run(*, start=DEFAULT_START, end=None):
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return compile_timeline(registry, collect(), start=start, end=end)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None:
        fail_if(args.output.resolve().is_relative_to(Path("/tmp")),
                "research timeline must stay in /tmp")
    result = run(start=args.start, end=args.end)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps({"schema": result["schema"], **result["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
