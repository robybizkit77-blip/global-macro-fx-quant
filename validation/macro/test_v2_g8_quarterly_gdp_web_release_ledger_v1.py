"""G8 GDP Q2 dated publisher statements: real past release vs future vintage."""
import copy
import json
import unittest

from validation.macro.v2_g8_quarterly_gdp_web_release_ledger_v1 import (
    FILE, FIRST, FOLLOWUP, asof, review, visible_at
)


class GDPQuarterlyPublisherLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FILE.read_text(encoding="utf-8"))
        cls.receipt = review(cls.data)

    def test_8_first_release_2_later_6_ordinary_qoq_and_zero_score_promotions(self):
        s = self.receipt["summary"]
        self.assertEqual(s["first_publisher_web_statements_documented"], 8)
        self.assertEqual(s["documented_followup_revisions"], 2)
        self.assertEqual(s["different_reported_GDP_horizon_or_special_adjustment"], 2)
        self.assertEqual(set(FIRST), {"USD", "EUR", "GBP", "JPY", "CHF",
                                       "CAD", "AUD", "NZD"})
        self.assertEqual(set(FOLLOWUP), {"EUR", "GBP"})
        self.assertEqual(len(self.receipt["events"]), 10)
        self.assertEqual(s["certified_historical_first_vintage_training_windows"], 0)
        self.assertEqual(s["approved_macro_growth_scores"], 0)
        for flag in ("identical_quarterly_growth_horizon_approved_for_G8_ranking",
                     "safe_to_update_live_macro_D", "safe_to_change_28_pairs",
                     "safe_to_use_for_beta", "safe_to_use_for_forward",
                     "writes_live_data"):
            self.assertIs(self.receipt[flag], False)
        self.assertTrue(self.receipt["source_document_is_not_release_day_archive"])
        for ev in self.receipt["events"]:
            self.assertFalse(ev["PIT_training_vintage_certified"])
            self.assertFalse(ev["eligible_for_macro_scoring"])
            self.assertFalse(ev["publisher_release_instant_verified"])
            self.assertIsNone(ev["source_artifact_original_day_sha256"])

    def test_conservative_day_only_no_future_data_at_release_instant(self):
        r = self.receipt
        self.assertEqual(asof(r, "2026-07-30T23:59:59Z")["visible_currency_count"], 0)
        self.assertEqual(asof(r, "2026-07-31T00:00:00Z")["visible_currency_count"], 2)
        self.assertEqual(asof(r, "2026-08-14T00:00:00Z")["visible_currency_count"], 3)
        self.assertEqual(asof(r, "2026-08-18T00:00:00Z")["visible_currency_count"], 5)
        self.assertEqual(asof(r, "2026-09-18T00:00:00Z")["visible_currency_count"], 8)
        self.assertEqual(visible_at("2026-09-17").isoformat(),
                         "2026-09-18T00:00:00+00:00")

    def test_first_vs_second_stage_eurostat_and_ons_same_quarter(self):
        early_eur = asof(self.receipt, "2026-09-07T23:59:59Z")["available_by_currency"]["EUR"]
        later_eur = asof(self.receipt, "2026-09-08T00:00:00Z")["available_by_currency"]["EUR"]
        self.assertEqual(early_eur["raw_publisher_value"], 0.4)
        self.assertEqual(early_eur["publication_stage"], "PRELIMINARY_FLASH")
        self.assertEqual(later_eur["raw_publisher_value"], 0.6)
        self.assertEqual(later_eur["publication_stage"], "REGULAR_ESTIMATE_REVISED")
        early_uk = asof(self.receipt, "2026-09-30T23:59:59Z")["available_by_currency"]["GBP"]
        later_uk = asof(self.receipt, "2026-10-01T00:00:00Z")["available_by_currency"]["GBP"]
        self.assertEqual(early_uk["raw_publisher_value"], 0.4)
        self.assertEqual(later_uk["raw_publisher_value"], 0.5)

    def test_us_annualized_and_swiss_sports_adjusted_not_mislabeled_qoq(self):
        all_c = asof(self.receipt, "2026-10-26T00:00:00Z")["available_by_currency"]
        self.assertEqual(all_c["USD"]["raw_publisher_value"], 1.5)
        self.assertEqual(all_c["USD"]["publisher_unit"], "PERCENT_SAAR_ANNUALIZED")
        self.assertIsNone(all_c["USD"]["research_nonannualized_qoq_publisher_value"])
        self.assertIsNone(all_c["CHF"]["research_nonannualized_qoq_publisher_value"])
        self.assertEqual(all_c["NZD"]["raw_publisher_value"], 0.2)
        self.assertEqual(all_c["NZD"]["research_nonannualized_qoq_publisher_value"], 0.2)
        self.assertTrue(all(not r["certified_for_common_G8_growth_score"]
                            for r in all_c.values()))

    def test_chf_first_publisher_must_be_primary_seco_not_federal_mirror(self):
        swiss = next(r for r in self.receipt["events"] if
                     r["currency"] == "CHF" and r["stage_order"] == 0)
        self.assertEqual(
            swiss["source_url"],
            "https://www.seco.admin.ch/en/newnsb/1BH4HnCuYPWb_WqjPywR4")
        self.assertEqual(swiss["publisher_release_day"], "2026-08-14")
        self.assertEqual(swiss["reported_value"], 1.5)
        self.assertEqual(swiss["reported_unit"], "PERCENT_QOQ_SA_CALENDAR_SPORTS")
        bad = copy.deepcopy(self.data)
        next(r for r in bad["records"] if
             r["currency"] == "CHF" and r["stage_order"] == 0)["source_url"] = (
            "https://www.schweizerischesseeschifffahrtsamt.eda.admin.ch/en/newnsb/1BH4HnCuYPWb_WqjPywR4")
        with self.assertRaises(ValueError):
            review(bad)

    def test_corrupt_values_dates_units_duplicates_unsafe_provenance_refused(self):
        patches = []
        d = copy.deepcopy(self.data)
        d["records"][0]["reported_unit"] = "PERCENT_QOQ_SA"
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][0]["reported_value"] = 0.4
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][0]["publisher_release_day"] = "2026-07-29"
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][2]["source_url"] = "https://www.ons.gov.uk.attacker.com/gdp"
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][3]["reference_quarter"] = "2026Q3"
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][8]["publication_stage"] = "PRELIMINARY_FLASH"
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][1] = copy.deepcopy(d["records"][0])
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["records"][2]["stage_order"] = 1
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["release_artifact_original_day_bytes_archived"] = True
        patches.append(d)
        d = copy.deepcopy(self.data)
        d["eligible_for_macro_scoring"] = True
        patches.append(d)
        for i, mutated in enumerate(patches):
            with self.subTest(i=i), self.assertRaises((ValueError, TypeError)):
                review(mutated)


if __name__ == "__main__":
    unittest.main()
