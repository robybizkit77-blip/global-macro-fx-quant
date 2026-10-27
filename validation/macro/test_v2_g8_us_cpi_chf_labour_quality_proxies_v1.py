"""USD CPI and CHF labour: two explicitly estimated descriptors, never first PIT."""
from __future__ import annotations

import copy
import json
import unittest

from validation.macro.v2_g8_us_cpi_chf_labour_quality_proxies_v1 import (
    ASOF, SCHEMA, DATA, profile
)
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_g8_24_axis_training_history_gap_audit_v1 import (
    evidence
)


class TwoResidualEstimatedResearchSeries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.research=profile()

    def test_two_models_estimates_not_claimed_as_original_source(self):
        r=self.research
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(set(r["two_explicitly_estimated_missing_source_windows"]),
                         {"USD.inflation","CHF.labour"})
        self.assertEqual(r["summary"]["estimates_added"],2)
        self.assertEqual(r["summary"]["genuinely_new_first_release_archival_rows_added"],0)
        self.assertTrue(r["these_are_not_canonical_first_vintages"])
        self.assertFalse(r["historical_joint_PIT_source_certification_changed"])
        self.assertTrue(r["can_label_two_sources_estimated_for_research_display"])
        for flag in ("safe_to_publish_new_D","safe_to_change_28_pairs",
                     "safe_for_beta","safe_for_forward","writes_live_data"):
            self.assertFalse(r[flag])
        self.assertEqual(r["summary"]["macro_model_scores_approved"],0)
        self.assertEqual(r["summary"]["FX_pair_rankings_changed"],0)
        for key,v in r["two_explicitly_estimated_missing_source_windows"].items():
            self.assertEqual(v["historical_first_web_periods_recovered_by_this"],0)
            self.assertFalse(v["original_first_web_training_history_complete"])
            self.assertEqual(v["revised_history_proxy_training_periods"],24)
            self.assertEqual(v["latest_economic_period"],"2026-09")
            self.assertFalse(v["may_backtest_or_rank_FX"])
            self.assertTrue(v["training_latest_observation_excluded"])
            self.assertIsInstance(v["estimated_descriptive_robust_z"],float)

    def test_us_one_missing_october_month_and_sa_index_not_nsa_headline(self):
        r=self.research["two_explicitly_estimated_missing_source_windows"]["USD.inflation"]
        self.assertEqual(r["source_series"],"CPIAUCSL")
        self.assertEqual(r["quality"],
                         "ESTIMATE_REVISED_CPIAUCSL_24_OBS_IN_25_MONTHS_NOT_PIT")
        self.assertEqual(r["training_calendar_periods"],25)
        self.assertEqual(r["missing_observation"],"2025-10")
        self.assertFalse(r["missing_value_imputed"])
        self.assertTrue(r["issuer_published_NSA_headline_not_equivalent_to_this_SA_index_yoy"])
        self.assertTrue(r["source_bytes_automated_retrieval_on_2026_10_27_blocked_403"])
        self.assertTrue(r["latest_current_revised_SA_index_yoy_pct"]>0)
        self.assertEqual(self.research["summary"]["USD_CPI_revised_history_observed_periods"],24)

    def test_chf_seco_one_decimal_and_snb_revision_precision_separate(self):
        r=self.research["two_explicitly_estimated_missing_source_windows"]["CHF.labour"]
        self.assertEqual(r["source_series"],"CH_UNEMP_RATE")
        self.assertEqual(r["quality"],
                         "ESTIMATE_REVISED_SNB_RETROSPECTIVE_24M_NOT_FIRST_RELEASE")
        self.assertEqual(r["latest_published_SECO_first_rounded_pct"],3.1)
        self.assertEqual(r["compatible_unrounded_first_rate_interval_pct"],
                         {"lower_inclusive":3.05,"upper_exclusive":3.15})
        self.assertGreater(r["latest_current_revised_SNB_exact_percent_NOT_FIRST_RELEASE"],3.12)
        self.assertFalse(r["original_SECO_first_vintages_for_prior_24_periods_verified"])
        self.assertFalse(r["historical_SNB_exact_initial_publication_time_known"])
        self.assertIsNone(r["missing_observation"])

    def test_different_cutoffs_are_not_fake_historical_PIT_replays(self):
        for x in ("2026-09-30T23:59:59Z","2026-10-27T23:59:59Z",
                  "2026-10-26T23:59:59+02:00"):
            with self.subTest(x=x),self.assertRaises(ValueError):
                profile(as_of=x)

    def test_fake_us_oct2025_obs_fails_closed(self):
        source=json.loads((DATA/"MACRO_SERIES.json").read_text())
        target=next(x for x in source["USD"] if x["id"]=="US_CPIAUCSL_history_value")
        target["dates"].insert(-11,"2025-10-01")
        target["values"].insert(-11,333.3)
        with self.assertRaises(ValueError):
            profile(source=source)

    def test_missing_swiss_previous_month_fails_closed(self):
        source=json.loads((DATA/"MACRO_SERIES.json").read_text())
        target=next(x for x in source["CHF"] if x["id"]=="CH_UNEMP_RATE_history_value")
        j=next(i for i,v in enumerate(target["dates"]) if v.startswith("2026-06"))
        del target["dates"][j]
        del target["values"][j]
        with self.assertRaises(ValueError):
            profile(source=source)

    def test_first_release_audit_remains_22_not_inflated_24(self):
        base=evidence()
        s=base["summary"]
        self.assertEqual(s["prior_first_web_contiguous_12Q_or_24M_slots"],22)
        self.assertEqual(s["slots_missing_required_initial_release_periods"],2)
        self.assertEqual(s["missing_required_prior_periods_total"],46)
        self.assertEqual(s["genuinely_historic_PIT_training_slots_certified"],0)
        self.assertEqual(s["secondary_provisional_descriptors_available"],2)
        self.assertEqual(s["source_slots_with_original_window_or_labeled_provisional_context"],24)
        self.assertEqual(s["secondary_provisional_first_release_corrections"],0)
        self.assertTrue(base[
            "observed_first_web_22_and_estimated_context_2_must_never_be_combined_as_PIT"])
        self.assertEqual(
            base["separate_revised_history_estimates_for_US_CPI_and_CHF_unemployment"]
                ["receipt_sha256"],self.research["receipt_sha256"])
        self.assertEqual(s["currency_FX_strength_scores_approved"],0)

    def test_does_not_change_live_core_and_pair_snapshots(self):
        d=ROOT/"live_data/sections"
        names=("D.json","PAIR_SETUP_OPERATIONAL_VIEW.json")
        before={n:(d/n).read_bytes() for n in names}
        second=profile()
        after={n:(d/n).read_bytes() for n in names}
        self.assertEqual(before,after)
        self.assertEqual(second["receipt_sha256"],self.research["receipt_sha256"])


if __name__=="__main__":
    unittest.main()
