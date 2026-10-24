import copy
import json
import unittest
from datetime import date
from validation.macro.v2_pit_g8_control_plane_v1 import build, normalize
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_pit_coverage_readiness_v1 import run as readiness_run
from validation.macro.v2_pit_g8_growth_web_bridges_v1 import (
    FIXTURE, OBSERVED, collect_growth_bridges, PINS, REVISED_EUR,
)

class G8SixGrowthPublisherBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.observed=json.loads(OBSERVED.read_text(encoding="utf-8"))
        cls.base=readiness_run(as_of=date(2026,10,24))
        cls.growth=collect_growth_bridges()
        cls.full=collect()

    def replay(self,when="2026-10-24T00:00:00Z"):
        return build(self.base,self.full,as_of=when)

    @staticmethod
    def slot(r,c,p="growth"):
        return next(x for x in r["rows"] if x["currency"]==c and x["pillar"]==p)

    def test_six_distinct_sources_all_twenty_four_slots_and_no_scores(self):
        self.assertEqual([s["currency"] for s in self.growth],
                         ["USD","EUR","GBP","JPY","CHF","CAD"])
        self.assertEqual(len(self.growth),6)
        self.assertEqual(len(self.full),24)
        r=self.replay()
        self.assertEqual(r["summary"]["candidate_source_streams_loaded"],24)
        self.assertEqual(r["summary"]["slots_without_shared_candidate_stream"],0)
        self.assertEqual(r["summary"]["candidate_first_release_reference_periods_visible"],75)
        self.assertEqual(r["summary"]["candidate_web_publication_stage_events_visible"],87)
        self.assertEqual(r["summary"]["growth_source_selection_unresolved"],8)
        self.assertEqual(r["summary"]["slots_with_full_canonical_first_release_pit_training_certified"],0)
        self.assertEqual(r["summary"]["slots_eligible_for_new_live_scores"],0)
        for cc in ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"):
            x=self.slot(r,cc)
            self.assertIsNone(x["canonical_series_id"])
            self.assertIsNone(x["minimum_training_first_releases_per_canonical_frequency"])
            self.assertEqual(x["candidate_documented_first_periods_visible"],1)
            self.assertFalse(x["canonical_first_release_chain_certified"])
            self.assertFalse(x["eligible_for_macro_score"])

    def test_us_published_index_rounded_not_exact_runtime_index(self):
        before=self.slot(self.replay("2026-09-18T13:14:59Z"),"USD")
        after=self.slot(self.replay("2026-09-18T13:15:00Z"),"USD")
        self.assertEqual(before["candidate_documented_first_periods_visible"],0)
        self.assertEqual(after["latest_candidate_value_at_cutoff"],103.1)
        self.assertEqual(after["candidate_metric_unit"],
                         "index 2017=100, SA, published 0.1 index rounding")
        self.assertNotEqual(after["latest_candidate_value_at_cutoff"],
                            PINS["USD"]["runtime_val"])
        self.assertEqual(PINS["USD"]["runtime_val"],103.0682)

    def test_eur_first_mom_change_then_later_retrospective_revision(self):
        earlier=self.slot(self.replay("2026-09-16T23:59:59Z"),"EUR")
        first=self.slot(self.replay("2026-09-17T00:00:00Z"),"EUR")
        before_rev=self.slot(self.replay("2026-10-15T23:59:59Z"),"EUR")
        after_rev=self.slot(self.replay("2026-10-16T00:00:00Z"),"EUR")
        self.assertEqual(earlier["candidate_documented_first_periods_visible"],0)
        self.assertEqual(first["latest_candidate_value_at_cutoff"],-0.1)
        self.assertEqual(before_rev["latest_candidate_value_at_cutoff"],-0.1)
        self.assertEqual(after_rev["latest_candidate_value_at_cutoff"],-0.3)
        self.assertEqual(after_rev["candidate_documented_first_periods_visible"],1)
        self.assertEqual(after_rev["candidate_revision_events_visible"],1)
        self.assertEqual(after_rev["candidate_revised_reference_periods_visible"],1)
        self.assertEqual(after_rev["latest_candidate_visible_stage"],"REVISION_WEB")
        self.assertIn("month-on-month",after_rev["candidate_metric_unit"])
        self.assertEqual(PINS["EUR"]["runtime_val"],98.3)
        self.assertNotEqual(after_rev["latest_candidate_value_at_cutoff"],98.3)

    def test_uk_rolling_three_month_growth_is_not_monthly_index(self):
        before=self.slot(self.replay("2026-09-11T05:59:59Z"),"GBP")
        after=self.slot(self.replay("2026-09-11T06:00:00Z"),"GBP")
        self.assertIsNone(before["latest_candidate_value_at_cutoff"])
        self.assertEqual(after["latest_candidate_value_at_cutoff"],-0.5)
        self.assertIn("ROLLING_THREE_MONTH",after["candidate_period_semantics"])
        self.assertEqual(PINS["GBP"]["runtime_val"],98.5)
        self.assertNotEqual(after["latest_candidate_value_at_cutoff"],98.5)

    def test_japan_meti_may_preliminary_not_july_final_data(self):
        before=self.slot(self.replay("2026-06-30T23:59:59Z"),"JPY")
        after=self.slot(self.replay("2026-07-01T00:00:00Z"),"JPY")
        self.assertIsNone(before["latest_candidate_value_at_cutoff"])
        self.assertEqual(after["latest_candidate_period_visible"],"2026-05")
        self.assertEqual(after["latest_candidate_value_at_cutoff"],103.0)
        self.assertEqual(PINS["JPY"]["runtime_period"],"2026-07")
        self.assertEqual(PINS["JPY"]["runtime_val"],104.4)
        self.assertIn("NOT_PERIOD_SPECIFIC_IMMUTABLE",after["candidate_period_semantics"])

    def test_swiss_real_gdp_q2_vs_industrial_monthly_index(self):
        before=self.slot(self.replay("2026-09-03T23:59:59Z"),"CHF")
        after=self.slot(self.replay("2026-09-04T00:00:00Z"),"CHF")
        self.assertEqual(before["candidate_documented_first_periods_visible"],0)
        self.assertEqual(after["candidate_frequency"],"Q")
        self.assertEqual(after["latest_candidate_period_visible"],"2026Q2")
        self.assertEqual(after["latest_candidate_value_at_cutoff"],1.5)
        self.assertEqual(PINS["CHF"]["runtime_freq"],"M")
        self.assertEqual(PINS["CHF"]["runtime_val"],122.0)
        self.assertFalse(after["canonical_first_release_chain_certified"])

    def test_canadian_monthly_gdp_original_index_level_not_mom_percent(self):
        before=self.slot(self.replay("2026-08-28T23:59:59Z"),"CAD")
        after=self.slot(self.replay("2026-08-29T00:00:00Z"),"CAD")
        self.assertEqual(before["candidate_documented_first_periods_visible"],0)
        self.assertEqual(after["latest_candidate_period_visible"],"2026-06")
        self.assertEqual(after["latest_candidate_value_at_cutoff"],2369309)
        self.assertIn("SAAR",after["candidate_metric_unit"])
        self.assertNotEqual(after["latest_candidate_value_at_cutoff"],0.3)
        self.assertEqual(after["candidate_documented_first_periods_visible"],1)
        self.assertFalse(after["canonical_first_release_chain_certified"])

    def test_source_manifest_independent_negatives_fail_closed(self):
        for cc,field,value in (
            ("EUR","reported_value",-0.3),
            ("EUR","source_url","https://example.com/official"),
            ("EUR","published_on","2026-09-15"),
            ("USD","conservative_visible_from_utc","2026-09-17T10:00:00Z"),
            ("GBP","source_clock","2026-09-11T07:00:00Z"),
            ("CHF","observation_period","2026-06"),
            ("CAD","reported_value",0.3),
            ("JPY","reported_value",104.4),
        ):
            d=copy.deepcopy(self.manifest)
            target=next(x for x in d["streams"] if x["currency"]==cc)
            target["events"][0][field]=value
            with self.subTest(cc=cc,field=field):
                with self.assertRaises((ValueError,TypeError)):
                    collect_growth_bridges(evidence=d,current=self.observed)
        revision=copy.deepcopy(self.manifest)
        next(x for x in revision["streams"] if x["currency"]=="EUR")["events"][1]["reported_value"]=-0.1
        with self.assertRaises(ValueError):
            collect_growth_bridges(evidence=revision,current=self.observed)
        changed=copy.deepcopy(self.observed)
        next(x for x in changed["USD"] if x["id"]=="US_INDPRO_history_value")["last_value"]=103.1
        with self.assertRaises(ValueError):
            collect_growth_bridges(evidence=self.manifest,current=changed)
        changed=copy.deepcopy(self.manifest)
        changed["canonical_growth_series_selected"]=True
        with self.assertRaises(ValueError):
            collect_growth_bridges(evidence=changed,current=self.observed)

    def test_prior_sources_nonmutated_and_replay_not_promoted(self):
        raw=copy.deepcopy(self.manifest)
        obs=copy.deepcopy(self.observed)
        checked=collect_growth_bridges(evidence=raw,current=obs)
        self.assertEqual(raw,self.manifest)
        self.assertEqual(obs,self.observed)
        for row in checked:
            audited=normalize(row)
            self.assertEqual(audited["first_reference_months_total"],1)
            self.assertFalse(audited["canonical_series_mapping_independently_certified"])
        r=self.replay()
        for key in ("scores_computed","model_parameters_fitted","ready_for_backtest",
                    "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
            self.assertFalse(r[key])
        self.assertEqual(self.slot(r,"NZD")["latest_candidate_value_at_cutoff"],2.6)
        self.assertEqual(self.slot(r,"AUD")["latest_candidate_value_at_cutoff"],0.4)

if __name__=="__main__":
    unittest.main()
