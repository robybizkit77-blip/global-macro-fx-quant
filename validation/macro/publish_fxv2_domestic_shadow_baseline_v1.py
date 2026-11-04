#!/usr/bin/env python3
"""V2 research-only publisher for the EXISTING, preregistered 50/50 Macro candidate.

No generator-fitting, no FX scores, no D.json writes or backtest eligibility.
The source/period fingerprint determines a new market observation; an audit
execution on a later day cannot manufacture a new macro release.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    run as candidate_run, run_source_readiness, FORMULA,
    activity_class, price_class, indicative_regime,
    continuous_weight_interval,independent_axis_revision_envelope,
)

from validation.macro.v2_g8_observed_feature_bridge_v1 import run as observed_run

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "site/fx-quant-v2/macro-shadow-formula-v1.json"
CCYS = ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
SCHEMA = "GMFQ_FXV2_MACRO_SHADOW_FORMULA_RESEARCH_V1"
FALLBACK_DATE = "2026-10-27"

def need(cond, why):
    if not cond:
        raise ValueError("FXV2_MACRO_SHADOW_PUBLISH_GUARD: " + why)

def valid_number(v):
    return type(v) in (float,int) and math.isfinite(v) and abs(v)<=3.0000001

def build(candidate:dict, readiness:dict, today:date)->dict:
    need(candidate.get("schema")=="GMFQ_MACRO_V2_EXPLICIT_DOMESTIC_CANDIDATE_V1" and
         candidate.get("formula_version")==FORMULA and
         candidate.get("status")=="EXPLICIT_8_COUNTRY_MACRO_CANDIDATE_RESEARCH_NO_PIT_NO_FX",
         "existing preregistered formula contract changed")
    need(candidate.get("summary",{}).get("currencies")==8 and
         candidate["summary"].get("axes")==24 and
         candidate["summary"].get("FX_scores_produced")==0 and
         candidate["summary"].get("28_pair_theses_recomputed")==0 and
         candidate["summary"].get("D_json_rebuilt") is False and
         candidate.get("safe_to_publish_D") is False and
         candidate.get("safe_to_update_pair_theses") is False and
         candidate.get("safe_to_use_for_beta") is False and
         candidate.get("safe_to_use_for_forward") is False and
         candidate.get("writes_live_data") is False and
         candidate.get("historical_first_publication_PIT_not_certified") is True and
         candidate.get("out_of_sample_falsification_not_completed") is True,
         "macro candidate is not a safe isolated V2-only research source")
    need(readiness.get("schema")=="GMFQ_MACRO_V2_G8_CURRENT_SOURCE_READINESS_V1" and
         readiness.get("eligible_to_publish_D") is False and
         readiness.get("eligible_to_recompute_28_pairs") is False and
         readiness.get("historical_PIT_or_OOS_validated") is False and
         readiness.get("writes_live_data") is False and
         set(readiness.get("countries",{}))==set(CCYS),
         "source readiness failed closed or country coverage invalid")
    cutoff=date.fromisoformat(candidate["economic_as_of"])
    need(cutoff<=today and cutoff>=date.fromisoformat(FALLBACK_DATE),
         "candidate checked after today or before registered formula")
    need(set(candidate["countries"])==set(CCYS),"candidate G8 missing")
    countries={}
    for ccy in CCYS:
        x=candidate["countries"][ccy]
        axes=x["source_quality_details"]
        need(set(axes)=={"growth","labour","inflation"} and
             all(axes[k].get("period") and axes[k].get("quality") and
                 axes[k].get("method") and type(axes[k].get("is_estimate")) is bool
                 for k in axes),"missing quality / observed periods "+ccy)
        z_g=x.get("growth_within_history_z")
        z_l=x.get("unemployment_tightness_within_history_z")
        z_p=x.get("inflation_pressure_within_history_z")
        z_a=x.get("domestic_activity_candidate_z")
        need(all(valid_number(z) for z in (z_g,z_l,z_p,z_a)) and
             abs(z_a-.5*(z_g+z_l))<1e-9,
             "numeric 50/50 domestic formula violated "+ccy)
        sensitivity=x["continuous_weight_sensitivity_RESEARCH_ONLY"]
        need(sensitivity["growth_weight_interval_inclusive"]==[0.25,0.75] and
             type(sensitivity["classification_unchanged_at_every_weight_in_interval"]) is bool and
             type(x["activity_class_stable_across_25_50_75pct_growth"]) is bool and
             sensitivity["classification_unchanged_at_every_weight_in_interval"]==
                 x["activity_class_stable_across_25_50_75pct_growth"],
             "continuous weight sensitivity contract invalid "+ccy)
        stresses=x["hypothetical_axis_revision_stress_RESEARCH_ONLY"]
        need(set(stresses)=={"10","25","50"} and all(
             type(v["class_invariant_to_all_weights_and_independent_axis_shifts"]) is bool
             for v in stresses.values()),"revision stress missing "+ccy)
        countries[ccy]={
           "activity_z_research":z_a,
           "growth_z_research":z_g,
           "labour_tightness_z_research":z_l,
           "inflation_pressure_z_research":z_p,
           "domestic_activity_class_research":x["domestic_activity_class"],
           "inflation_pressure_class_research":x["domestic_inflation_pressure_class"],
           "indicative_regime_NOT_canonical_D":x["indicative_domestic_regime"],
           "stable_for_continuous_growth_weight_25_to_75_pct":
               sensitivity["classification_unchanged_at_every_weight_in_interval"],
           "hypothetical_independent_axis_z_revision_stability":{
               eps:stresses[eps]["class_invariant_to_all_weights_and_independent_axis_shifts"]
               for eps in ("10","25","50")
           },
           "data_quality_flags":x["source_quality_flags"],
           "source_axes":axes,
           "official_first_publication_PIT_replay_complete":False,
           "fx_policy_or_return_signal":None,
        }
    economic_fingerprint=hashlib.sha256(json.dumps(countries,
       sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    return {
      "schema":SCHEMA,"status":"RESEARCH_SHADOW_FORMULA_READY_NOT_FX_MODEL",
      "formula_version":FORMULA,
      "economic_source_cutoff_rome":cutoff.isoformat(),
      "source_fingerprint_sha256":economic_fingerprint,
      "formula":"Activity = 0.50 * GDP_z + 0.50 * (- unemployment_rate_z); inflation_pressure = CPI_z separately",
      "weights":{"growth_z":0.5,"labour_tightness_z":0.5,"inflation_in_activity":0},
      "weight_sensitivity":[0.25,0.5,0.75],
      "source_and_revision_quality_is_not_historical_PIT":True,
      "hypothetical_revision_stress_not_a_historical_revision_distribution":True,
      "country_z_scores_not_cross_country_strength":True,
      "original_frozen_legacy_D_asof":candidate["legacy_core_as_of"],
      "source_readiness_status":readiness["status"],
      "source_readiness_blocked_axes":readiness["blocked"],
      "countries":countries,
      "summary":{
         "currencies":8,"research_axes":24,
         "unstable_to_weights":candidate["summary"]["countries_unstable_to_weights"],
         "countries_with_estimates":candidate["summary"]["countries_with_estimates"],
         "hypothetically_robust_to_0p25z_axis_shifts":
             candidate["summary"]["countries_robust_hypothetical_axis_shift_0p25_z"],
         "fx_pairs_unchanged":28,
         "fx_directional_signals_generated":0,
      },
      "eligible_for_fx_core":False,"eligible_for_pair_rankings":False,
      "eligible_for_trading":False,"eligible_for_forward":False,
      "eligible_for_backtests":False,"canonical_D_untouched":True,
      "note":"New reproducible within-country research formula, NOT original legacy D generator. GDP initial issuer web + revised labour/CPI data with source estimates, mixed vintages and country definition caveats. Experimental z levels and weight sensitivities must not be compared as FX strength. Historical PIT OOS not certified.",
    }

def partial_from_strict_source(observed:dict, readiness:dict, today:date) -> dict:
    """Compute only documented domestic A where BOTH strict z inputs exist.

    A missing/zero-MAD point stays None; do not invent a replacement score.
    This is a separate incomplete RESEARCH snapshot, not the approved 8-country
    candidate nor permission to touch the old D generator.
    """
    need(observed.get("status")=="OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL" and
         observed.get("safe_to_publish_new_D") is False and
         observed.get("safe_to_update_pair_theses") is False and
         observed.get("safe_to_use_for_forward") is False and
         observed.get("writes_live_data") is False and
         observed.get("current_values_are_not_verified_first_release_vintages") is True and
         observed.get("gdp_initial_web_features_not_model_growth_scores") is True,
         "observed research source not isolated from the Core")
    need(readiness.get("schema")=="GMFQ_MACRO_V2_G8_CURRENT_SOURCE_READINESS_V1" and
         readiness.get("eligible_to_publish_D") is False and
         readiness.get("eligible_to_recompute_28_pairs") is False and
         readiness.get("historical_PIT_or_OOS_validated") is False and
         readiness.get("writes_live_data") is False and
         set(readiness.get("countries",{}))==set(CCYS),
         "partial current-source admission invalid")
    raw=observed["inflation_labour"]
    gdp=observed["growth_quarterly_gdp_initial_web_research_features"]
    need(set(raw)=={c+"."+p for c in CCYS for p in ("labour","inflation")} and
         set(gdp)==set(CCYS),"unexpected G8 economic source identities")
    countries={}
    calculated=0
    for c in CCYS:
        g=gdp[c]
        l=raw[c+".labour"]
        p=raw[c+".inflation"]
        need(g.get("currency")==c and l.get("currency")==c and p.get("currency")==c and
             l.get("pillar")=="labour" and p.get("pillar")=="inflation" and
             g.get("current_initial_value_excluded_from_training") is True and
             l.get("eligible_for_macro_score") is False and
             p.get("eligible_for_macro_score") is False,
             c+" economic lineage incompatible")
        zv={}
        source_axes={}
        for pillar,row,zkey,period,sign in [
           ("growth",g,"research_robust_growth_z",g.get("latest_initial_period"),1),
           ("labour",l,"research_robust_z",l.get("observation_period"),-1),
           ("inflation",p,"research_robust_z",p.get("observation_period"),1),
        ]:
            z=row.get(zkey)
            available=valid_number(z)
            need(z is None or available,c+" "+pillar+" invalid numerical z")
            status=row.get("status","UNKNOWN")
            quality=(
                "CURRENT_REVISED_NOT_PIT" if pillar!="growth" else
                "FIRST_PUBLISHER_WEB_NOT_ARCHIVED_PIT"
            )
            source_axes[pillar]={
               "period":period,
               "method":status,
               "quality":quality,
               "is_estimate":False,
               "strict_z_available":available,
               "missing_reason":None if available else status,
            }
            need(isinstance(period,str) and bool(period) and
                 period[:4]<=today.isoformat()[:4],c+" source period unavailable or future")
            zv[pillar]=sign*float(z) if available else None
        a=.5*(zv["growth"]+zv["labour"]) if zv["growth"] is not None and zv["labour"] is not None else None
        sensitivity=None
        stress=None
        class_a=None
        if a is not None:
            calculated+=1
            sensitivity=continuous_weight_interval(zv["growth"],zv["labour"])
            class_a=activity_class(a)
            stress={
               str(int(eps*100)):independent_axis_revision_envelope(
                    zv["growth"],zv["labour"],eps
               )["class_invariant_to_all_weights_and_independent_axis_shifts"]
               for eps in (.10,.25,.50)
            }
        countries[c]={
          "activity_z_research":round(a,12) if a is not None else None,
          "growth_z_research":zv["growth"],
          "labour_tightness_z_research":zv["labour"],
          "inflation_pressure_z_research":zv["inflation"],
          "domestic_activity_class_research":class_a,
          "inflation_pressure_class_research":(
              price_class(zv["inflation"]) if zv["inflation"] is not None else None),
          "indicative_regime_NOT_canonical_D":(
              indicative_regime(a,zv["inflation"])
              if a is not None and zv["inflation"] is not None else None),
          "stable_for_continuous_growth_weight_25_to_75_pct":(
              sensitivity["classification_unchanged_at_every_weight_in_interval"]
              if sensitivity else None),
          "hypothetical_independent_axis_z_revision_stability":stress,
          "data_quality_flags":[k+"_"+v["missing_reason"] for k,v in source_axes.items()
                                if v["missing_reason"]],
          "source_axes":source_axes,
          "official_first_publication_PIT_replay_complete":False,
          "fx_policy_or_return_signal":None,
        }
    need(calculated<8,
         "full strict eight-country input arrived; use preregistered full candidate instead")
    fingerprint=hashlib.sha256(json.dumps(countries,sort_keys=True,ensure_ascii=False,
                 separators=(",",":")).encode("utf-8")).hexdigest()
    return {
       "schema":SCHEMA,"status":"PARTIAL_SHADOW_SOURCE_GAPS_RESEARCH_ONLY",
       "formula_version":FORMULA,"economic_source_cutoff_rome":today.isoformat(),
       "source_fingerprint_sha256":fingerprint,
       "formula":"Activity = 0.50 * GDP_z + 0.50 * (- unemployment_rate_z); inflation_pressure = CPI_z separately",
       "weights":{"growth_z":.5,"labour_tightness_z":.5,"inflation_in_activity":0},
       "weight_sensitivity":[.25,.5,.75],
       "source_and_revision_quality_is_not_historical_PIT":True,
       "hypothetical_revision_stress_not_a_historical_revision_distribution":True,
       "country_z_scores_not_cross_country_strength":True,
       "original_frozen_legacy_D_asof":"2026-09-25",
       "source_readiness_status":readiness["status"],
       "source_readiness_blocked_axes":readiness["blocked"],
       "countries":countries,
       "summary":{"currencies":8,"research_axes":24,
          "countries_with_calculable_activity":calculated,
          "countries_blocked_activity":8-calculated,
          "unstable_to_weights":sum(v["activity_z_research"] is not None and
            v["stable_for_continuous_growth_weight_25_to_75_pct"] is False
            for v in countries.values()),
          "countries_with_estimates":0,
          "hypothetically_robust_to_0p25z_axis_shifts":sum(
             v["hypothetical_independent_axis_z_revision_stability"] is not None and
             v["hypothetical_independent_axis_z_revision_stability"]["25"] is True
             for v in countries.values()),
          "fx_pairs_unchanged":28,"fx_directional_signals_generated":0},
       "eligible_for_fx_core":False,"eligible_for_pair_rankings":False,
       "eligible_for_trading":False,"eligible_for_forward":False,
       "eligible_for_backtests":False,"canonical_D_untouched":True,
       "note":"Incomplete strict-z source coverage. Country activity and inflation axes without a valid prior-window robust z remain NULL. No imputation, no model FX strength. GDP web first statements and revised labour/inflation are not complete point-in-time vintages. Formula 50/50 is a research scenario, not old D generator."
    }

def run(today:date):
    # The complete source check is reusable even when exact historical z is
    # missing. Never weaken the existing candidate's fail-closed policy.
    observed=observed_run(as_of=today.isoformat())
    readiness=run_source_readiness(as_of=today.isoformat())
    try:
        candidate=candidate_run(as_of=today.isoformat())
    except ValueError as exc:
        if not any(marker in str(exc) for marker in (
            "missing strict z cannot be replaced by unapproved estimates",
            "strict z", "missing source", "ZERO_ROBUST_DISPERSION")):
            raise
        print("FXV2_MACRO_SHADOW_COMPLETE_MODEL_BLOCKED_STRICT_SOURCE "+str(exc))
        return partial_from_strict_source(observed,readiness,today)
    return build(candidate,readiness,today)


def publish(report,path:Path):
    previous=json.loads(path.read_text("utf-8")) if path.exists() else None
    if previous and previous.get("status")==report["status"] and \
       previous.get("source_fingerprint_sha256")==report["source_fingerprint_sha256"] and \
       previous.get("formula_version")==report["formula_version"]:
        print("FXV2_MACRO_SHADOW_SAME_ECONOMIC_OBSERVATIONS_NO_SYNTHETIC_FRESHNESS")
        return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n","utf-8")
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--as-of",type=date.fromisoformat,
                   default=datetime.now(ZoneInfo("Europe/Rome")).date())
    p.add_argument("--output",type=Path,default=TARGET)
    args=p.parse_args()
    report=run(args.as_of)
    changed=publish(report,args.output)
    print("FXV2_MACRO_SHADOW_CANDIDATE",
          json.dumps({"changed":changed,"currencies":8,
             "source_cutoff":report["economic_source_cutoff_rome"],
             "unstable_to_weight":report["summary"]["unstable_to_weights"],
             "estimates":report["summary"]["countries_with_estimates"],
             "core_untouched":True}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
