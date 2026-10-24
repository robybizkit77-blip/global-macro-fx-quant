import copy
import math
import unittest

from validation.macro.v2_us_fed_g17_seven_release_growth_replay_v1 import (
    read_fixture, replay, validate, build_events, TABLE_ROWS,
)


class FedG17SevenRealPublicationReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=read_fixture()
        cls.timeline=validate(cls.source)

    def test_seven_source_publication_dates_unique_preliminary_first_months(self):
        self.assertEqual(len(self.timeline),7)
        self.assertEqual([t[1] for t in self.timeline],
                         ["2026-03","2026-04","2026-05","2026-06",
                          "2026-07","2026-08","2026-09"])
        events=build_events(self.timeline)
        self.assertEqual(len(events),20)
        self.assertEqual(sum(e["kind"]=="FIRST_WEB" for e in events),7)
        self.assertEqual(sum(e["kind"]=="REVISION_WEB" for e in events),13)
        self.assertTrue(all("federalreserve.gov" in e["official_publisher_url"]
                            for e in events))

    def test_september_first_feature_not_available_one_second_early(self):
        before=replay("2026-09-18T13:14:59Z",self.source)
        after=replay("2026-09-18T13:15:00Z",self.source)
        self.assertEqual(before["distinct_first_economic_months_visible"],5)
        self.assertIsNone(before["growth_3m3m_asof_revised_publisher_rounded_pct"])
        self.assertEqual(after["distinct_first_economic_months_visible"],6)
        self.assertEqual(after["latest_first_published_reference_month"],"2026-08")
        self.assertEqual(after["value_changing_revisions_visible"],9)
        self.assertAlmostEqual(after["growth_3m3m_asof_revised_publisher_rounded_pct"],
                               0.6516780710329018,places=9)
        self.assertAlmostEqual(after["growth_3m3m_only_first_rounded_publication_pct"],
                               0.5865102639296182,places=9)
        self.assertEqual(after["growth_3m3m_status"],
                         "SIX_MONTH_DESCRIPTIVE_RESEARCH_MATH_ONLY")
        self.assertNotEqual(after["growth_3m3m_only_first_rounded_publication_pct"],
                            after["growth_3m3m_asof_revised_publisher_rounded_pct"])

    def test_october_new_september_preliminary_and_contemporaneous_prior_revisions(self):
        before=replay("2026-10-16T13:14:59Z",self.source)
        after=replay("2026-10-16T13:15:00Z",self.source)
        self.assertEqual(before["distinct_first_economic_months_visible"],6)
        self.assertEqual(after["distinct_first_economic_months_visible"],7)
        self.assertEqual(before["value_changing_revisions_visible"],9)
        self.assertEqual(after["value_changing_revisions_visible"],13)
        self.assertEqual(after["latest_first_published_reference_month"],"2026-09")
        self.assertEqual(after["asof_last_reported_rounded_levels_by_month"]["2026-09"],104.0)
        self.assertEqual(after["asof_last_reported_rounded_levels_by_month"]["2026-08"],103.3)
        self.assertEqual(after["asof_last_reported_rounded_levels_by_month"]["2026-07"],103.2)
        self.assertEqual(after["asof_last_reported_rounded_levels_by_month"]["2026-06"],103.0)
        self.assertAlmostEqual(after["growth_3m3m_asof_revised_publisher_rounded_pct"],
                               0.7135906584495588,places=9)
        self.assertAlmostEqual(after["growth_3m3m_only_first_rounded_publication_pct"],
                               0.7799805004875093,places=9)
        self.assertNotEqual(before["growth_3m3m_asof_revised_publisher_rounded_pct"],
                            after["growth_3m3m_asof_revised_publisher_rounded_pct"])

    def test_explicit_change_observations_for_same_month_not_recounted_as_first_month(self):
        ev=build_events(self.timeline)
        march=[x for x in ev if x["reference_period"]=="2026-03"]
        self.assertEqual([x["kind"] for x in march],
                         ["FIRST_WEB","REVISION_WEB","REVISION_WEB","REVISION_WEB"])
        self.assertEqual([x["value"] for x in march],[101.8,101.6,101.8,101.7])
        jul=[x for x in ev if x["reference_period"]=="2026-07"]
        self.assertEqual([x["value"] for x in jul],[103.0,103.2])
        self.assertEqual([x["kind"] for x in jul],["FIRST_WEB","REVISION_WEB"])
        for x in ev:
            self.assertTrue(x["official_publisher_url"].startswith("https://www.federalreserve.gov/"))

    def test_dated_release_inventories_0_to_7_first_months_no_interpolation(self):
        dates=["2026-04-16","2026-05-15","2026-06-15",
               "2026-07-17","2026-08-18","2026-09-18","2026-10-16"]
        for idx,day in enumerate(dates):
            pre=replay(day+"T13:14:59Z",self.source)
            post=replay(day+"T13:15:00Z",self.source)
            self.assertEqual(pre["distinct_first_economic_months_visible"],idx)
            self.assertEqual(post["distinct_first_economic_months_visible"],idx+1)
        first=replay("2026-04-16T13:14:59Z",self.source)
        self.assertEqual(first["distinct_first_economic_months_visible"],0)
        self.assertEqual(first["asof_last_reported_rounded_levels_by_month"],{})

    def test_source_metric_version_or_source_clock_tampering_fails_closed(self):
        cases=[
            (0,"publisher_url","https://not-fed.example.com/20260416"),
            (1,"release_clock_et","2026-05-15T10:15:00-04:00"),
            (2,"new_preliminary_period","2026-04"),
            (3,"release_date","2026-07-18"),
            (4,"release_utc","2026-08-18T12:15:00Z"),
            (5,"all_table_values_from_dated_publisher_page_not_first_releases",False),
            (6,"source_table","wrong row Capacity Utilization"),
        ]
        for index,key,value in cases:
            data=copy.deepcopy(self.source)
            data["snapshots"][index][key]=value
            with self.subTest(index=index,key=key):
                with self.assertRaises((ValueError,TypeError)):
                    validate(data)
        corrupt=copy.deepcopy(self.source)
        corrupt["snapshots"][5]["total_index_sa_2017_100_by_observation_period"]["2026-08"]=103.0682
        with self.assertRaises(ValueError):
            validate(corrupt)
        corrupt=copy.deepcopy(self.source)
        corrupt["snapshots"][6]["total_index_sa_2017_100_by_observation_period"]["2026-08"]=103.1
        with self.assertRaises(ValueError):
            validate(corrupt)
        corrupt=copy.deepcopy(self.source)
        corrupt["archived_release_day_original_page_bytes_verified"]=True
        with self.assertRaises(ValueError):
            validate(corrupt)
        corrupt=copy.deepcopy(self.source)
        corrupt["canonical_G8_growth_series_selected"]=True
        with self.assertRaises(ValueError):
            validate(corrupt)

    def test_replay_never_creates_normalized_growth_scores_or_updates_site(self):
        r=replay("2026-10-24T00:00:00Z",self.source)
        self.assertEqual(r["source_first_releases_short_of_25"],18)
        self.assertFalse(r["source_has_complete_25month_first_release_history"])
        self.assertFalse(r["publisher_original_release_day_bytes_hash_verified"])
        self.assertFalse(r["canonical_growth_series_mapping_certified"])
        self.assertFalse(r["model_growth_score_permitted"])
        self.assertFalse(r["fx_pair_ranking_permitted"])
        self.assertFalse(r["safe_to_publish_new_D"])
        self.assertFalse(r["writes_live_data"])
        self.assertTrue(r["source_rounded_one_decimal_not_unrounded_INDPRO"])
        self.assertTrue(r["no_historical_normalized_zscore"])
        self.assertTrue(r["source_current_dated_pages_not_original_day_hashed_archive"])

    def test_source_fixture_is_pure_and_repeatable(self):
        original=copy.deepcopy(self.source)
        a=replay("2026-09-18T13:15:00Z",original)
        b=replay("2026-09-18T13:15:00Z",original)
        self.assertEqual(a,b)
        self.assertEqual(original,self.source)
        self.assertEqual(len(TABLE_ROWS),7)


if __name__=="__main__":
    unittest.main()
