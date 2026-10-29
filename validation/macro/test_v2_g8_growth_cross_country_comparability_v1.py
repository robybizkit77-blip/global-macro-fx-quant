"""G8 GDP same-quarter absolute growth vs within-history z: NOT an FX rank."""
import copy
import itertools
import json
import math
import unittest
from pathlib import Path

from validation.macro.v2_g8_growth_cross_country_comparability_v1 import (
    CURRENCIES, GDP_CUTOFF, CANDIDATE_ASOF, audit, direction, run, UNITS,
)
from validation.macro.v2_g8_gdp_first_web_growth_features_v1 import (
    run as gdp_run,
)
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    run as candidate_run,
)

ROOT = Path(__file__).resolve().parents[2]


class G8GDPNonFXComparabilityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gdp = gdp_run(as_of=GDP_CUTOFF)
        cls.candidate = candidate_run(as_of=CANDIDATE_ASOF)
        cls.obj = audit(cls.gdp, cls.candidate)

    def test_first_web_8_countries_28_exhaustive_pairs_and_dates(self):
        d = self.obj
        self.assertEqual(len(d["countries"]), 8)
        self.assertEqual(len(d["all_28_GDP_representation_comparisons"]), 28)
        self.assertEqual(d["economic_reference_quarter"], "2026Q2")
        self.assertEqual(d["issuer_first_statement_days_span"]["first"], "2026-07-30")
        self.assertEqual(d["issuer_first_statement_days_span"]["last"], "2026-09-17")
        self.assertEqual(d["issuer_first_statement_days_span"]["calendar_days"], 49)
        names = {frozenset(p.split("/")) for p in d["all_28_GDP_representation_comparisons"]}
        self.assertEqual(names, {frozenset(x) for x in
                         itertools.combinations(CURRENCIES, 2)})
        self.assertEqual(set(d["countries"]), set(CURRENCIES))
        self.assertEqual(d["summary"]["eligible_cross_country_FX_strength_pairs"], 0)
        self.assertTrue(d["same_quarter_does_not_equal_simultaneously_available"])
        self.assertTrue(d["own_history_z_cross_section_not_a_common_GDP_level_or_FX_strength"])

    def test_us_saar_not_directly_compared_to_qoq_and_warnings_visible(self):
        rows=self.obj["countries"]
        self.assertEqual(rows["USD"]["original_reported_unit"],"PERCENT_SAAR_ANNUALIZED")
        self.assertAlmostEqual(rows["USD"]["nonannualized_qoq_pct_research"],
                               100*((1+1.5/100)**.25-1),places=10)
        self.assertAlmostEqual(rows["CHF"]["nonannualized_qoq_pct_research"],1.5)
        self.assertAlmostEqual(rows["CAD"]["nonannualized_qoq_pct_research"],0.8)
        self.assertAlmostEqual(rows["EUR"]["nonannualized_qoq_pct_research"],0.4)
        self.assertEqual(set(self.obj["summary"]) >=
                         {"pairs_with_EUR_or_CHF_definition_caveats"},True)
        self.assertEqual(self.obj["summary"]["pairs_with_EUR_or_CHF_definition_caveats"],13)
        self.assertTrue(rows["EUR"]["definition_warning"])
        self.assertTrue(rows["CHF"]["definition_warning"])
        for c in CURRENCIES:
            self.assertEqual(rows[c]["original_reported_unit"],UNITS[c])
            self.assertIsNone(rows[c]["FX_direction"])
            self.assertIsNone(rows[c]["new_core_growth_score"])

    def test_all_28_distinctions_exhaustive_and_order_not_fx_strength(self):
        pairs=self.obj["all_28_GDP_representation_comparisons"]
        summary=self.obj["summary"]
        self.assertEqual(sum(summary[k] for k in (
            "within_history_vs_qoq_order_agreements",
            "within_history_vs_qoq_order_inversions",
            "pairs_with_order_ties")),28)
        self.assertGreater(summary["within_history_vs_qoq_order_inversions"],0)
        for pair,p in pairs.items():
            a,b=pair.split("/")
            x,y=self.obj["countries"][a],self.obj["countries"][b]
            raw=direction(x["nonannualized_qoq_pct_research"],
                          y["nonannualized_qoq_pct_research"])
            zz=direction(x["within_own_12_prior_quarters_z_research"],
                         y["within_own_12_prior_quarters_z_research"])
            expected=("TIE_IN_AT_LEAST_ONE_REPRESENTATION" if raw==0 or zz==0
                      else "ORDER_INVERSION" if raw!=zz else "ORDER_AGREEMENT")
            self.assertEqual(p["order_comparison"],expected)
            self.assertFalse(p["eligible_for_fx_strength_ranking"])
            self.assertFalse(p["joint_original_publisher_vintage_certified"])

    def test_mutation_in_gdp_units_horizon_vintage_or_candidate_rejected(self):
        def reject_gdp(change):
            gd=copy.deepcopy(self.gdp);change(gd)
            with self.assertRaises(ValueError):
                audit(gd,self.candidate)
        def reject_candidate(change):
            co=copy.deepcopy(self.candidate);change(co)
            with self.assertRaises(ValueError):
                audit(self.gdp,co)
        reject_gdp(lambda d:d["features"]["USD"].update(
            latest_nonannualized_qoq_pct=1.5))
        reject_gdp(lambda d:d["features"]["AUD"].update(
            latest_reported_unit="PERCENT_SAAR_ANNUALIZED"))
        reject_gdp(lambda d:d["features"]["JPY"].update(
            latest_initial_period="2026Q1"))
        reject_gdp(lambda d:d["features"]["CHF"].update(
            growth_definition_caveats=[]))
        reject_gdp(lambda d:d["features"]["NZD"].update(
            historical_first_web_observations_used=11))
        reject_gdp(lambda d:d.update(can_publish_D_json=True))
        reject_candidate(lambda d:d["countries"]["EUR"].update(
            growth_within_history_z=-2.1))
        reject_candidate(lambda d:d["countries"]["GBP"].update(
            FX_strength_candidate=0.75))
        reject_candidate(lambda d:d.update(safe_to_publish_D=True))

    def test_research_only_no_production_or_forward_modification(self):
        files=("live_data/sections/D.json",
               "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
               "live_data/sections/MACRO_SERIES.json",
               "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl")
        before={p:(ROOT/p).read_bytes() for p in files}
        a=run();b=run()
        self.assertEqual(a,b)
        self.assertTrue(len(a["receipt_sha256"])==64)
        self.assertEqual(before,{p:(ROOT/p).read_bytes() for p in files})
        for key in ("safe_to_publish_D","safe_to_recalculate_28_pairs",
                    "safe_for_beta","safe_for_forward","writes_live_data"):
            self.assertFalse(a[key])


if __name__=="__main__":
    unittest.main()
