#!/usr/bin/env python3
"""V9: first runner-observed *metric-specific secondary forecasts* before release.

This is a research-only, append-only evidence register. A Fair Economy label
matched to a series is not proof of the publisher's original forecast vintage,
survey composition, economic seasonal adjustment or market consensus.
No actuals, surprises, causal claims, OIS repricing or FX signals are created.
The two legacy USD/CAD signed event ledgers are not modified.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from validation.macro.freeze_pre_release_consensus_v1 import (
    digest, exact_event_key, parse_forecast, scheduled, utc_iso, utc_text,
)
from validation.macro.g8_metric_issuer_contract_v8 import (
    interpret_provider_label, verify_contract,
)

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json"
SOURCE = ROOT / "live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json"
LEDGER = ROOT / "validation/macro/MACRO_EXACT_METRIC_FORECAST_FIRST_SEEN_V9.jsonl"
SCHEMA = "GMFQ_G8_METRIC_SECONDARY_FORECAST_FIRST_RUNNER_OBSERVATION_V9"
PROVIDER = "FOREX_FACTORY_FAIR_ECONOMY_WEEKLY"
ENDPOINT = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
STATUS = "LABEL_MATCHED_UNFROZEN_SECONDARY_NOT_ACCEPTED"


def ensure(condition, message):
    if not condition:
        raise ValueError("METRIC_FORECAST_V9_REJECTED: " + message)


def validate_existing(rows):
    ensure(isinstance(rows, list), "ledger rows must be a list")
    previous = "GENESIS"
    seen = set()
    for row in rows:
        ensure(isinstance(row, dict) and row.get("schema") == SCHEMA,
               "unexpected historical record schema")
        sha = row.get("record_sha256")
        ensure(isinstance(sha, str) and len(sha) == 64 and
               sha == digest({k: v for k, v in row.items() if k != "record_sha256"}),
               "ledger row digest mismatch")
        ensure(row.get("previous_record_sha256") == previous,
               "ledger hash chain mismatch")
        identity = (row.get("event_key"), row.get("metric_id"))
        ensure(all(isinstance(x, str) and x for x in identity) and identity not in seen,
               "metric first-seen record duplicated")
        seen.add(identity)
        before = utc_iso(row.get("official_release_scheduled_utc"))
        captured = utc_iso(row.get("captured_at_utc"))
        generated = utc_iso(row.get("source_feed_fetched_at_utc"))
        ensure(generated <= captured < before,
               "forecast not first captured before scheduled release")
        ensure(row.get("source_provider") == PROVIDER and
               row.get("source_endpoint") == ENDPOINT and
               row.get("source_field") == "forecast" and
               row.get("publisher_original_forecast_timestamp_verified") is False,
               "source provenance not explicitly limited")
        ensure(row.get("quality") ==
               "SECONDARY_EXACT_LABEL_RUNNER_OBSERVED_NOT_SURVEY_CERTIFIED" and
               row.get("candidate_series_identity_not_issuer_attested") is True,
               "unverified provider series must not be certified")
        ensure(row.get("actual") is None and row.get("surprise") is None and
               row.get("FX_signal") is None and
               row.get("eligible_for_live_model") is False and
               row.get("eligible_for_macro_surprise") is False and
               row.get("eligible_for_event_causality") is False,
               "forecast record promoted into unsupported inference")
        ensure(row.get("forecast_value_percent") ==
               parse_forecast(row.get("provider_forecast_original")),
               "forecast value inconsistent with original provider text")
        previous = sha
    return previous, seen


def freeze(official, feed, existing, captured_at):
    now = utc_iso(captured_at) if isinstance(captured_at, str) else captured_at
    ensure(isinstance(now, datetime) and now.tzinfo is not None and
           now.utcoffset() is not None, "capture time must be aware")
    now = now.astimezone(timezone.utc)
    ensure(official.get("schema") == "GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1",
           "official seed schema unexpected")
    verify_contract(official)
    ensure(feed.get("schema") == "GMFQ_MACRO_CONSENSUS_SECONDARY_V1" and
           feed.get("provider") == PROVIDER and
           feed.get("provider_endpoint") == ENDPOINT and
           feed.get("provider_field") == "forecast" and
           feed.get("rules", {}).get("metric_candidates_not_frozen_and_never_promoted") is True and
           feed.get("rules", {}).get("actual_not_used_as_pre_release_consensus") is True,
           "source is not the existing V8 non-official forecast feed")
    generated = utc_iso(feed.get("generated_at_utc"))
    ensure(generated <= now, "feed snapshot generated after capture clock")
    candidates = feed.get("metric_candidates_research_v8")
    ensure(isinstance(candidates, list), "metric candidate list missing")
    by_event = {exact_event_key(e): e for e in official["events"]}
    ensure(len(by_event) == len(official["events"]), "duplicate official event")
    previous, seen = validate_existing(existing)
    # Never pick an arbitrary provider observation when a metric appears twice.
    counts = Counter((r.get("event_key"), r.get("metric_id"))
                     for r in candidates if isinstance(r, dict))
    appended, skipped = [], Counter()
    for row in sorted(candidates, key=lambda x: (
            str(x.get("event_key")), str(x.get("metric_id")))
            if isinstance(x, dict) else ("", "")):
        if not isinstance(row, dict):
            skipped["MALFORMED_CANDIDATE"] += 1
            continue
        identity = (row.get("event_key"), row.get("metric_id"))
        if counts[identity] != 1:
            skipped["DUPLICATE_METRIC_PROVIDER_CANDIDATES"] += 1
            continue
        if identity in seen:
            skipped["ALREADY_ARCHIVED_FIRST_OBSERVATION"] += 1
            continue
        event = by_event.get(row.get("event_key"))
        if event is None:
            skipped["NOT_VERIFIED_EXACT_OFFICIAL_RELEASE"] += 1
            continue
        release = scheduled(event)
        if release is None or now >= release or generated >= release:
            skipped["NO_VERIFIED_PRE_RELEASE_RUNNER_OBSERVATION"] += 1
            continue
        m = interpret_provider_label(event, row.get("provider_event"))
        if not (m and row.get("metric_id") == m["metric_id"] and
                row.get("unit") == m["unit"] and
                row.get("component") == m["component"] and
                row.get("ccy") == event["ccy"] and
                row.get("official_date") == event["date"] and
                row.get("provider_date") == event["date"] and
                row.get("official_release_utc") == utc_text(release) and
                row.get("forecast_status") == STATUS and
                row.get("eligible_for_existing_v1_freeze") is False and
                row.get("eligible_for_macro_surprise") is False and
                row.get("eligible_for_fx_signals") is False):
            skipped["SERIES_IDENTITY_OR_V8_GUARDS_MISMATCH"] += 1
            continue
        try:
            value = parse_forecast(row.get("forecast"))
        except ValueError:
            skipped["PROVIDER_FORECAST_MISSING_OR_UNIT_UNPROVEN"] += 1
            continue
        record = {
            "schema": SCHEMA,
            "event_key": row["event_key"],
            "metric_id": m["metric_id"],
            "currency": event["ccy"],
            "official_release_reference_period": event.get("reference_period"),
            "official_release_scheduled_utc": utc_text(release),
            "scheduled_clock_is_not_first_public_delivery": True,
            "metric_component": m["component"],
            "metric_unit_provider_label_hypothesis": m["unit"],
            "source_provider": PROVIDER,
            "source_endpoint": ENDPOINT,
            "source_field": "forecast",
            "provider_event_label": row["provider_event"],
            "provider_forecast_original": row["forecast"],
            "forecast_value_percent": value,
            "source_feed_fetched_at_utc": utc_text(generated),
            "captured_at_utc": utc_text(now),
            "publisher_original_forecast_timestamp_verified": False,
            "candidate_series_identity_not_issuer_attested": True,
            "quality": "SECONDARY_EXACT_LABEL_RUNNER_OBSERVED_NOT_SURVEY_CERTIFIED",
            "actual": None,
            "surprise": None,
            "FX_signal": None,
            "eligible_for_macro_surprise": False,
            "eligible_for_event_causality": False,
            "eligible_for_live_model": False,
            "previous_record_sha256": previous,
        }
        record["record_sha256"] = digest(record)
        appended.append(record)
        seen.add(identity)
        previous = record["record_sha256"]
    result = existing + appended
    validate_existing(result)
    return result, {
        "status": "METRIC_SECONDARY_FORECAST_FIRST_SEEN_RESEARCH_ONLY",
        "records_before": len(existing),
        "new_metrics_observed_before_release": len(appended),
        "records_after": len(result),
        "new_metric_ids": [r["metric_id"] for r in appended],
        "skipped": dict(skipped),
        "not_survey_consensus_certified": True,
        "not_first_public_publisher_timestamp": True,
        "eligible_for_macro_surprise": False,
        "eligible_for_fx_signals": False,
        "existing_usd_cad_forecast_ledger_untouched": True,
    }


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def run(official=OFFICIAL, source=SOURCE, ledger=LEDGER, captured_at=None):
    now = captured_at if captured_at is not None else datetime.now(timezone.utc)
    old = read_rows(Path(ledger))
    new, receipt = freeze(
        json.loads(Path(official).read_text(encoding="utf-8")),
        json.loads(Path(source).read_text(encoding="utf-8")),
        old, now)
    if len(new) > len(old):
        with Path(ledger).open("a", encoding="utf-8") as f:
            for row in new[len(old):]:
                f.write(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--official", type=Path, default=OFFICIAL)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args()
    print(json.dumps(run(args.official, args.source, args.ledger),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
