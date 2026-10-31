#!/usr/bin/env python3
"""No false spot-vs-forward OIS precision; adversarial date/source tests."""
import copy
import json
import unittest

from validation.cb_pricing.eur_estr_contract_benchmark_bridge_v1 import (
    SOURCE, MATCH_CLASS, admitted_reference, compare, contract_period, eur_archive
)


class EurFst3BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive=SOURCE.read_text(encoding="utf-8")
        cls.contracts=eur_archive(cls.archive)
        cls.first=cls.contracts["observations"][0]

    def reference(self):
        x=self.first
        return {
            "source_class":MATCH_CLASS,"currency":"EUR",
            "floating_index":"ESTR","compounding":"DAILY_COMPOUNDED",
            "accrual_convention":"ACT_360",
            "source_independent_of_fst3":True,
            "source_instrument":"FORWARD_START_3M_OIS_SWAP",
            "official_data_licence_authorized":True,
            "source_url":"https://independent.test/authorized/frozen-statement",
            "source_content_sha256":"a"*64,
            "quote_date":x["quote_date"],"accrual_start":x["accrual_start"],
            "accrual_end":x["accrual_end"],
            "source_first_seen_at_utc":x["quote_date"]+"T23:59:59Z",
            "rate_pct":x["rate_pct"]-0.03,
            "time_alignment":"END_OF_DAY_BOTH_SOURCES"
        }

    def test_archive_matches_real_eurex_compounding_windows(self):
        x=self.contracts
        self.assertGreaterEqual(len(x["observations"]),28)
        self.assertGreaterEqual(len(x["contracts"]),4)
        self.assertGreaterEqual(sum(q["accrual_already_started_at_quote_date"]
                             for q in x["observations"]),5)
        self.assertEqual(sum(q["needs_realized_ESTR_component_for_OIS_comparison"]
                             for q in x["observations"]),
                         sum(q["accrual_already_started_at_quote_date"] for q in x["observations"]))

        windows={r["contract"]:(r["accrual_start"],r["accrual_end"])
                 for r in x["contracts"]}
        for contract,window in {
             "FST3V2026":("2026-10-21","2027-01-20"),
             "FST3Z2026":("2026-12-16","2027-03-17"),
             "FST3G2027":("2027-02-17","2027-05-19"),
             "FST3M2027":("2027-06-16","2027-09-15")}.items():
            self.assertEqual(windows[contract],window)
        for q in x["observations"]:
            self.assertEqual(q["official_ois"],False)
            self.assertEqual(q["accrual_end"],
                             contract_period(q["contract"])[1])

    def test_no_independent_reference_is_explicit_no_go(self):
        o=compare(self.archive,[])
        self.assertEqual(o["status"],
                         "NO_ADMISSIBLE_INDEPENDENT_SAME_WINDOW_OIS_REFERENCE")
        self.assertEqual(o["admissible_same_window_pairs"],0)
        self.assertEqual(len(o["unmatched"]),len(self.contracts["observations"]))
        self.assertGreaterEqual(o["started_compounding_period_quote_count"],5)
        self.assertEqual(o["not_yet_started_or_start_day_quote_count"],
                         len(self.contracts["observations"])-o["started_compounding_period_quote_count"])
        self.assertEqual(sum(r["reason"]==
          "COMPOUNDING_ALREADY_STARTED_REQUIRES_REALIZED_ESTR_SPLICE"
          for r in o["unmatched"]),o["started_compounding_period_quote_count"])

        self.assertIsNone(o["actual_model_OIS_level_MAE_bp"])
        self.assertIsNone(o["predicted_OIS_direction_hit_rate"])
        self.assertFalse(o["historical_PIT_and_walk_forward_validated"])
        self.assertFalse(o["eligible_to_change_OIS_operational_feed"])
        self.assertFalse(o["eligible_to_change_FX_or_forward_models"])
        self.assertFalse(o["writes_live_data"])

    def test_synthetic_same_period_reference_only_yields_descriptive_spread(self):
        b=self.reference()
        o=compare(self.archive,[b])
        self.assertEqual(o["admissible_same_window_pairs"],1)
        p=o["matched"][0]
        self.assertAlmostEqual(p["descriptive_futures_minus_ois_spread_bp"],3,places=5)
        self.assertTrue(p["not_OIS_prediction_error"])
        self.assertFalse(p["historical_trade_PIT_certified"])
        self.assertIsNone(o["actual_model_OIS_level_MAE_bp"])
        self.assertIsNone(o["predicted_OIS_direction_hit_rate"])
        self.assertFalse(o["eligible_to_change_FX_or_forward_models"])

    def test_spot_term_estr_or_in_arrears_is_not_same_future_window(self):
        for cls in ("CME_TERM_ESTR_SPOT","LSEG_TERM_ESTR_SPOT",
                    "ECB_ESTR_COMPOUNDED_IN_ARREARS","EURIBOR_INTERBANK_RATE",
                    "FUTURES_ESTR_SAME_SOURCE"):
            b=self.reference()
            b["source_class"]=cls
            with self.subTest(cls=cls),self.assertRaisesRegex(ValueError,
                    "spot/start/underlying not eligible"):
                compare(self.archive,[b])

    def test_wrong_date_underlying_convention_and_permissions_are_rejected(self):
        base=self.reference()
        for field,value in [
            ("accrual_start","2026-01-01"),
            ("accrual_end","2028-01-01"),
            ("floating_index","EURIBOR"),
            ("compounding","SIMPLE"),
            ("accrual_convention","ACT_365"),
            ("source_instrument","TERM_RATE_FIXING"),
            ("source_independent_of_fst3",False),
            ("official_data_licence_authorized",False),
            ("source_content_sha256","bad-sha"),
            ("source_first_seen_at_utc","2020-01-01T00:00:00Z"),
            ("time_alignment","MIXED_TIMESTAMPS")
        ]:
            b=copy.deepcopy(base)
            b[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                compare(self.archive,[b])
        wrong_day=copy.deepcopy(base)
        wrong_day["quote_date"]="2026-10-15"
        self.assertEqual(compare(self.archive,[wrong_day])["admissible_same_window_pairs"],0,
                         "same-period quote published on a different date cannot be joined")
        with self.assertRaisesRegex(ValueError,"duplicated independent"):
            compare(self.archive,[base,base])

    def test_wrong_futures_expiry_is_not_repaired_using_benchmark_data(self):
        rows=[json.loads(z) for z in self.archive.splitlines() if z]
        row=next(x for x in rows if x["currency"]=="EUR")
        row["expiration"]="2027-05-20"
        text="\n".join(json.dumps(x) for x in rows)
        with self.assertRaisesRegex(ValueError,"futures expiry != third Wednesday"):
            eur_archive(text)


if __name__=="__main__":
    unittest.main()
