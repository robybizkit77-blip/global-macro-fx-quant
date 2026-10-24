import copy
import unittest

from validation.macro.v2_us_fed_g17_shutdown_13_month_replay_v1 import (
    load, validate, build_events, replay, PINNED, PERIODS,
)
from validation.macro.v2_us_fed_g17_seven_release_growth_replay_v1 import (
    replay as older_seven_replay,
)


class FedG17ShutdownAndThirteenMonthPublisherVintageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load()
        cls.editions=validate(cls.data)
        cls.events=build_events(cls.editions)

    def test_12_real_publisher_editions_for_13_economic_months(self):
        self.assertEqual(len(self.editions),12)
        self.assertEqual(len(PINNED),12)
        self.assertEqual(len(PERIODS),13)
        self.assertEqual(PERIODS[0],"2025-09")
        self.assertEqual(PERIODS[-1],"2026-09")
        self.assertEqual(sum(len(e["rows"]) for e in self.editions),61)
        self.assertEqual(len(self.events),48)
        self.assertEqual(sum(e["kind"]=="FIRST_WEB" for e in self.events),13)
        self.assertEqual(sum(e["kind"]=="REVISION_WEB" for e in self.events),35)
        self.assertEqual(
            [e["reference_period"] for e in self.events if e["kind"]=="FIRST_WEB"],
            list(PERIODS))
        self.assertTrue(all(e["official_publisher_url"].startswith(
            "https://www.federalreserve.gov/releases/g17/") for e in self.events))

    def test_2025_shutdown_three_months_only_two_publication_editions(self):
        before_sep=replay("2025-12-03T14:14:59Z",self.data)
        sep=replay("2025-12-03T14:15:00Z",self.data)
        before_double=replay("2025-12-23T14:14:59Z",self.data)
        double=replay("2025-12-23T14:15:00Z",self.data)
        self.assertEqual(before_sep["first_periods_visible"],0)
        self.assertEqual(sep["first_periods_visible"],1)
        self.assertEqual(sep["asof_known_publisher_rounded_2017_index_levels"],
                         {"2025-09":101.4})
        self.assertEqual(before_double["first_periods_visible"],1)
        self.assertEqual(double["first_periods_visible"],3)
        self.assertEqual(double["revised_source_value_events_visible"],1)
        self.assertEqual(double["asof_known_publisher_rounded_2017_index_levels"],
                         {"2025-09":101.7,"2025-10":101.6,"2025-11":101.8})
        self.assertEqual(double["first_publications_with_shared_release_day"][0][
            "economic_reference_months"],["2025-10","2025-11"])
        self.assertEqual(double["first_publications_with_shared_release_day"][0][
            "publisher_time_utc"],"2025-12-23T14:15:00+00:00")
        # Original Nov 18/Dec 16 G17 release dates cannot be substituted.
        for forbidden in ("2025-11-18T14:15:00Z","2025-12-16T14:15:00Z"):
            old=replay(forbidden,self.data)
            self.assertLessEqual(old["first_periods_visible"],1)

    def test_est_vs_edt_transition_and_six_released_month_first_feature(self):
        feb_pre=replay("2026-02-18T14:14:59Z",self.data)
        feb_at=replay("2026-02-18T14:15:00Z",self.data)
        march_pre=replay("2026-03-16T13:14:59Z",self.data)
        march_at=replay("2026-03-16T13:15:00Z",self.data)
        self.assertEqual(feb_pre["first_periods_visible"],4)
        self.assertEqual(feb_at["first_periods_visible"],5)
        self.assertEqual(march_pre["first_periods_visible"],5)
        self.assertEqual(march_at["first_periods_visible"],6)
        self.assertIsNone(march_pre["asof_last_known_3m3m_rounded_pct"])
        self.assertAlmostEqual(march_at["asof_last_known_3m3m_rounded_pct"],
                               0.7886953664147267,places=10)
        self.assertAlmostEqual(march_at["asof_initial_first_release_3m3m_rounded_pct"],
                               0.7874015748031482,places=10)
        self.assertEqual(march_at["last_first_economic_month_visible"],"2026-02")
        self.assertEqual(len(march_at["frozen_asof_release_features"]),1)

    def test_all_twenty_twenty_six_first_release_cutoffs_include_single_month(self):
        dates=["2026-04-16","2026-05-15","2026-06-15","2026-07-17",
               "2026-08-18","2026-09-18","2026-10-16"]
        for i,day in enumerate(dates):
            before=replay(day+"T13:14:59Z",self.data)
            after=replay(day+"T13:15:00Z",self.data)
            self.assertEqual(before["first_periods_visible"],6+i)
            self.assertEqual(after["first_periods_visible"],7+i)
        full=replay("2026-10-24T00:00:00Z",self.data)
        self.assertEqual(full["first_periods_visible"],13)
        self.assertEqual(full["revised_source_value_events_visible"],35)
        self.assertEqual(full["first_periods_missing_to_research_minimum_25"],12)
        self.assertEqual(full["last_first_economic_month_visible"],"2026-09")
        self.assertEqual(len(full["frozen_asof_release_features"]),7)

    def test_september_and_october_results_match_prior_seven_month_source_pilot(self):
        for at in ("2026-09-18T13:15:00Z","2026-10-16T13:15:00Z",
                   "2026-10-24T00:00:00Z"):
            with self.subTest(asof=at):
                extended=replay(at,self.data)
                prior=older_seven_replay(at)
                self.assertAlmostEqual(
                    extended["asof_last_known_3m3m_rounded_pct"],
                    prior["growth_3m3m_asof_revised_publisher_rounded_pct"],places=12)
                self.assertAlmostEqual(
                    extended["asof_initial_first_release_3m3m_rounded_pct"],
                    prior["growth_3m3m_only_first_rounded_publication_pct"],places=12)
        september=replay("2026-09-18T13:15:00Z",self.data)
        october=replay("2026-10-16T13:15:00Z",self.data)
        self.assertAlmostEqual(september["asof_last_known_3m3m_rounded_pct"],
                               0.6516780710329018,places=10)
        self.assertAlmostEqual(october["asof_last_known_3m3m_rounded_pct"],
                               0.7135906584495588,places=10)

    def test_frozen_first_feature_not_recomputed_from_later_publication(self):
        march=replay("2026-03-16T13:15:00Z",self.data)
        later=replay("2026-10-16T13:15:00Z",self.data)
        frozen=march["frozen_asof_release_features"][0]
        self.assertEqual(frozen["latest_reference_period"],"2026-02")
        self.assertAlmostEqual(frozen[
            "feature_3m3m_from_rounding_and_asof_known_revisions_pct"],
            0.7886953664147267,places=10)
        self.assertEqual(frozen,later["frozen_asof_release_features"][0])
        self.assertEqual(later["frozen_asof_release_features"][-1][
            "latest_reference_period"],"2026-09")
        self.assertEqual(len(later["frozen_asof_release_features"]),7)
        self.assertTrue(all(f["frozen_at_own_publisher_cutoff_not_recomputed_later"]
                            for f in later["frozen_asof_release_features"]))

    def test_mismatched_release_date_price_precision_or_double_first_fails_closed(self):
        cases=[
            (1,"new_preliminary_economic_periods",["2025-11"]),
            (0,"release_utc","2025-12-03T13:15:00Z"),
            (1,"publisher_release_local","2025-12-23T09:15:00-04:00"),
            (4,"publisher_release_local","2026-03-16T09:15:00-05:00"),
            (7,"official_url","https://imitation.example.com/fed/g17.html"),
            (2,"date","2026-01-15"),
            (8,"historical_table_older_month_cells_are_revision_stage_not_first_release",False),
        ]
        for i,key,value in cases:
            x=copy.deepcopy(self.data)
            x["release_editions"][i][key]=value
            with self.subTest(i=i,key=key):
                with self.assertRaises((ValueError,TypeError)):
                    validate(x)
        x=copy.deepcopy(self.data)
        x["release_editions"][1]["total_index_sa_2017_100_rounded_table_subset"]["2025-10"]=101.5
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.data)
        x["release_editions"][10]["total_index_sa_2017_100_rounded_table_subset"]["2026-08"]=103.0682
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.data)
        x["historical_publish_day_source_bytes_archived_and_verified"]=True
        with self.assertRaises(ValueError):
            validate(x)
        x=copy.deepcopy(self.data)
        x["canonical_unrounded_US_INDPRO_history_value_matched"]=True
        with self.assertRaises(ValueError):
            validate(x)

    def test_missing_old_source_releases_not_backfilled_as_2025_first_estimates(self):
        result=replay("2026-10-24T00:00:00Z",self.data)
        self.assertTrue(result[
            "unobserved_pre_2025_september_source_first_release_values_not_backfilled"])
        self.assertEqual(result["source_editions_in_verified_dossier"],12)
        self.assertEqual(result["first_periods_in_full_dossier"],13)
        self.assertNotIn("2025-08",result["asof_known_publisher_rounded_2017_index_levels"])
        self.assertFalse(result["full_25month_original_release_PIT_chain_ready"])
        self.assertFalse(result["valid_25_previous_feature_vintages_for_rolling_z"])

    def test_no_original_archive_claim_no_score_no_live_change_and_pure_replay(self):
        data=copy.deepcopy(self.data)
        a=replay("2026-10-24T00:00:00Z",data)
        b=replay("2026-10-24T00:00:00Z",data)
        self.assertEqual(a,b)
        self.assertEqual(data,self.data)
        for k in (
            "official_webpages_checked_later_not_original_day_archive_bytes",
            "source_one_decimal_is_not_current_four_decimal_INDPRO",
            "no_automatic_updating_old_frozen_features_after_later_releases"
        ):
            self.assertTrue(a[k])
        for k in (
            "full_25month_original_release_PIT_chain_ready",
            "valid_25_previous_feature_vintages_for_rolling_z",
            "canonical_G8_growth_series_source_mapping_certified",
            "model_score_permitted","fx_pair_rank_change_permitted",
            "backtest_permitted","safe_to_publish_new_D","writes_live_data",
        ):
            self.assertFalse(a[k])


if __name__=="__main__":
    unittest.main()
