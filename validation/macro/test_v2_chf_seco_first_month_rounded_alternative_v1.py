"""Swiss original SECO one-decimal first monthly release values, NOT exact SNB PIT."""
import copy
import json
import unittest

from validation.macro.v2_chf_seco_first_month_rounded_alternative_v1 import (
    audit, ASOF, FIXTURE, SCHEMA, EARLY_INDEX_ONLY,
    INDEXED_OFFICIAL_PDF_TEXT_ONLY, from_index_only
)
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_g8_24_axis_training_history_gap_audit_v1 import evidence


class CHFOfficialFirstRoundedAlternative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=audit()

    def test_source_tiers_are_21_downloaded_original_pdfs_plus_4_index_only(self):
        d=self.a
        self.assertEqual(d["schema"],SCHEMA)
        self.assertEqual(len(d["publisher_first_rounded_monthly_reports"]),25)
        self.assertEqual(d["summary"]["official_PDF_raw_bytes_SHA_captured_now"],21)
        self.assertEqual(d["summary"]["official_2024_original_PDF_search_index_only_currently_404"],4)
        self.assertEqual(d["summary"]["separate_new_SNB_canonical_first_release_history_periods"],0)
        self.assertFalse(d["writes_live_data"])
        rows=d["publisher_first_rounded_monthly_reports"]
        self.assertEqual([e["reference_month"] for e in rows[:4]],
                         ["2024-09","2024-10","2024-11","2024-12"])
        self.assertEqual([e["original_seco_rounded_sa_registered_unemployment_pct"]
                          for e in rows[:4]],[2.6]*4)
        self.assertTrue(all(e["official_pdf_sha256_captured_now"] is None
                            for e in rows[:4]))
        self.assertTrue(all(len(e["official_pdf_sha256_captured_now"])==64
                            for e in rows[4:]))
        self.assertEqual(rows[-1]["reference_month"],"2026-09")
        self.assertEqual(rows[-1]["original_seco_rounded_sa_registered_unemployment_pct"],3.1)
        self.assertEqual(rows[16]["reference_month"],"2026-01")
        self.assertEqual(rows[16]["original_seco_rounded_sa_registered_unemployment_pct"],2.9)

    def test_four_cached_full_pdf_text_links_do_not_promote_raw_pdf_bytes(self):
        rows=from_index_only()
        self.assertEqual(len(rows),4)
        self.assertEqual(set(INDEXED_OFFICIAL_PDF_TEXT_ONLY),
                         {r["reference_month"] for r in rows})
        self.assertEqual([r["indexed_document_pages_reported_NOT_verified_raw_PDF"]
                          for r in rows],[26,27,27,28])
        for r in rows:
            self.assertEqual(r["indexed_pdf_first_table_SA_rate_one_decimal_confirmed"],2.6)
            self.assertTrue(r["official_web_indexed_full_PDF_text_locator_NOT_downloadable_original"]
                            .startswith("https://www.arbeit.swiss/"))
            self.assertTrue(r["indexed_official_PDF_text_is_not_original_bytes_or_source_day_snapshot"])
            self.assertIsNone(r["official_pdf_sha256_captured_now"])
            self.assertFalse(r["source_first_month_raw_document_bytes_downloaded"])
            self.assertFalse(r["document_original_release_day_HTTP_snapshot_verified"])
            self.assertFalse(r["publisher_first_original_exact_SNB_values_verified"])
        summary=self.a["summary"]
        self.assertEqual(summary["official_2024_original_full_PDF_text_index_locators_identified"],4)
        self.assertEqual(summary["original_PDF_bytes_still_missing_despite_indexed_text"],4)
        self.assertEqual(summary["official_PDF_raw_bytes_SHA_captured_now"],21)
        self.assertEqual(summary["authorized_G8_macro_currency_scores"],0)

    def test_rounded_research_z_is_not_precise_snb_first_vintage(self):
        d=self.a
        r=d["statistical_research"]
        self.assertTrue(r["24_prior_calendar_months_present_for_alternative_metric"])
        self.assertTrue(r["24_prior_observations_from_FIRST_MONTH_WEB_REPORTS"])
        self.assertEqual(r["total_previous_publisher_byte_recovered_PDF_months"],20)
        self.assertEqual(r["total_previous_web_index_only_first_report_months"],4)
        self.assertIsNotNone(r["descriptive_robust_z_of_rounded_first_SECO_rates"])
        self.assertTrue(r["not_equivalent_to_exact_SNB_first_release_z"])
        self.assertFalse(r["original_SNBSI_values_reconstructed"])
        self.assertTrue(d["historical_24_SNB_exact_first_release_percentages_unavailable"])
        self.assertTrue(d["source_first_publication_intraday_timestamp_not_proven"])
        self.assertEqual(d["summary"]["authorized_G8_macro_currency_scores"],0)
        self.assertEqual(d["summary"]["FX_pair_rankings_changed"],0)
        for name in ["safe_to_publish_new_D","safe_to_change_28_pairs",
                     "safe_for_beta","safe_for_forward","writes_live_data"]:
            self.assertFalse(d[name])

    def test_no_publish_clock_from_real_report_day(self):
        d=self.a
        by={x["reference_month"]:x for x in d["publisher_first_rounded_monthly_reports"]}
        self.assertEqual(by["2024-09"]["conservative_available_from_utc"],
                         "2024-10-05T00:00:00+00:00")
        self.assertEqual(by["2024-12"]["conservative_available_from_utc"],
                         "2025-01-11T00:00:00+00:00")
        self.assertEqual(by["2026-09"]["conservative_available_from_utc"],
                         "2026-10-07T00:00:00+00:00")
        self.assertEqual(by["2025-01"]["conservative_available_from_utc"],
                         "2025-02-07T00:00:00+00:00")

    def test_no_invalid_exact_claims_when_one_source_corrupted(self):
        f=json.loads(FIXTURE.read_text())
        f["archived_issuer_first_rounded_reports"][-1][
            "original_seco_rounded_sa_registered_unemployment_pct"]=3.1249882357461
        with self.assertRaises(ValueError):
            audit(raw=f)
        f=json.loads(FIXTURE.read_text())
        f["verified_issuer_first_rounded_reports"]=25
        with self.assertRaises(ValueError):
            audit(raw=f)
        f=json.loads(FIXTURE.read_text())
        f["archived_issuer_first_rounded_reports"][0]["official_pdf_sha256_captured_now"]=None
        with self.assertRaises(ValueError):
            audit(raw=f)

    def test_cannot_replay_today_revised_2026_contents_as_past(self):
        for asof in ("2025-01-10T23:59:59Z","2026-10-27T23:59:59Z",
                     "2026-10-26T23:59:59+02:00"):
            with self.subTest(asof=asof),self.assertRaises(ValueError):
                audit(cutoff=asof)

    def test_22_first_web_original_registered_windows_stay_22(self):
        r=evidence()
        self.assertEqual(r["summary"]["prior_first_web_contiguous_12Q_or_24M_slots"],22)
        self.assertEqual(r["summary"]["slots_missing_required_initial_release_periods"],2)
        self.assertEqual(r["summary"]["missing_required_prior_periods_total"],46)
        self.assertEqual(r["summary"]["genuinely_historic_PIT_training_slots_certified"],0)

    def test_no_mutation_to_core_D_or_fx_pairs(self):
        folder=ROOT/"live_data/sections"
        old={x:(folder/x).read_bytes() for x in ("D.json","PAIR_SETUP_OPERATIONAL_VIEW.json")}
        again=audit()
        self.assertEqual(again["receipt_sha256"],self.a["receipt_sha256"])
        self.assertEqual(old,{x:(folder/x).read_bytes() for x in old})


if __name__=="__main__":
    unittest.main()
