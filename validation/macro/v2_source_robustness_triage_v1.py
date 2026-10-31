#!/usr/bin/env python3
"""Read-only G8 Macro V2 source-gap and exact weight robustness triage.

Combines independently dated snapshots. The historical archive and frozen
candidate are NOT a current synchronized PIT observation panel. Never creates
FX strength, policy repricing, trade signals, D.json or a live data update.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from validation.macro.v2_g8_24_axis_training_history_gap_audit_v1 import (
    SCHEMA as GAP_SCHEMA,
)
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    SCHEMA as CANDIDATE_SCHEMA,
    G8, activity_class, continuous_weight_interval,
)

SCHEMA = "GMFQ_MACRO_V2_SOURCE_AND_ROBUSTNESS_TRIAGE_V1"
PILLARS = ("growth", "labour", "inflation")
CURRENT_READINESS_SCHEMA = "GMFQ_MACRO_V2_G8_CURRENT_SOURCE_READINESS_V1"


def require(condition, reason):
    if not condition:
        raise ValueError("MACRO_V2_TRIAGE_REJECTED: " + reason)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def boundary_distance(growth, labour):
    """Exact z-distance to a classification boundary for EVERY weight in [1/4,3/4].

    An independent +/-epsilon shift on both underlying z-coordinates
    changes the weighted sum by at most epsilon because weights are
    nonnegative and sum to one. This is geometry, NOT an empirical vintage
    revision quantile or a probability. Zero means already weight-sensitive.
    """
    require(finite(growth) and finite(labour)
            and abs(growth) <= 3.00000001 and abs(labour) <= 3.00000001,
            "input z must be finite and within fixed prior clipping range")
    band = continuous_weight_interval(growth, labour)
    lo = band["domestic_activity_z_min"]
    hi = band["domestic_activity_z_max"]
    if not band["classification_unchanged_at_every_weight_in_interval"]:
        return 0.0
    state = activity_class((growth + labour) / 2)
    if state == "FIRM_RELATIVE_TO_OWN_HISTORY":
        margin = lo - 0.5
    elif state == "SOFT_RELATIVE_TO_OWN_HISTORY":
        margin = -0.5 - hi
    else:
        margin = min(lo + 0.5, 0.5 - hi)
    require(margin >= -1e-10, "weight interval classification contradicted")
    return round(max(0.0, margin), 9)


def build(gap, candidate, readiness):
    require(isinstance(gap, dict) and gap.get("schema") == GAP_SCHEMA
            and gap.get("safe_to_publish_new_D") is False
            and gap.get("safe_to_recalculate_28_pairs") is False,
            "historical source audit cannot authorize scores")
    require(isinstance(candidate, dict)
            and candidate.get("schema") == CANDIDATE_SCHEMA
            and candidate.get("safe_to_publish_D") is False
            and candidate.get("safe_to_update_pair_theses") is False
            and candidate.get("writes_live_data") is False
            and candidate.get("summary", {}).get("FX_scores_produced") == 0,
            "frozen candidate must remain research-only")
    require(isinstance(readiness, dict)
            and readiness.get("schema") == CURRENT_READINESS_SCHEMA
            and readiness.get("eligible_to_publish_D") is False
            and readiness.get("eligible_to_recompute_28_pairs") is False
            and readiness.get("historical_PIT_or_OOS_validated") is False
            and readiness.get("no_missing_z_substituted") is True,
            "current input readiness unexpectedly promoted to model")
    keys = {c + "." + pillar for c in G8 for pillar in PILLARS}
    slots = gap.get("slots", {})
    cases = candidate.get("countries", {})
    current = readiness.get("countries", {})
    require(set(slots) == keys and len(slots) == 24,
            "24 distinct G8 source audit slots required")
    require(set(cases) == set(G8) and set(current) == set(G8),
            "8-country candidate/readiness not aligned")
    require(gap.get("summary", {}).get("genuinely_historic_PIT_training_slots_certified") == 0,
            "not a vintage-certified historical panel")
    require(candidate.get("summary", {}).get("axes") == 24
            and candidate.get("summary", {}).get("currencies") == 8,
            "candidate size drift")
    result_slots = []
    for key in sorted(keys):
        raw = slots[key]
        ccy, pillar = key.split(".")
        missing = raw.get("missing_required_prior_periods")
        caveats = raw.get("current_PIT_research_comparability_caveats")
        required = raw.get("prior_first_release_periods_required")
        require(raw.get("slot") == key and raw.get("currency") == ccy
                and raw.get("pillar") == pillar
                and type(missing) is list and len(missing) == len(set(missing))
                and type(caveats) is list and type(required) is int
                and required in (12, 24)
                and len(missing) <= required
                and raw.get("model_PIT_training_approved") is False
                and raw.get("FX_signal_approved") is False
                and raw.get("complete_source_day_original_bytes_and_revision_chain_certified") is False,
                key + " source/vintage contract violation")
        complete = raw.get("prior_initial_web_sequence_complete_mathematically")
        require(type(complete) is bool and complete == (len(missing) == 0),
                key + " contradicts contiguous previous periods")
        if missing:
            action = ("RETRIEVE_OR_DOCUMENT_NONRELEASED_BLS_CPI_MONTH_NO_IMPUTATION"
                      if key == "USD.inflation" else
                      "RECOVER_ORIGINAL_SNB_PRECISE_FIRST_RELEASE_NOT_ROUNDED_SECO"
                      if key == "CHF.labour" else
                      "RECOVER_PREVIOUS_FIRST_RELEASE_PERIODS")
            phase = "MISSING_PRIOR_FIRST_RELEASES"
        elif caveats:
            phase, action = ("DEFINITION_OR_VINTAGE_RECONCILIATION",
                             "RECONCILE_SOURCE_DEFINITION_AND_FIRST_RELEASE_CLOCK")
        else:
            phase, action = ("ISSUER_DAY_VINTAGE_ARCHIVE_UNCERTIFIED",
                             "CERTIFY_FIRST_RELEASE_SOURCE_BYTES_AND_REVISION_CHAIN")
        result_slots.append({
            "key": key, "currency": ccy, "pillar": pillar,
            "frequency": raw["published_observation_frequency"],
            "evidence_asof_period": raw["reference_period_last_first_web"],
            "prior_required": required, "missing_prior_periods": sorted(missing),
            "missing_count": len(missing), "comparability_caveats": caveats,
            "quality": raw["research_only_quality_label"],
            "phase": phase, "next_documentary_action": action,
            "first_release_training_PIT_certified": False,
        })
    # Source work priority is ranked by evidence deficit, NOT by a FX bias or
    # putative opportunity. Missing slots first, then definition and PIT archive.
    action_order = {"MISSING_PRIOR_FIRST_RELEASES": 0,
                    "DEFINITION_OR_VINTAGE_RECONCILIATION": 1,
                    "ISSUER_DAY_VINTAGE_ARCHIVE_UNCERTIFIED": 2}
    queue = sorted(result_slots,
                   key=lambda x: (action_order[x["phase"]],
                                  -x["missing_count"], x["key"]))
    country_diagnostics = {}
    for c in G8:
        row = cases[c]
        g = row.get("growth_within_history_z")
        l = row.get("unemployment_tightness_within_history_z")
        margin = boundary_distance(g, l)
        interval = continuous_weight_interval(g, l)
        require(row.get("continuous_weight_sensitivity_RESEARCH_ONLY") == interval
                and row.get("activity_class_stable_across_25_50_75pct_growth") is
                interval["classification_unchanged_at_every_weight_in_interval"],
                c + " existing weight stress disagrees with exact interval")
        stresses = row.get("hypothetical_axis_revision_stress_RESEARCH_ONLY", {})
        for key, eps in (("10", .10), ("25", .25), ("50", .50)):
            item = stresses.get(key, {})
            # Exact boundary distance and pre-existing three stress gates must
            # agree; these are hypothetical epsilon shifts, NOT revision data.
            expected = (activity_class(interval["domestic_activity_z_min"] - eps) ==
                        activity_class(interval["domestic_activity_z_max"] + eps))
            require(item.get("class_invariant_to_all_weights_and_independent_axis_shifts")
                    is expected, c + " stress gate disagrees with the interval")
        axes = current[c].get("axes")
        require(isinstance(axes, dict) and set(axes) == set(PILLARS)
                and current[c].get("complete_three_axis_research_candidate") is
                all(axes[p].get("z_available_for_RESEARCH_ONLY") is True
                    for p in PILLARS), c + " observed readiness contract mismatch")
        blocked = [p for p in PILLARS if axes[p].get("z_available_for_RESEARCH_ONLY") is not True]
        country_diagnostics[c] = {
            "frozen_candidate_asof": candidate["economic_as_of"],
            "current_input_asof": readiness["as_of"],
            "current_blocked_research_axes": blocked,
            "historical_weight_interval": [0.25, 0.75],
            "classification_at_fixed_candidate": row["domestic_activity_class"],
            "classification_weight_robust": interval[
                "classification_unchanged_at_every_weight_in_interval"],
            "exact_boundary_distance_z_hypothetical_not_empirical": margin,
            "weight_min_activity_z": interval["domestic_activity_z_min"],
            "weight_max_activity_z": interval["domestic_activity_z_max"],
            "caveats": row["source_quality_flags"],
            "cannot_promote_to_current_macro_FX_or_policy_score": True,
        }
    source_missing = [x for x in queue if x["missing_count"] > 0]
    assert sum(x["missing_count"] for x in result_slots) == gap["summary"][
        "missing_required_prior_periods_total"]
    assert len(result_slots) - len(source_missing) == gap["summary"][
        "prior_first_web_contiguous_12Q_or_24M_slots"]
    return {
        "schema": SCHEMA,
        "historical_source_evidence_asof": gap["as_of_utc"],
        "frozen_domestic_candidate_asof": candidate["economic_as_of"],
        "current_input_readiness_asof": readiness["as_of"],
        "snapshots_are_not_synchronous_and_cannot_be_joined_into_backtest": True,
        "status": "DOCUMENTARY_WORK_QUEUE_AND_FIXED_CANDIDATE_STRESS_RESEARCH_ONLY",
        "source_work_queue": queue,
        "countries": country_diagnostics,
        "summary": {
            "g8_currencies": 8, "source_axes": 24,
            "mathematically_contiguous_windows": len(result_slots)-len(source_missing),
            "missing_window_axes": [r["key"] for r in source_missing],
            "missing_prior_reference_periods": sum(x["missing_count"] for x in result_slots),
            "fully_certified_historical_PIT_axes": 0,
            "candidate_countries_weight_robust": sum(
                x["classification_weight_robust"] for x in country_diagnostics.values()),
            "candidate_countries_weight_ambiguous": sum(
                not x["classification_weight_robust"] for x in country_diagnostics.values()),
            "current_research_input_blocked_countries": readiness["currencies_blocked"],
        },
        "risk_and_inference_constraints": {
            "z_distance_is_hypothetical_not_empirically_calibrated": True,
            "historical_web_windows_not_complete_PIT": True,
            "mixed_reference_periods_not_cross_country_comparable": True,
            "source_work_priority_is_not_investment_ranking": True,
            "no_missing_months_imputed_as_observed": True,
        },
        "safe_to_publish_new_D": False,
        "safe_to_recalculate_28_pairs": False,
        "safe_to_use_for_beta_or_forward": False,
        "writes_live_data": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gap", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(Path("/tmp")),
            "research receipt must remain in /tmp")
    data = build(json.loads(args.gap.read_text()),
                 json.loads(args.candidate.read_text()),
                 json.loads(args.readiness.read_text()))
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": data["status"],
                      "summary": data["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))


if __name__ == "__main__":
    main()
