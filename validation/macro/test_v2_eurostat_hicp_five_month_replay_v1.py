import copy
import json
import unittest

from validation.macro.v2_eurostat_hicp_five_month_replay_v1 import (
    SOURCE, validate, replay,
)


class EurostatHICPFiveMonthReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SOURCE.read_text(encoding="utf-8"))

    def row(self, receipt, period):
        return next(x for x in receipt["snapshot_by_reference_period"]
                    if x["reference_period"] == period)

    def test_five_months_ten_publisher_events_not_sixty_independent_months(self):
        r = replay("2026-10-24T00:00:00Z", self.data)
        self.assertEqual(r["research_scope"], {
            "reference_months": 5, "distinct_publisher_publications": 10,
            "comparable_annual_rate_metrics_per_stage": 6,
            "annual_rate_metric_publication_observations": 60,
            "extra_retrospective_reference_observations": 2,
        })
        self.assertEqual(r["source_publications_visible"], 10)
        self.assertEqual(r["reference_months_with_any_flash_visible"], 5)
        self.assertEqual(r["additional_first_release_months_needed_for_25"], 20)
        self.assertEqual(r["visible_nonzero_component_comparisons"], 11)
        self.assertEqual([x["reference_period"] for x in r["snapshot_by_reference_period"]],
                         ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"])
        self.assertEqual(r["headline_flash_detailed_changes_visible"],
                         {"2026-05":0.0,"2026-06":0.0,
                          "2026-07":0.0,"2026-08":-0.1,"2026-09":0.0})

    def test_may_flash_and_detailed_gate_before_after_exact_utc_second(self):
        before = replay("2026-06-02T23:59:59Z", self.data)
        first = replay("2026-06-03T00:00:00Z", self.data)
        detail_before = replay("2026-06-17T23:59:59Z", self.data)
        detail = replay("2026-06-18T00:00:00Z", self.data)
        self.assertIsNone(self.row(before, "2026-05")["visible_metric_values"]["ALL_ITEMS_HICP"])
        self.assertEqual(self.row(first, "2026-05")["visible_metric_values"]["ENERGY"], 10.9)
        self.assertEqual(self.row(detail_before, "2026-05")["visible_metric_values"]["CORE_HICP"], 2.5)
        self.assertEqual(self.row(detail, "2026-05")["visible_metric_values"]["CORE_HICP"], 2.6)
        self.assertEqual(self.row(detail, "2026-05")["visible_metric_values"]["ENERGY"], 10.8)
        self.assertEqual(self.row(detail, "2026-05")["component_flash_to_detailed_change_pp"], {
            "ALL_ITEMS_HICP": 0.0,"CORE_HICP": 0.1,"ENERGY":-0.1,
            "FOOD_ALCOHOL_TOBACCO":-0.1,
            "NON_ENERGY_INDUSTRIAL_GOODS":0.0,"SERVICES":0.0})

    def test_june_flash_then_final_component_revisions_no_premature_data(self):
        pre = replay("2026-07-01T23:59:59Z", self.data)
        flash = replay("2026-07-02T00:00:00Z", self.data)
        predetail = replay("2026-07-17T23:59:59Z", self.data)
        detail = replay("2026-07-18T00:00:00Z", self.data)
        self.assertIsNone(self.row(pre, "2026-06")["original_flash_headline"])
        self.assertEqual(self.row(flash, "2026-06")["original_flash_headline"], 2.8)
        self.assertEqual(self.row(flash, "2026-06")["visible_metric_values"]["ENERGY"], 8.7)
        self.assertIsNone(self.row(predetail, "2026-06")["detailed_headline"])
        self.assertEqual(self.row(detail, "2026-06")["visible_metric_values"]["ENERGY"], 8.5)
        self.assertEqual(self.row(detail, "2026-06")["visible_metric_values"]["NON_ENERGY_INDUSTRIAL_GOODS"], 0.7)
        self.assertEqual(self.row(detail, "2026-06")["component_flash_to_detailed_change_pp"]["ENERGY"], -0.2)
        self.assertEqual(self.row(detail, "2026-06")["component_flash_to_detailed_change_pp"]["FOOD_ALCOHOL_TOBACCO"], -0.1)
        self.assertEqual(self.row(detail, "2026-06")["component_flash_to_detailed_change_pp"]["NON_ENERGY_INDUSTRIAL_GOODS"], -0.2)

    def test_prior_month_march_services_revision_reference_not_backdated(self):
        before_june_detail = replay("2026-06-17T23:59:59Z", self.data)
        may_detail = replay("2026-06-18T00:00:00Z", self.data)
        before_june_flash = replay("2026-07-01T23:59:59Z", self.data)
        june_flash = replay("2026-07-02T00:00:00Z", self.data)
        a = before_june_detail["march_services_retrospective_cross_report"]
        b = may_detail["march_services_retrospective_cross_report"]
        c = before_june_flash["march_services_retrospective_cross_report"]
        d = june_flash["march_services_retrospective_cross_report"]
        self.assertIsNone(a["earlier_reported_yoy_percent"])
        self.assertEqual(b["earlier_reported_yoy_percent"],3.3)
        self.assertIsNone(b["later_reported_yoy_percent"])
        self.assertIsNone(c["later_reported_yoy_percent"])
        self.assertEqual(d["later_reported_yoy_percent"],3.2)
        self.assertEqual(d["difference_pp"],-0.1)
        self.assertTrue(d["later_report_source_has_r_marker"])
        self.assertEqual(d["first_different_web_source_gate_utc"],"2026-07-02T00:00:00+00:00")
        self.assertFalse(d["actual_revision_effective_time_verified"])
        self.assertFalse(d["original_march_first_publication_was_verified"])
        self.assertEqual(d["additional_independent_first_release_month_count"],0)

    def test_july_september_existing_model_replay_not_changed(self):
        r = replay("2026-10-24T00:00:00Z", self.data)
        self.assertEqual(self.row(r,"2026-07")["visible_metric_values"]["ENERGY"],10.3)
        self.assertEqual(self.row(r,"2026-08")["original_flash_headline"],3.3)
        self.assertEqual(self.row(r,"2026-08")["detailed_headline"],3.2)
        self.assertEqual(self.row(r,"2026-09")["visible_metric_values"]["ENERGY"],18.9)
        self.assertEqual(r["latest_visible_reference_month"],"2026-09")
        self.assertEqual(r["latest_visible_headline_yoy_percent"],3.8)

    def test_pin_tamper_rejected_and_full_certification_still_false(self):
        alterations=(
            (0,1,"CORE_HICP","flash_percent_yoy",2.6),
            (0,2,"ENERGY","detailed_percent_yoy",10.9),
            (1,4,"NON_ENERGY_INDUSTRIAL_GOODS","detailed_percent_yoy",0.9),
        )
        for period,i,category,field,value in alterations:
            with self.subTest(period=period,category=category):
                changed=copy.deepcopy(self.data)
                self.assertEqual(changed["months"][period]["annual_rate_components"][i]["component_id"],category)
                changed["months"][period]["annual_rate_components"][i][field]=value
                with self.assertRaises(ValueError):
                    validate(changed)
        changed=copy.deepcopy(self.data)
        changed["months"][1]["flash"]["conservative_visibility_from_utc"]="2026-07-01T10:00:00Z"
        with self.assertRaises(ValueError):
            validate(changed)
        changed=copy.deepcopy(self.data)
        changed["retrospective_prior_month_observation"]["later_report_has_explicit_r_marker"]=False
        with self.assertRaises(ValueError):
            validate(changed)
        changed=copy.deepcopy(self.data)
        changed["full_historical_first_and_revised_vintage_chain_certified"]=True
        with self.assertRaises(ValueError):
            validate(changed)

    def test_pure_inputs_no_scoring_or_live_data(self):
        data=copy.deepcopy(self.data)
        for cutoff in ("2026-06-02T23:59:59Z","2026-06-18T00:00:00Z",
                       "2026-07-02T00:00:00Z","2026-09-02T00:00:00Z",
                       "2026-10-24T00:00:00Z"):
            r = replay(cutoff,data)
            self.assertFalse(r["complete_historical_revision_matrix_certified"])
            self.assertFalse(r["actual_intraday_publication_clocks_certified"])
            for key in ("eligible_for_macro_scoring","eligible_for_backtest",
                        "safe_to_publish_new_D","safe_to_update_pair_theses",
                        "writes_live_data"):
                self.assertFalse(r[key])
        self.assertEqual(data,self.data)


if __name__=="__main__":
    unittest.main()
