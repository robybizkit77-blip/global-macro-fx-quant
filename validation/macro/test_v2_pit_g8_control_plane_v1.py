import copy
import unittest

from validation.macro.v2_pit_g8_control_plane_v1 import (
    CURRENCIES, PILLAR_ORDER, build, normalize, run,
)
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_pit_coverage_readiness_v1 import run as readiness_run
from datetime import date


class G8SharedPITControlPlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = readiness_run(as_of=date(2026, 10, 24))
        cls.sources = collect()

    def slot(self, result, currency, pillar):
        return next(x for x in result["rows"]
                    if x["currency"] == currency and x["pillar"] == pillar)

    def audit(self, at="2026-10-24T00:00:00Z"):
        return build(self.base, self.sources, as_of=at)

    def test_exactly_24_g8_slots_in_fixed_order(self):
        r = self.audit()
        self.assertEqual(len(r["rows"]), 24)
        self.assertEqual([(x["currency"],x["pillar"]) for x in r["rows"]],
                         [(c,p) for c in CURRENCIES for p in PILLAR_ORDER])
        self.assertEqual(r["summary"]["pillar_slots"],24)
        self.assertEqual(r["summary"]["core_registry_slots"],16)
        self.assertEqual(r["summary"]["growth_source_selection_unresolved"],8)
        self.assertTrue(all(x["eligible_for_macro_score"] is False
                            for x in r["rows"]))

    def test_twenty_four_candidate_adapters_without_growth_canonical_selection(self):
        r=self.audit()
        expected=[(c,p) for c in CURRENCIES for p in PILLAR_ORDER]
        actual=[(x["currency"],x["pillar"]) for x in r["rows"]
                if x["candidate_evidence_source_id"]]
        self.assertEqual(actual,expected)
        self.assertEqual(r["summary"]["candidate_source_streams_loaded"],24)
        self.assertEqual(r["summary"]["slots_without_shared_candidate_stream"],0)
        self.assertEqual(r["summary"]["candidate_first_release_reference_periods_visible"],75)
        self.assertEqual(r["summary"]["candidate_web_publication_stage_events_visible"],87)
        self.assertEqual(r["summary"]["growth_source_selection_unresolved"],8)
        for cc in CURRENCIES:
            self.assertIsNotNone(self.slot(r,cc,"growth")["candidate_evidence_source_id"])
            self.assertEqual(self.slot(r,cc,"growth")["candidate_documented_first_periods_visible"],1)
            self.assertIsNone(self.slot(r,cc,"growth")["canonical_series_id"])
            self.assertFalse(self.slot(r,cc,"growth")["canonical_first_release_chain_certified"])
        self.assertEqual(self.slot(r,"NZD","labour")["candidate_revision_events_visible"],1)
        self.assertEqual(self.slot(r,"EUR","growth")["candidate_revision_events_visible"],1)
        self.assertEqual(r["summary"]["slots_eligible_for_new_live_scores"],0)

    def test_bls_25_first_release_web_records_do_not_override_unrate(self):
        r = self.audit()
        row = self.slot(r,"USD","labour")
        self.assertEqual(row["canonical_series_id"],"UNRATE")
        self.assertEqual(row["candidate_evidence_source_id"],"LNS14000000")
        self.assertFalse(row["canonical_series_id_matches_candidate"])
        self.assertEqual(row["candidate_reference_range_gaps_in_dossier"],0)
        self.assertIsNone(row["has_enough_candidate_web_periods_for_target"])
        self.assertEqual(row["minimum_training_first_releases_per_canonical_frequency"],25)
        self.assertFalse(row["canonical_first_release_chain_certified"])

    def test_abs_monthly_candidate_not_quarterly_registry_pit(self):
        r=self.audit()
        row=self.slot(r,"AUD","inflation")
        self.assertEqual(row["canonical_frequency"],"Q")
        self.assertEqual(row["candidate_frequency"],"M")
        self.assertEqual(row["canonical_series_id"],"AU_CPI_HEADLINE_Q_YOY")
        self.assertEqual(row["candidate_evidence_source_id"],"AU_CPI_HEADLINE_M_YOY_context_value")
        self.assertIsNone(row["has_enough_candidate_web_periods_for_target"])
        self.assertEqual(row["minimum_training_first_releases_per_canonical_frequency"],13)
        self.assertIn("MISMATCH",row["source_status"])

    def test_eurostat_candidate_not_unreviewed_canonical_alias(self):
        r=self.audit()
        row=self.slot(r,"EUR","inflation")
        self.assertEqual(row["canonical_series_id"],"EA_HICP_HEADLINE_YOY")
        self.assertEqual(row["candidate_evidence_source_id"],"EA_HICP_HEADLINE_YOY_history_value")
        self.assertFalse(row["canonical_series_id_matches_candidate"])
        self.assertEqual(row["candidate_detailed_events_visible"],10)
        self.assertEqual(row["latest_candidate_period_visible"],"2026-09")
        self.assertEqual(row["latest_candidate_initial_web_value"],3.8)
        self.assertEqual(row["latest_candidate_value_at_cutoff"],3.8)

    def test_gbp_lfs_window_is_not_calendar_center_month(self):
        r=self.audit()
        row=self.slot(r,"GBP","labour")
        self.assertEqual(row["canonical_series_id"],"MGSX")
        self.assertTrue(row["canonical_series_id_matches_candidate"])
        self.assertTrue(row["canonical_frequency_matches_candidate"])
        self.assertEqual(row["candidate_period_semantics"],
                         "THREE_MONTH_LFS_WINDOW_END_MONTH_NOT_SOURCE_CENTER_MONTH")
        self.assertEqual(row["latest_candidate_period_visible"],"2026-08")
        self.assertEqual(row["latest_candidate_value_at_cutoff"],4.7)
        self.assertIn("VINTAGE_REVIEW",row["source_status"])
        self.assertFalse(row["canonical_first_release_chain_certified"])

    def test_december_hicp_flash_detailed_asof_prevents_future_revision(self):
        pre=self.audit("2026-01-07T23:59:59Z")
        first=self.audit("2026-01-08T00:00:00Z")
        pre_final=self.audit("2026-01-19T23:59:59Z")
        final=self.audit("2026-01-20T00:00:00Z")
        eu=lambda r:self.slot(r,"EUR","inflation")
        self.assertEqual(eu(pre)["candidate_documented_first_periods_visible"],0)
        self.assertEqual(eu(first)["latest_candidate_value_at_cutoff"],2.0)
        self.assertEqual(eu(first)["latest_candidate_visible_stage"],"FIRST_WEB")
        self.assertEqual(eu(pre_final)["latest_candidate_value_at_cutoff"],2.0)
        self.assertEqual(eu(final)["latest_candidate_value_at_cutoff"],1.9)
        self.assertEqual(eu(final)["latest_candidate_visible_stage"],"DETAILED_WEB")

    def test_jan_eurostat_flash_final_corrigenda_remain_only_in_source_specific_history(self):
        before=self.audit("2026-02-04T23:59:59Z")
        feb5=self.audit("2026-02-05T00:00:00Z")
        feb6=self.audit("2026-02-06T00:00:00Z")
        self.assertEqual(self.slot(before,"EUR","inflation")["candidate_documented_first_periods_visible"],1)
        self.assertEqual(self.slot(feb5,"EUR","inflation")["candidate_documented_first_periods_visible"],2)
        self.assertEqual(self.slot(feb6,"EUR","inflation")["candidate_documented_first_periods_visible"],2)
        self.assertEqual(self.slot(feb6,"EUR","inflation")["candidate_detailed_events_visible"],1)
        # The new G8 gateway only counts comparable first/final headline-rate
        # records; existing source-specific Jan-Feb corrigendum module remains
        # the authoritative explanation for corrected components/weights.

    def test_bls_exact_timezone_and_gbp_date_only_gates(self):
        early=self.audit("2025-11-20T13:29:59Z")
        released=self.audit("2025-11-20T13:30:00Z")
        self.assertEqual(self.slot(early,"USD","labour")["candidate_documented_first_periods_visible"],24)
        self.assertEqual(self.slot(released,"USD","labour")["candidate_documented_first_periods_visible"],25)
        before_gbp=self.audit("2026-10-20T23:59:59Z")
        after_gbp=self.audit("2026-10-21T00:00:00Z")
        self.assertEqual(self.slot(before_gbp,"GBP","labour")["candidate_documented_first_periods_visible"],2)
        self.assertEqual(self.slot(after_gbp,"GBP","labour")["candidate_documented_first_periods_visible"],3)

    def test_fail_closed_generic_validation_and_no_canonical_promotion(self):
        invalids=[]
        s=copy.deepcopy(self.sources[0])
        s["events"][0]["source_url"]="https://example.com/fake-release"
        invalids.append(s)
        s=copy.deepcopy(self.sources[0])
        s["events"][0]["reported_value"]=float("nan")
        invalids.append(s)
        s=copy.deepcopy(self.sources[0])
        s["canonical_series_mapping_independently_certified"]=True
        invalids.append(s)
        s=copy.deepcopy(self.sources[0])
        s["complete_revision_history_verified"]=True
        invalids.append(s)
        s=copy.deepcopy(self.sources[0])
        s["events"][1]["visible_from_utc"]=s["events"][0]["visible_from_utc"]
        invalids.append(s)
        s=copy.deepcopy(self.sources[0])
        s["events"].append(copy.deepcopy(s["events"][0]))
        invalids.append(s)
        s=copy.deepcopy(self.sources[0])
        s["events"][0]["visible_from_utc"]="2025-11-01T00:00:00"
        invalids.append(s)
        for i,source in enumerate(invalids):
            with self.subTest(case=i):
                with self.assertRaises((ValueError,TypeError)):
                    normalize(source)

    def test_no_duplicate_slot_or_missing_slot_accepted(self):
        with self.assertRaises(ValueError):
            build(self.base,self.sources+[copy.deepcopy(self.sources[0])],
                  as_of="2026-10-24T00:00:00Z")
        b=copy.deepcopy(self.base)
        b["rows"].pop()
        with self.assertRaises(ValueError):
            build(b,self.sources,as_of="2026-10-24T00:00:00Z")
        b=copy.deepcopy(self.base)
        b["safe_to_publish_new_D"]=True
        with self.assertRaises(ValueError):
            build(b,self.sources,as_of="2026-10-24T00:00:00Z")

    def test_no_retroactive_registry_inventory_and_no_scores(self):
        r=self.audit("2025-11-20T13:30:00Z")
        self.assertTrue(r["inventory_snapshot_is_not_historical_asof_reconstruction"])
        self.assertEqual(r["canonical_inventory_review_snapshot_date"],"2026-10-24")
        self.assertTrue(r["candidate_source_events_obey_asof_cutoff"])
        for key in ("scores_computed","model_parameters_fitted",
                    "ready_for_backtest","safe_to_publish_new_D",
                    "safe_to_update_pair_theses","writes_live_data"):
            self.assertIs(r[key],False)
        self.assertEqual(r["summary"]["slots_eligible_for_new_live_scores"],0)
        self.assertEqual(r["summary"]["slots_with_full_canonical_first_release_pit_training_certified"],0)

    def test_readonly_repeatability(self):
        base=copy.deepcopy(self.base)
        data=copy.deepcopy(self.sources)
        first=build(base,data,as_of="2026-10-24T00:00:00Z")
        self.assertEqual(first,build(base,data,as_of="2026-10-24T00:00:00Z"))
        self.assertEqual(base,self.base)
        self.assertEqual(data,self.sources)


if __name__=="__main__":
    unittest.main()
