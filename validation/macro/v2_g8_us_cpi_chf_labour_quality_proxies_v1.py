#!/usr/bin/env python3
"""Two MISSING first-web historical G8 training windows: RESEARCH-only proxies.

The 24-slot official initial-publisher audit still proves only 22 numerically
continuous windows. This adds two visibly different *as-of current revised*
comparators, not recovered original release histories:

USD inflation: canonical registered CPIAUCSL SA INDEX yoy, current revised
data only; use the pre-existing 2025-10 BLS one-gap 24 OBSERVED months / 25
calendar months normalization. Never fabricate October CPI or confuse BLS
published NSA headline CPI with a CPIAUCSL SA-index vintage.

CHF labour: source currently revised exact SNB/SECO seasonally adjusted
unemployment rate level with 24 preceding monthly CURRENT-REVISED levels.
SECO's latest publisher first headline is 3.1% one decimal, not the exact
3.124988... first release; do not infer first release SA vintages for prior
24 months from the retrospectively revised SNB cube.

No output of this module is a macro model score, FX rank, backtest or Core.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    normalized_source, pillar_feature, index_to_period
)
from validation.macro.v2_us_shutdown_gap_research_v1 import (
    shadow_gap_estimate
)
from validation.macro.v2_eur_ea_regime_chf_precision_guard_v1 import (
    swiss_quality
)

SCHEMA = "GMFQ_MACRO_V2_US_CHF_TWO_MISSING_RELEASE_WINDOWS_PROVISIONAL_REVISED_PROXY_V1"
ASOF = "2026-10-26T23:59:59Z"
REGISTRY = ROOT / "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json"
DATA = ROOT / "live_data/sections"
WINDOW = 24


def require(valid, why):
    if not valid:
        raise ValueError("GMFQ_US_CHF_TWO_RESEARCH_ESTIMATES_REJECTED: " + why)


def _row(rows, wanted):
    hits = [x for x in rows if x.get("id") == wanted]
    require(len(hits) == 1, "exact one registered original metric required: " + wanted)
    return hits[0]


def profile(*, as_of=ASOF, source=None, thermo=None, registry=None):
    # This is NOT a replay at other historical dates: it uses current
    # revised values, which can have been updated AFTER previous cutoffs.
    require(as_of == ASOF, "single fixed comparison cutoff, not historic PIT availability")
    cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    require(cutoff.tzinfo is not None and cutoff.utcoffset().total_seconds()==0,
            "UTC required")
    snapshot = source if source is not None else json.loads(
        (DATA / "MACRO_SERIES.json").read_text(encoding="utf-8"))
    temperature = thermo if thermo is not None else json.loads(
        (DATA / "MACRO_THERMOMETER_DATA.json").read_text(encoding="utf-8"))
    settings = registry if registry is not None else json.loads(
        REGISTRY.read_text(encoding="utf-8"))
    require(set(snapshot)=={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}
            and temperature.get("currencies") and
            settings.get("series"), "G8 source and thermometer required")
    results = {}

    for ccy, dim in (("USD", "inflation"), ("CHF", "labour")):
        key=f"{ccy}.{dim}"
        canonical=settings["series"][key]
        thermo_dim=temperature["currencies"][ccy][dim]
        source_id=canonical["historical_replay_evidence"]["macro_series_id"]
        row=_row(snapshot[ccy],source_id)
        original = pillar_feature(ccy,dim,canonical,row,thermo_dim,cutoff.date())
        require(original["observation_period"]=="2026-09"
                and original["source_observation_is_current_revised_history_not_historic_pit"],
                "expected 2026-09 canonical current-revised series, not an issuer first-vintage")
        if ccy=="USD":
            require(canonical["series_id"]=="CPIAUCSL"
                    and canonical["transformation"]=="yoy_pct_from_index"
                    and original["research_robust_z"] is None
                    and original["missing_prior_periods"]==["2025-10"],
                    "official CPIAUCSL 2025 shutdown gap must remain unfilled")
            bridge=shadow_gap_estimate(
                "inflation",canonical,row,thermo_dim,original,cutoff.date())
            require(bridge["status"]==
                    "BLS_SHUTDOWN_GAP_AWARE_RESEARCH_ESTIMATE_NOT_PIT"
                    and bridge["training_observed_months_used"]==24
                    and bridge["training_calendar_months"]==25
                    and bridge["missing_calendar_periods"]==["2025-10"]
                    and bridge["original_missing_value_imputed"] is False
                    and bridge["not_equivalent_to_strict_24_consecutive_month_normalization"],
                    "USD gap-aware CPI must be explicit research approximation")
            results[key]={
                "slot":key,
                "source_series":"CPIAUCSL",
                "historical_first_web_periods_recovered_by_this":0,
                "original_first_web_training_history_complete":False,
                "revised_history_proxy_training_periods":24,
                "training_calendar_periods":25,
                "missing_observation":"2025-10",
                "missing_value_imputed":False,
                "latest_economic_period":"2026-09",
                "latest_current_revised_SA_index_yoy_pct":
                    original["observation_value"],
                "estimated_descriptive_robust_z":
                    bridge["estimated_research_robust_z"],
                "quality":"ESTIMATE_REVISED_CPIAUCSL_24_OBS_IN_25_MONTHS_NOT_PIT",
                "issuer_published_NSA_headline_not_equivalent_to_this_SA_index_yoy":True,
                "first_release_originals_acquired":False,
                "BLS_explanation":bridge["official_evidence_url"],
                "BLS_archived_CPI_news_release_index":
                    "https://www.bls.gov/bls/news-release/cpi.htm",
                "source_bytes_automated_retrieval_on_2026_10_27_blocked_403":True,
                "training_latest_observation_excluded":True,
                "may_backtest_or_rank_FX":False,
            }
        else:
            require(canonical["series_id"]=="CH_UNEMP_RATE"
                    and canonical["transformation"]=="level"
                    and thermo_dim["frequency"]=="M"
                    and thermo_dim["series_id"]=="CH_UNEMP_RATE",
                    "SECO SA registered jobless percentage, not CPI or ILO survey")
            samples, aliases=normalized_source(row,"M")
            latest=max(samples)
            required=list(range(latest-WINDOW,latest))
            require([index_to_period(i,"M") for i in required]==[
                f"{y:04d}-{m:02d}" for y in (2024,2025,2026)
                for m in range(1,13)
                if "2024-09"<=f"{y:04d}-{m:02d}"<="2026-08"
            ] and all(i in samples for i in required),
                "CHF 24 preceding revised months must be genuinely present")
            latest_exact=samples[latest][1]
            first=swiss_quality(cutoff=as_of)
            require(first["rounded_SECO_sa_rate_pct_visible"]==3.1
                    and first["original_exact_SNB_value_on_official_SECO_release_unverified"]
                    and first["SNB_exact_historic_release_PIT_approved"] is False
                    and first["rounding_consistency_interval_pct"]==
                    {"lower_inclusive":3.05,"upper_exclusive":3.15}
                    and math.isclose(latest_exact,first[
                        "current_SNB_exact_observation_pct_NOT_FIRST_RELEASE_VINTAGE"],
                                     rel_tol=0,abs_tol=1e-9),
                    "2026 Sep current revised SNB level must be distinct from SECO first rounded release")
            earlier=[samples[i][1] for i in required]
            med=statistics.median(earlier)
            mad=statistics.median(abs(v-med) for v in earlier)
            require(mad>1e-9,"CH unemployment revised-history robust dispersion zero")
            z=max(-3.,min(3.,(latest_exact-med)/(1.4826*mad)))
            require(math.isfinite(z), "invalid descriptive unemployment intensity")
            results[key]={
                "slot":key,
                "source_series":"CH_UNEMP_RATE",
                "historical_first_web_periods_recovered_by_this":0,
                "original_first_web_training_history_complete":False,
                "revised_history_proxy_training_periods":24,
                "training_calendar_periods":24,
                "missing_observation":None,
                "missing_value_imputed":False,
                "latest_economic_period":"2026-09",
                "latest_current_revised_SNB_exact_percent_NOT_FIRST_RELEASE":latest_exact,
                "latest_published_SECO_first_rounded_pct":3.1,
                "compatible_unrounded_first_rate_interval_pct":
                    first["rounding_consistency_interval_pct"],
                "estimated_descriptive_robust_z":z,
                "revised_historical_sample_median":med,
                "revised_historical_sample_mad":mad,
                "original_SECO_first_vintages_for_prior_24_periods_verified":False,
                "historical_SNB_exact_initial_publication_time_known":False,
                "source_day_2026_09_SECO_headline_document":
                    first["official_SECO_september_url"],
                "quality":"ESTIMATE_REVISED_SNB_RETROSPECTIVE_24M_NOT_FIRST_RELEASE",
                "first_release_originals_acquired":False,
                "training_latest_observation_excluded":True,
                "may_backtest_or_rank_FX":False,
            }
        require(results[key]["estimated_descriptive_robust_z"] is not None,
                "research fallback cannot be withheld without reason")
    ret={
        "schema":SCHEMA,
        "as_of_utc":as_of,
        "status":"TWO_PROVISIONAL_REVISED_HISTORICAL_DESCRIPTORS_NOT_FIRST_RELEASES",
        "two_explicitly_estimated_missing_source_windows":results,
        "summary":{
            "estimates_added":2,
            "USD_CPI_revised_history_observed_periods":24,
            "USD_CPI_unpublished_October_2025_first_release":True,
            "CHF_labour_revised_history_prior_periods":24,
            "CHF_SNB_first_release_exact_value_recovered":False,
            "genuinely_new_first_release_archival_rows_added":0,
            "macro_model_scores_approved":0,
            "FX_pair_rankings_changed":0,
        },
        "can_label_two_sources_estimated_for_research_display":True,
        "these_are_not_canonical_first_vintages":True,
        "historical_joint_PIT_source_certification_changed":False,
        "safe_to_publish_new_D":False,
        "safe_to_change_28_pairs":False,
        "safe_for_beta":False,"safe_for_forward":False,"writes_live_data":False,
    }
    ret["receipt_sha256"]=hashlib.sha256(json.dumps(
        {"as_of":as_of,"results":results},sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    return ret


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--as-of",default=ASOF)
    cli.add_argument("--output",type=Path)
    args=cli.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "research output only under /tmp")
    output=profile(as_of=args.as_of)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",
                               encoding="utf-8")
    print(json.dumps({"status":output["status"],**output["summary"],
                      "safe_to_publish_new_D":False},sort_keys=True))


if __name__=="__main__":
    main()
