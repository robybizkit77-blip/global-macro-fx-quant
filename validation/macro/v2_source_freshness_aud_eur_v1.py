#!/usr/bin/env python3
"""Bounded source-freshness audit: original official pages vs observed G8 series.

Does NOT infer revised index levels from MoM growth, invent release timestamps,
reconstruct historical PIT snapshots, write live data or compute scores.
"""
import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from validation.macro.v2_shadow_features_v1 import ROOT, require
from validation.macro.v2_growth_inflation_g8_desk_inventory_v1 import parse_reference_period

EVIDENCE = "validation/macro/MACRO_V2_AUD_EUR_OFFICIAL_FRESHNESS_GAPS_2026-10-24.json"
SOURCE = "live_data/sections/MACRO_SERIES.json"
SCHEMA = "GMFQ_MACRO_V2_OFFICIAL_FRESHNESS_GAPS_AUD_EUR_V1"
CONCEPTS = {
    "AU_CPI_HEADLINE_M_YOY_context_value": ("AUD", "Inflazione", "REPORTED_ANNUAL_RATE_SAME_CONCEPT"),
    "AU_CPI_TRIMMED_MEAN_M_YOY_context_value": ("AUD", "Inflazione", "REPORTED_ANNUAL_RATE_SAME_CONCEPT"),
    "EA_IP_history_value": ("EUR", "Crescita", "DIFFERENT_METRIC_INDEX_LEVEL_VS_REPORTED_MOM"),
}
OFFICIAL_HOSTS = {"AUD": "www.abs.gov.au", "EUR": "ec.europa.eu"}


def period_month(raw, frequency):
    parsed = parse_reference_period(raw, frequency)
    require(parsed is not None, "invalid observed/reference period")
    return parsed[0].strftime("%Y-%m")


