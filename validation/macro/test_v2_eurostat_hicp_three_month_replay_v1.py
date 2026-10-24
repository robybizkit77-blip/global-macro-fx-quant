import copy
import json
import unittest

from validation.macro.v2_eurostat_hicp_three_month_replay_v1 import (
    SOURCE, SEPTEMBER_COMPONENTS, ROOT, replay, validate,
)


class EurostatHICPThreeMonthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.sep=json.loads(SEPTEMBER_COMPONENTS.read_text(encoding="utf-8"))
        cls.original=json.loads((ROOT/"validation/macro/MACRO_V2_EUR_HICP_SEP_2026_RELEASE_SEQUENCE_2026-10-24.json").read_text(encoding="utf-8"))

    def row(self,receipt,period):
        return next(x for x in receipt["snapshot_by_reference_period"]
                    if x["reference_period"]==period)

    def test_source_counts_and_final_summary(self):
        r=replay("2026-10-24T00:00:00Z",self.data,self.sep,self.original)
        self.assertEqual(r["research_scope"],{
            "reference_months":3,"source_publications":6,
            "annual_rate_components":6,"published_metric_value_records_total":36})
        self.assertEqual(r["source_publications_visible"],6)
        self.assertEqual(r["months_with_at_least_one_publication"],3)
        self.assertEqual(r["missing_independent_monthly_first_release_periods"],22)
        self.assertEqual(r["headline_flash_to_detailed_revisions_visible"],
                         {"2026-07":0.0,"2026-08":-0.1,"2026-09":0.0})
        self.assertEqual(r["latest_known_headline_at_cutoff"],3.8)

    def test_no_data_before_july_flash(self):
        r=replay("2026-07-31T23:59:59Z",self.data,self.sep,self.original)
        self.assertEqual(r["source_publications_visible"],0)
        self.assertIsNone(r["latest_known_reference_period"])
        self.assertIsNone(self.row(r,"2026-07")["visible_metric_values"]["ALL_ITEMS_HICP"])

    def test_july_flash_then_final_energy_revision(self):
        flash=replay("2026-08-01T00:00:00Z",self.data,self.sep,self.original)
        before=replay("2026-08-19T23:59:59Z",self.data,self.sep,self.original)
        final=replay("2026-08-20T00:00:00Z",self.data,self.sep,self.original)
        self.assertEqual(self.row(flash,"2026-07")["visible_metric_values"]["ENERGY"],10.0)
        self.assertEqual(self.row(before,"2026-07")["visible_metric_values"]["ENERGY"],10.0)
        self.assertEqual(self.row(final,"2026-07")["visible_metric_values"]["ENERGY"],10.3)
        self.assertEqual(self.row(final,"2026-07")["component_flash_to_detailed_change_pp"]["ENERGY"],0.3)
        self.assertEqual(self.row(final,"2026-07")["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"],0.0)

    def test_august_flash_headline_33_and_final_32(self):
        before=replay("2026-09-01T23:59:59Z",self.data,self.sep,self.original)
        flash=replay("2026-09-02T00:00:00Z",self.data,self.sep,self.original)
        prefinal=replay("2026-09-17T23:59:59Z",self.data,self.sep,self.original)
        final=replay("2026-09-18T00:00:00Z",self.data,self.sep,self.original)
        self.assertIsNone(self.row(before,"2026-08")["original_flash_headline"])
        self.assertEqual(self.row(flash,"2026-08")["visible_metric_values"]["ALL_ITEMS_HICP"],3.3)
        self.assertEqual(self.row(prefinal,"2026-08")["visible_metric_values"]["ALL_ITEMS_HICP"],3.3)
        self.assertIsNone(self.row(prefinal,"2026-08")["detailed_headline"])
        self.assertEqual(self.row(final,"2026-08")["detailed_headline"],3.2)
        self.assertEqual(self.row(final,"2026-08")["component_flash_to_detailed_change_pp"]["ALL_ITEMS_HICP"],-0.1)
        self.assertEqual(self.row(final,"2026-08")["component_flash_to_detailed_change_pp"]["FOOD_ALCOHOL_TOBACCO"],-0.1)
        self.assertEqual(final["latest_known_headline_at_cutoff"],3.2)

    def test_september_flash_depends_on_revised_august_not_future_september_final(self):
        flash=replay("2026-10-03T00:00:00Z",self.data,self.sep,self.original)
        sep=self.row(flash,"2026-09")
        self.assertEqual(flash["latest_known_headline_at_cutoff"],3.8)
        self.assertEqual(self.row(flash,"2026-08")["visible_metric_values"]["ALL_ITEMS_HICP"],3.2)
        self.assertEqual(sep["visible_metric_values"]["ENERGY"],18.8)
        self.assertEqual(sep["visible_metric_values"]["FOOD_ALCOHOL_TOBACCO"],1.4)
        self.assertIsNone(sep["component_flash_to_detailed_change_pp"])
        final=replay("2026-10-17T00:00:00Z",self.data,self.sep,self.original)
        self.assertEqual(self.row(final,"2026-09")["visible_metric_values"]["ENERGY"],18.9)
        self.assertEqual(self.row(final,"2026-09")["component_flash_to_detailed_change_pp"]["FOOD_ALCOHOL_TOBACCO"],-0.1)

    def test_reference_periods_not_confused_with_publication_events(self):
        for asof in ("2026-08-01T00:00:00Z","2026-09-02T00:00:00Z",
                     "2026-10-03T00:00:00Z","2026-10-24T00:00:00Z"):
            r=replay(asof,self.data,self.sep,self.original)
            self.assertLessEqual(r["months_with_at_least_one_publication"],3)
            self.assertGreaterEqual(r["missing_independent_monthly_first_release_periods"],22)
            for k in ("original_release_day_immutable_bytes_certified",
                      "complete_historical_first_and_revised_vintage_chain_certified",
                      "actual_intraday_eurostat_release_timing_certified",
                      "eligible_for_macro_scoring","eligible_for_backtest",
                      "safe_to_publish_new_D","safe_to_update_pair_theses",
                      "writes_live_data"):
                self.assertIs(r[k],False)

    def test_fail_closed_on_metric_tampering_and_date_only_backdating(self):
        cases=[
            (0,"components",0,"flash_rate_yoy_percent",3.0),
            (1,"components",0,"detailed_rate_yoy_percent",3.3),
            (2,"components",2,"detailed_rate_yoy_percent",18.8),
            (0,"components",1,"component_id","ENERGY"),
        ]
        for period,group,index,key,value in cases:
            with self.subTest(period=period,key=key):
                data=copy.deepcopy(self.data)
                data["months"][period][group][index][key]=value
                with self.assertRaises(ValueError):
                    validate(data,self.sep,self.original)
        for period,stage,key,value in (
            (1,"flash","conservative_visible_from_utc","2026-09-01T08:00:00Z"),
            (0,"detailed","published_on","2026-08-18"),
            (2,"detailed","original_clock_verified","2026-10-16T11:00:00+02:00"),
            (0,"flash","url","https://example.com/2-31072026-ap"),
        ):
            data=copy.deepcopy(self.data)
            data["months"][period][stage][key]=value
            with self.assertRaises(ValueError):
                validate(data,self.sep,self.original)
        data=copy.deepcopy(self.data)
        data["model_promotion_allowed"]=True
        with self.assertRaises(ValueError):
            validate(data,self.sep,self.original)

    def test_old_september_pinned_comparison_must_remain_intact(self):
        changed=copy.deepcopy(self.sep)
        changed["components"][0]["flash_percent_yoy"]=4.0
        with self.assertRaises(ValueError):
            validate(self.data,changed,self.original)

    def test_inputs_immutable_and_repeatable(self):
        d=copy.deepcopy(self.data)
        s=copy.deepcopy(self.sep)
        o=copy.deepcopy(self.original)
        one=replay("2026-10-24T00:00:00Z",d,s,o)
        two=replay("2026-10-24T00:00:00Z",d,s,o)
        self.assertEqual(one,two)
        self.assertEqual((d,s,o),(self.data,self.sep,self.original))


if __name__=="__main__":
    unittest.main()
