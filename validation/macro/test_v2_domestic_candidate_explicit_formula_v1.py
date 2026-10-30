"""Adversarial offline economic formula test; no tradable Core mutation."""
import copy
import json
import math
import unittest
from pathlib import Path

from validation.macro.v2_g8_three_axis_economic_shadow_v1 import (
    SCHEMA as SHADOW_SCHEMA, run as shadow_run
)
from validation.macro.v2_g8_observed_feature_bridge_v1 import run as observed_run
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    build,run,activity_class,indicative_regime,continuous_weight_interval,
    independent_axis_revision_envelope, REVISION_STRESS_EPSILONS_Z,
    source_readiness, run_source_readiness, G8,FORMULA
)


FROZEN_RESEARCH = (Path(__file__).resolve().parents[2] /
    "validation/macro/fixtures/v2_g8_frozen_domestic_research_coordinates_2026_10_27.json")


def frozen_research_shadow():
    """Reconstitute ONLY a 27-Oct offline regression fixture from CI evidence.

    This deliberately cannot be called today's observation or historical
    first-release PIT. Only numerical research-test input fields are retained.
    """
    fixture = json.loads(FROZEN_RESEARCH.read_text(encoding="utf-8"))
    assert fixture["schema"] == "GMFQ_MACRO_V2_FROZEN_RESEARCH_COORDINATES_TEST_FIXTURE_V1"
    assert fixture["economic_as_of"] == "2026-10-27"
    assert fixture["artifact_id"] == 12721884785
    assert fixture["original_shadow_receipt_sha256"] == (
        "8b56f7fac1d97b59f71939105509032dcaa799d9a1a938c9f13a9e4313638027")
    assert fixture["original_candidate_receipt_sha256"] == (
        "9f9d4182974db3c5425a8a7e0191da3d3d90ee29a3ef82d258716896c1ee919d")
    assert fixture["research_coordinates_from_prior_observed_revised_histories_not_historical_first_release_PIT"] is True
    assert fixture["original_artifact_is_not_live_current_source"] is True
    assert fixture["eligible_to_recompute_D"] is False
    assert fixture["eligible_to_recompute_28_pairs"] is False
    assert set(fixture["countries"]) == set(G8)
    countries = {}
    for ccy, source in fixture["countries"].items():
        g, l, p = (source[k] for k in ("g","l","p"))
        assert all(type(v) in (float,int) and math.isfinite(v) and abs(v) <= 3
                   for v in (g,l,p)), ccy
        assert type(source["estimated"]) is bool
        flags = list(source["flags"])
        assert source["estimated"] == (ccy == "USD")
        assert set(source) == {"g","l","p","lp","ip","flags","estimated"}
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


class CandidateFormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shadow=frozen_research_shadow()
        cls.legacy=json.loads((Path(__file__).resolve().parents[2]/
                              "live_data/sections/D.json").read_text())

    def test_real_8_by_3_candidate_is_separately_versioned_not_live(self):
        result=build(self.shadow,self.legacy)
        self.assertEqual(result["formula_version"],FORMULA)
        self.assertEqual(set(result["countries"]),set(G8))
        self.assertEqual(result["summary"]["axes"],24)
        self.assertEqual(result["summary"]["D_json_rebuilt"],False)
        self.assertEqual(result["summary"]["FX_scores_produced"],0)
        self.assertEqual(result["summary"]["28_pair_theses_recomputed"],0)
        self.assertFalse(result["safe_to_publish_D"])
        self.assertFalse(result["safe_to_update_pair_theses"])
        self.assertFalse(result["safe_to_use_for_beta"])
        self.assertFalse(result["safe_to_use_for_forward"])
        self.assertFalse(result["writes_live_data"])
        self.assertFalse(result["canonical_core_score_formula_recovered"])
        self.assertTrue(result["out_of_sample_falsification_not_completed"])
        for x in result["countries"].values():
            self.assertAlmostEqual(x["domestic_activity_candidate_z"],
                                   .5*x["growth_within_history_z"]+
                                   .5*x["unemployment_tightness_within_history_z"],
                                   places=10)
            self.assertEqual(x["growth_weight_sensitivity_z"]["50"],
                             x["domestic_activity_candidate_z"])
            self.assertIsNone(x["FX_strength_candidate"])
            self.assertTrue(x["legacy_D_numbers_are_NOT_in_new_candidate_units"])

    def test_US_estimation_and_EUR_CHF_definition_caveats_not_hidden(self):
        r=build(self.shadow,self.legacy)["countries"]
        self.assertTrue(r["USD"]["source_quality_details"]["labour"]["is_estimate"])
        self.assertTrue(r["USD"]["source_quality_details"]["inflation"]["is_estimate"])
        self.assertTrue(r["EUR"]["source_quality_flags"])
        self.assertTrue(r["CHF"]["source_quality_flags"])
        self.assertFalse(r["CAD"]["source_quality_flags"])

    def test_continuous_weight_range_is_not_cherry_picked(self):
        r=build(self.shadow,self.legacy)
        for ccy,row in r["countries"].items():
            z=row["continuous_weight_sensitivity_RESEARCH_ONLY"]
            g=row["growth_within_history_z"]
            l=row["unemployment_tightness_within_history_z"]
            left=0.25*g+0.75*l
            right=0.75*g+0.25*l
            self.assertEqual(z["growth_weight_interval_inclusive"],[0.25,0.75])
            self.assertAlmostEqual(z["domestic_activity_z_min"],min(left,right),places=10)
            self.assertAlmostEqual(z["domestic_activity_z_max"],max(left,right),places=10)
            self.assertEqual(z["continuous_weight_math_is_NOT_PIT_or_FX_validation"],True)
            stable=(activity_class(left)==activity_class(.5*g+.5*l)==activity_class(right))
            self.assertEqual(z["classification_unchanged_at_every_weight_in_interval"],stable,ccy)
            self.assertEqual(z["weight_invariant_domestic_class_RESEARCH_ONLY"],
                activity_class(.5*g+.5*l) if stable else None,ccy)
            self.assertEqual(stable,row["activity_class_stable_across_25_50_75pct_growth"])
            self.assertIsNone(row["FX_strength_candidate"])
        self.assertEqual(
            r["summary"]["countries_weight_ambiguous_no_robust_class"],
            r["summary"]["countries_unstable_to_weights"])
        self.assertEqual(
            r["summary"]["countries_robust_for_ALL_continuous_weights_25_75pct"]+
            r["summary"]["countries_weight_ambiguous_no_robust_class"],8)
        # Synthetic economic inputs exercise threshold equality and a range
        # crossing both +0.5 and -0.5. Never select the 'best' outcome post hoc.
        case=continuous_weight_interval(1,-1)
        self.assertEqual(case["domestic_activity_z_min"],-0.5)
        self.assertEqual(case["domestic_activity_z_max"],0.5)
        self.assertIsNone(case["weight_invariant_domestic_class_RESEARCH_ONLY"])
        self.assertTrue(case["class_changes_with_admissible_weights"])
        for growth,labour,expected in [
                (1,1,"FIRM_RELATIVE_TO_OWN_HISTORY"),
                (-1,-1,"SOFT_RELATIVE_TO_OWN_HISTORY"),
                (0.1,0.2,"MIXED_RELATIVE_TO_OWN_HISTORY"),
                (0.5,0.5,"FIRM_RELATIVE_TO_OWN_HISTORY")]:
            z=continuous_weight_interval(growth,labour)
            self.assertTrue(z["classification_unchanged_at_every_weight_in_interval"])
            self.assertEqual(z["weight_invariant_domestic_class_RESEARCH_ONLY"],expected)
        for invalid in (float("nan"),float("inf"),3.1):
            with self.assertRaises(ValueError):
                continuous_weight_interval(invalid,0)

    def test_zero_mad_descriptive_source_attached_without_numeric_promotion(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from validation.macro import v2_zero_mad_ordinal_quality_v1 as quality
        today=datetime.now(ZoneInfo("Europe/Rome")).date()
        observed=observed_run(as_of=today.isoformat())
        raw_series=json.loads(quality.SOURCE.read_text(encoding="utf-8"))
        registry=json.loads(quality.REGISTRY.read_text(encoding="utf-8"))
        ordinal=quality.build(observed,raw_series,registry,today=today)
        full=source_readiness(observed,ordinal_quality=ordinal)
        actual=run_source_readiness(as_of=today.isoformat())
        self.assertEqual(full,actual)
        without=source_readiness(observed)
        self.assertEqual(full["blocked"],without["blocked"])
        self.assertEqual(full["currencies_blocked"],without["currencies_blocked"])
        self.assertFalse(full["strict_eight_country_candidate_allowed_now"] and
                         full["eligible_to_publish_D"])
        self.assertEqual(full["zero_mad_context_descriptors_validated"],
                         len(full["zero_mad_source_keys"]))
        self.assertEqual(set(full["zero_mad_source_keys"]),
                         set(ordinal["zero_mad_components"]))
        self.assertTrue(full["zero_mad_ordinals_never_become_numeric_features"])
        self.assertEqual(full["ordinal_source_policy_id"],quality.POLICY_ID)
        for key in full["zero_mad_source_keys"]:
            ccy,pillar=key.split(".")
            slot=full["countries"][ccy]["axes"][pillar]
            desc=slot["zero_mad_descriptive_context_only"]
            self.assertIsNotNone(desc,key)
            self.assertIsNone(slot["strict_numeric_z"])
            self.assertIsNone(desc["numeric_replacement_z"])
            self.assertFalse(desc["eligible_for_activity_score"])
            self.assertIsNone(desc["FX_or_policy_direction_derived"])
            self.assertTrue(desc["not_historical_PIT"])
            self.assertEqual(desc["ordinal_relation"],
                             ordinal["zero_mad_components"][key]["ordinal_relation"])
            self.assertFalse(without["countries"][ccy]["axes"][pillar][
                             "zero_mad_descriptive_context_only"])
        if "EUR.labour" in full["zero_mad_source_keys"]:
            eur=full["countries"]["EUR"]["axes"]["labour"]
            d=eur["zero_mad_descriptive_context_only"]
            self.assertEqual(eur["upstream_status"],"NO_Z_ZERO_ROBUST_DISPERSION")
            self.assertEqual(d["ordinal_relation"],"ABOVE_ALL_PRIOR")
            self.assertAlmostEqual(d["latest_observation"],6.5)
            self.assertAlmostEqual(d["prior_median"],6.4)
            self.assertAlmostEqual(d["current_minus_prior_median_original_units"],.1)
            self.assertEqual(d["prior_reference_periods"],24)
            self.assertEqual(d["midrank_fraction_of_prior"],1.0)
            self.assertFalse(full["countries"]["EUR"][
                             "complete_three_axis_research_candidate"])

    def test_forged_ordinal_context_is_rejected_not_recast_as_fx(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from validation.macro import v2_zero_mad_ordinal_quality_v1 as quality
        today=datetime.now(ZoneInfo("Europe/Rome")).date()
        observed=observed_run(as_of=today.isoformat())
        ordinal=quality.build(observed,
            json.loads(quality.SOURCE.read_text(encoding="utf-8")),
            json.loads(quality.REGISTRY.read_text(encoding="utf-8")),
            today=today)
        keys=list(ordinal["zero_mad_components"])
        spoof=copy.deepcopy(ordinal)
        spoof["can_generate_legacy_D"]=True
        with self.assertRaisesRegex(ValueError,"ordinal-only quality contract"):
            source_readiness(observed,ordinal_quality=spoof)
        spoof=copy.deepcopy(ordinal)
        spoof["as_of_observed_economic_bridge"]="2026-10-23"
        with self.assertRaisesRegex(ValueError,"ordinal-only quality contract"):
            source_readiness(observed,ordinal_quality=spoof)
        if keys:
            key=keys[0]
            for mut in (
                lambda d: d.update({"numeric_replacement_z":0.0}),
                lambda d: d.update({"eligible_for_domestic_activity_weighting":True}),
                lambda d: d.update({"current_observation":d["current_observation"]+1}),
                lambda d: d.update({"ordinal_relation":"FX_LONG"}),
                lambda d: d.update({"midrank_percentile_of_prior":1.5}),
            ):
                spoof=copy.deepcopy(ordinal)
                mut(spoof["zero_mad_components"][key])
                with self.assertRaises(ValueError):
                    source_readiness(observed,ordinal_quality=spoof)
            spoof=copy.deepcopy(ordinal)
            del spoof["zero_mad_components"][key]
            with self.assertRaisesRegex(ValueError,"coverage does not match source"):
                source_readiness(observed,ordinal_quality=spoof)

    def test_current_missing_source_cannot_be_forged_as_numeric(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        observed=observed_run(as_of=today)
        spoof=copy.deepcopy(observed)
        item=spoof["inflation_labour"]["EUR.labour"]
        if item["status"] == "NO_Z_ZERO_ROBUST_DISPERSION":
            item["research_robust_z"]=0.0
            with self.assertRaisesRegex(ValueError,"strict numeric status/zero-MAD contradiction"):
                source_readiness(spoof)
            item["research_robust_z"]=None
        item["currency"]="GBP"
        with self.assertRaisesRegex(ValueError,"invalid axis identity"):
            source_readiness(spoof)
        spoof=copy.deepcopy(observed)
        spoof["safe_to_publish_new_D"]=True
        with self.assertRaises(ValueError):
            source_readiness(spoof)

    def test_frozen_research_fixture_matches_27_oct_original_candidate_values(self):
        r=build(self.shadow,self.legacy)
        self.assertEqual(r["economic_as_of"],"2026-10-27")
        self.assertEqual(r["formula_version"],FORMULA)
        self.assertTrue(r["historical_first_publication_PIT_not_certified"])
        self.assertFalse(r["safe_to_publish_D"])
        self.assertFalse(r["safe_to_update_pair_theses"])
        self.assertEqual(r["summary"]["countries_robust_for_ALL_continuous_weights_25_75pct"],4)

    def test_current_source_admission_does_not_reuse_frozen_fixture(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        observed=observed_run(as_of=now)
        readiness=source_readiness(observed)
        self.assertEqual(readiness["as_of"],now)
        self.assertEqual(len(readiness["countries"]),8)
        self.assertFalse(readiness["eligible_to_publish_D"])
        self.assertFalse(readiness["eligible_to_recompute_28_pairs"])
        self.assertFalse(readiness["writes_live_data"])
        self.assertTrue(readiness["no_missing_z_substituted"])
        self.assertEqual(readiness["currencies_with_three_research_axes"]+
                         readiness["currencies_blocked"],8)
        self.assertNotEqual(observed["checked_as_of"],self.shadow["as_of"])
        self.assertTrue(observed["current_values_are_not_verified_first_release_vintages"])
        eu=observed["inflation_labour"]["EUR.labour"]
        if eu["status"] == "NO_Z_ZERO_ROBUST_DISPERSION":
            self.assertIsNone(eu["research_robust_z"])
            self.assertIn({"currency":"EUR","pillar":"labour",
                           "reason":"NO_Z_ZERO_ROBUST_DISPERSION"}, readiness["blocked"])
            self.assertFalse(readiness["strict_eight_country_candidate_allowed_now"])
            with self.assertRaisesRegex(ValueError,
                    "missing strict z cannot be replaced by unapproved estimates"):
                shadow_run(as_of=now)
        else:
            # Source may advance. Only a genuinely computable current G8
            # snapshot can pass; do not force a historical source status.
            self.assertIn(eu["status"],(
                "DESCRIPTIVE_REVISED_HISTORY_ROBUST_Z_NOT_PIT",
                "NO_Z_MISSING_PRIOR_ECONOMIC_PERIODS",
            ))
        self.assertFalse(observed["safe_to_publish_new_D"])

    def test_independent_revision_stress_is_mathematical_not_empirical(self):
        self.assertEqual(REVISION_STRESS_EPSILONS_Z, (0.10, 0.25, 0.50))
        for g, l, eps, lower, upper in [
            (0.30, 0.30, 0.10, 0.20, 0.40),
            (0.30, 0.30, 0.25, 0.05, 0.55),
            (1.00, 1.00, 0.50, 0.50, 1.50),
            (1.00, -1.00, 0.25, -0.75, 0.75),
        ]:
            with self.subTest(g=g, l=l, eps=eps):
                x=independent_axis_revision_envelope(g,l,eps)
                self.assertAlmostEqual(x["stressed_activity_z_min"],lower)
                self.assertAlmostEqual(x["stressed_activity_z_max"],upper)
                self.assertTrue(x["this_is_not_an_empirical_revision_error_estimate"])
                self.assertTrue(x["not_a_PIT_or_FX_forecast_test"])
        self.assertTrue(independent_axis_revision_envelope(
            0.30,0.30,0.10)["class_invariant_to_all_weights_and_independent_axis_shifts"])
        self.assertFalse(independent_axis_revision_envelope(
            0.30,0.30,0.25)["class_invariant_to_all_weights_and_independent_axis_shifts"])
        self.assertEqual(independent_axis_revision_envelope(
            1,1,0.50)["robust_domestic_class_RESEARCH_ONLY"],
            "FIRM_RELATIVE_TO_OWN_HISTORY")
        for eps in [-1, 0.51, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                independent_axis_revision_envelope(0.2,0.3,eps)

    def test_g8_stress_nested_without_promoting_FX(self):
        out=build(self.shadow,self.legacy)
        self.assertTrue(out["revision_stress_is_hypothetical_not_data_calibrated"])
        counts=[]
        for key in ("10","25","50"):
            valid=0
            for ccy,row in out["countries"].items():
                diag=row["hypothetical_axis_revision_stress_RESEARCH_ONLY"][key]
                self.assertTrue(diag["this_is_not_an_empirical_revision_error_estimate"])
                self.assertTrue(diag["not_a_PIT_or_FX_forecast_test"])
                self.assertIsNone(row["FX_strength_candidate"])
                robust=diag["class_invariant_to_all_weights_and_independent_axis_shifts"]
                if robust:
                    self.assertTrue(row["activity_class_stable_across_25_50_75pct_growth"])
                    self.assertEqual(diag["robust_domestic_class_RESEARCH_ONLY"],
                                     row["domestic_activity_class"])
                else:
                    self.assertIsNone(diag["robust_domestic_class_RESEARCH_ONLY"])
                valid+=robust
            counts.append(valid)
        self.assertGreaterEqual(counts[0],counts[1])
        self.assertGreaterEqual(counts[1],counts[2])
        self.assertEqual(counts,[4,2,0])
        self.assertEqual(counts[0],out["summary"][
            "countries_robust_hypothetical_axis_shift_0p10_z"])
        self.assertEqual(counts[1],out["summary"][
            "countries_robust_hypothetical_axis_shift_0p25_z"])
        self.assertEqual(counts[2],out["summary"][
            "countries_robust_hypothetical_axis_shift_0p50_z"])
        self.assertEqual(out["summary"]["FX_scores_produced"],0)
        self.assertFalse(out["safe_to_publish_D"])
        print("G8_HYPOTHETICAL_REVISION_STRESS_COUNTS_10_25_50",counts)

    def test_inflation_is_separate_no_false_growth_increase(self):
        a=build(self.shadow,self.legacy)["countries"]["CAD"]
        modified=copy.deepcopy(self.shadow)
        old=modified["countries"]["CAD"]["inflation_pressure_relative_to_own_history_z"]
        modified["countries"]["CAD"]["inflation_pressure_relative_to_own_history_z"]=(-3 if old>0 else 3)
        b=build(modified,self.legacy)["countries"]["CAD"]
        self.assertEqual(a["domestic_activity_candidate_z"],b["domestic_activity_candidate_z"])
        self.assertNotEqual(a["inflation_pressure_within_history_z"],b["inflation_pressure_within_history_z"])

    def test_source_score_and_future_age_cannot_be_forged(self):
        for bad_path,value in [
            (("safe_to_publish_new_D",),True),
            (("countries","GBP","approved_for_live_core_D"),True),
            (("countries","JPY","fx_directional_bias"),"LONG"),
            (("countries","EUR","growth_relative_to_own_history_z"),float("nan")),
            (("scope","activity_weights"),{"growth":1,"labour_tightness":0,"inflation_in_activity":0}),
        ]:
            with self.subTest(path=bad_path):
                wrong=copy.deepcopy(self.shadow)
                node=wrong
                for k in bad_path[:-1]:node=node[k]
                node[bad_path[-1]]=value
                with self.assertRaises(ValueError):
                    build(wrong,self.legacy)
        wrong=copy.deepcopy(self.legacy)
        wrong["asOf"]="2027-01-01"
        with self.assertRaises(ValueError): build(self.shadow,wrong)

    def test_sensitivity_class_and_neutral_regime_not_forced(self):
        self.assertEqual(activity_class(0.1),"MIXED_RELATIVE_TO_OWN_HISTORY")
        self.assertEqual(indicative_regime(0.1,2),
                         "MIXED_OR_TURNING_DOMESTIC_CYCLE")
        self.assertEqual(indicative_regime(.75,-.9),
                         "FIRM_GROWTH_WITH_SUBDUED_PRICE_PRESSURE")
        self.assertEqual(indicative_regime(-.75,.9),
                         "SOFT_GROWTH_WITH_ELEVATED_PRICE_PRESSURE")
        self.assertEqual(indicative_regime(-.75,-.9),
                         "SOFT_GROWTH_WITH_SUBDUED_PRICE_PRESSURE")

    def test_repository_inputs_not_mutated(self):
        root=Path(__file__).resolve().parents[2]
        paths=[root/"live_data/sections/D.json",
               root/"live_data/sections/MACRO_SERIES.json",
               root/"live_data/sections/MACRO_THERMOMETER_DATA.json"]
        before={str(x):x.read_bytes() for x in paths}
        out=build(self.shadow,self.legacy)
        self.assertEqual(out["economic_as_of"],"2026-10-27")
        self.assertEqual({str(x):x.read_bytes() for x in paths},before)


if __name__=="__main__": unittest.main()
