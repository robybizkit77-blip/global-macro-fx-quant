import copy
import json
import unittest

from validation.macro.v2_eurostat_hicp_seven_month_replay_v1 import (
    EVIDENCE, replay, validate,
)


class EurostatHICPSevenMonthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def row(self,r,period):
        return next(x for x in r["snapshot_by_reference_period"]
                    if x["reference_period"]==period)

    def history(self,r):
        return r["march_services_cross_report_history"]["known_publication_values"]

    def test_final_scope_7_months_14_release_events_not_84_months(self):
        r=replay("2026-10-24T00:00:00Z",self.fixture)
        self.assertEqual(r["research_scope"],{
            "reference_months":7,"publisher_release_events":14,
            "annual_rate_components_per_stage":6,
            "report_value_observations":84,
            "march_services_retrospective_statement_count":4})
        self.assertEqual(r["publisher_events_visible"],14)
        self.assertEqual(r["monthly_first_publication_periods_visible"],7)
        self.assertEqual(r["months_short_of_25_release_research_minimum"],18)
        self.assertEqual([x["reference_period"] for x in r["snapshot_by_reference_period"]],
                         ["2026-03","2026-04","2026-05","2026-06",
                          "2026-07","2026-08","2026-09"])
        self.assertEqual(r["headline_flash_detailed_changes_visible"],{
            "2026-03":0.1,"2026-04":0.0,"2026-05":0.0,"2026-06":0.0,
            "2026-07":0.0,"2026-08":-0.1,"2026-09":0.0})
        self.assertEqual(r["component_rate_differences_nonzero_visible"],15)

    def test_march_flash_then_detailed_headline_revision_no_future_leak(self):
        before=replay("2026-03-31T23:59:59Z",self.fixture)
        flash=replay("2026-04-01T00:00:00Z",self.fixture)
        prefinal=replay("2026-04-16T23:59:59Z",self.fixture)
        final=replay("2026-04-17T00:00:00Z",self.fixture)
        self.assertIsNone(self.row(before,"2026-03")["original_flash_headline"])
        self.assertEqual(self.row(flash,"2026-03")["visible_metric_values"]["ALL_ITEMS_HICP"],2.5)
        self.assertEqual(self.row(prefinal,"2026-03")["visible_metric_values"]["ENERGY"],4.9)
        self.assertEqual(self.row(final,"2026-03")["visible_metric_values"]["ALL_ITEMS_HICP"],2.6)
        self.assertEqual(self.row(final,"2026-03")["visible_metric_values"]["ENERGY"],5.1)
        self.assertEqual(self.row(final,"2026-03")["component_flash_to_detailed_change_pp"]["ENERGY"],0.2)
        self.assertEqual(self.row(final,"2026-03")["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"],0.1)
        self.assertIsNone(self.row(final,"2026-04")["original_flash_headline"])

    def test_april_flash_then_detailed_component_revisions(self):
        flash=replay("2026-05-01T00:00:00Z",self.fixture)
        before=replay("2026-05-20T23:59:59Z",self.fixture)
        final=replay("2026-05-21T00:00:00Z",self.fixture)
        self.assertEqual(self.row(flash,"2026-04")["original_flash_headline"],3.0)
        self.assertEqual(self.row(before,"2026-04")["visible_metric_values"]["ENERGY"],10.9)
        self.assertIsNone(self.row(before,"2026-04")["detailed_headline"])
        self.assertEqual(self.row(final,"2026-04")["visible_metric_values"]["ENERGY"],10.8)
        self.assertEqual(self.row(final,"2026-04")["visible_metric_values"]["FOOD_ALCOHOL_TOBACCO"],2.4)
        self.assertEqual(self.row(final,"2026-04")["component_flash_to_detailed_change_pp"]["ENERGY"],-0.1)
        self.assertEqual(self.row(final,"2026-04")["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"],0.0)

    def test_march_services_four_publication_statements_not_four_first_releases(self):
        a=replay("2026-04-17T00:00:00Z",self.fixture)
        b=replay("2026-05-20T23:59:59Z",self.fixture)
        c=replay("2026-05-21T00:00:00Z",self.fixture)
        d=replay("2026-06-18T00:00:00Z",self.fixture)
        e=replay("2026-07-01T23:59:59Z",self.fixture)
        f=replay("2026-07-02T00:00:00Z",self.fixture)
        self.assertEqual([x["reported_value"] for x in self.history(a)],[3.2])
        self.assertEqual([x["reported_value"] for x in self.history(b)],[3.2])
        self.assertEqual([x["reported_value"] for x in self.history(c)],[3.2,3.3])
        self.assertEqual([x["reported_value"] for x in self.history(d)],[3.2,3.3,3.3])
        self.assertEqual([x["reported_value"] for x in self.history(e)],[3.2,3.3,3.3])
        self.assertEqual([x["reported_value"] for x in self.history(f)],[3.2,3.3,3.3,3.2])
        self.assertTrue(self.history(f)[-1]["report_has_revised_marker"])
        self.assertEqual(self.row(f,"2026-03")["visible_metric_values"]["SERVICES"],3.2)
        # The selected source is still the original March detailed publication,
        # not a retroactively overwritten March first-vintage time series.
        self.assertFalse(f["march_services_cross_report_history"]["full_march_vintage_chain_certified"])
        self.assertFalse(f["march_services_cross_report_history"]["historical_month_counts_as_extra_first_release"])

    def test_invalid_source_or_false_timestamps_fail_closed(self):
        cases=(
            (0,0,"flash_percent_yoy",2.6),
            (0,2,"detailed_percent_yoy",4.9),
            (1,2,"detailed_percent_yoy",10.9),
        )
        for mi,ci,field,value in cases:
            x=copy.deepcopy(self.fixture)
            x["months"][mi]["rate_components"][ci][field]=value
            with self.subTest(mi=mi,ci=ci):
                with self.assertRaises(ValueError):
                    validate(x)
        x=copy.deepcopy(self.fixture)
        x["months"][1]["flash"]["confirmed_intraday_clock"]="2026-04-30T09:00:00Z"
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.fixture)
        x["months"][1]["flash"]["conservative_visible_from_utc"]="2026-04-30T09:00:00Z"
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.fixture)
        x["march_services_cross_report_history"][3]["reported_services_percent_yoy"]=3.3
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.fixture)
        x["march_services_cross_report_history"][2]["conservative_visible_from_utc"]="2026-06-17T12:00:00Z"
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.fixture)
        x["backtest_eligible"]=True
        with self.assertRaises(ValueError):
            validate(x)

    def test_prior_five_month_data_preserved_no_scores(self):
        final=replay("2026-10-24T00:00:00Z",self.fixture)
        self.assertEqual(self.row(final,"2026-05")["original_flash_headline"],3.2)
        self.assertEqual(self.row(final,"2026-06")["original_flash_headline"],2.8)
        self.assertEqual(self.row(final,"2026-07")["original_flash_headline"],2.9)
        self.assertEqual(self.row(final,"2026-08")["original_flash_headline"],3.3)
        self.assertEqual(self.row(final,"2026-08")["detailed_headline"],3.2)
        self.assertEqual(self.row(final,"2026-09")["detailed_headline"],3.8)
        for k in ("original_release_day_bytes_archived",
                  "true_intraday_eurostat_release_times_certified",
                  "full_pit_revisions_certified",
                  "eligible_for_macro_scoring","eligible_for_backtest",
                  "safe_to_publish_new_D","safe_to_update_pair_theses",
                  "writes_live_data"):
            self.assertFalse(final[k])
        original=copy.deepcopy(self.fixture)
        self.assertEqual(replay("2026-10-24T00:00:00Z",original),
                         replay("2026-10-24T00:00:00Z",original))
        self.assertEqual(original,self.fixture)

if __name__=="__main__":
    unittest.main()
