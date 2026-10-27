#!/usr/bin/env python3
"""Resolve four *semantic* mismatches in the G8 labour/inflation web ledger.

This reconciles SOURCE IDENTITY only. Two identities have independent lineage
evidence (FRED UNRATE/BLS LNS14000000; Eurostat HICP dossier ID suffix).
Two are genuine non-substitutable measurement differences (monthly AUD
monthly CPI vs quarterly canonical CPI; SECO CHF rounded vs SNB exact SA rate).
It DOES NOT rewrite official vintages, manufacture first-release history,
authenticate immutable source bytes, or enable new live Macro/FX scores.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT

SCHEMA = "GMFQ_MACRO_V2_FOUR_SOURCE_SEMANTIC_RECONCILIATION_V1"
DOCS = {
    "USD.labour": "https://fred.stlouisfed.org/series/UNRATE",
    "EUR.inflation": "https://ec.europa.eu/eurostat/web/products-euro-indicators",
    "AUD.inflation": "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia",
    "CHF.labour": "https://data.snb.ch/api/cube/amarbma/data/json/en",
}
RESEARCH_PINNED = {
    "USD.labour": ("UNRATE", "M", "LNS14000000", "M",
                   "U.S. Bureau of Labor Statistics",
                   "SOURCE_LINEAGE_ALIAS_VERIFIED_NOT_PIT_CERTIFIED"),
    "EUR.inflation": ("EA_HICP_HEADLINE_YOY", "M",
                       "EA_HICP_HEADLINE_YOY_history_value", "M",
                       "Eurostat", "RESEARCH_DOSSIER_ID_SUFFIX_ALIAS_NOT_PIT_CERTIFIED"),
    "AUD.inflation": ("AU_CPI_HEADLINE_Q_YOY", "Q",
                       "AU_CPI_HEADLINE_M_YOY_context_value", "M",
                       "Australian Bureau of Statistics",
                       "CANDIDATE_NOT_EQUIVALENT_QUARTERLY_VS_MONTHLY"),
    "CHF.labour": ("CH_UNEMP_RATE", "M",
                    "CH_SECO_SA_REGISTERED_UNEMP_RATE_ONE_DECIMAL", "M",
                    "Swiss State Secretariat for Economic Affairs",
                    "CANDIDATE_NOT_EQUIVALENT_ROUNDED_VS_EXACT"),
}
STRICT_PINS = {
    "EUR.inflation": {
        "path": "validation/macro/eur_inflation_strict_pit_evidence_v1_2026-10-10.json",
        "schema": "GMFQ_EUR_INFLATION_STRICT_PIT_EVIDENCE_V1",
        "start": "2018-01", "end": "2026-09", "total": 105,
        "total_key": "materialized_months", "unit": "% YoY",
    },
    "AUD.inflation": {
        "path": "validation/macro/aud_inflation_strict_pit_evidence_v1_2026-10-09.json",
        "schema": "GMFQ_AUD_INFLATION_STRICT_PIT_EVIDENCE_V1",
        "start": "2018-03", "end": "2026-06", "total": 34,
        "total_key": "materialized_quarters", "unit": None,
    },
}
ROOT_PINS = {
    "USD.labour": "BLS Employment Situation CPS U-3, same source code LNS14000000 as FRED UNRATE, distinct dated web vintages",
    "EUR.inflation": "Eurostat flash first headline; EA20 before 2026 and EA21 after Jan 2026 require explicit population break controls",
    "AUD.inflation": "Quarterly historical original-release materialization exists in separate evidence receipt; monthly 11-web stream cannot replace it",
    "CHF.labour": "SECO rounded 3.1 percent news release does not certify exact SNB amarbma source precision or release clock",
}


def require(ok, detail):
    if not ok:
        raise ValueError("MACRO_V2_SOURCE_CROSSWALK_REJECTED: " + detail)


def official_strict_receipt(root: Path, key: str, catalogue_row: dict):
    pin = STRICT_PINS[key]
    data = json.loads((root / pin["path"]).read_text(encoding="utf-8"))
    core_id = catalogue_row["registered_core_series_id"]
    core_freq = catalogue_row["registered_core_frequency"]
    require(data.get("schema") == pin["schema"] and
            data.get("status") == "PASS" and
            data.get("target") == key and
            data.get("evidence_class") == "STRICT_DIRECT_ARCHIVAL_PIT" and
            data.get("authority") == catalogue_row["official_publisher"],
            "archival receipt schema/status/publisher drift: " + key)
    sc, coverage = data["series_contract"], data["coverage"]
    require(sc["series_id"] == core_id and
            sc["frequency"] == core_freq and
            coverage["start"] == pin["start"] and
            coverage["end"] == pin["end"] and
            coverage[pin["total_key"]] == pin["total"] and
            data.get("missing") == [] and data.get("duplicates") == [] and
            data.get("errors") == [],
            "archival receipt series identity, frequency or complete period drift: " + key)
    require(data.get("strict_rules", {}).get("revised_history_fallback_used") is False,
            "archival quarterly/monthly evidence must not use revised fallback")
    require(isinstance(data.get("semantic_rowset_sha256"), str) and
            len(data["semantic_rowset_sha256"]) == 64,
            "archival source semantic receipt hash missing")
    return {
        "archival_evidence_receipt_path": pin["path"],
        "archival_receipt_status": "PASS",
        "archival_documented_first_release_periods": pin["total"],
        "archival_documented_range": [pin["start"], pin["end"]],
        "archival_receipt_semantic_hash": data["semantic_rowset_sha256"],
        "archival_source_events_materialized_in_this_timeline": False,
        "receipt_does_not_independently_reverify_original_source_bytes_now": True,
        "safe_to_use_for_live_scores": False,
    }


def reconcile(catalogue: dict, *, root=ROOT):
    require(isinstance(catalogue, dict) and len(catalogue) == 16 and
            set(catalogue) == {
                f"{c}.{p}" for c in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
                for p in ("labour", "inflation")},
            "exact G8 16-dimension catalogue required")
    verdicts = {}
    for key, row in sorted(catalogue.items()):
        require(row["currency"] + "." + row["pillar"] == key and
                row.get("candidate_source_canonical_mapping_certified") is False and
                row.get("eligible_for_live_macro_score") is False,
                "unapproved mapping/model promotion: " + key)
        was_equal = row["series_and_frequency_match"]
        independent_equal = (
            row["candidate_series_id"] == row["registered_core_series_id"] and
            row["candidate_frequency"] == row["registered_core_frequency"])
        require(was_equal is independent_equal, "reported ID/frequency match spoofed")
        out = {
            "slot": key, "registered_series_id": row["registered_core_series_id"],
            "registered_frequency": row["registered_core_frequency"],
            "web_candidate_series_id": row["candidate_series_id"],
            "web_candidate_frequency": row["candidate_frequency"],
            "official_publisher": row["official_publisher"],
            "mapping_independently_certified_for_production": False,
            "complete_joint_historical_PIT_replay_certified": False,
            "ready_to_modify_live_core_D": False,
            "eligible_for_currency_strength_ranking": False,
        }
        if key not in RESEARCH_PINNED:
            require(was_equal, "unreviewed mismatch outside four documented cases")
            out.update({
                "decision": "EXACT_SOURCE_ID_AND_FREQUENCY_NO_PIT_CERTIFICATION",
                "economic_identity_recognized_by_matching_ids": True,
                "candidate_can_replace_canonical_historical_vintages": False,
            })
        else:
            (core_id, core_f, can_id, can_f, publisher, decision) = RESEARCH_PINNED[key]
            require(not was_equal and
                    (core_id, core_f, can_id, can_f, publisher) ==
                    (row["registered_core_series_id"],
                     row["registered_core_frequency"],
                     row["candidate_series_id"],
                     row["candidate_frequency"], row["official_publisher"]),
                    "four-case source contract changed; manual re-review mandatory: " + key)
            recognized = key in ("USD.labour", "EUR.inflation")
            out.update({
                "decision": decision,
                "economic_identity_recognized_by_matching_ids": False,
                "conceptual_source_lineage_documented": recognized,
                "candidate_can_replace_canonical_historical_vintages": False,
                "specific_evidence_url": DOCS[key],
                "source_definition_limitation": ROOT_PINS[key],
            })
            if key in STRICT_PINS:
                out.update(official_strict_receipt(root, key, row))
            if key == "USD.labour":
                # Proven by the Federal Reserve Bank of St Louis notes. This
                # link resolves concept/source lineage, NOT first-web values.
                out.update({
                    "fred_unrate_BLS_source_code": "LNS14000000",
                    "bls_web_first_release_pilot_not_full_current_chain": True,
                    "source_lineage_confident_not_replay_ready": True,
                    "missing_october_2025_unemployment_not_imputed": True,
                })
            if key == "CHF.labour":
                # No inversion of rounding: 3.1% cannot prove exact 3.124...
                out.update({
                    "documented_SECO_press_release_precision": "one decimal percentage point",
                    "canonical_SNB_series_precision": "more than one decimal",
                    "rounding_information_loss_not_recoverable": True,
                    "original_precise_first_release_timestamp_unknown": True,
                })
        verdicts[key] = out
    statuses = [r["decision"] for r in verdicts.values()]
    exact = sum(s == "EXACT_SOURCE_ID_AND_FREQUENCY_NO_PIT_CERTIFICATION"
                for s in statuses)
    aliases = sum(s in (
        "SOURCE_LINEAGE_ALIAS_VERIFIED_NOT_PIT_CERTIFIED",
        "RESEARCH_DOSSIER_ID_SUFFIX_ALIAS_NOT_PIT_CERTIFIED")
        for s in statuses)
    real = sum(s.startswith("CANDIDATE_NOT_EQUIVALENT") for s in statuses)
    require((exact, aliases, real) == (12, 2, 2),
            "12 exact + 2 lineage + 2 genuine measurement mismatches expected")
    return {
        "schema": SCHEMA,
        "status": "RESEARCH_IDENTITY_RECONCILED_NOT_PIT_VINTAGES_APPROVED",
        "verdicts": verdicts,
        "summary": {
            "slots": 16, "exact_series_ID_and_frequency": exact,
            "source_lineage_aliases_documented_not_production_approved": aliases,
            "genuine_measurement_mismatches_to_replace": real,
            "registered_AUD_quarterly_archival_receipt_periods": 34,
            "registered_EUR_monthly_archival_receipt_periods": 105,
            "whole_PIT_timelines_newly_materialized": 0,
            "macro_model_scores_approved": 0,
            "fx_ranking_score_replacements": 0,
        },
        "research_aliases_are_not_source_bytes_or_release_vintages": True,
        "quarterly_AUD_receipt_not_monthly_CPI_source_substitution": True,
        "SECO_rounded_rate_not_SNB_exact_first_release": True,
        "never_overwrite_G8_source_registry": True,
        "safe_to_publish_new_D": False,
        "safe_to_change_28_pairs": False,
        "safe_for_beta": False,
        "safe_for_forward": False,
        "writes_live_data": False,
    }


def main():
    from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import (
        run as timeline_run
    )
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "only research outputs in /tmp permitted")
    t = timeline_run()
    report = t["source_semantic_reconciliation"]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n",
                               encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, **report["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
