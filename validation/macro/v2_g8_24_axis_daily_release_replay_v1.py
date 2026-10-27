#!/usr/bin/env python3
"""Macro V2 G8: longitudinal *release evidence*, NEVER a historical model backtest.

Replays every UTC calendar day in a bounded interval using the independently
validated 24-slot single-cutoff adapter. Original publisher web statements and
available-at-that-date revisions remain separate. This builds a factual
chronological *availability* series, not a complete 24-source original-release
PIT dataset; it never computes an FX score or rewrites D.json / 28 pairs.

Every entry is a first-web report documented in the research ledger. No
current-revised history may be presented as a previous day's known observation.
No interpolation on quiet days: carry-forward of the last known publication is
explicitly "unchanged evidence", not a new data point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from validation.macro.v2_g8_24_axis_asof_evidence_v1 import (
    FX, DIMENSIONS, REGISTRY, SCHEMA as SNAPSHOT_SCHEMA,
    parse_utc, source_snapshot
)
from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import (
    catalogue
)
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import archived_overlay
from validation.macro.v2_shadow_features_v1 import ROOT, timestamp

SCHEMA = "GMFQ_MACRO_V2_G8_24_AXIS_DAILY_ASOF_RELEASE_EVIDENCE_REPLAY_V1"
DEFAULT_START = "2026-07-01"
MAX_REPLAY_DAYS = 190


def require(ok, msg):
    if not ok:
        raise ValueError("MACRO_V2_G8_24_AXIS_DAILY_REPLAY_REJECTED: " + msg)


def day(raw):
    require(isinstance(raw, str) and len(raw) == 10 and
            date.fromisoformat(raw).isoformat() == raw,
            "calendar day must be YYYY-MM-DD")
    return date.fromisoformat(raw)


def utc_day_close(d):
    return datetime.combine(d, time(23, 59, 59, 999999), timezone.utc)


def economic_projection(full_snapshot):
    """Slim, factual state; no model outputs, ranks, nowcast or bad freshness."""
    require(full_snapshot["schema"] == SNAPSHOT_SCHEMA and
            full_snapshot["safe_to_publish_new_D"] is False and
            full_snapshot["safe_to_update_pair_theses"] is False and
            full_snapshot["summary"]["official_complete_PIT_training_slots"] == 0,
            "unapproved model validation/promotion in one-day source")
    result = {}
    for name, raw in full_snapshot["slots"].items():
        require(raw["model_score_authorized"] is False and
                raw["fx_signal_authorized"] is False and
                raw["complete_pit_training_history_verified"] is False,
                "unapproved FX/model score in source record")
        result[name] = {
            "reference_period": raw["reported_economic_period"],
            "first_web_value": raw["first_web_value"],
            "latest_value_revised_known_asof":
                raw["asof_value_latest_known_revision"],
            "first_web_gate_utc": raw["first_documented_web_gate_utc"],
            "source_url": raw["first_web_source_url"],
            "source_quality": raw.get("source_quality", "NO_WEB_SOURCE_VISIBLE"),
            "value_precision": raw.get("value_precision", "NOT_KNOWN"),
            "first_web_known_asof": raw["web_first_release_known_at_cutoff"],
            "canonical_series_id": raw["registered_canonical_series_id"],
            "canonical_frequency": raw["registered_canonical_frequency"],
            "official_web_candidate_id": raw.get("official_web_candidate_series_id"),
            "candidate_series_id_is_canonical":
                raw.get("canonical_id_frequency_exact_match"),
            "is_canonical_quarterly_AUD_not_monthly":
                raw.get("quarterly_abs_cpi_never_replaced_by_monthly_candidate"),
            "eur_membership_regime": raw.get("eurozone_membership"),
            "eur_24_prior_month_same_membership":
                raw.get("homogeneous_24_month_EA_membership_reference"),
            "chf_precision_interval_if_rounded":
                raw.get("compatible_exact_rate_interval_pct"),
            "source_PIT_historical_training_certified": False,
            "can_use_for_FX_ranking": False,
        }
    require(len(result) == 24, "exact 24 G8 economic slots required")
    return result


def _substantive(row):
    """Only source economic value/period, never decorative quality text."""
    return (row["reference_period"], row["first_web_value"],
            row["latest_value_revised_known_asof"],
            row["first_web_gate_utc"])


def _publisher_event_ledger(candidates, archival, gdp_rows, begin, end):
    """Independent issuer gate log, including revisions to older periods."""
    all_events = []
    for key, stream in candidates.items():
        for ev in stream["all_documented_publication_events"]:
            all_events.append({
                "slot": key, "stage": ev["stage"],
                "reference_period": ev["reference_period"],
                "publisher_gate_utc": ev["visible_from_utc"],
                "source_channel": "OFFICIAL_CANDIDATE_WEB_DOSSIER_NOT_CANONICAL_PIT",
                "value": ev["reported_value"],
                "source_url": ev["source_url"],
                "model_event": False,
            })
    for key, archive in archival["histories"].items():
        for ev in archive["events"]:
            all_events.append({
                "slot": key, "stage": "FIRST_WEB",
                "reference_period": ev["reference_period"],
                "publisher_gate_utc": ev["visible_from_utc"],
                "source_channel": "OFFICIAL_CANONICAL_FIRST_WEB_ARCHIVED_RESEARCH",
                "value": ev["reported_value"],
                "source_url": ev["source_url"],
                "original_source_sha256": ev["archived_source_sha256"],
                "model_event": False,
            })
    for item in gdp_rows:
        if item["stage_order"] != 0 and item["stage_order"] not in (1, 2, 3):
            require(False, "unknown GDP historical publisher stage")
        gate = (datetime.combine(date.fromisoformat(item["publisher_release_day"])
                + timedelta(days=1), time.min, timezone.utc)).isoformat()
        all_events.append({
            "slot": item["currency"] + ".growth",
            "stage": "FIRST_WEB" if item["stage_order"] == 0 else "REVISION_WEB",
            "reference_period": item["reference_quarter"],
            "publisher_gate_utc": gate,
            "source_channel": "OFFICIAL_GDP_WEB_STATEMENT_NOT_SOURCE_DAY_ARCHIVE",
            "value": item["reported_value"],
            "reported_unit": item["reported_unit"],
            "source_url": item["source_url"],
            "model_event": False,
        })
    all_events.append({
        "slot": "CHF.labour", "stage": "FIRST_WEB",
        "reference_period": "2026-09",
        "publisher_gate_utc": "2026-10-07T00:00:00+00:00",
        "source_channel": "OFFICIAL_SECO_ROUNDED_ALTERNATIVE_NOT_SNB_EXACT",
        "value": 3.1, "source_url":
            "https://www.konsum.admin.ch/it/newnsb/Cdju9-o8WGML",
        "model_event": False,
    })
    seen = set()
    filtered = []
    for ev in all_events:
        gate = timestamp(ev["publisher_gate_utc"])
        require(gate.tzinfo is not None and gate.utcoffset() == timedelta(0),
                "publisher event is not a real UTC gate")
        k = (ev["slot"], ev["source_channel"], ev["reference_period"], ev["stage"], gate)
        require(k not in seen, "duplicate economic publication stage")
        seen.add(k)
        if utc_day_close(begin) >= gate or gate > utc_day_close(end):
            continue
        filtered.append(ev)
    return sorted(filtered, key=lambda e: (
        timestamp(e["publisher_gate_utc"]), e["slot"],
        e["reference_period"], e["source_channel"]))


def replay(*, start=DEFAULT_START, end=None, source_candidates=None,
           GDP_rows=None, archive=None, registry=None):
    first = day(start)
    # Completed UTC days only. Today's live as-of snapshot is a separate
    # report; calling an unfinished day "23:59 UTC" would leak future data.
    now = datetime.now(timezone.utc)
    last = day(end or (now.date() - timedelta(days=1)).isoformat())
    require(last >= first and (last-first).days < MAX_REPLAY_DAYS and
            last < now.date(),
            "longitudinal replay must cover only completed UTC calendar days")
    catalogue_data = (registry if registry is not None else
                      json.loads(REGISTRY.read_text(encoding="utf-8")))
    raw_candidates = source_candidates if source_candidates is not None else collect()
    normalized = catalogue(raw_candidates, catalogue_data)
    raw_gdp = GDP_rows if GDP_rows is not None else unified_research_rows()
    raw_archive = archive if archive is not None else archived_overlay(
        as_of=utc_day_close(last).isoformat())
    event_log = _publisher_event_ledger(normalized, raw_archive, raw_gdp, first, last)
    observations = []
    prior = None
    for offset in range((last-first).days+1):
        current = first + timedelta(days=offset)
        cutoff = utc_day_close(current)
        snapshot = source_snapshot(
            cutoff=cutoff.isoformat(), registry=catalogue_data,
            source_candidates=raw_candidates,
            archival=raw_archive, growth_rows=raw_gdp)
        projection = economic_projection(snapshot)
        transitions = []
        if prior is not None:
            for key in projection:
                before, after = prior[key], projection[key]
                if _substantive(before) != _substantive(after):
                    when = after["first_web_gate_utc"]
                    # Revised values can change while the first gate remains
                    # unchanged. The independent ledger proves there was an
                    # official event ON that day, not necessarily that every
                    # source has a full revision chain.
                    events = [e for e in event_log
                              if e["slot"] == key and
                              timestamp(e["publisher_gate_utc"]).date() == current]
                    change_kind = ("NEW_FIRST_WEB_REFERENCE_PERIOD"
                                   if before["reference_period"] != after["reference_period"]
                                   else "KNOWN_LATEST_REFERENCE_REVISION_OR_RESEARCH_VALUE")
                    require(events or (key == "CHF.labour" and current == date(2026,10,7)),
                            "source value changed on day without recorded official publisher gate: " + key)
                    transitions.append({
                        "slot": key, "kind": change_kind,
                        "previous_reference_period": before["reference_period"],
                        "next_reference_period": after["reference_period"],
                        "previous_value": before["first_web_value"],
                        "next_value": after["first_web_value"],
                        "previous_latest_known_revision":
                            before["latest_value_revised_known_asof"],
                        "next_latest_known_revision":
                            after["latest_value_revised_known_asof"],
                        "recorded_source_events_that_day": [
                            {"stage": e["stage"], "channel": e["source_channel"],
                             "publisher_gate_utc": e["publisher_gate_utc"]}
                            for e in events],
                        "not_a_causal_event_FX_claim": True,
                    })
        visible = sum(x["first_web_known_asof"] for x in projection.values())
        country_visible = {c: sum(
            projection[f"{c}.{pillar}"]["first_web_known_asof"]
            for pillar in DIMENSIONS) for c in FX}
        require(all(0 <= v <= 3 for v in country_visible.values()),
                "invalid country research coverage")
        observations.append({
            "as_of_day_utc": current.isoformat(),
            "as_of_end_utc": cutoff.isoformat(),
            "24_slots_latest_known_source": projection,
            "visible_latest_first_web_slots": visible,
            "not_documented_first_web_slots":
                sorted(k for k, v in projection.items() if not v["first_web_known_asof"]),
            "visible_axes_by_currency": country_visible,
            "publisher_gate_driven_changes_from_prior_day": transitions,
            "days_without_new_first_web_or_latest_revision":
                prior is not None and len(transitions) == 0,
            "unchanged_values_are_CARRIED_VISIBLE_EVIDENCE_not_interpolated_new_data": True,
            "no_joint_PIT_macro_training_certification": True,
        })
        prior = projection
    require(len(observations) == (last-first).days+1 and
            all(x["24_slots_latest_known_source"]["CHF.labour"]
                ["source_PIT_historical_training_certified"] is False
                for x in observations), "daily 24 source evidence drift")
    res = {
        "schema": SCHEMA, "status": "RESEARCH_DAILY_G8_24_AXIS_WEB_RELEASE_EVIDENCE_NO_PIT_BACKTEST",
        "window": {"start": first.isoformat(), "end": last.isoformat(),
                   "daily_cuts": len(observations), "cut_utc": "23:59:59.999999",
                   "latest_incomplete_UTC_day_excluded": True},
        "daily_evidence_snapshots": observations,
        "official_candidate_and_archived_release_gates": event_log,
        "summary": {
            "G8_currencies": len(FX), "economic_slots_per_day": 24,
            "source_evidence_days": len(observations),
            "first_day_source_slots_visible": observations[0]["visible_latest_first_web_slots"],
            "last_day_source_slots_visible": observations[-1]["visible_latest_first_web_slots"],
            "days_with_issuer_gated_changes": sum(
                bool(d["publisher_gate_driven_changes_from_prior_day"])
                for d in observations),
            "total_current_reference_changes": sum(
                len(d["publisher_gate_driven_changes_from_prior_day"])
                for d in observations),
            "issuer_release_events_in_bounded_period": len(event_log),
            "24_axis_joint_original_vintage_training_days_certified": 0,
            "FX_out_of_sample_tests": 0, "macro_model_scores_approved": 0,
            "pair_rankings_reshuffled": 0,
        },
        "original_publication_day_source_bytes_independently_certified": False,
        "source_event_attestations_not_complete_revision_history": True,
        "quarterly_monthly_reference_periods_may_differ_on_same_cutoff": True,
        "limited_bounded_web_evidence_is_not_24_long_PIT_model_training_histories": True,
        "carry_forward_is_only_LAST_KNOWN_RELEASE_not_economic_estimation": True,
        "never_fit_macro_weights_from_old_D_json": True,
        "safe_to_publish_new_D": False, "safe_to_update_pair_theses": False,
        "safe_for_beta": False, "safe_for_forward": False, "writes_live_data": False,
    }
    res["receipt_sha256"] = hashlib.sha256(json.dumps(
        {"window": res["window"], "days": observations,
         "event_gates": event_log}, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return res


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--start", default=DEFAULT_START)
    arg.add_argument("--end")
    arg.add_argument("--output", type=Path)
    opts = arg.parse_args()
    if opts.output:
        require(opts.output.resolve().is_relative_to(Path("/tmp")),
                "research artifact must be under /tmp only")
    out = replay(start=opts.start, end=opts.end)
    if opts.output:
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(json.dumps(out, ensure_ascii=False,
                                         indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "status": out["status"],
                      **out["summary"], "safe_to_publish_new_D": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
