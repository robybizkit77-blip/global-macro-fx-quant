#!/usr/bin/env python3
"""ABS trimmed mean cross-publication evidence replay, NOT fully certified PIT revisions.

Do not treat later retrospective values as the first-release number. Every source
is a period-specific ABS web publication *as currently served*, not a preserved
release-day HTML vintage. Later numbers are evidence observed in later reports,
not proofs of exact revision mechanism/first effective change time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, require, timestamp
from validation.macro.v2_abs_complete_monthly_cpi_11_release_replay_v1 import (
    SOURCE as ABS_LEDGER, audit_ledger, BASE,
)

SOURCE = ROOT / "validation/macro/fixtures/v2_abs_trimmed_cross_publication_2026_v1.json"
SCHEMA = "GMFQ_MACRO_V2_ABS_TRIMMED_CROSS_PUBLICATION_EVIDENCE_V1"
RECEIPT = "GMFQ_MACRO_V2_ABS_TRIMMED_CROSS_PUBLICATION_REPLAY_V1"
SERIES = "AU_CPI_TRIMMED_MEAN_M_YOY_context_value"

# Independent reference contract, not derived from the editable source fixture.
# (reference period, reporting period, % YoY, source section).
PINNED = (
    ("2026-01", "2026-01", 3.4, "JANUARY_OWN_PERIOD_KEY_STATISTICS"),
    ("2026-01", "2026-02", 3.3, "FEBRUARY_RELEASE_RETROSPECTIVE_JANUARY_KEY_STATISTICS"),
    ("2026-05", "2026-05", 3.6, "MAY_OWN_PERIOD_KEY_STATISTICS"),
    ("2026-05", "2026-06", 3.6, "JUNE_RELEASE_RETROSPECTIVE_MAY_KEY_STATISTICS"),
    ("2026-05", "2026-07", 3.5, "JULY_RELEASE_RETROSPECTIVE_MAY_HISTORICAL_CHART"),
)
REVIEWED = {
    "2026-01": (3.4, 3.3),
    "2026-05": (3.6, 3.5),
}


def audit(evidence, ledger):
    require(evidence.get("schema") == SCHEMA and evidence.get("review_as_of") == "2026-10-24",
            "incorrect ABS cross-publication evidence version")
    require(evidence.get("publisher") == "Australian Bureau of Statistics"
            and evidence.get("series_id") == SERIES
            and evidence.get("economic_metric") == "Trimmed mean CPI annual growth"
            and evidence.get("unit") == "percent YoY seasonally adjusted"
            and evidence.get("evidence_class") ==
            "PERIOD_SPECIFIC_OFFICIAL_WEB_STATEMENTS_NOT_RELEASE_DAY_IMMUTABLE_SOURCE_BYTES"
            and evidence.get("interpretation") ==
            "TWO_CROSS_REPORT_DIFFERENCES_CAUSE_AND_FULL_REVISION_VINTAGE_UNCERTIFIED",
            "ABS series/source or revision interpretation drift")
    for key in ("count_as_independent_initial_release_events",
                "complete_revision_chain_certified",
                "independent_original_day_byte_archive_verified",
                "backtest_allowed", "live_score_update_allowed", "writes_live_data"):
        require(evidence.get(key) is False, "restricted research evidence status changed: " + key)
    original = {item["period"]: item for item in audit_ledger(ledger)}
    obs = evidence.get("observations")
    require(isinstance(obs, list) and len(obs) == len(PINNED), "five cross-publication observations required")
    validated = []
    seen = set()
    for item, (period, reporting, value, section) in zip(obs, PINNED):
        require(item.get("reference_period") == period
                and item.get("report_period") == reporting
                and item.get("reported_value") == value
                and type(item.get("reported_value")) in (int, float)
                and item.get("source_section") == section
                and item.get("page_capture_at_first_release_proven") is False,
                "ABS value/identity/provenance not pinned")
        require(period in original and reporting in original and reporting >= period,
                "official report period unavailable or predates measurement")
        report = original[reporting]
        expected_url = BASE + report["source_url"].rsplit("/", 1)[-1]
        require(item.get("source_url") == expected_url,
                "retrospective statement must use actual period-specific ABS source URL")
        require(item.get("reported_at_local") == report["publication_at_local"],
                "report timestamp is not the official event")
        report_clock = timestamp(item["reported_at_local"])
        require(report_clock == timestamp(report["publication_at_utc"]), "timezone/clock mismatch")
        key = (period, reporting)
        require(key not in seen, "duplicate cross-publication record")
        seen.add(key)
        if period == reporting:
            require(value == original[period]["trimmed_mean"], "initial web headline overwritten")
        validated.append({
            "reference_period": period, "report_period": reporting,
            "reported_value": value, "source_url": item["source_url"],
            "reported_at_utc": report_clock.isoformat(),
            "source_section": section,
        })
    require(list(REVIEWED) == ["2026-01", "2026-05"], "expected two revision candidates")
    require(len(validated) == 5, "event coverage drift")
    return validated


def replay(as_of, evidence=None, ledger=None):
    if evidence is None:
        evidence = json.loads(SOURCE.read_text(encoding="utf-8"))
    if ledger is None:
        ledger = json.loads(ABS_LEDGER.read_text(encoding="utf-8"))
    events = audit(evidence, ledger)
    cutoff = timestamp(as_of)
    known = [e for e in events if timestamp(e["reported_at_utc"]) <= cutoff]
    cases = []
    for period, (initial, latest) in REVIEWED.items():
        event_list = [e for e in known if e["reference_period"] == period]
        original = next((e for e in event_list if e["report_period"] == period), None)
        newest = event_list[-1] if event_list else None
        # Earliest known publication with the differing retrospective value;
        # not necessarily the true date a statistical revision became effective.
        first_differing = next(
            (e for e in event_list if e["reported_value"] != initial),
            None,
        )
        cases.append({
            "reference_period": period, "initial_web_reported_value": initial if original else None,
            "latest_accessible_reported_value": newest["reported_value"] if newest else None,
            "known_cross_report_difference_pp":
                round(newest["reported_value"] - initial, 1) if original and newest else None,
            "first_different_publication_in_scoped_evidence_utc":
                first_differing["reported_at_utc"] if first_differing else None,
            "initial_source_url": original["source_url"] if original else None,
            "latest_report_source_url": newest["source_url"] if newest else None,
            "later_report_known_at_cutoff": bool(first_differing),
            "exact_statistical_revision_effective_time_verified": False,
            "revised_original_release_day_bytes_certified": False,
            "source_difference_is_proof_of_original_release_day_vintage": False,
        })
        # The independent pin ensures a source that reverts to initial at latest
        # would need a separate review instead of being silently recast.
        require(latest != initial, "expected independent contradictory values")
    return {
        "schema": RECEIPT,
        "as_of_utc": cutoff.isoformat(),
        "scope": "TWO_ABS_TRIMMED_MEAN_CROSS_REPORT_DIFFERENCES_NOT_COMPLETE_VINTAGES",
        "official_source_web_evidence_count_total": len(events),
        "official_source_web_evidence_visible_at_cutoff": len(known),
        "cases": cases,
        "cross_report_changes_visible": sum(r["later_report_known_at_cutoff"] for r in cases),
        "changes_certified_as_complete_original_vintage_revisions": 0,
        "source_release_day_bytes_archived": False,
        "historical_revision_chain_complete": False,
        "training_observation_count_changed": False,
        "eligible_for_backtest": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "writes_live_data": False,
        "evidence_fingerprint_sha256": hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asof", default="2026-10-24T00:00:00Z")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    receipt = replay(args.asof)
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipt only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "total": receipt["official_source_web_evidence_count_total"],
        "visible": receipt["official_source_web_evidence_visible_at_cutoff"],
        "cross_report_changes_visible": receipt["cross_report_changes_visible"],
        "certified_revision_histories": receipt["changes_certified_as_complete_original_vintage_revisions"],
        "eligible_for_backtest": False,
    }))


if __name__ == "__main__":
    main()
