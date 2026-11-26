"""A real 8-economy / 28-pair observed Macro V3 input, NOT frozen 2026-09 D scores."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_observed_feature_bridge_v1 import run as observed_run
from validation.macro.v3_current_g8_28pair_economic_evidence_v1 import (
    FX, ROOT, SCHEMA, build, load, movement, run, attach_q2_prior, Q2_SAME_EDITION_PRIOR,
)
from validation.macro.v3_gdp_q3_official_overlay_v1 import observed_q3_updates, LEDGER
from validation.macro.ons_quarterly_gdp_v1 import latest_growth, previous_quarter
from validation.macro.esri_quarterly_gdp_v1 import latest_growth as latest_jp_growth
from validation.macro.seco_quarterly_gdp_v1 import latest_growth as latest_ch_growth
from validation.macro.abs_quarterly_gdp_v1 import latest_growth as latest_au_growth
from validation.macro.statcan_quarterly_gdp_v1 import latest_growth as latest_ca_growth
from validation.macro.eurostat_quarterly_gdp_v1 import latest_growth as latest_eu_growth
from validation.macro.statsnz_quarterly_gdp_v1 import latest_growth as latest_nz_growth


class CurrentEconomicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asof = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        cls.observed = observed_run(as_of=cls.asof)
        cls.heat = load("MACRO_THERMOMETER_DATA")
        cls.legacy = load("D")
        cls.setup = load("PAIR_SETUP_OPERATIONAL_VIEW")
        cls.jp_growth = latest_jp_growth(cls.asof)
        cls.ch_growth = latest_ch_growth(cls.asof)
        cls.au_growth = latest_au_growth(cls.asof)
        cls.ca_growth = latest_ca_growth(cls.asof)
        cls.eu_growth = latest_eu_growth(cls.asof)
        cls.nz_growth = latest_nz_growth(cls.asof)
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
            expected = (latest_growth(self.asof) or {}).get("reference_quarter", "2026Q3") if c == "GBP" else (
                "2026Q3" if c in ("USD", "EUR", "CHF") else "2026Q2"
            )
            if c == "JPY" and self.jp_growth:
                expected = self.jp_growth["reference_quarter"]
            if c == "NZD" and self.nz_growth:
                expected = self.nz_growth["reference_quarter"]
            if c == "EUR" and self.eu_growth:
                expected = self.eu_growth["reference_quarter"]
            if c == "CAD" and self.ca_growth:
                expected = self.ca_growth["reference_quarter"]
            if c == "AUD" and self.au_growth:
                expected = self.au_growth["reference_quarter"]
            if c == "CHF" and self.ch_growth:
                expected = self.ch_growth["reference_quarter"]
            self.assertEqual(country["growth"]["reference_quarter"], expected)
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

    def test_q3_latest_real_official_releases_no_fictional_g8_growth(self):
        import math
        self.assertEqual(self.result["summary"]["GDP_later_quarter_official_releases"], 4 + bool(self.jp_growth) + bool(self.au_growth) + bool(self.ca_growth) + bool(self.nz_growth))
        countries = self.result["country_evidence"]
        self.assertEqual(set(observed_q3_updates("2026-10-29")), set())
        self.assertEqual(set(observed_q3_updates("2026-10-30")), {"USD"})
        self.assertEqual(set(observed_q3_updates("2026-10-31")), {"USD", "EUR"})
        self.assertEqual(set(observed_q3_updates("2026-11-12")), {"USD", "EUR"})
        self.assertEqual(set(observed_q3_updates("2026-11-13")), {"USD", "EUR", "GBP"})
        self.assertNotIn("CHF", observed_q3_updates("2026-11-16"))
        chf = observed_q3_updates("2026-11-17")["CHF"]
        self.assertEqual(countries["CHF"]["growth"], self.ch_growth or chf)
        self.assertEqual(chf["nonannualized_qoq_descriptive_pct"], 0.2)
        self.assertEqual(chf["publisher_release_day"], "2026-11-16")
        self.assertEqual(chf["publication_stage"], "PRELIMINARY_FLASH")
        self.assertTrue(chf["comparison_uses_distinct_publisher_editions"])
        chf_prior = chf["prior_documented_quarter"]
        self.assertEqual(chf_prior["reference_quarter"], "2026Q2")
        self.assertEqual(chf_prior["publisher_release_day"], "2026-09-03")
        self.assertEqual(chf_prior["nonannualized_qoq_descriptive_pct"], 1.5)
        self.assertEqual(chf_prior["reported_unit"], chf["reported_unit"])
        self.assertNotEqual(chf_prior["publisher_source"], chf["publisher_source"])
        self.assertTrue(math.isclose(
            countries["USD"]["growth"]["nonannualized_qoq_descriptive_pct"],
            100*((1+3.4/100)**.25-1), abs_tol=1e-6))
        if self.eu_growth:
            self.assertEqual(countries["EUR"]["growth"], self.eu_growth)
        else:
            self.assertEqual(countries["EUR"]["growth"]["nonannualized_qoq_descriptive_pct"], 0.4)
        gbp = countries["GBP"]["growth"]
        self.assertEqual(gbp["publication_stage"], "FIRST_QUARTERLY_ESTIMATE")
        self.assertEqual(observed_q3_updates("2026-11-13")["GBP"]["reported_value"], 0.7)
        if gbp["reference_quarter"] == "2026Q3":
            self.assertEqual(gbp["nonannualized_qoq_descriptive_pct"], 0.7)
        prior = gbp["prior_documented_quarter"]
        if prior is not None:
            self.assertEqual(prior["reference_quarter"], previous_quarter(gbp["reference_quarter"]))
            self.assertEqual(gbp["reported_unit"], prior["reported_unit"])
        self.assertIs(gbp["is_growth_strength_score"], False)
        for c in ("USD", "EUR"):
            self.assertEqual(countries[c]["growth"]["prior_documented_quarter"]["reference_quarter"],
                             previous_quarter(countries[c]["growth"]["reference_quarter"]))
            self.assertIs(countries[c]["growth"]["is_growth_strength_score"], False)
        if self.jp_growth:
            jpy = countries["JPY"]["growth"]
            self.assertEqual(jpy, self.jp_growth)
            self.assertTrue(jpy["prior_value_from_same_esri_edition"])
            self.assertFalse(jpy["is_growth_strength_score"])
        for c, expected in {"CAD": 0.7, "AUD": 0.1, "NZD": -0.7}.items():
            g = countries[c]["growth"]
            prior = g["prior_documented_quarter"]
            self.assertEqual(prior["reference_quarter"], previous_quarter(g["reference_quarter"]))
            self.assertEqual(prior["reported_unit"], g["reported_unit"])
            self.assertEqual(prior["publisher_release_day"], g["publisher_release_day"])
            self.assertEqual(prior["publisher_source"], g["publisher_source"])
            self.assertTrue(g["prior_value_from_same_publisher_edition"])
            if c == "NZD" and self.nz_growth:
                self.assertEqual(g, self.nz_growth)
            elif c == "CAD" and self.ca_growth:
                self.assertEqual(g, self.ca_growth)
            elif c == "AUD" and self.au_growth:
                self.assertEqual(g, self.au_growth)
            else:
                self.assertAlmostEqual(g["nonannualized_qoq_descriptive_pct"] -
                                       prior["nonannualized_qoq_descriptive_pct"], expected)
            self.assertFalse(prior["historical_pit_training_vintages_certified"])
        for pair, row in self.result["pair_context"].items():
            for c in (row["base"], row["quote"]):
                self.assertEqual(row["growth_periods"][c], countries[c]["growth"]["reference_quarter"])
            self.assertIsNone(row["pair_trade_bias"])
        for change in (
            lambda d: d["events"][0].update(reported_value=6.5),
            lambda d: d["events"][1].update(source_url="https://example.org/"),
            lambda d: d["events"][0].update(publisher_release_day="2026-10-20"),
            lambda d: d["events"][2].update(reported_unit="PERCENT_QOQ_UNADJUSTED"),
            lambda d: d["events"][3]["prior_documented_quarter"].update(
                reported_unit="PERCENT_QOQ_SA_CALENDAR"),
            lambda d: d["events"][3].update(methodology_url="https://example.org/"),
        ):
            ledger = json.loads(LEDGER.read_text())
            change(ledger)
            with self.assertRaisesRegex(ValueError, "MACRO_V3_GDP_Q3"):
                observed_q3_updates(self.asof, evidence=ledger)

    def test_q2_prior_cannot_be_backdated_or_reused_with_different_edition(self):
        for c, (day, current, prior, unit, url, _) in Q2_SAME_EDITION_PRIOR.items():
            g = {"reference_quarter": "2026Q2", "publisher_release_day": day,
                 "reported_value": current, "reported_unit": unit, "publisher_source": url}
            self.assertEqual(attach_q2_prior(c,g,day),g)
            self.assertEqual(attach_q2_prior(c,g,"2026-11-25")["prior_documented_quarter"]["reported_value"],prior)
            for changed in ({"reference_quarter":"2026Q3"}, {"reported_value":current+1},
                            {"reported_unit":"PERCENT_YOY"}, {"publisher_source":"https://example.org/"},
                            {"publisher_release_day":"2026-11-25"}):
                altered={**g,**changed}
                self.assertEqual(attach_q2_prior(c,altered,"2026-11-26"),altered)

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

    def test_live_cutoff_reaches_every_dedicated_producer(self):
        from unittest.mock import patch
        from datetime import timezone
        from contextlib import ExitStack
        now=datetime.fromisoformat(self.asof+"T12:00:00+01:00")
        module="validation.macro.v3_current_g8_28pair_economic_evidence_v1."
        with ExitStack() as stack:
            producers=[stack.enter_context(patch(module+name,return_value=None))
                       for name in ("latest_uk_growth","latest_jp_growth","latest_ch_growth",
                                    "latest_au_growth","latest_ca_growth","latest_nz_growth","latest_eu_growth")]
            build(self.observed,self.heat,self.legacy,self.setup,as_of=self.asof,live_cutoff=now)
            for producer in producers:
                producer.assert_called_once_with(self.asof,live_cutoff=now)

    def test_same_day_release_propagates_to_public_snapshot_and_every_affected_pair(self):
        """Synthetic values confined to the regression; no publisher actual is fabricated."""
        from contextlib import ExitStack
        from datetime import timedelta
        from unittest.mock import patch
        from validation.macro.ons_quarterly_gdp_v1 import archived_growth
        from validation.macro.publish_v3_current_context_v1 import snapshot
        now=datetime.fromisoformat(self.asof+"T12:00:00").replace(tzinfo=ZoneInfo("Europe/Rome"))
        module="validation.macro.v3_current_g8_28pair_economic_evidence_v1."
        names={"GBP":"latest_uk_growth","JPY":"latest_jp_growth","CHF":"latest_ch_growth",
               "AUD":"latest_au_growth","CAD":"latest_ca_growth","NZD":"latest_nz_growth",
               "EUR":"latest_eu_growth"}
        values={c:round(0.11+i*0.13,2) for i,c in enumerate(names)}
        def producer(c):
            def read(as_of, live_cutoff=None):
                rows=[{"quarter":"2026Q3","publisher_release_day":self.asof,
                       "first_observed_at_utc":now.isoformat(),"reported_value":values[c],
                       "prior_qoq":-0.2,"source_url":"https://example.invalid/test-only"}]
                return archived_growth(as_of,rows,stage="TEST_ONLY",
                    same_edition_field="prior_value_from_same_publisher_edition",
                    live_cutoff=live_cutoff)
            return read
        with ExitStack() as stack:
            for c,name in names.items():
                stack.enter_context(patch(module+name,side_effect=producer(c)))
            historical=build(self.observed,self.heat,self.legacy,self.setup,as_of=self.asof)
            premature=build(self.observed,self.heat,self.legacy,self.setup,as_of=self.asof,
                            live_cutoff=now-timedelta(seconds=1))
            self.assertEqual(historical,premature)
            live=build(self.observed,self.heat,self.legacy,self.setup,as_of=self.asof,live_cutoff=now)
            public=snapshot(live)
        self.assertEqual(len(public["pair_context"]),28)
        self.assertEqual(public["summary"]["GDP_later_quarter_official_releases"],8)
        for c,value in values.items():
            growth=public["countries"][c]["growth"]
            self.assertEqual(growth["reported_value"],value)
            self.assertEqual(growth["prior_documented_quarter"]["reported_value"],-0.2)
            self.assertEqual(growth["publisher_release_day"],self.asof)
            affected=[p for p in public["pair_context"].values() if c in (p["base"],p["quote"])]
            self.assertEqual(len(affected),7)
            for pair in affected:
                self.assertEqual(pair["growth"][c],value)
                self.assertEqual(pair["growth_periods"][c],"2026Q3")
                self.assertIsNone(pair["pair_trade_bias"])
        self.assertEqual(public["summary"]["pair_trade_signals_generated"],0)
        self.assertFalse(public["safe_to_republish_D"])

    def test_deterministic_snapshot_and_read_only(self):
        paths = [ROOT / "live_data/sections/D.json",
                 ROOT / "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
                 ROOT / "live_data/sections/MACRO_SERIES.json",
                 ROOT / "live_data/sections/MACRO_THERMOMETER_DATA.json"]
        before = {str(p): p.read_bytes() for p in paths}
        # Compare the same explicit-date issuer archive inputs.
        from datetime import timezone
        from validation.macro.recurring_official_actuals_v1 import validated_record
        raw = load("NEWS_PULSE_OPERATIONAL").get("recurring_official_archive", [])
        now = datetime.now(timezone.utc)
        releases = [validated_record(row, now) for row in raw]
        releases = [row for row in releases if row["as_of"] < self.asof and
                    row["first_runner_observed_at_utc"][:10] < self.asof]
        expected = build(self.observed, self.heat, self.legacy, self.setup,
                         as_of=self.asof, issuer_releases=releases)
        again = run(as_of=self.asof)
        self.assertEqual(expected, again)
        self.assertEqual(again, run(as_of=self.asof))
        self.assertEqual(self.result, build(self.observed, self.heat, self.legacy,
                                           self.setup, as_of=self.asof))
        self.assertEqual(before, {str(p): p.read_bytes() for p in paths})


if __name__ == "__main__":
    unittest.main()
