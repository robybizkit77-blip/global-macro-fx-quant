"""Replay the immutable 27 October Macro V2 research coordinates."""

from hashlib import sha256
import json
from pathlib import Path

from validation.macro.score_formula_provenance_v1 import FROZEN_HISTORICAL_SCORES, FROZEN_MACRO_ASOF
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import build
from validation.macro.v2_g8_three_axis_economic_shadow_v1 import SCHEMA as SHADOW_SCHEMA

ROOT = Path(__file__).resolve().parents[2]

FROZEN_RESEARCH = (ROOT /
    "validation/macro/fixtures/v2_g8_frozen_domestic_research_coordinates_2026_10_27.json")


def frozen_research_shadow():
    """Load the 27 October observed/revised research input from its saved CI artifact."""
    raw = FROZEN_RESEARCH.read_bytes()
    if sha256(raw).hexdigest() != "205962094f9cf10de035892f0b3eef2d30f529b3cc319dd0d94c62271ee5e232":
        raise ValueError("27 October research input differs from its frozen fixture")
    fixture = json.loads(raw)
    countries = {}
    for ccy, source in fixture["countries"].items():
        g, l, p = (source[k] for k in ("g","l","p"))
        flags = list(source["flags"])
        details = {
            "growth":{
                "reference_period":"2026Q2",
                "method":"FIRST_WEB_GDP_12_PRIOR_QUARTERS_RESEARCH_ONLY",
                "quality":("GDP_FIRST_WEB_DEFINITION_CAVEAT_NO_PIT"
                           if ccy in ("EUR","CHF") else
                           "GDP_FIRST_WEB_RESEARCH_NO_ORIGINAL_DAY_ARCHIVE"),
                "is_estimate":False,
            },
            "labour":{
                "reference_period":source["lp"],
                "method":("ESTIMATE_BLS_SHUTDOWN_EXACT_ONE_GAP_25_CALENDAR_MONTHS"
                          if source["estimated"] else
                          "OBSERVED_REVISED_HISTORY_24M_OR_12Q"),
                "quality":("ESTIMATED_NOT_OBSERVED_24_CONSECUTIVE_MONTHS_NO_PIT"
                           if source["estimated"] else
                           "RESEARCH_CURRENT_REVISED_HISTORY_NO_HISTORIC_PIT"),
                "is_estimate":source["estimated"],
            },
            "inflation":{
                "reference_period":source["ip"],
                "method":("ESTIMATE_BLS_SHUTDOWN_EXACT_ONE_GAP_25_CALENDAR_MONTHS"
                          if source["estimated"] else
                          "OBSERVED_REVISED_HISTORY_24M_OR_12Q"),
                "quality":("ESTIMATED_NOT_OBSERVED_24_CONSECUTIVE_MONTHS_NO_PIT"
                           if source["estimated"] else
                           "RESEARCH_CURRENT_REVISED_HISTORY_NO_HISTORIC_PIT"),
                "is_estimate":source["estimated"],
            },
        }
        countries[ccy] = {
            "currency":ccy,
            "growth_relative_to_own_history_z":g,
            "labour_tightness_relative_to_own_history_z":l,
            "inflation_pressure_relative_to_own_history_z":p,
            "illustrative_activity_labour_balance_z":round(.5*(g+l),12),
            "quality_flags":flags,
            "dimensions":details,
            "fx_currency_strength_score":None,
            "fx_directional_bias":None,
            "policy_rate_signal":None,
            "cb_pricing_signal":None,
            "candidate_for_pair_ranking":False,
            "approved_for_live_core_D":False,
        }
    return {
        "schema":SHADOW_SCHEMA,
        "status":"EIGHT_SHADOW_THREE_AXIS_ECONOMIC_SCENARIOS_NOT_MACRO_SCORES",
        "as_of":fixture["economic_as_of"],
        "scope":{"activity_weights":{
            "growth":0.5, "labour_tightness":0.5,"inflation_in_activity":0.0}},
        "summary":{"research_axes":24,"economies":8,"FX_scores_approved":0},
        "countries":countries,
        "observed_data_is_not_historic_publication_vintage_replay":True,
        "economic_axis_math_not_validated_against_out_of_sample_events":True,
        "safe_to_publish_new_D":False,
        "safe_to_update_pair_theses":False,
        "safe_for_beta":False,
        "safe_for_forward":False,
        "writes_live_data":False,
    }


def run_frozen_candidate():
    return build(frozen_research_shadow(), {
        "asOf": FROZEN_MACRO_ASOF,
        "macro": FROZEN_HISTORICAL_SCORES,
    })