def audit(series, dossier, *, as_of=date(2026, 10, 24)):
    """Report current snapshot gaps and release-event visibility separately.

    as_of filters official RELEASE EVENTS only. Current observed snapshot is *not*
    rolled backwards and must never be represented as PIT at earlier cutoffs.
    """
    require(dossier.get("schema") == SCHEMA and dossier["review_as_of"] == "2026-10-24",
            "unknown source evidence version")
    require(dossier["scores_computed"] is False and dossier["writes_live_data"] is False
            and dossier["eligible_for_backtest"] is False,
            "nonproduction status changed")
    require(set(series) == {"AUD", "EUR", "USD", "GBP", "JPY", "CHF", "CAD", "NZD"},
            "G8 observed series drift")
    events = dossier.get("events")
    require(isinstance(events, list) and len(events) == 3
            and {x["series_id"] for x in events} == set(CONCEPTS), "limited 3-series scope drift")
    event_labels, outputs = set(), []
    for item in events:
        sid = item["series_id"]
        ccy, category, alignment = CONCEPTS[sid]
        require((item["currency"], item["pillar"], item["metric_alignment"]) ==
                (ccy, "inflation" if ccy == "AUD" else "growth", alignment),
                "pillar/metric/source identity drift")
        rows = [r for r in series[ccy] if r["id"] == sid and r["category"] == category]
        require(len(rows) == 1, "source snapshot series not found or ambiguous")
        observed = rows[0]
        require(observed.get("frequency") == "M", "monthly contract drift")
        observed_period = period_month(observed["last_date"], "M")
        release_period = period_month(item["official_reference_period"], "M")
        require(item["series_reference_period_expected"] == "2026-07"
                and release_period == "2026-08", "evidence month contract drift")
        released = date.fromisoformat(item["official_release_date"])
        require(released >= date.fromisoformat(release_period + "-01")
                and released <= date.fromisoformat(dossier["review_as_of"]),
                "release outside observed-period/review chronology")
        url = urlparse(item["official_source_url"])
        require(url.scheme == "https" and url.hostname == OFFICIAL_HOSTS[ccy]
                and url.path, "official source domain mismatch")
        clock = item.get("official_release_at_local")
        if clock is not None:
            when = datetime.fromisoformat(clock)
            require(when.tzinfo is not None and when.utcoffset() is not None
                    and when.date() == released, "release clock not certified local date")
        require(item.get("official_page_bytes_hashed") is False
                and item.get("full_pit_vintage_chain_certified") is False,
                "unsupported PIT certification")
        for field in ("official_metric_value", "prior_month_metric_value", "series_value_expected"):
            require(type(item.get(field)) in (int, float) and math.isfinite(item[field]),
                    "missing finite released or observed value")
        if alignment == "DIFFERENT_METRIC_INDEX_LEVEL_VS_REPORTED_MOM":
            require(item["official_metric_unit"] == "percent MoM"
                    and observed["unit"] == "Index 2021=100"
                    and item["matching_august_index_level_from_same_vintage"] is None,
                    "do not manufacture August Eurostat level from MoM change")
        else:
            require(item["official_metric_unit"] == "percent YoY"
                    and observed["unit"] == ("percent YoY SA" if "TRIMMED" in sid else "percent YoY"),
                    "CPI metric unit mismatch")
        require(observed_period <= release_period, "snapshot newer than pinned release")
        observed_value_agrees = (type(observed.get("last_value")) in (int, float)
                                 and math.isfinite(observed["last_value"])
                                 and abs(observed["last_value"] -
                                         item["series_value_expected"]) < 1e-8)
        event_labels.add(item["event_id"])
        visible = released <= as_of
        if not visible:
            status = "OFFICIAL_EVENT_AFTER_REQUESTED_CUTOFF"
        elif observed_period < release_period:
            status = ("LAGGING_METRIC_COMPATIBLE_OFFICIAL_RELEASE" if
                      alignment == "REPORTED_ANNUAL_RATE_SAME_CONCEPT" else
                      "LAGGING_SERIES_REQUIRES_SAME_DEFINITION_OFFICIAL_INDEX_LEVEL")
        else:
            status = ("SAME_PERIOD_VERIFY_RELEASE_VALUE" if
                      alignment == "REPORTED_ANNUAL_RATE_SAME_CONCEPT" else
                      "SAME_PERIOD_LEVEL_RECONCILIATION_REQUIRED")
        outputs.append({
            "currency": ccy, "pillar": item["pillar"], "series_id": sid,
            "observed_period": observed_period,
            "observed_value": observed.get("last_value"), "observed_unit": observed.get("unit"),
            "observed_value_matches_pinned_review_snapshot": observed_value_agrees,
            "review_snapshot_drift_requires_investigation": not observed_value_agrees,
            "official_release_event_id": item["event_id"],
            "official_reference_period": release_period,
            "official_release_date": item["official_release_date"],
            "official_release_at_local_verified_when_provided": clock,
            "official_source_url": item["official_source_url"],
            "official_metric_value": item["official_metric_value"] if visible else None,
            "official_metric_unit": item["official_metric_unit"],
            "official_prior_month_value": item["prior_month_metric_value"] if visible else None,
            "official_change_in_annual_rate_pp": (
                round(item["official_metric_value"] - item["prior_month_metric_value"], 3)
                if visible and alignment == "REPORTED_ANNUAL_RATE_SAME_CONCEPT" else None),
            "official_event_visible_at_cutoff": visible,
            "source_freshness": status,
            "matching_official_new_index_level": None,
            "source_historical_first_release_chain_certified": False,
            "eligible_for_new_macro_score": False,
        })
    require(event_labels == {"ABS_CPI_2026_09_30", "EUROSTAT_IP_2026_10_15"},
            "expected two release events")
    planned = dossier["published_next_release_not_current_observation"]
    require(planned["is_observed_release"] is False and
            planned["scheduled_release_local"] == "2026-10-28T11:30:00+11:00",
            "planned CPI release cannot become an observation")
    return {
        "schema": "GMFQ_MACRO_V2_SOURCE_FRESHNESS_AUDIT_RECEIPT_V1",
        "as_of": as_of.isoformat(),
        "snapshot_as_of_evidence_review": dossier["review_as_of"],
        "status": "OFFICIAL_RELEASE_GAP_RESEARCH_ONLY_NOT_PIT",
        "summary": {
            "series_examined": len(outputs),
            "distinct_documented_official_release_events": len(event_labels),
            "events_visible_by_requested_cutoff": len({
                o["official_release_event_id"] for o in outputs if o["official_event_visible_at_cutoff"]
            }),
            "lagging_series_where_release_visible": sum(
                o["official_event_visible_at_cutoff"] and
                o["observed_period"] < o["official_reference_period"] for o in outputs),
            "values_requiring_source_metric_reconciliation": sum(
                o["official_event_visible_at_cutoff"] and
                o["matching_official_new_index_level"] is None and o["series_id"] == "EA_IP_history_value"
                for o in outputs),
            "full_historical_pit_vintages_certified": 0,
        },
        "rows": outputs,
        "planned_abs_september_release_not_observed": planned["scheduled_release_local"],
        "current_series_snapshot_reconstructed_at_cutoff": False,
        "first_release_event_timing_sufficient_for_intradaday_fx_backtest": False,
        "safe_to_update_macro_series": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "eligible_for_backtest": False,
        "writes_live_data": False,
    }


def run():
    series = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    evidence = json.loads((ROOT / EVIDENCE).read_text(encoding="utf-8"))
    return audit(series, evidence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run()
    if args.out:
        require(args.out.resolve().is_relative_to(Path("/tmp")), "research receipts only /tmp")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
