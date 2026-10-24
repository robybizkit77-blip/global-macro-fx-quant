import copy
import json
import unittest

from validation.macro.v2_eurostat_hicp_nine_month_corrigendum_replay_v1 import (
    EVIDENCE, replay, validate,
)


class HICPNineMonthCorrigendaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=json.loads(EVIDENCE.read_text(encoding="utf-8"))

    @staticmethod
    def month(r,period):
        return next(x for x in r["snapshot_by_reference_period"]
                    if x["reference_period"]==period)

    @staticmethod
    def correction(r,period):
        return next(x for x in r["corrigenda"] if x["reference_period"]==period)

    def test_final_audit_counts_are_months_not_component_rows(self):
        final=replay("2026-10-24T00:00:00Z",self.evidence)
        self.assertEqual(final["scope"],{
            "reference_months":9,"ordinary_flash_and_detailed_events":18,
            "separate_corrigendum_events":2,
            "all_publisher_publication_or_correction_events":20,
            "selected_annual_rate_metrics_per_release":6,
            "ordinary_metric_event_observations":108})
        self.assertEqual(final["ordinary_publications_visible"],18)
        self.assertEqual(final["corrigenda_visible"],2)
        self.assertEqual(final["months_with_first_web_release_available"],9)
        self.assertEqual(final["remaining_independent_monthly_first_release_periods_for_25"],16)
        self.assertEqual(final["nonzero_flash_to_detailed_component_comparisons_visible"],19)
        self.assertEqual(final["headline_flash_to_detailed_changes_visible"],{
            "2026-01":0.0,"2026-02":0.0,"2026-03":0.1,"2026-04":0.0,
            "2026-05":0.0,"2026-06":0.0,"2026-07":0.0,"2026-08":-0.1,
            "2026-09":0.0})

    def test_january_flash_corrigendum_and_final_are_three_separate_gates(self):
        prior=replay("2026-02-04T23:59:59Z",self.evidence)
        flash=replay("2026-02-05T00:00:00Z",self.evidence)
        before_correction=replay("2026-02-05T23:59:59Z",self.evidence)
        corrected=replay("2026-02-06T00:00:00Z",self.evidence)
        before_final=replay("2026-02-25T23:59:59Z",self.evidence)
        final=replay("2026-02-26T00:00:00Z",self.evidence)
        self.assertFalse(self.month(prior,"2026-01")["flash_visible"])
        self.assertEqual(self.month(flash,"2026-01")["original_flash_headline"],1.7)
        self.assertEqual(self.month(flash,"2026-01")["stage_at_cutoff"],
                         "FLASH_WEB_REPORT_WITH_UNCERTIFIED_ORIGINAL_BODY")
        self.assertFalse(self.correction(before_correction,"2026-01")
                         ["official_corrigendum_web_note_visible"])
        self.assertTrue(self.correction(corrected,"2026-01")
                        ["official_corrigendum_web_note_visible"])
        self.assertEqual(self.month(corrected,"2026-01")["stage_at_cutoff"],
                         "POST_FLASH_CORRIGENDUM")
        self.assertFalse(self.month(before_final,"2026-01")["detailed_visible"])
        self.assertEqual(self.month(final,"2026-01")["visible_metric_values"]["ENERGY"],-4.0)
        self.assertEqual(self.month(final,"2026-01")["visible_metric_values"]["FOOD_ALCOHOL_TOBACCO"],2.6)
        self.assertEqual(self.month(final,"2026-01")["visible_metric_values"]["ALL_ITEMS_HICP"],1.7)

    def test_february_flash_weights_corrigendum_and_final(self):
        before=replay("2026-03-03T23:59:59Z",self.evidence)
        flash=replay("2026-03-04T00:00:00Z",self.evidence)
        pre_correction=replay("2026-03-04T23:59:59Z",self.evidence)
        corrected=replay("2026-03-05T00:00:00Z",self.evidence)
        before_final=replay("2026-03-18T23:59:59Z",self.evidence)
        final=replay("2026-03-19T00:00:00Z",self.evidence)
        self.assertIsNone(self.month(before,"2026-02")["original_flash_headline"])
        self.assertEqual(self.month(flash,"2026-02")["original_flash_headline"],1.9)
        self.assertEqual(self.month(flash,"2026-02")["visible_metric_values"]["ENERGY"],-3.2)
        self.assertFalse(self.correction(pre_correction,"2026-02")
                         ["official_corrigendum_web_note_visible"])
        self.assertTrue(self.correction(corrected,"2026-02")
                        ["official_corrigendum_web_note_visible"])
        self.assertEqual(self.correction(corrected,"2026-02")["correction_type"],
                         "COMPONENT_WEIGHT_TECHNICAL_ERROR")
        self.assertFalse(self.month(before_final,"2026-02")["detailed_visible"])
        self.assertEqual(self.month(final,"2026-02")["visible_metric_values"]["ENERGY"],-3.1)
        self.assertEqual(self.month(final,"2026-02")["visible_metric_values"]["FOOD_ALCOHOL_TOBACCO"],2.5)
        self.assertEqual(self.month(final,"2026-02")["visible_metric_values"]["ALL_ITEMS_HICP"],1.9)

    def test_corrigendum_does_not_create_new_first_release_month_or_fabricated_weights(self):
        january_pre=replay("2026-02-05T00:00:00Z",self.evidence)
        january_corr=replay("2026-02-06T00:00:00Z",self.evidence)
        self.assertEqual(january_pre["months_with_first_web_release_available"],
                         january_corr["months_with_first_web_release_available"])
        self.assertEqual(january_pre["ordinary_publications_visible"],
                         january_corr["ordinary_publications_visible"])
        self.assertEqual(january_pre["corrigenda_visible"]+1,
                         january_corr["corrigenda_visible"])
        for record in january_corr["corrigenda"]:
            self.assertFalse(record["actual_correction_instant_timezone_certified"])
            self.assertFalse(record["pre_corrigendum_corrected_values_reconstructible"])

    def test_preexisting_seven_month_data_and_march_services_history_preserved(self):
        r=replay("2026-10-24T00:00:00Z",self.evidence)
        self.assertEqual(self.month(r,"2026-03")["original_flash_headline"],2.5)
        self.assertEqual(self.month(r,"2026-03")["detailed_headline"],2.6)
        self.assertEqual(self.month(r,"2026-08")["original_flash_headline"],3.3)
        self.assertEqual(self.month(r,"2026-08")["detailed_headline"],3.2)
        self.assertEqual(r["march_services_cross_report_history"]["latest_sampled_value"],3.2)
        self.assertEqual(len(r["march_services_cross_report_history"]
                             ["known_publication_values"]),4)

    def test_research_safety_and_no_false_archive_claims(self):
        for when in ("2026-02-05T00:00:00Z","2026-02-06T00:00:00Z",
                     "2026-03-04T00:00:00Z","2026-03-05T00:00:00Z",
                     "2026-10-24T00:00:00Z"):
            r=replay(when,self.evidence)
            for key in ("jan_feb_flash_original_uncorrected_full_bytes_certified",
                        "actual_eurostat_intraday_release_hour_certified",
                        "complete_pit_revision_archive_certified",
                        "source_release_day_original_bytes_archived",
                        "eligible_for_macro_scoring","eligible_for_backtest",
                        "safe_to_publish_new_D","safe_to_update_pair_theses",
                        "writes_live_data"):
                self.assertIs(r[key],False)

    def test_mutating_correction_or_values_fails_closed(self):
        changes=(
            (0,"annual_rate_components",2,"flash_percent_yoy",-4.0),
            (1,"annual_rate_components",3,"detailed_percent_yoy",2.6),
            (0,"annual_rate_components",0,"flash_percent_yoy",1.8),
        )
        for month,group,index,key,value in changes:
            with self.subTest(month=month,index=index):
                x=copy.deepcopy(self.evidence)
                x["months"][month][group][index][key]=value
                with self.assertRaises(ValueError):
                    validate(x)
        for month,section,key,value in (
            (0,"flash","conservative_visible_from_utc","2026-02-04T12:00:00Z"),
            (0,"corrigendum","publication_day","2026-02-04"),
            (1,"corrigendum","corrected_metric","ANNUAL_RATE"),
            (1,"corrigendum","publisher_wall_clock_timezone_certified",True),
            (0,"detailed","source_url","https://example.com/official"),
        ):
            x=copy.deepcopy(self.evidence)
            x["months"][month][section][key]=value
            with self.assertRaises(ValueError):
                validate(x)
        for key in ("first_uncorrected_all_metrics_certified","macro_score_ready",
                    "full_revision_history_certified"):
            x=copy.deepcopy(self.evidence)
            x[key]=True
            with self.assertRaises(ValueError):
                validate(x)

    def test_pure_repeatable_source(self):
        data=copy.deepcopy(self.evidence)
        one=replay("2026-10-24T00:00:00Z",data)
        self.assertEqual(one,replay("2026-10-24T00:00:00Z",data))
        self.assertEqual(data,self.evidence)


if __name__=="__main__":
    unittest.main()
