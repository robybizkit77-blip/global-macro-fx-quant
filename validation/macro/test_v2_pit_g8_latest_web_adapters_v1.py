import copy
import json
import unittest
from datetime import date

from validation.macro.v2_pit_g8_latest_web_adapters_v1 import (
    CORE_FILE, GROWTH_FILE, latest_core, latest_growth, observed_gate,
)
from validation.macro.v2_pit_g8_control_plane_v1 import build, normalize
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_pit_coverage_readiness_v1 import run as readiness_run


class G8LatestPublisherAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=readiness_run(as_of=date(2026,10,24))
        cls.streams=collect()
        cls.core=latest_core()
        cls.growth=latest_growth()

    def receipt(self,ts):
        return build(self.base,self.streams,as_of=ts)

    def row(self,r,ccy,pillar):
        return next(x for x in r["rows"] if
                    (x["currency"],x["pillar"])==(ccy,pillar))

    def test_eight_core_latest_releases_seven_new_streams_and_duplicate_gbp_reconciled(self):
        self.assertEqual(len(self.core),7)
        self.assertEqual(len(self.growth),2)
        self.assertEqual(len(self.streams),24)
        self.assertEqual(len({(x["currency"],x["pillar"]) for x in self.streams}),24)
        expected={("USD","inflation"),("CAD","inflation"),("AUD","labour"),
                  ("CAD","labour"),("JPY","labour"),("GBP","inflation"),
                  ("NZD","inflation")}
        self.assertEqual({(x["currency"],x["pillar"]) for x in self.core},expected)
        self.assertEqual({(x["currency"],x["pillar"]) for x in self.growth},
                         {("AUD","growth"),("NZD","growth")})
        self.assertFalse(any(s["currency"]=="GBP" and s["pillar"]=="labour"
                             for s in self.core))
        self.assertEqual(sum(s["currency"]=="GBP" and s["pillar"]=="labour"
                             for s in self.streams),1)
        for s in self.streams:
            self.assertFalse(s["canonical_series_mapping_independently_certified"])
            self.assertFalse(s["complete_revision_history_verified"])
            self.assertFalse(s["original_release_day_immutable_bytes_verified"])
            audited=normalize(s)
            self.assertGreaterEqual(audited["first_reference_months_total"],1)

    def test_quarterly_cpi_and_two_gdp_anchors_have_real_reference_quarters(self):
        r=self.receipt("2026-10-24T00:00:00Z")
        for cc,pillar,period,value in (
            ("NZD","inflation","2026Q3",3.7),
            ("AUD","growth","2026Q2",0.4),
            ("NZD","growth","2026Q2",2.6),
        ):
            with self.subTest(cc=cc,pillar=pillar):
                a=self.row(r,cc,pillar)
                self.assertEqual(a["candidate_frequency"],"Q")
                self.assertEqual(a["latest_candidate_period_visible"],period)
                self.assertEqual(a["latest_candidate_value_at_cutoff"],value)
                self.assertEqual(a["candidate_documented_first_periods_visible"],1)
                self.assertFalse(a["canonical_first_release_chain_certified"])
        nzgrowth=self.row(r,"NZD","growth")
        augrowth=self.row(r,"AUD","growth")
        self.assertIn("YOY",nzgrowth["candidate_period_semantics"])
        self.assertIn("QOQ",augrowth["candidate_period_semantics"])
        self.assertIsNone(nzgrowth["minimum_training_first_releases_per_canonical_frequency"])
        self.assertIsNone(augrowth["minimum_training_first_releases_per_canonical_frequency"])

    def test_2026Q3_nzd_cpi_not_visible_on_its_publisher_date(self):
        before=self.receipt("2026-10-22T23:59:59Z")
        after=self.receipt("2026-10-23T00:00:00Z")
        n1=self.row(before,"NZD","inflation")
        n2=self.row(after,"NZD","inflation")
        self.assertEqual(n1["candidate_documented_first_periods_visible"],0)
        self.assertIsNone(n1["latest_candidate_period_visible"])
        self.assertEqual(n2["latest_candidate_period_visible"],"2026Q3")
        self.assertEqual(n2["latest_candidate_value_at_cutoff"],3.7)
        self.assertEqual(n2["canonical_frequency"],"Q")
        self.assertEqual(n2["minimum_training_first_releases_per_canonical_frequency"],13)
        self.assertFalse(n2["eligible_for_backtest"])

    def test_exact_australian_releases_respect_timezone_not_next_day(self):
        before=self.receipt("2026-10-15T00:29:59Z")
        after=self.receipt("2026-10-15T00:30:00Z")
        self.assertEqual(self.row(before,"AUD","labour")["candidate_documented_first_periods_visible"],0)
        self.assertEqual(self.row(after,"AUD","labour")["candidate_documented_first_periods_visible"],1)
        self.assertEqual(self.row(after,"AUD","labour")["latest_candidate_value_at_cutoff"],4.7)
        before_gdp=self.receipt("2026-09-02T01:29:59Z")
        after_gdp=self.receipt("2026-09-02T01:30:00Z")
        self.assertEqual(self.row(before_gdp,"AUD","growth")["candidate_documented_first_periods_visible"],0)
        self.assertEqual(self.row(after_gdp,"AUD","growth")["latest_candidate_value_at_cutoff"],0.4)

    def test_us_cpi_index_not_conflated_with_rate_or_rounding(self):
        r=self.receipt("2026-10-24T00:00:00Z")
        usd=self.row(r,"USD","inflation")
        cad=self.row(r,"CAD","inflation")
        self.assertEqual(usd["canonical_series_id"],"CPIAUCSL")
        self.assertEqual(usd["candidate_metric_unit"],"SA CPI-U index, September 2026")
        self.assertEqual(usd["latest_candidate_value_at_cutoff"],336.298)
        self.assertEqual(cad["latest_candidate_value_at_cutoff"],3.092783505154628)
        self.assertIn("computed",cad["candidate_metric_unit"])
        self.assertNotEqual(usd["latest_candidate_value_at_cutoff"],3.7172508442689933)
        self.assertEqual(usd["candidate_documented_first_periods_visible"],1)
        self.assertFalse(usd["canonical_first_release_chain_certified"])

    def test_japan_lfs_mutable_index_is_limited_one_anchored_month(self):
        a=self.row(self.receipt("2026-10-24T00:00:00Z"),"JPY","labour")
        self.assertEqual(a["latest_candidate_period_visible"],"2026-08")
        self.assertEqual(a["candidate_documented_first_periods_visible"],1)
        self.assertEqual(a["latest_candidate_value_at_cutoff"],2.5)
        self.assertFalse(a["eligible_for_backtest"])

    def test_growth_new_zealand_date_only_no_unverified_1045_local_to_utc(self):
        pre=self.receipt("2026-09-17T23:59:59Z")
        post=self.receipt("2026-09-18T00:00:00Z")
        self.assertEqual(self.row(pre,"NZD","growth")["candidate_documented_first_periods_visible"],0)
        self.assertEqual(self.row(post,"NZD","growth")["candidate_documented_first_periods_visible"],1)
        self.assertEqual(self.row(post,"NZD","growth")["latest_candidate_value_at_cutoff"],2.6)
        self.assertEqual(observed_gate("2026-09-17",None),
                         "2026-09-18T00:00:00+00:00")

    def test_no_live_model_promotion_for_exact_matching_id(self):
        r=self.receipt("2026-10-24T00:00:00Z")
        for cc,pillar in (("USD","inflation"),("CAD","labour"),("AUD","labour"),
                          ("NZD","inflation"),("GBP","inflation")):
            a=self.row(r,cc,pillar)
            self.assertTrue(a["canonical_series_id_matches_candidate"])
            self.assertTrue(a["canonical_frequency_matches_candidate"])
            self.assertFalse(a["canonical_first_release_chain_certified"])
            self.assertFalse(a["eligible_for_macro_score"])
            self.assertFalse(a["safe_to_publish_new_D"])
        for k in ("scores_computed","ready_for_backtest","safe_to_publish_new_D",
                  "safe_to_update_pair_theses","writes_live_data"):
            self.assertFalse(r[k])
        self.assertEqual(r["summary"]["slots_eligible_for_new_live_scores"],0)

    def test_yoy_index_tampering_and_missing_growth_evidence_fail_closed(self):
        from validation.macro.v2_pit_g8_latest_web_adapters_v1 import (
            CORE_REFERENCE, CORE_PINS, GROWTH_PINS,
        )
        self.assertEqual(CORE_PINS["NZD.inflation"][4],"Q")
        self.assertEqual(GROWTH_PINS["AUD"][5],0.4)
        self.assertEqual(GROWTH_PINS["NZD"][5],2.6)
        self.assertEqual(CORE_REFERENCE["USD.inflation"][-2:],(324.245,336.298))
        self.assertEqual(CORE_REFERENCE["CAD.inflation"][-2:],(164.9,170.0))
        bad=copy.deepcopy(next(s for s in self.streams if (s["currency"],s["pillar"])==("NZD","growth")))
        bad["events"][0]["observation_period"]="2026-09"
        with self.assertRaises(ValueError):
            normalize(bad)
        bad=copy.deepcopy(next(s for s in self.streams if (s["currency"],s["pillar"])==("NZD","growth")))
        bad["events"][0]["visible_from_utc"]="2026-09-17T10:45:00"
        with self.assertRaises(ValueError):
            normalize(bad)
        bad=copy.deepcopy(next(s for s in self.streams if (s["currency"],s["pillar"])==("NZD","growth")))
        bad["events"][0]["source_url"]="https://not-official.example/release"
        with self.assertRaises(ValueError):
            normalize(bad)

    def test_new_adapters_do_not_mutate_existing_readiness_or_source_inputs(self):
        base=copy.deepcopy(self.base)
        sources=copy.deepcopy(self.streams)
        first=build(base,sources,as_of="2026-10-24T00:00:00Z")
        self.assertEqual(first,build(base,sources,as_of="2026-10-24T00:00:00Z"))
        self.assertEqual(base,self.base)
        self.assertEqual(sources,self.streams)


if __name__=="__main__":
    unittest.main()
