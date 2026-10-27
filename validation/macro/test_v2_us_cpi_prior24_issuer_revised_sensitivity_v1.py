"""Tests: corrected CPI 24 PRIOR issuer BLS observations and two-z robustness."""
from __future__ import annotations
import copy
import json
import unittest
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_cpi_prior24_issuer_revised_sensitivity_v1 import (
    PATH, SCHEMA, audit
)

class USCPIPrior24IssuerRevisedSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(PATH.read_text(encoding="utf-8"))
        cls.result=audit()

    def reject(self,fn):
        d=copy.deepcopy(self.fixture)
        fn(d)
        with self.assertRaises(ValueError): audit(fixture=d)

    def test_24_Prior_not_23_and_latest_not_leaking_into_training(self):
        r=self.result
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["summary"]["prior_calendar_months"],25)
        self.assertEqual(r["summary"]["official_published_prior_months"],24)
        self.assertEqual(len(self.fixture["comparison_samples"]),25)
        self.assertEqual(self.fixture["comparison_samples"][0]["economic_month"],"2024-08")
        self.assertEqual(self.fixture["comparison_samples"][-2]["economic_month"],"2026-08")
        self.assertEqual(self.fixture["comparison_samples"][-1]["economic_month"],"2026-09")
        self.assertEqual(self.fixture["comparison_samples"][-1]["sample_role"],"CURRENT_EVALUATION_ONLY")
        self.assertNotIn("2025-10",[x["economic_month"] for x in self.fixture["comparison_samples"]])
        self.assertTrue(r["24_prior_observed_not_24_consecutive"])
        self.assertTrue(r["latest_Sep2026_excluded_from_training"])
        self.reject(lambda d:d["comparison_samples"].pop(0))
        self.reject(lambda d:d["comparison_samples"].pop(-1))
        self.reject(lambda d:d["comparison_samples"][-1].update(sample_role="PRIOR_TRAINING_ONLY"))
        self.reject(lambda d:d["comparison_samples"][13].update(economic_month="2025-10"))

    def test_original_aug2024_byte_receipt_and_publication_clock(self):
        s=self.fixture["original_aug_2024_source"]
        self.assertEqual(s["source_binary_byte_size"],150338)
        self.assertEqual(s["publisher_release_day"],"2024-09-11")
        self.assertEqual(s["SA_index_at_issue"],"314.121")
        self.assertEqual(s["same_issue_SA_12m_base"],"306.187")
        self.assertEqual(s["SA_index_yoy_pct_same_issue"],"2.591227")
        self.assertEqual(s["raw_xlsx_sha256"],
                         "41f4de5b7035be83cec85fca05d2339bd929290683206846f9b43b46d84a3a4d")
        self.assertFalse(self.result["Aug_2024_new_first_issuer_day_bytes_certified"])
        self.reject(lambda d:d["original_aug_2024_source"].update(
            source_binary_capture_utc="2024-09-11T08:30:00+00:00"))
        self.reject(lambda d:d["original_aug_2024_source"].update(
            raw_xlsx_sha256="a"*64))
        self.reject(lambda d:d["original_aug_2024_source"].update(
            publisher_release_day="2024-09-10"))

    def test_issuer_vs_current_revised_z_at_24_prior_published_months(self):
        s=self.result["summary"]
        self.assertAlmostEqual(s["issuer_month_candidate_robust_z"]["clipped_z"],2.257242,places=6)
        self.assertAlmostEqual(s["asof_revised_series_robust_z"]["clipped_z"],2.260357,places=6)
        self.assertAlmostEqual(s["robust_z_candidate_minus_revised"],-0.003115,places=6)
        self.assertEqual(s["prior_months_abs_change_gt_0_05_pp"],0)
        self.assertEqual(s["revision_comparison_months"],24)
        self.assertTrue(s["same_direction_both_robust_z_positive"])
        self.reject(lambda d:d["summary"]["issuer_month_candidate_robust_z"].update(clipped_z=0))
        self.reject(lambda d:d["summary"].update(robust_z_candidate_minus_revised=0.0))
        self.reject(lambda d:d["summary"].update(official_published_prior_months=25))

    def test_revised_history_not_misrepresented_as_original_issuer_source(self):
        self.assertTrue(self.result["comparison_first_issue_vs_asof_revised_never_full_PIT"])
        self.assertFalse(self.result["safe_to_publish_D_json"])
        self.assertFalse(self.result["safe_to_recalculate_28_pairs"])
        self.assertFalse(self.result["safe_to_claim_PIT_training"])
        self.reject(lambda d:d.update(asof_revised_history_is_NOT_first_vintage=False))
        self.reject(lambda d:d.update(source_oct2026_cpiaucsl_revised_git_blob_sha="fake"))
        self.reject(lambda d:d["comparison_samples"][1].update(
            asof_revised_CPIAUCSL_SA_current_index="314.686"))
        self.reject(lambda d:d["comparison_samples"][1].update(
            issuer_original_issue_month_SA_yoy_pct="2.300000"))
        self.reject(lambda d:d["comparison_samples"][1].update(
            sample_role="CURRENT_EVALUATION_ONLY"))
        self.reject(lambda d:d.update(safe_for_beta=True))
        self.reject(lambda d:d.update(safe_to_claim_PIT_training=True))
        self.reject(lambda d:d.update(writes_live_data=True))

    def test_fixed_ledger_and_production_read_only(self):
        directory=ROOT/"live_data/sections"
        before={(n): (directory/n).read_bytes()
                for n in ("D.json","PAIR_SETUP_OPERATIONAL_VIEW.json")}
        another=audit()
        after={(n): (directory/n).read_bytes() for n in before}
        self.assertEqual(before,after)
        self.assertEqual(self.result["receipt_sha256"],another["receipt_sha256"])

if __name__=="__main__":
    unittest.main()
