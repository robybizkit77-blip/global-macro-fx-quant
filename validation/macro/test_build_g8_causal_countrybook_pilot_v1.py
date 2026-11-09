"""Research pilot contract, source quality and no implicit FX signal promotion."""
from __future__ import annotations
import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from validation.macro import build_g8_causal_countrybook_pilot_v1 as m


class TestG8CausalCountryBookPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day=date(2026,11,9)
        cls.source,cls.hashes=m.sources()

    def test_all_eight_distinct_causal_narratives_and_24_axes(self):
        b=m.build(today=self.day)
        self.assertEqual(b["schema"],m.SCHEMA)
        self.assertEqual(tuple(b["countries"]),m.FX)
        self.assertEqual(b["scope"]["currencies"],8)
        self.assertEqual(b["scope"]["macro_axes"],24)
        self.assertEqual(b["scope"]["fx_pair_universe"],28)
        self.assertEqual(b["scope"]["fx_signals_created"],0)
        self.assertFalse(b["scope"]["safe_to_update_D"])
        self.assertFalse(b["scope"]["safe_to_update_28_pair_ranking"])
        self.assertFalse(b["scope"]["official_historic_PIT"])
        self.assertEqual(len(set(b["source_sha256"].values())),len(m.PATHS))
        chains=set()
        for c,p in b["countries"].items():
            with self.subTest(currency=c):
                self.assertEqual(p["currency"],c)
                self.assertEqual(len(p["archived_transmission_context"]),2)
                self.assertTrue(all(
                    row["quality"]=="HISTORICAL_CONTEXT_NOT_CERTIFIED_CURRENT_RELEASE_OR_PIT"
                    for row in p["archived_transmission_context"]))
                self.assertIsNone(p["automatic_fx_signal"])
                self.assertIsNone(p["expected_return"])
                self.assertIsNone(p["thesis_strength"])
                self.assertIsNone(p["trade_attractiveness"])
                self.assertEqual(len(p["narrative_it"]),7)
                self.assertIn("Se",p["causal_hypothesis"])
                self.assertIn("Se",p["alternative_hypothesis"])
                self.assertIn("consenso",p["coverage_limit"])
                self.assertIn(p["bank"],p["central_bank_conditional_reaction"])
                self.assertIsNone(p["rates_and_pricing"]["same_contract_event_repricing_bp"])
                chains.add(p["causal_hypothesis"])
        self.assertEqual(len(chains),8)

    def test_stale_two_year_not_false_current(self):
        b=m.build(today=self.day)
        self.assertEqual(
            b["countries"]["CHF"]["rates_and_pricing"]["yield_freshness"],
            "2Y_OLDER_THAN_7_CALENDAR_DAYS")
        self.assertEqual(
            b["countries"]["NZD"]["rates_and_pricing"]["yield_freshness"],
            "2Y_OLDER_THAN_7_CALENDAR_DAYS")
        self.assertEqual(
            b["countries"]["USD"]["rates_and_pricing"]["yield_freshness"],
            "2Y_DATED_REFERENCE_NOT_LIVE")

    def test_non_official_curve_never_policy_delta(self):
        b=m.build(today=self.day)
        for c in ("USD","EUR","CHF","NZD"):
            self.assertIsNone(b["countries"][c]["rates_and_pricing"]["six_month_rate_pct"])
        for c in ("AUD","CAD","JPY"):
            self.assertEqual(
                b["countries"][c]["rates_and_pricing"]["six_month_quality"],
                "OFFICIAL_FUTURES_CONTEXT_NOT_OIS_LEVEL")

    def test_gbp_is_official_boe_ois_not_futures(self):
        b=m.build(today=self.day)
        self.assertEqual(
            b["countries"]["GBP"]["rates_and_pricing"]["six_month_quality"],
            "OFFICIAL_BOE_ESTIMATED_OIS_CURVE_NOT_EVENT_REPRICING")
        self.assertIn("WANT:",b["countries"]["GBP"]["central_bank_conditional_reaction"])
        self.assertIn("CAN:",b["countries"]["GBP"]["central_bank_conditional_reaction"])

    def test_false_official_ois_rate_rejected(self):
        d=copy.deepcopy(self.source)
        d["ois"]["currencies"]["AUD"]["horizons"]["6m"]["rate"]=None
        with self.assertRaisesRegex(ValueError,"false official six-month rate"):
            m.study_country("AUD",d,self.day)

    def test_future_published_rates_rejected(self):
        d=copy.deepcopy(self.source)
        d["rates"]["CAD"]["date"]="2026-11-10"
        with self.assertRaisesRegex(ValueError,"two-year quote in future"):
            m.study_country("CAD",d,self.day)

    def test_macro_dimensions_reject_bad_units(self):
        d=copy.deepcopy(self.source)
        d["macro"]["features"]["USD"]["inflation_change_pp"]["unit"]="UNVERIFIED"
        with self.assertRaisesRegex(ValueError,"macro transformation drift"):
            m.study_country("USD",d,self.day)

    def test_no_production_path_in_input_or_output(self):
        self.assertTrue(all(not p.startswith("live_data/sections/D.")
                            for p in m.PATHS.values()))
        self.assertTrue(all(not p.startswith(".github/workflows/publish")
                            for p in m.PATHS.values()))
        self.assertIn("NON segnali",m.markdown(m.build(today=self.day)))
        self.assertTrue(m.ROOT.joinpath(
            "validation/macro/G8_CAUSAL_REACTION_COUNTRY_BOOK_V1.json").exists())

if __name__=="__main__":
    unittest.main()
