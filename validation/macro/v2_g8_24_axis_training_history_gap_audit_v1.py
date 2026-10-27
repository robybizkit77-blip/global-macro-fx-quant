#!/usr/bin/env python3
"""Evidence-backed 24-slot G8 historical training-window *gap* audit.

For EACH currency/pillar at a single already-completed UTC cutoff, count
first-web economic-period observations in its intended 24-month/12-quarter
prior window, enumerate missing reference periods, and explicitly isolate
non-canonical candidates, data-definition breaks and missing issuer-day
vintage certification. This is diagnostic math, NOT a model-ready PIT ledger.

One current first release + 24 monthly (or 12 quarterly) PRIOR first releases
is required. A source that contains >25 other unrelated months still fails
when any required consecutive month is missing (e.g. U.S. 2025 BLS gap).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT, period_index, timestamp
from validation.macro.v2_g8_24_axis_asof_evidence_v1 import (
    FX, DIMENSIONS, REGISTRY, parse_utc, source_snapshot
)
from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import catalogue
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import archived_overlay
from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
    asof_visible, receipt as GDP_receipt
)
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
from validation.macro.v2_eur_ea_regime_chf_precision_guard_v1 import euro_quality
from validation.macro.v2_g8_source_semantic_reconciliation_v1 import RESEARCH_PINNED

SCHEMA = "GMFQ_MACRO_V2_G8_24_AXIS_FIRST_RELEASE_TRAINING_GAP_AUDIT_V1"
ASOF = "2026-10-26T23:59:59Z"
MONTHLY_PRIOR = 24
QUARTERLY_PRIOR = 12


def check(cond, reason):
    if not cond:
        raise ValueError("G8_MACRO_TRAINING_HISTORY_AUDIT_REJECTED: " + reason)


def idx(period, freq):
    if freq == "Q" and len(period) == 7 and period[4] == "-":
        year, month = period.split("-")
        check(month in ("03", "06", "09", "12"), "quarterly archived period must end in Mar/Jun/Sep/Dec")
        period = year + "Q" + str(int(month)//3)
    return period_index(period, freq)


def period_label(index, freq):
    if freq == "M":
        return f"{index//12:04d}-{index%12+1:02d}"
    return f"{index//4:04d}Q{index%4+1}"


def evidence(*, cutoff=ASOF, source_candidates=None, GDP_rows=None,
             archive=None, registry=None):
    cut = parse_utc(cutoff)
    check(cut.date() < datetime.now(timezone.utc).date(),
          "only completed historical UTC days; ongoing day belongs to live as-of")
    r = registry if registry is not None else json.loads(REGISTRY.read_text(encoding="utf-8"))
    raw = source_candidates if source_candidates is not None else collect()
    gdp = GDP_rows if GDP_rows is not None else unified_research_rows()
    original = archive if archive is not None else archived_overlay(as_of=cut.isoformat())
    # Reuse the already-integrated, independently reviewed source identity
    # contract. Rejects a fifth mismatch, future values and incorrect proxies.
    snapshot = source_snapshot(
        cutoff=cut.isoformat(), registry=r, source_candidates=raw,
        archival=original, growth_rows=gdp)
    check(snapshot["schema"] ==
          "GMFQ_MACRO_V2_G8_24_AXIS_SINGLE_UTC_ASOF_EVIDENCE_V1" and
          snapshot["safe_to_publish_new_D"] is False and
          snapshot["summary"]["official_complete_PIT_training_slots"] == 0,
          "source snapshot attempted unapproved promotion")
    normalized = catalogue(raw, r)
    GDP = GDP_receipt(gdp, as_of=cut.isoformat())
    ea = euro_quality(cutoff=cut.isoformat())
    from validation.macro.v2_g8_11_retained_source_archives_v1 import run as retained_run
    retained = retained_run()
    check(retained["summary"]["g8_histories_added"] == 11 and
          retained["safe_to_publish_new_D"] is False and
          retained["source_bytes_equal_to_prior_independently_audited_archives"],
          "11 original source materializations failed integrity/promotion gates")

    details = {}
    for currency in FX:
        for pillar in DIMENSIONS:
            key = currency + "." + pillar
            current = snapshot["slots"][key]
            freq = current["registered_canonical_frequency"]
            required_prior = QUARTERLY_PRIOR if freq == "Q" else MONTHLY_PRIOR
            first_web = []
            method = "OFFICIAL_WEB_CANDIDATE_UNCERTIFIED_HISTORIC_PIT"
            source_id = current["registered_canonical_series_id"]
            if pillar == "growth":
                # GDP is a separate GDP research target, not a registered
                # canonical 16-source inflation/labour series.
                check(freq == "Q" and source_id is None,
                      "do not invent canonical GDP registration")
                first_web = [
                    (row["reference_quarter"], asof_visible(row),
                     row["reported_value"])
                    for row in gdp if row["currency"] == currency
                    and row["stage_order"] == 0 and asof_visible(row) <= cut
                ]
                method = "GDP_FIRST_PUBLISHER_WEB_RESEARCH_12Q_NOT_SOURCE_DAY_ARCHIVE"
                source_id = "GDP_RESEARCH_TARGET_NOT_CANONICAL_REGISTERED"
            elif key in retained["histories"]:
                item = retained["histories"][key]
                check(item["frequency"] == freq and
                      item["FX_scoring_approved"] is False and
                      item["historical_issuer_source_bytes_attested_by_earlier_materializer"],
                      "historical source record not provenance-safe")
                first_web = [
                    (row["reference_period"],
                     timestamp(row["first_web_publisher_gate_utc"]),
                     row["first_web_value"])
                    for row in item["records"]
                    if timestamp(row["first_web_publisher_gate_utc"]) <= cut
                ]
                method = "RETAINED_OFFICIAL_STRICT_FIRST_RELEASE_ARTIFACT_HASH_PINNED"
                # Keep this separate from the newer latest-web candidate;
                # source archive may end BEFORE the latest candidate month.
                source_id = current["registered_canonical_series_id"]
            elif key in ("EUR.inflation", "AUD.inflation"):
                item = original["histories"][key]
                check(item["source_id"] == source_id and
                      item["frequency"] == freq,
                      "archival first-web metric/frequency drift")
                first_web = [
                    (row["reference_period"], timestamp(row["visible_from_utc"]),
                     row["reported_value"])
                    for row in item["events"]
                    if timestamp(row["visible_from_utc"]) <= cut
                ]
                method = "ARCHIVED_PUBLISHER_FIRST_WEB_CSV_SHA_PINNED_NOT_REVERIFIED_SOURCE_DAY"
            else:
                stream = normalized[key]
                source_id = stream["source_series_id"]
                check((key in RESEARCH_PINNED) or (
                      stream["source_series_id"] == source_id and
                      stream["frequency"] == freq),
                      "noncanonical unapproved candidate source")
                first_web = [
                    (row["reference_period"], timestamp(row["visible_from_utc"]),
                     row["reported_value"])
                    for row in stream["all_documented_publication_events"]
                    if row["stage"] == "FIRST_WEB" and
                    timestamp(row["visible_from_utc"]) <= cut
                ]
                if key == "CHF.labour":
                    method = "SECO_ROUNDED_ALTERNATIVE_NEVER_EXACT_SNB_SOURCE"
                elif key == "USD.labour":
                    method = "BLS_LNS14000000_TO_FRED_UNRATE_LINEAGE_NOT_ORIGINAL_FULL_CHAIN"
            indices = {}
            for period, gate, value in first_web:
                pidx = idx(period, freq)
                check(pidx not in indices and gate <= cut,
                      "duplicate first release period or future release leak")
                indices[pidx] = (period, gate, value)
            latest_source_period = current["reported_economic_period"]
            # Existing 16-slot latest-web view can be from a shorter research
            # pilot than the new full archive. For archived complete sources
            # source period might also be OLDER than a brand new 2026 web release;
            # preserve both, never claim a stale source equals the latest.
            visible = bool(first_web)
            if key not in retained["histories"]:
                check(visible == current["web_first_release_known_at_cutoff"],
                      "visible initial web evidence and single cutoff disagree: " + key)
            last_idx = max(indices) if indices else None
            if last_idx is not None and key not in retained["histories"]:
                check(idx(latest_source_period, freq) == last_idx,
                      "latest reported reference differs from first-web ledger: " + key)
            source_last_period = (indices[last_idx][0] if last_idx is not None else None)
            future_candidate_lag = (
                idx(latest_source_period, freq) - last_idx
                if last_idx is not None and latest_source_period is not None
                else None)
            needed = ([last_idx - i for i in range(required_prior, 0, -1)]
                      if last_idx is not None else [])
            missing = [period_label(i, freq) for i in needed if i not in indices]
            prior_with_observed = [i for i in needed if i in indices]
            # With only the web records in the bounded dossier, we must NOT
            # "fill" missing historical periods from today's revised series.
            complete = (last_idx is not None and not missing)
            later_leaks = [period_label(i, freq) for i in prior_with_observed
                           if indices[i][1] >= indices[last_idx][1]]
            check(not later_leaks, "prior first-release publication was not visible by current release")
            definition = []
            if key == "EUR.inflation":
                recent = ea["last_visible_first_flash"]
                if recent:
                    check(recent["period"] == current["reported_economic_period"],
                          "EA latest month disagrees with source")
                    if not recent["same_membership_24m_reference_sufficient"]:
                        definition.append("EURO_AREA_EA19_EA20_EA21_PRIOR_24M_NOT_HOMOGENEOUS")
            if key == "CHF.labour":
                definition.append("SECO_ONE_DECIMAL_NOT_CANONICAL_SNB_EXACT_FIRST_VINTAGE")
            if pillar == "growth":
                check(GDP["features"][currency]["latest_initial_period"] ==
                      current["reported_economic_period"],
                      "GDP release source and latest research period mismatch")
                definition.extend(GDP["features"][currency].get("growth_definition_caveats", []))
            if key == "EUR.labour" and key in retained["histories"]:
                definition.append("EUROSTAT_UNEMPLOYMENT_EA19_EA20_EA21_GEOGRAPHY_REQUIRES_AUDIT")
            if key == "GBP.labour" and key in retained["histories"]:
                definition.append("ONS_3M_LFS_ROLLING_REFERENCE_END_MONTH_NOT_SINGLE_MONTH_MEASURE")
            if key == "JPY.inflation" and key in retained["histories"]:
                definition.append("JAPAN_CPI_2015_2020_2025_INDEX_BASE_TRANSITIONS")
            if key == "AUD.labour" and key in retained["histories"]:
                definition.append("ABS_AUSSTATS_TO_MODERN_FIRST_RELEASE_ROUTE_TRANSITION")
            if key == "AUD.inflation":
                check(freq == "Q" and
                      normalized[key]["frequency"] == "M",
                      "quarterly canonical CPI accidentally replaced by monthly")
            # Explicitly distinguish the *historical* BLS 25-release pilot
            # ending Sep-2025 from the latest Sep-2026 observed/revised
            # unemployment value in the operational source. The known
            # Oct-2025 structural BLS gap is AFTER the pilot's last period,
            # not inside that pilot's 24 prior-month training window.
            current_frequency_index = (
                cut.year * (4 if freq == "Q" else 12) +
                ((cut.month-1)//3 if freq == "Q" else cut.month-1))
            lag_in_periods = (
                current_frequency_index - last_idx
                if last_idx is not None else None)
            stale_pilot = key == "USD.labour" and (
                current["reported_economic_period"] == "2025-09" and
                lag_in_periods is not None and lag_in_periods >= 12)
            check(key != "USD.labour" or stale_pilot,
                  "USD BLS bounded web pilot must not silently become 2026 latest releases")
            require_mismatch = key in RESEARCH_PINNED
            record = {
                "slot": key, "currency": currency, "pillar": pillar,
                "model_canonical_source_id": current["registered_canonical_series_id"],
                "training_evidence_source_id": source_id,
                "training_web_data_source_type": method,
                "published_observation_frequency": freq,
                "reference_period_last_first_web": source_last_period,
                "newest_bounded_research_web_reference_period": latest_source_period,
                "retained_archive_vs_latest_web_gap_periods": future_candidate_lag,
                "historical_original_archive_latest_release_gate_utc": (
                    indices[last_idx][1].isoformat() if last_idx is not None else None),
                "last_first_web_gate_utc": (
                    indices[last_idx][1].isoformat() if last_idx is not None else None),
                "first_web_periods_documented_asof": len(indices),
                "last_documented_period_lag_in_own_frequency_units": lag_in_periods,
                "bounded_BLS_pilot_ends_before_structural_oct2025_gap": stale_pilot,
                "BLS_oct2025_observation_not_published": (
                    ["2025-10"] if key == "USD.labour" else []),
                "current_live_observed_series_not_equivalent_to_bounded_web_pilot": stale_pilot,
                "prior_first_release_periods_required": required_prior,
                "prior_contiguous_first_web_periods_documented": len(prior_with_observed),
                "missing_required_prior_periods": missing,
                "prior_initial_web_sequence_complete_mathematically": complete,
                "complete_source_day_original_bytes_and_revision_chain_certified": False,
                "not_same_as_model_PIT_training_approved": True,
                "model_PIT_training_approved": False,
                "current_PIT_research_comparability_caveats": definition,
                "candidate_differs_from_core_or_alias_needs_review": require_mismatch,
                "source_measurement_alternative_not_interchangeable": key == "CHF.labour",
                "research_only_quality_label": (
                    "NO_FIRST_WEB_FOUND" if not visible else
                    "INCOMPLETE_PRIOR_FIRST_RELEASES" if not complete else
                    "STALE_BLS_WEB_PILOT_ONLY_NOT_2026_ECONOMIC_RELEASES"
                    if stale_pilot else
                    "DEFINITION_OR_SEMANTIC_RISK" if definition else
                    "NUMERIC_WEB_WINDOW_AVAILABLE_NOT_PIT_CERTIFIED"),
                "FX_signal_approved": False, "safe_to_update_D": False,
            }
            details[key] = record
    check(len(details) == 24 and set(details) ==
          {c + "." + p for c in FX for p in DIMENSIONS},
          "24-slot G8 matrix no missing/duplicate")
    stat = {
        "currencies": len(FX), "economic_slots": len(details),
        "first_web_latest_available_slots": sum(
            x["reference_period_last_first_web"] is not None for x in details.values()),
        "prior_first_web_contiguous_12Q_or_24M_slots": sum(
            x["prior_initial_web_sequence_complete_mathematically"] for x in details.values()),
        "slots_missing_required_initial_release_periods": sum(
            bool(x["missing_required_prior_periods"]) for x in details.values()),
        "missing_required_prior_periods_total": sum(
            len(x["missing_required_prior_periods"]) for x in details.values()),
        "slots_with_semantic_or_definition_caveats": sum(
            bool(x["current_PIT_research_comparability_caveats"]) for x in details.values()),
        "slots_with_stale_historical_BLS_pilot_not_live_2026": sum(
            x["bounded_BLS_pilot_ends_before_structural_oct2025_gap"]
            for x in details.values()),
        "retained_official_first_release_source_archives_ingested": 11,
        "retained_source_original_issuer_records_imported":
            retained["summary"]["archived_first_release_observations"],
        "archive_source_rows_are_original_materializer_proof_not_updated_live_data": True,
        "genuinely_historic_PIT_training_slots_certified": 0,
        "currency_FX_strength_scores_approved": 0,
        "cross_currency_pair_rankings_changed": 0,
    }
    # Secondary, explicitly estimated research view. This must NEVER alter
    # the 22/24 actual first-web window counts or any source-data values.
    # The proxy is only reproducible at its fixed 2026-10-26 baseline:
    # CURRENTLY REVISED history cannot be replayed as an earlier PIT archive.
    estimated_proxies = None
    if cutoff == ASOF:
        from validation.macro.v2_g8_us_cpi_chf_labour_quality_proxies_v1 import (
            profile as provisional_profile
        )
        estimated_proxies = provisional_profile(as_of=ASOF)
        check(set(estimated_proxies["two_explicitly_estimated_missing_source_windows"])
              == {"USD.inflation", "CHF.labour"} and
              estimated_proxies["summary"]["genuinely_new_first_release_archival_rows_added"] == 0
              and estimated_proxies["safe_to_publish_new_D"] is False,
              "provisional sources must not be mistaken for original PIT histories")
        check(stat["prior_first_web_contiguous_12Q_or_24M_slots"] == 22 and
              stat["slots_missing_required_initial_release_periods"] == 2,
              "proxy values cannot overwrite 22/24 real first-release coverage")
        stat["secondary_provisional_descriptors_available"] = 2
        stat["source_slots_with_original_window_or_labeled_provisional_context"] = 24
        stat["secondary_provisional_first_release_corrections"] = 0
    # Separate official SECO alternative: 21 fresh publisher PDF source
    # SHA captures plus 4 official 2024 report excerpts currently searchable
    # but with original direct PDF URLs returning 404. Not the exact SNB
    # registered CH_UNEMP_RATE first-vintage needed by the production core.
    swiss_alternative = None
    if cutoff == ASOF:
        from validation.macro.v2_chf_seco_first_month_rounded_alternative_v1 import (
            audit as swiss_alternative_audit
        )
        swiss_alternative=swiss_alternative_audit(cutoff=ASOF)
        check(swiss_alternative["summary"]["official_PDF_raw_bytes_SHA_captured_now"]==21 and
              swiss_alternative["summary"]["official_2024_original_PDF_search_index_only_currently_404"]==4 and
              swiss_alternative["summary"]["separate_new_SNB_canonical_first_release_history_periods"]==0 and
              swiss_alternative["safe_to_publish_new_D"] is False and
              stat["prior_first_web_contiguous_12Q_or_24M_slots"]==22,
              "SECO 25-month rounded alternate cannot promote SNB canonical PIT coverage")
        stat["CH_labour_SECO_alternative_issuer_rounded_months"]=25
        stat["CH_labour_SECO_alternative_downloaded_report_PDFs"]=21
        stat["CH_labour_SECO_alternative_search_index_only_reports"]=4
        stat["CH_labour_exact_SNB_first_release_history_approved"]=0
    out = {
        "schema": SCHEMA, "as_of_utc": cut.isoformat(),
        "status": "24_G8_SOURCE_WINDOW_COMPLETENESS_RESEARCH_ONLY_NOT_MODEL_PIT",
        "training_rules": {"monthly_prior": MONTHLY_PRIOR,
                           "quarterly_prior": QUARTERLY_PRIOR,
                           "latest_initial_observation_excluded_from_training": True},
        "slots": details, "summary": stat,
        "separate_revised_history_estimates_for_US_CPI_and_CHF_unemployment":
            estimated_proxies,
        "separate_first_rounded_SECO_issuer_reports_not_SNB_exact":
            swiss_alternative,
        "SECO_25_rounded_report_months_do_NOT_close_SNB_original_exact_PIT": True,
        "observed_first_web_22_and_estimated_context_2_must_never_be_combined_as_PIT": True,
        "series_counts_do_not_equal_valid_historical_PIT_trading_samples": True,
        "current_monthly_and_quarterly_observation_periods_not_comparable": True,
        "no_future_revision_or_backfill_from_revised_history": True,
        "current_US_BLS_oct2025_gap_never_imputed_as_observed": True,
        "EUR_EA21_membership_break_not_hidden": True,
        "CHF_SECO_rounded_never_called_first_SNB_exact": True,
        "retained_official_source_archive_original_SHA256_checked_each_run": True,
        "safe_to_publish_new_D": False, "safe_to_recalculate_28_pairs": False,
        "safe_to_use_for_beta": False, "safe_to_use_for_forward": False,
        "writes_live_data": False,
    }
    out["receipt_sha256"] = hashlib.sha256(json.dumps(
        {"cutoff": out["as_of_utc"], "slots": details}, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=ASOF)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        check(args.output.resolve().is_relative_to(Path("/tmp")),
              "read-only research output must remain under /tmp")
    out = evidence(cutoff=args.as_of)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, **out["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
