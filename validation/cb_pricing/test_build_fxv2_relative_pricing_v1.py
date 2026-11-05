#!/usr/bin/env python3
"""Adversarial research-only tests: 28 pairs, 84 date-aware comparisons."""
import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
import unittest

from validation.cb_pricing.build_fxv2_relative_pricing_v1 import (
    ROOT, G8, SCHEMA, TENORS, build,
)

P = ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json"
M = ROOT / "site/fx-quant-v2/macro-baseline-candidate-v1.json"


class RelativePricingResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = P.read_bytes()
        cls.pricing = json.loads(cls.source)
        cls.macro = json.loads(M.read_text())
        cls.report = build(cls.pricing, cls.macro, cls.source)

    def test_exact_28pair_macro_universe_and_84_comparisons(self):
        r = self.report
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["summary"]["pairs"], 28)
        self.assertEqual(r["summary"]["currencies"], 8)
        self.assertEqual(r["summary"]["horizon_comparisons"], 84)
        self.assertEqual(list(r["pairs"]), list(self.macro["pairs"]))
        for name, row in r["pairs"].items():
            self.assertEqual(set(row["horizons"]), set(TENORS))
            self.assertEqual(name, row["base"] + "/" + row["quote"])
            self.assertIsNone(row["fx_signal"])
            self.assertIsNone(row["expected_return"])
            self.assertIsNone(row["carry_estimate"])

    def test_arithmetic_orientation_and_published_real_inputs(self):
        # Current exchange/pricing snapshots MUST be allowed to advance.
        # Inspect latest real inputs, never pin an old EUR/USD level or date.
        for name in ("EUR/USD", "GBP/JPY", "AUD/NZD"):
            base, quote = name.split("/")
            a = self.pricing["currencies"][base]
            b = self.pricing["currencies"][quote]
            x, y = a["horizons"]["6m"], b["horizons"]["6m"]
            observed = self.report["pairs"][name]["horizons"]["6m"]
            self.assertAlmostEqual(
                observed["spread_bp"], round(100 * (x["rate"] - y["rate"]), 3),
                places=3, msg=name + " orientation/base-minus-quote")
            self.assertEqual(observed["base_rate_pct"], x["rate"])
            self.assertEqual(observed["quote_rate_pct"], y["rate"])
            self.assertEqual(observed["base_as_of"], x["as_of"])
            self.assertEqual(observed["quote_as_of"], y["as_of"])
            days = abs((date.fromisoformat(x["as_of"]) -
                        date.fromisoformat(y["as_of"])).days)
            self.assertEqual(observed["date_gap_days"], days)
            self.assertEqual(observed["same_date"], days == 0)
            self.assertEqual(observed["estimate_involved"],
                             "STIMA INDICATIVA" in (a["quality"], b["quality"]))
            self.assertEqual(observed["proxy_involved"],
                             "PROXY FUTURES" in (a["kind"], b["kind"]))
            self.assertEqual(observed["base_contract"], x.get("contract"))
            self.assertEqual(observed["quote_contract"], y.get("contract"))

        # Independent *frozen synthetic scenario* certifies the original
        # -145.25 bp orientation, one-day mismatch, and 122.5bp AUD/NZD
        # proxy. It must not depend on daily published quotes or expiry rolls.
        p = copy.deepcopy(self.pricing)
        asof = date.fromisoformat(p["snapshot_built_from_repo_date"])
        older = (asof - timedelta(days=1)).isoformat()
        current = asof.isoformat()
        eur = p["currencies"]["EUR"]
        usd = p["currencies"]["USD"]
        eur["quality"] = usd["quality"] = "STIMA INDICATIVA"
        eur["kind"] = usd["kind"] = "FUTURES SECONDARI"
        eur["horizons"]["6m"].update(rate=2.8275, as_of=older)
        usd["horizons"]["6m"].update(rate=4.28, as_of=current)
        aud = p["currencies"]["AUD"]
        nzd = p["currencies"]["NZD"]
        aud["kind"], aud["quality"] = "FUTURES", "FONTE UFFICIALE"
        nzd["kind"], nzd["quality"] = "PROXY FUTURES", "PROXY DIREZIONALE"
        aud["horizons"]["6m"].update(rate=4.925, as_of=current)
        nzd["horizons"]["6m"].update(rate=3.7, as_of=current, contract="Jun 2027")
        sample = build(p, self.macro, b"frozen-synthetic-2026-11-05")
        e = sample["pairs"]["EUR/USD"]["horizons"]["6m"]
        self.assertEqual(e["spread_bp"], -145.25)
        self.assertEqual(e["base_as_of"], older)
        self.assertEqual(e["quote_as_of"], current)
        self.assertFalse(e["same_date"])
        self.assertEqual(e["date_gap_days"], 1)
        self.assertTrue(e["estimate_involved"])
        self.assertFalse(e["proxy_involved"])
        q = sample["pairs"]["AUD/NZD"]["horizons"]["6m"]
        self.assertEqual(q["spread_bp"], 122.5)
        self.assertTrue(q["proxy_involved"])
        self.assertTrue(q["same_date"])
        self.assertEqual(q["quote_contract"], "Jun 2027")
        self.assertTrue(sample["not_ois_equivalent"])
        self.assertFalse(sample["eligible_for_fx_engine"])

    def test_all_observations_dated_and_only_arithmetic(self):
        r = self.report
        self.assertEqual(r["pricing_source_content_sha256"], hashlib.sha256(self.source).hexdigest())
        for key in ("not_ois_equivalent", "not_policy_repricing", "not_fx_carry",
                    "no_cross_date_market_move_inferred",
                    "source_dates_are_independent",
                    "same_bucket_does_not_guarantee_same_expiry_or_index"):
            self.assertTrue(r[key], key)
        for key in ("eligible_for_fx_engine", "eligible_for_backtests",
                    "eligible_for_automatic_core_rebase"):
            self.assertFalse(r[key], key)
        self.assertTrue(r["canonical_fx_core_untouched"])
        summary = r["summary"]
        self.assertEqual(summary["same_date_comparisons"] + summary["mixed_date_comparisons"], 84)
        self.assertGreater(summary["mixed_date_comparisons"], 0)
        self.assertGreater(summary["estimated_comparisons"], 0)
        self.assertGreater(summary["proxy_comparisons"], 0)
        self.assertEqual(summary["generated_fx_signals"], 0)
        self.assertEqual(summary["generated_policy_repricing_signals"], 0)
        for pair in r["pairs"].values():
            for tenor in pair["horizons"].values():
                self.assertIsNone(tenor["fx_signal"])
                self.assertIsNone(tenor["policy_repricing_bp"])
                self.assertEqual(
                    round(100 * (tenor["base_rate_pct"] - tenor["quote_rate_pct"]), 3),
                    tenor["spread_bp"])

    def test_refuse_incomplete_rates_or_future_date(self):
        p = copy.deepcopy(self.pricing)
        del p["currencies"]["NZD"]["horizons"]["12m"]
        with self.assertRaisesRegex(ValueError, "missing tenor"):
            build(p, self.macro, self.source)
        p = copy.deepcopy(self.pricing)
        p["currencies"]["EUR"]["horizons"]["6m"]["as_of"] = "2027-03-05"
        with self.assertRaisesRegex(ValueError, "newer than snapshot"):
            build(p, self.macro, self.source)
        p = copy.deepcopy(self.pricing)
        p["currencies"]["CHF"]["horizons"]["3m"]["rate"] = 100
        with self.assertRaisesRegex(ValueError, "invalid rate"):
            build(p, self.macro, self.source)

    def test_refuse_relabeling_as_operational_and_pair_coverage_drift(self):
        p = copy.deepcopy(self.pricing)
        p["eligible_for_fx_engine"] = True
        with self.assertRaisesRegex(ValueError, "informational"):
            build(p, self.macro, self.source)
        m = copy.deepcopy(self.macro)
        m["eligible_for_live_fx_signals"] = True
        with self.assertRaisesRegex(ValueError, "non-operational"):
            build(self.pricing, m, self.source)
        m = copy.deepcopy(self.macro)
        del m["pairs"]["EUR/USD"]
        with self.assertRaisesRegex(ValueError, "28-pair universe"):
            build(self.pricing, m, self.source)


if __name__ == "__main__":
    unittest.main()
