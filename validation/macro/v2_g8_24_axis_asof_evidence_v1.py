#!/usr/bin/env python3
"""One point-in-time *evidence view* of 24 G8 macro economic dimensions.

This independently synchronizes the latest issuer-web statement documented
at a single UTC cutoff, using:
* GDP: 8 first-web quarterly releases (SAAR -> nonannualized US GDP documented).
* Inflation/Labour: 16 issuer-web release ledgers, with different *canonical*
  first-release overrides for EUR HICP (105 flash months) and AUD quarterly CPI
  (34 quarters). Keep candidate revisions separate.
* CHF labour: actual official rounded SECO report (3.1%), never historic exact
  SNB rate; first visibility conservatively next UTC day.

This is evidence availability, NOT a joint historical PIT vintage backtest,
nor 24 contemporaneous economic observations. Different reference months/
quarters coexist in the same clock snapshot. Never publish D/rank/pairs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
    FX, receipt as gdp_receipt,
)
from validation.macro.v2_g8_gdp_unified_web_research_v1 import (
    unified_research_rows
)
from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import (
    REGISTRY, asof_source, catalogue
)
from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import (
    archived_overlay
)
from validation.macro.v2_eur_ea_regime_chf_precision_guard_v1 import (
    euro_quality, swiss_quality
)
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_g8_source_semantic_reconciliation_v1 import (
    RESEARCH_PINNED
)
from validation.macro.v2_shadow_features_v1 import ROOT

SCHEMA = "GMFQ_MACRO_V2_G8_24_AXIS_SINGLE_UTC_ASOF_EVIDENCE_V1"
DIMENSIONS = ("growth", "inflation", "labour")
OVERRIDE_CANONICAL_ARCHIVE = ("EUR.inflation", "AUD.inflation")
MAX_REPLAY_DATE = "2026-10-27"


def require(ok, reason):
    if not ok:
        raise ValueError("MACRO_V2_24_AXIS_SYNCHRONIZATION_REJECTED: " + reason)


def parse_utc(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("MACRO_V2_24_AXIS_SYNCHRONIZATION_REJECTED: bad UTC date") from exc
    require(d.tzinfo is not None and d.utcoffset() == timedelta(0),
            "UTC cutoff MUST contain UTC offset")
    require(d <= datetime.now(timezone.utc) + timedelta(minutes=2),
            "future publication cutoffs forbidden")
    return d


def _base(currency, dimension, canonical_id, frequency):
    return {
        "currency": currency, "pillar": dimension,
        "registered_canonical_series_id": canonical_id,
        "registered_canonical_frequency": frequency,
        "reported_economic_period": None,
        "first_web_value": None, "asof_value_latest_known_revision": None,
        "first_documented_web_gate_utc": None, "first_web_source_url": None,
        "web_first_release_known_at_cutoff": False,
        "source_byte_archived_for_original_publication_day_independently_reverified": False,
        "complete_historical_revision_vintage_chain_verified": False,
        "complete_pit_training_history_verified": False,
        "model_score_authorized": False,
        "fx_signal_authorized": False,
    }


def _set_first(row, *, period, value, gate, url, quality, precision):
    row.update({
        "reported_economic_period": period,
        "first_web_value": value,
        "asof_value_latest_known_revision": value,
        "first_documented_web_gate_utc": gate,
        "first_web_source_url": url,
        "web_first_release_known_at_cutoff": True,
        "source_quality": quality,
        "value_precision": precision,
    })
    return row


def source_snapshot(*, cutoff, registry, source_candidates=None,
                    archival=None, growth_rows=None):
    clock = parse_utc(cutoff)
    require(isinstance(registry, dict) and
            registry.get("schema") == "GMFQ_MACRO_SOURCE_REGISTRY_V1" and
            set(registry.get("series", {})) ==
            {f"{c}.{p}" for c in FX for p in ("inflation", "labour")},
            "16 G8 published registry source contracts required")
    candidates = catalogue(
        source_candidates if source_candidates is not None else collect(), registry)
    archived = archival if archival is not None else archived_overlay(
        as_of=clock.isoformat())
    require(archived["schema"] ==
            "GMFQ_MACRO_V2_EUR_AUD_139_FIRST_WEB_SOURCE_ROW_OVERLAY_V1" and
            archived["summary"]["pinned_original_first_web_rows"] == 139 and
            set(archived["histories"]) == set(OVERRIDE_CANONICAL_ARCHIVE) and
            archived["safe_to_publish_new_D"] is False,
            "archived canonical EUR/AUD original statements not genuine")
    growth = gdp_receipt(
        growth_rows if growth_rows is not None else unified_research_rows(),
        as_of=clock.isoformat(),
    )
    require(set(growth["features"]) == set(FX) and
            growth["can_publish_D_json"] is False and
            growth["summary"]["model_growth_scores_computed"] == 0,
            "eight GDP first-web statements research-only required")

    eur_quality = euro_quality(cutoff=clock.isoformat())
    chf_quality = swiss_quality(cutoff=clock.isoformat())
    require(eur_quality["source_first_flash_periods"] if "source_first_flash_periods" in eur_quality
            else sum(eur_quality["regime_counts"].values()) == 105,
            "EA19/EA20/EA21 source quality audit drift")
    require(chf_quality["exact_SNB_release_timestamp_utc"] is None and
            chf_quality["SNB_exact_historic_release_PIT_approved"] is False,
            "SNB unverified exact first-release clock must stay unknown")

    rows = {}
    for currency in FX:
        g = growth["features"][currency]
        target = _base(currency, "growth",
                       "OFFICIAL_REAL_GDP_SEASONALLY_ADJUSTED_QOQ",
                       "Q")
        _set_first(
            target, period=g["latest_initial_period"],
            value=g["latest_nonannualized_qoq_pct"],
            gate=(datetime.fromisoformat(g["latest_first_web_release_day"])
                  .replace(tzinfo=timezone.utc) + timedelta(days=1)).isoformat(),
            url=g["latest_source_url"],
            quality="PUBLISHER_FIRST_WEB_QUARTERLY_RESEARCH_NOT_ORIGINAL_DAY_ARCHIVE",
            precision="QOQ_NONANNUALIZED_PCT_AS_DOCUMENTED_CONVERSION",
        )
        target["original_reported_value"] = g["latest_reported_value"]
        target["original_reported_unit"] = g["latest_reported_unit"]
        target["economic_definition_caveats"] = g.get("growth_definition_caveats", [])
        target["first_web_prior_quarters_available_for_research"] = (
            g["historical_first_web_observations_used"] if
            g.get("research_robust_growth_z") is not None else None)
        target["web_initial_research_z_current_not_FX_score"] = (
            g.get("research_robust_growth_z"))
        target["last_web_revision_not_substituted_in_first_release_training"] = (
            g["latest_visible_revision"])
        # Do not compare the SAAR headline and a revised QoQ figure directly.
        target["revisions_tracked_separately_from_initial"] = True
        rows[f"{currency}.growth"] = target

        for dimension in ("inflation", "labour"):
            key = f"{currency}.{dimension}"
            canonical = registry["series"][key]
            candidate = candidates[key]
            target = _base(currency, dimension, canonical["series_id"],
                           canonical["frequency"])
            live_candidate = asof_source(candidate, clock)
            target["official_web_candidate_series_id"] = candidate["source_series_id"]
            target["official_web_candidate_frequency"] = candidate["frequency"]
            target["candidate_web_release_count_at_cutoff"] = (
                live_candidate["first_issuer_web_releases_seen"])
            target["canonical_id_frequency_exact_match"] = (
                canonical["series_id"] == candidate["source_series_id"] and
                canonical["frequency"] == candidate["frequency"])
            target["candidate_semantic_status"] = (
                "MATCHED_IDS_NOT_PIT_CERTIFIED" if
                target["canonical_id_frequency_exact_match"] else
                "ALIAS_WITH_RESEARCH_LINEAGE" if
                key in ("USD.labour", "EUR.inflation") else
                "CANDIDATE_DIFFERENT_METRIC_OR_PRECISION")
            # The 139 original official rows are separate from the short
            # recent web candidate histories; no silent 10-month substitution.
            if key in OVERRIDE_CANONICAL_ARCHIVE:
                canonical_history = archived["histories"][key]
                require(canonical_history["source_id"] == canonical["series_id"] and
                        canonical_history["frequency"] == canonical["frequency"] and
                        canonical_history["reference_periods"] in (34, 105) and
                        canonical_history["safe_to_publish_new_D"] is False,
                        "wrong archived EUR/AUD canonical series override")
                available = [e for e in canonical_history["events"]
                             if parse_utc(e["visible_from_utc"]) <= clock]
                target["available_canonical_initial_archived_release_records"] = len(available)
                if available:
                    chosen = available[-1]
                    _set_first(
                        target, period=chosen["reference_period"],
                        value=chosen["reported_value"],
                        gate=chosen["visible_from_utc"],
                        url=chosen["source_url"],
                        quality="CANONICAL_ARCHIVED_FIRST_WEB_ROWS_WITH_SOURCE_SHA_NOT_FULL_VINTAGE",
                        precision="PUBLISHED_RATE_ONE_DECIMAL",
                    )
                    target["archived_original_publisher_source_sha256"] = (
                        chosen["archived_source_sha256"])
                    target["original_artifact_csv_sha256"] = (
                        canonical_history["source_csv_sha256"])
                    if key == "EUR.inflation":
                        eo = eur_quality["last_visible_first_flash"]
                        require(eo and eo["period"] == chosen["reference_period"] and
                                eo["value_yoy_pct"] == chosen["reported_value"],
                                "Eurostat 105 first-web selected flash and EA-regime mismatch")
                        target["eurozone_membership"] = eo["membership"]
                        target["homogeneous_24_month_EA_membership_reference"] = (
                            eo["same_membership_24m_reference_sufficient"])
                        if not eo["same_membership_24m_reference_sufficient"]:
                            target["source_quality"] = (
                                "CANONICAL_FIRST_FLASH_EA_MEMBERSHIP_MIXED_24M_NOT_PIT")
                        target["same_membership_prior_months"] = (
                            eo["prior_visible_same_membership_months"])
                    else:
                        target["quarterly_abs_cpi_never_replaced_by_monthly_candidate"] = True
                if live_candidate["latest_reference_period"] == target["reported_economic_period"]:
                    target["separate_candidate_detailed_or_revised_web_value"] = (
                        live_candidate["asof_known_value"])
                    target["separate_candidate_detailed_or_revised_web_stage"] = (
                        live_candidate["last_visible_publication_stage"])
                    target["candidate_detailed_never_rewrites_first_flash"] = True
            elif key == "CHF.labour":
                target["canonical_exact_SNB_first_release_timestamp_utc"] = None
                target["canonical_exact_SNB_value_on_first_release_verified"] = False
                target["rounded_SECO_as_provisional_alternative_not_exact_SNB"] = True
                rounded = chf_quality["rounded_SECO_sa_rate_pct_visible"]
                if rounded is not None:
                    _set_first(
                        target, period="2026-09", value=rounded,
                        gate=chf_quality["SECO_rounded_first_report_consistently_visible_from_utc"],
                        url=chf_quality["official_SECO_september_url"],
                        quality="ALTERNATIVE_SECO_ROUNDED_FIRST_WEB_NOT_SNB_EXACT_VINTAGE",
                        precision="ONE_DECIMAL_PCT_INTERVAL",
                    )
                    target["compatible_exact_rate_interval_pct"] = (
                        chf_quality["rounding_consistency_interval_pct"])
                elif live_candidate["latest_reference_period"] is not None:
                    _set_first(
                        target, period=live_candidate["latest_reference_period"],
                        value=live_candidate["first_web_value"],
                        gate=live_candidate["first_gate_utc"],
                        url=live_candidate["first_source_url"],
                        quality="ALTERNATIVE_SECO_ROUNDED_WEB_CANDIDATE_NOT_SNB_EXACT",
                        precision="ONE_DECIMAL_PERCENT",
                    )
            elif live_candidate["latest_reference_period"] is not None:
                _set_first(
                    target, period=live_candidate["latest_reference_period"],
                    value=live_candidate["first_web_value"],
                    gate=live_candidate["first_gate_utc"],
                    url=live_candidate["first_source_url"],
                    quality=("CONCEPTUALLY_SAME_BLS_ISSUER_LINEAGE_NO_COMPLETE_VINTAGE"
                             if key == "USD.labour" else
                             "OFFICIAL_WEB_CANDIDATE_MATCHES_CANONICAL_ID_NOT_PIT"),
                    precision="PUBLISHER_STATED_UNIT",
                )
                target["asof_value_latest_known_revision"] = (
                    live_candidate["asof_known_value"])
                target["latest_revision_known_as_of_gate"] = live_candidate["last_gate_utc"]
                target["candidate_revision_count_latest_period"] = (
                    live_candidate["known_revision_count_for_latest"])
            else:
                target["source_quality"] = "NO_FIRST_WEB_EVENT_DOCUMENTED_BY_CUTOFF"
                target["value_precision"] = "NOT_YET_KNOWN"
            rows[key] = target

    require(len(rows) == 24 and set(rows) ==
            {f"{ccy}.{dim}" for ccy in FX for dim in DIMENSIONS},
            "exact 24 canonical G8 dimensions required")
    missing = sorted(k for k, x in rows.items() if not x["web_first_release_known_at_cutoff"])
    visible_count = len(rows) - len(missing)
    for key, x in rows.items():
        if x["web_first_release_known_at_cutoff"]:
            require(x["reported_economic_period"] is not None and
                    x["first_documented_web_gate_utc"] is not None and
                    parse_utc(x["first_documented_web_gate_utc"]) <= clock,
                    "leaked future first web statement: " + key)
        require(x["model_score_authorized"] is False and
                x["fx_signal_authorized"] is False and
                x["complete_pit_training_history_verified"] is False,
                "an unapproved model score or FX signal has been promoted")
    out = {
        "schema": SCHEMA,
        "as_of_utc": clock.isoformat(),
        "status": "24_AXIS_RELEASE_CLOCK_ALIGNED_EVIDENCE_NOT_JOINT_PIT_MODEL",
        "slots": rows,
        "summary": {
            "currency_count": 8,
            "economic_pillars": 3,
            "target_slots": 24,
            "first_web_latest_source_slots_visible": visible_count,
            "first_web_not_documented_at_cutoff": missing,
            "first_web_visible_not_equivalent_to_joint_training_PIT": True,
            "canonical_archived_initial_source_rows": 139,
            "candidate_source_id_frequency_equal": sum(
                rows[k]["canonical_id_frequency_exact_match"]
                for k in rows if k.endswith((".labour", ".inflation"))),
            "first_release_observations_in_archived_EUR_AUD": sum(
                rows[k].get("available_canonical_initial_archived_release_records", 0)
                for k in OVERRIDE_CANONICAL_ARCHIVE),
            "official_complete_PIT_training_slots": 0,
            "model_macro_scores_approved": 0,
            "FX_pair_rankings_rebuilt": 0,
        },
        "release_clock_not_same_as_economic_reference_period": True,
        "all_current_revised_history_not_valid_historical_asof_source": True,
        "latest_known_candidate_revisions_not_backfilled_into_first_release": True,
        "cross_country_economic_periods_not_synchronized": True,
        "no_cross_currency_rank_or_FX_direction_estimated": True,
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_theses": False,
        "safe_to_use_for_beta": False,
        "safe_to_use_for_forward": False,
        "writes_live_data": False,
    }
    out["receipt_sha256"] = hashlib.sha256(json.dumps(
        {"as_of": out["as_of_utc"], "slots": rows},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return out


def run(*, as_of=None):
    day = as_of or datetime.now(ZoneInfo("Europe/Rome")).astimezone(
        timezone.utc).isoformat()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return source_snapshot(cutoff=day, registry=registry)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=None)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "research artifacts only in /tmp")
    data = run(as_of=args.as_of)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": data["status"], **data["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
