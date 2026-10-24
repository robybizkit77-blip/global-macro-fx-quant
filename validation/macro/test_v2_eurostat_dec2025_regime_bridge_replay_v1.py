import copy
import json
import unittest

from validation.macro.v2_eurostat_dec2025_regime_bridge_replay_v1 import (
    SOURCE, validate, replay,
)


class EurostatDecemberEA20BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(SOURCE.read_text(encoding="utf-8"))

    def dec(self,receipt):
        return receipt["vintage_by_economic_reference_month"][0]

    def jan(self,receipt):
        return receipt["vintage_by_economic_reference_month"][1]

    def test_flash_hidden_before_conservative_source_date_gate(self):
        before=replay("2026-01-07T23:59:59Z",self.data)
        after=replay("2026-01-08T00:00:00Z",self.data)
        self.assertFalse(self.dec(before)["flash_visible"])
        self.assertIsNone(self.dec(before)["visible_metric_values"]["ALL_ITEMS_HICP"])
        self.assertTrue(self.dec(after)["flash_visible"])
        self.assertEqual(self.dec(after)["visible_metric_values"]["ALL_ITEMS_HICP"],2.0)
        self.assertEqual(self.dec(after)["visible_metric_values"]["FOOD_ALCOHOL_TOBACCO"],2.6)
        self.assertFalse(self.dec(after)["detailed_visible"])
        self.assertEqual(after["months_with_initial_web_publication_visible"],1)
        self.assertEqual(after["months_short_of_25"],24)

    def test_december_detailed_19_january_one_tenth_headline_revision(self):
        before=replay("2026-01-19T23:59:59Z",self.data)
        after=replay("2026-01-20T00:00:00Z",self.data)
        self.assertEqual(self.dec(before)["visible_metric_values"]["ALL_ITEMS_HICP"],2.0)
        self.assertEqual(self.dec(after)["visible_metric_values"]["ALL_ITEMS_HICP"],1.9)
        self.assertEqual(self.dec(after)["original_flash_headline"],2.0)
        self.assertEqual(self.dec(after)["detailed_headline"],1.9)
        self.assertEqual(self.dec(after)["visible_metric_values"]["CORE_HICP"],2.3)
        self.assertEqual(self.dec(after)["visible_metric_values"]["ENERGY"],-1.9)
        self.assertEqual(self.dec(after)["visible_metric_values"]["FOOD_ALCOHOL_TOBACCO"],2.5)
        self.assertEqual(self.dec(after)["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"],-0.1)
        self.assertEqual(self.dec(after)["component_flash_to_detailed_change_pp"]["FOOD_ALCOHOL_TOBACCO"],-0.1)
        self.assertEqual(after["headline_flash_to_detailed_changes_visible"],{"2025-12":-0.1})

    def test_later_february_4_december_2point0_never_overwrites_jan19_final(self):
        before=replay("2026-02-04T23:59:59Z",self.data)
        after=replay("2026-02-05T00:00:00Z",self.data)
        self.assertEqual(len(before["retrospective_december_headline_in_2026_reports"]),0)
        self.assertEqual(len(after["retrospective_december_headline_in_2026_reports"]),1)
        self.assertEqual(after["retrospective_december_headline_in_2026_reports"][0]
                         ["value_reported_percent_yoy"],2.0)
        self.assertFalse(after["retrospective_december_headline_in_2026_reports"][0]
                         ["overwrites_december_detailed_1point9"])
        self.assertFalse(after["retrospective_december_headline_in_2026_reports"][0]
                         ["cause_of_discrepancy_verified"])
        self.assertEqual(self.dec(after)["visible_metric_values"]["ALL_ITEMS_HICP"],1.9)
        self.assertEqual(self.jan(after)["original_flash_headline"],1.7)
        self.assertEqual(after["ordinary_publications_visible"],3)

    def test_second_retrospective_only_visible_after_february_25_release(self):
        before=replay("2026-02-25T23:59:59Z",self.data)
        after=replay("2026-02-26T00:00:00Z",self.data)
        self.assertEqual(len(before["retrospective_december_headline_in_2026_reports"]),1)
        self.assertEqual(len(after["retrospective_december_headline_in_2026_reports"]),2)
        self.assertEqual([e["value_reported_percent_yoy"]
                          for e in after["retrospective_december_headline_in_2026_reports"]],
                         [2.0,2.0])
        self.assertEqual(self.dec(after)["detailed_headline"],1.9)
        self.assertEqual(self.jan(after)["detailed_headline"],1.7)
        self.assertTrue(after["regime_transition"]["has_both_month_values"])

    def test_two_independent_2026_transition_flags_not_false_homogeneity(self):
        r=replay("2026-02-26T00:00:00Z",self.data)
        b=r["regime_transition"]
        self.assertEqual((b["previous_reference_month"],b["previous_region"]),
                         ("2025-12","EA20"))
        self.assertEqual((b["next_reference_month"],b["next_region"]),
                         ("2026-01","EA21"))
        self.assertTrue(b["historical_all_items_unchanged_due_to_ECOICOP_alone"])
        self.assertTrue(b["chain_index_context_from_eurostat"])
        self.assertIsNone(b["automatic_cross_regime_headline_delta_pp"])
        self.assertIsNone(b["automatic_cross_regime_weighted_component_comparison"])
        self.assertFalse(b["cross_regime_model_normalization_certified"])
        self.assertTrue(b["regime_bridge_independent_evidence_review_required"])

    def test_final_scope_is_ten_months_twenty_ordinary_events_two_corrigenda(self):
        r=replay("2026-10-24T00:00:00Z",self.data)
        self.assertEqual(r["research_scope"],{
            "reference_months":10,"ordinary_release_events":20,
            "separate_correction_events":2,
            "year_on_year_metric_stage_values":120,
            "sampled_later_december_references":2})
        self.assertEqual(r["ordinary_publications_visible"],20)
        self.assertEqual(r["correction_events_visible"],2)
        self.assertEqual(r["months_with_initial_web_publication_visible"],10)
        self.assertEqual(r["months_short_of_25"],15)
        self.assertEqual([x["reference_period"] for x in r["vintage_by_economic_reference_month"]],
                         ["2025-12","2026-01","2026-02","2026-03","2026-04",
                          "2026-05","2026-06","2026-07","2026-08","2026-09"])
        self.assertEqual(r["headline_flash_to_detailed_changes_visible"]["2025-12"],-0.1)
        self.assertEqual(r["headline_flash_to_detailed_changes_visible"]["2026-03"],0.1)
        self.assertEqual(r["headline_flash_to_detailed_changes_visible"]["2026-08"],-0.1)

    def test_safe_cutoffs_reject_promotion_in_every_stage(self):
        for asof in ("2026-01-07T23:59:59Z","2026-01-08T00:00:00Z",
                     "2026-01-20T00:00:00Z","2026-02-05T00:00:00Z",
                     "2026-02-26T00:00:00Z","2026-10-24T00:00:00Z"):
            with self.subTest(asof=asof):
                r=replay(asof,self.data)
                for k in ("release_day_original_bytes_verified",
                          "full_historical_pit_revision_matrix_certified",
                          "intraday_eurostat_publisher_clock_certified",
                          "eligible_for_macro_scoring","eligible_for_backtest",
                          "safe_to_publish_new_D","safe_to_update_pair_theses",
                          "writes_live_data"):
                    self.assertIs(r[k],False)

    def test_tampered_metric_source_and_regime_contract_rejected(self):
        cases=(
            ("components",0,"flash_percent_yoy",1.9),
            ("components",0,"detailed_percent_yoy",2.0),
            ("components",3,"detailed_percent_yoy",2.6),
        )
        for _,i,k,value in cases:
            with self.subTest(i=i,k=k):
                bad=copy.deepcopy(self.data)
                bad["components"][i][k]=value
                with self.assertRaises(ValueError):
                    validate(bad)
        bad=copy.deepcopy(self.data)
        bad["stage_publications"][0]["conservative_visible_from_utc"]="2026-01-07T11:00:00Z"
        with self.assertRaises(ValueError):
            validate(bad)
        bad=copy.deepcopy(self.data)
        bad["later_2026_report_references"][0]["publisher_reported_december_2025_headline_percent"]=1.9
        with self.assertRaises(ValueError):
            validate(bad)
        for field,value in (
            ("membership_2025","EA21"),
            ("membership_2026","EA20"),
            ("eurostat_all_items_historical_unaffected_by_ecoicop_reclassification_alone",False),
            ("no_automatic_cross_regime_normalized_macro_signal",False),
        ):
            with self.subTest(field=field):
                bad=copy.deepcopy(self.data)
                bad["transition"][field]=value
                with self.assertRaises(ValueError):
                    validate(bad)
        bad=copy.deepcopy(self.data)
        bad["backtest_eligible"]=True
        with self.assertRaises(ValueError):
            validate(bad)

    def test_nonmutating_reproducible(self):
        evidence=copy.deepcopy(self.data)
        a=replay("2026-10-24T00:00:00Z",evidence)
        self.assertEqual(a,replay("2026-10-24T00:00:00Z",evidence))
        self.assertEqual(evidence,self.data)


if __name__=="__main__":
    unittest.main()
