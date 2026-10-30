#!/usr/bin/env python3
"""Adversarial tests: data provenance != OIS prediction accuracy."""
import copy
import json
import math
import unittest

from validation.cb_pricing.audit_estimated_ois_reliability_v1 import (
    SOURCE, NZD, build, check_archive, new_zealand_evidence, futures_evidence
)


class EstimatedOisReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = SOURCE.read_text(encoding="utf-8")
        cls.rows = [json.loads(x) for x in cls.archive.splitlines() if x]
        cls.nzd = json.loads(NZD.read_text(encoding="utf-8"))

    def test_research_archive_is_real_observations_no_trading_promotion(self):
        out = build(self.archive, self.nzd)
        self.assertEqual(out["quotes_observed"], 86)
        self.assertEqual(out["total_matched_same_contract_changes"], 74)
        self.assertEqual(out["currencies_with_verified_OIS_accuracy"], 0)
        self.assertIsNone(out["level_MAE_vs_OIS"])
        self.assertIsNone(out["directional_hit_rate_vs_OIS"])
        self.assertFalse(out["can_assign_empirical_OIS_prediction_confidence"])
        self.assertFalse(out["eligible_to_publish_official_OIS"])
        self.assertFalse(out["eligible_for_H1_or_Forward"])
        self.assertFalse(out["eligible_to_reprice_CB_or_28_pairs"])
        self.assertFalse(out["writes_live_data"])
        self.assertEqual(set(out["currencies"]), {"USD", "EUR", "CHF", "NZD"})
        for c, expected in (("USD", 30), ("EUR", 28), ("CHF", 28)):
            self.assertEqual(out["currencies"][c]["quote_count"], expected)
            self.assertFalse(out["currencies"][c]["independent_OIS_benchmark_available"])
            self.assertIsNone(out["currencies"][c]["level_error_MAE_bp"])
            self.assertIsNone(out["currencies"][c]["direction_accuracy_percent"])
            self.assertFalse(out["currencies"][c]["historical_first_release_PIT_certified"])
            self.assertTrue(out["currencies"][c]["same_contract_moves_are_NOT_predicted_OIS_direction"])

    def test_three_month_nzd_holdout_measures_basis_not_ois(self):
        o = new_zealand_evidence(self.nzd)
        self.assertEqual(o["calibration_months"], 19)
        self.assertEqual(o["held_out_months"], 3)
        self.assertEqual(o["frozen_basis_point_estimate_bp"], 24)
        self.assertAlmostEqual(o["monthly_bill_minus_OCR_holdout_MAE_bp"], 16.333, places=3)
        self.assertAlmostEqual(o["monthly_bill_minus_OCR_holdout_bias_bp"], -16.333, places=3)
        self.assertEqual(o["monthly_bill_minus_OCR_holdout_max_abs_error_bp"], 24)
        self.assertEqual([v["observed_bill_minus_OCR_basis_bp"] for v in
                          o["holdout_months"]], [35, 48, 38])
        self.assertIsNone(o["level_error_MAE_bp"])
        self.assertIsNone(o["direction_accuracy_percent"])
        self.assertTrue(o["cash_bill_minus_OCR_is_NOT_the_traded_BB_minus_OIS_basis"])
        self.assertTrue(o["expanded_band_is_NOT_an_out_of_sample_confidence_interval"])

    def test_adversarial_quotes_rejected_without_smoothing(self):
        perturbations = (
            ("identity", lambda x: x.update({"futures_price": x["futures_price"] + .05})),
            ("permission", lambda x: x.update({"official_ois_quote": True})),
            ("trade", lambda x: x.update({"policy_delta_eligible": True})),
            ("first_seen", lambda x: x.update({"first_seen_at_utc": "2026-01-01T00:00:00Z"})),
            ("symbol", lambda x: x.update({"symbol": "FAKE:UNLISTED"})),
            ("expiry", lambda x: x.update({"expiration": "2025-01-01"})),
            ("date", lambda x: x.update({"observation_date": "2026-1-16"})),
            ("nan", lambda x: x.update({"implied_rate": math.nan})),
        )
        for name, mutate in perturbations:
            rows = copy.deepcopy(self.rows)
            mutate(rows[0])
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_archive(rows)

    def test_duplicate_and_contract_roll_cannot_generate_fake_direction(self):
        rows = copy.deepcopy(self.rows)
        rows.append(copy.deepcopy(rows[0]))
        with self.assertRaisesRegex(ValueError, "duplicate dated contract"):
            check_archive(rows)
        checked = check_archive(self.rows)
        valid = futures_evidence(checked, "USD")
        self.assertEqual(valid["same_contract_valid_move_count"], 26)
        for m in valid["same_contract_changes"]:
            self.assertTrue(m["contract"].startswith("ZQ"))
            self.assertGreaterEqual(m["change_bp"], -100)
            self.assertLessEqual(m["change_bp"], 100)
        # One additional document wrongly tagging the same dated contract as
        # a different tenor must not create a cross-tenor comparison.
        rows = copy.deepcopy(self.rows)
        first = rows[0]
        match = next((r for r in rows[1:] if r["contract"] == first["contract"]
                      and r["currency"] == first["currency"]), None)
        self.assertIsNotNone(match)
        match["observed_under_horizon"] = "12m"
        with self.assertRaisesRegex(ValueError, "contract changed horizon label"):
            futures_evidence(check_archive(rows), first["currency"])

    def test_bad_nzd_reference_cannot_validate_model(self):
        f = copy.deepcopy(self.nzd)
        f["provenance"]["historical_pit_certified"] = True
        with self.assertRaisesRegex(ValueError, "NZD basis provenance"):
            new_zealand_evidence(f)
        f = copy.deepcopy(self.nzd)
        for v in f["recent_plateau"]["rows"]:
            v["bank_bill_90d_pct"] += .12
        with self.assertRaisesRegex(ValueError, "NZD central fit"):
            new_zealand_evidence(f)
        f = copy.deepcopy(self.nzd)
        f["holdout_2026_q3"]["rows"][0]["month"] = "2026-01"
        with self.assertRaisesRegex(ValueError, "holdout"):
            new_zealand_evidence(f)


if __name__ == "__main__":
    unittest.main()
