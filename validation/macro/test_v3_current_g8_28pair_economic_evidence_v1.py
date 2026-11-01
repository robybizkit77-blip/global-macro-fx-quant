"""A real 8-economy / 28-pair observed Macro V3 input, NOT frozen 2026-09 D scores."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_observed_feature_bridge_v1 import run as observed_run
from validation.macro.v3_current_g8_28pair_economic_evidence_v1 import (
    FX, ROOT, SCHEMA, build, load, movement, run,
)


class CurrentEconomicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asof = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        cls.observed = observed_run(as_of=cls.asof)
        cls.heat = load("MACRO_THERMOMETER_DATA")
        cls.legacy = load("D")
        cls.setup = load("PAIR_SETUP_OPERATIONAL_VIEW")
        cls.result = build(cls.observed, cls.heat, cls.legacy,
                           cls.setup, as_of=cls.asof)

    def error(self, field, mutate):
        cases = {
            "observed": copy.deepcopy(self.observed),
            "heat": copy.deepcopy(self.heat),
            "legacy": copy.deepcopy(self.legacy),
            "setup": copy.deepcopy(self.setup),
        }
        mutate(cases[field])
        with self.assertRaisesRegex(ValueError, "MACRO_V3_ECONOMIC_INPUT_REJECTED"):
            build(cases["observed"], cases["heat"], cases["legacy"],
                  cases["setup"], as_of=self.asof)

    def test_all_8_country_observed_axes_28_pairs(self):
        r = self.result
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["summary"]["currencies"], 8)
        self.assertEqual(r["summary"]["economic_dimensions"], 24)
        self.assertEqual(r["summary"]["latest_observation_values_present"], 24)
        self.assertEqual(r["summary"]["pairs"], 28)
        self.assertEqual(set(r["country_evidence"]), set(FX))
        self.assertEqual(len(r["pair_context"]), 28)
        self.assertEqual(r["canonical_D_macro_baseline_as_of"], "2026-09-25")
        self.assertEqual(r["fx_price_as_of"], self.setup["price_asof"])
        self.assertEqual(r["summary"]["numeric_old_D_macro_scores_replaced"], 0)
        self.assertEqual(r["summary"]["pair_trade_signals_generated"], 0)
        self.assertFalse(r["safe_to_republish_D"])
        self.assertFalse(r["safe_to_recompute_structural_pair_theses"])
        self.assertFalse(r["eligible_for_trading_or_forward_backtest"])
        self.assertFalse(r["point_in_time_historical_backtest_certified"])
        self.assertFalse(r["writes_live_data"])
        for c in FX:
            country = r["country_evidence"][c]
            self.assertIsNone(country["FX_strength"])
            self.assertIsNone(country["macro_score"])
            self.assertIsNone(country["country_relative_rank"])
            self.assertEqual(country["growth"]["reference_quarter"], "2026Q2")
            self.assertFalse(country["growth"]["is_growth_strength_score"])
            for dim in ("labour", "inflation"):
                item = country[dim]
                self.assertTrue(item["normalization_not_required_for_observed_value"])
                self.assertTrue(item["observation_period_is_not_release_instant"])
                self.assertTrue(item["observed_history_revised_not_historic_PIT"])
                self.assertEqual(item["series_id"],
                                 self.heat["currencies"][c][dim]["series_id"])
                self.assertEqual(item["observation_value"],
                                 self.heat["currencies"][c][dim]["latest_value"])
        for pair, x in r["pair_context"].items():
            self.assertEqual(pair, x["base"] + "/" + x["quote"])
            self.assertIsNone(x["pair_trade_bias"])
            self.assertIsNone(x["estimated_FX_expected_return"])
            self.assertFalse(x["recalculated_structural_thesis"])
            self.assertEqual(set(x["labour_changes_pp"]), {x["base"], x["quote"]})
            self.assertEqual(set(x["inflation_periods"]), {x["base"], x["quote"]})

    def test_ordinal_and_missing_z_do_not_block_actual_observations(self):
        # USD historical missing periods and EUR zero-MAD must NOT erase a
        # perfectly source-verified observed economic value or create fake z.
        rows = self.result["country_evidence"]
        for c, dim in (("USD", "inflation"), ("EUR", "labour")):
            item = rows[c][dim]
            self.assertEqual(item["observation_value"],
                             self.heat["currencies"][c][dim]["latest_value"])
            upstream = self.observed["inflation_labour"][c + "." + dim]
            self.assertEqual(item["research_z_only_when_available"],
                             upstream["research_robust_z"])
            if upstream["research_robust_z"] is None:
                self.assertTrue(item["research_z_was_not_imputed"])

    def test_observation_direction_and_symmetry(self):
        self.assertEqual(movement(-0.1), "DOWN")
        self.assertEqual(movement(0.11), "UP")
        self.assertEqual(movement(0.049), "FLAT")
        self.assertEqual(movement(0.05), "FLAT")
        for pair, x in self.result["pair_context"].items():
            a, b = x["base"], x["quote"]
            sa = self.result["country_evidence"][a]["labour"]["change_direction"]
            sb = self.result["country_evidence"][b]["labour"]["change_direction"]
            if x["labour_change_contrast"] == "BASE_UNEMPLOYMENT_FALLING_QUOTE_RISING":
                self.assertEqual((sa, sb), ("DOWN", "UP"))
            if x["labour_change_contrast"] == "BASE_UNEMPLOYMENT_RISING_QUOTE_FALLING":
                self.assertEqual((sa, sb), ("UP", "DOWN"))

    def test_tampered_sources_and_future_publications_rejected(self):
        self.error("heat", lambda x: x["currencies"]["CHF"]["labour"]
                   .update(latest_value=100.0))
        self.error("heat", lambda x: x["currencies"]["EUR"]["inflation"]
                   .update(as_of="2028-09"))
        self.error("observed", lambda x: x["inflation_labour"]["CAD.labour"]
                   .update(eligible_for_macro_score=True))
        self.error("observed", lambda x: x["growth_quarterly_gdp_web"]["GBP"]
                   .update(published_on="2028-10-01"))
        self.error("observed", lambda x: x["growth_quarterly_gdp_web"]["AUD"]
                   .update(growth_score=1.9))
        self.error("legacy", lambda x: x.update(asOf="2026-10-30"))
        self.error("setup", lambda x: x.update(pair_count=27))
        self.error("setup", lambda x: x["pairs"].pop(next(iter(x["pairs"]))))

    def test_deterministic_snapshot_and_read_only(self):
        paths = [ROOT / "live_data/sections/D.json",
                 ROOT / "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
                 ROOT / "live_data/sections/MACRO_SERIES.json",
                 ROOT / "live_data/sections/MACRO_THERMOMETER_DATA.json"]
        before = {str(p): p.read_bytes() for p in paths}
        again = run(as_of=self.asof)
        self.assertEqual(self.result["receipt_sha256"], again["receipt_sha256"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in paths})


if __name__ == "__main__":
    unittest.main()
