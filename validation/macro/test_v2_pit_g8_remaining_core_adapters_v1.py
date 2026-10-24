import copy
import json
import unittest
from datetime import date

from validation.macro.v2_pit_g8_control_plane_v1 import build, normalize
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_pit_coverage_readiness_v1 import run as readiness_run
from validation.macro.v2_pit_g8_remaining_core_adapters_v1 import (
    BOOTSTRAP_PINS, SOURCE_FILES, SWISS_ARCHIVE_PINS,
    collect_remaining_core, load, verified_strict,
)


class RemainingG8LabourInflationAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline=readiness_run(as_of=date(2026,10,24))
        cls.sources=collect()
        cls.latest=collect_remaining_core()

    def receipt(self,cutoff):
        return build(self.baseline,self.sources,as_of=cutoff)

    def slot(self,receipt,c,p):
        return next(r for r in receipt["rows"]
                    if (r["currency"],r["pillar"])==(c,p))

    def test_five_distinct_remaining_core_candidates_and_six_growth_left(self):
        self.assertEqual(len(self.latest),5)
        self.assertEqual({(e["currency"],e["pillar"]) for e in self.latest},
                         {("EUR","labour"),("JPY","inflation"),("CHF","inflation"),
                          ("CHF","labour"),("NZD","labour")})
        self.assertEqual(len(self.sources),24)
        self.assertEqual(len({(s["currency"],s["pillar"]) for s in self.sources}),24)
        r=self.receipt("2026-10-24T00:00:00Z")
        self.assertEqual(r["summary"]["candidate_source_streams_loaded"],24)
        self.assertEqual(r["summary"]["slots_without_shared_candidate_stream"],0)
        self.assertEqual(r["summary"]["candidate_first_release_reference_periods_visible"],75)
        self.assertEqual(r["summary"]["candidate_web_publication_stage_events_visible"],87)
        self.assertEqual(r["summary"]["slots_with_full_canonical_first_release_pit_training_certified"],0)
        self.assertEqual(r["summary"]["slots_eligible_for_new_live_scores"],0)

    def test_eurostat_unemployment_dates_headlines_not_2018_2026_auto_vintages(self):
        before=self.receipt("2026-09-01T23:59:59Z")
        first=self.receipt("2026-09-02T00:00:00Z")
        after=self.receipt("2026-10-02T00:00:00Z")
        self.assertEqual(self.slot(before,"EUR","labour")["candidate_documented_first_periods_visible"],0)
        self.assertEqual(self.slot(first,"EUR","labour")["latest_candidate_period_visible"],"2026-07")
        self.assertEqual(self.slot(first,"EUR","labour")["latest_candidate_value_at_cutoff"],6.4)
        self.assertEqual(self.slot(after,"EUR","labour")["latest_candidate_period_visible"],"2026-08")
        self.assertEqual(self.slot(after,"EUR","labour")["candidate_documented_first_periods_visible"],2)
        self.assertEqual(self.slot(after,"EUR","labour")["candidate_source_publisher"],"Eurostat")
        self.assertTrue(self.slot(after,"EUR","labour")["canonical_series_id_matches_candidate"])
        self.assertFalse(self.slot(after,"EUR","labour")["canonical_first_release_chain_certified"])

    def test_japan_archived_original_jst_0830_timezone_and_base_pins(self):
        original=verified_strict("JPY.inflation")
        self.assertEqual(original["coverage"]["materialized_months"],104)
        self.assertEqual(original["anchors"]["2026-08"]["release_time_jst"],"08:30")
        before=self.receipt("2026-09-17T23:29:59Z")
        after=self.receipt("2026-09-17T23:30:00Z")
        self.assertEqual(self.slot(before,"JPY","inflation")["candidate_documented_first_periods_visible"],1)
        s=self.slot(after,"JPY","inflation")
        self.assertEqual(s["candidate_documented_first_periods_visible"],2)
        self.assertEqual(s["latest_candidate_period_visible"],"2026-08")
        self.assertEqual(s["latest_candidate_value_at_cutoff"],1.9)
        self.assertEqual(s["latest_candidate_publisher_gate_utc"],"2026-09-17T23:30:00+00:00")
        self.assertFalse(s["canonical_first_release_chain_certified"])

    def test_swiss_cpi_archived_assets_not_105_unloaded_first_web_events(self):
        original=verified_strict("CHF.inflation")
        self.assertEqual(original["coverage"]["materialized_months"],105)
        self.assertEqual(SWISS_ARCHIVE_PINS["2026-09"][3],36870831)
        before=self.receipt("2026-10-01T06:29:59Z")
        after=self.receipt("2026-10-01T06:30:00Z")
        r1=self.slot(before,"CHF","inflation")
        r2=self.slot(after,"CHF","inflation")
        self.assertEqual(r1["candidate_documented_first_periods_visible"],1)
        self.assertEqual(r2["candidate_documented_first_periods_visible"],2)
        self.assertEqual(r2["candidate_reference_range_gaps_in_dossier"],1)
        self.assertEqual(r2["latest_candidate_period_visible"],"2026-09")
        self.assertEqual(r2["latest_candidate_value_at_cutoff"],1.0)
        self.assertEqual(r2["latest_candidate_publisher_gate_utc"],"2026-10-01T06:30:00+00:00")
        self.assertFalse(r2["canonical_first_release_chain_certified"])

    def test_swiss_seco_rounded_press_rate_not_snb_exact_unemployment(self):
        r=self.receipt("2026-10-24T00:00:00Z")
        s=self.slot(r,"CHF","labour")
        self.assertEqual(s["canonical_series_id"],"CH_UNEMP_RATE")
        self.assertEqual(s["candidate_evidence_source_id"],
                         "CH_SECO_SA_REGISTERED_UNEMP_RATE_ONE_DECIMAL")
        self.assertFalse(s["canonical_series_id_matches_candidate"])
        self.assertTrue(s["canonical_frequency_matches_candidate"])
        self.assertEqual(s["candidate_documented_first_periods_visible"],3)
        self.assertEqual(s["latest_candidate_period_visible"],"2026-09")
        self.assertEqual(s["latest_candidate_value_at_cutoff"],3.1)
        self.assertIn("ROUNDED",s["candidate_period_semantics"])
        self.assertIn("MISMATCH",s["source_status"])
        self.assertFalse(s["canonical_first_release_chain_certified"])
        before=self.receipt("2026-10-06T23:59:59Z")
        after=self.receipt("2026-10-07T00:00:00Z")
        self.assertEqual(self.slot(before,"CHF","labour")["candidate_documented_first_periods_visible"],2)
        self.assertEqual(self.slot(after,"CHF","labour")["candidate_documented_first_periods_visible"],3)

    def test_nzd_march_2026_first_then_revised_in_june_report(self):
        before_first=self.receipt("2026-05-06T23:59:59Z")
        first=self.receipt("2026-05-07T00:00:00Z")
        before_revision=self.receipt("2026-08-05T23:59:59Z")
        after_revision=self.receipt("2026-08-06T00:00:00Z")
        self.assertEqual(self.slot(before_first,"NZD","labour")["candidate_documented_first_periods_visible"],0)
        self.assertEqual(self.slot(first,"NZD","labour")["latest_candidate_period_visible"],"2026Q1")
        self.assertEqual(self.slot(first,"NZD","labour")["latest_candidate_value_at_cutoff"],5.3)
        self.assertEqual(self.slot(before_revision,"NZD","labour")["candidate_revision_events_visible"],0)
        s=self.slot(after_revision,"NZD","labour")
        self.assertEqual(s["candidate_documented_first_periods_visible"],2)
        self.assertEqual(s["candidate_revision_events_visible"],1)
        self.assertEqual(s["candidate_revised_reference_periods_visible"],1)
        self.assertEqual(s["latest_candidate_period_visible"],"2026Q2")
        self.assertEqual(s["latest_candidate_value_at_cutoff"],5.6)
        source=next(q for q in self.latest if (q["currency"],q["pillar"])==("NZD","labour"))
        normalized=normalize(source)
        rev=next(e for e in normalized["all_documented_publication_events"]
                 if e["stage"]=="REVISION_WEB")
        self.assertEqual(rev["reference_period"],"2026Q1")
        self.assertEqual(rev["reported_value"],5.4)
        self.assertEqual(rev["visible_from_utc"],"2026-08-06T00:00:00+00:00")

    def test_fails_closed_revision_before_first_or_wrong_url_and_rate(self):
        s=next(q for q in self.latest if (q["currency"],q["pillar"])==("NZD","labour"))
        for edit in ("ahead","duplicate","unsafe_url","bad_period","fake_source_cert"):
            obj=copy.deepcopy(s)
            if edit=="ahead":
                obj["events"][2]["visible_from_utc"]="2026-05-06T00:00:00Z"
            elif edit=="duplicate":
                obj["events"].append(copy.deepcopy(obj["events"][2]))
            elif edit=="unsafe_url":
                obj["events"][2]["source_url"]="https://evil.example/made-up"
            elif edit=="bad_period":
                obj["events"][2]["observation_period"]="2026-03"
            else:
                obj["canonical_series_mapping_independently_certified"]=True
            with self.subTest(edit=edit):
                with self.assertRaises((ValueError,TypeError)):
                    normalize(obj)

    def test_no_loss_of_prior_archival_audit_and_no_automatic_scoring(self):
        for target in ("EUR.labour","JPY.inflation","CHF.inflation","NZD.labour"):
            result=verified_strict(target)
            self.assertEqual(result["status"],"PASS")
            self.assertFalse(result.get("changes_live_data",False))
        r=self.receipt("2026-10-24T00:00:00Z")
        for rec in r["rows"]:
            self.assertFalse(rec["canonical_first_release_chain_certified"])
            self.assertFalse(rec["complete_revision_history_certified"])
            self.assertFalse(rec["eligible_for_macro_score"])
            self.assertFalse(rec["eligible_for_backtest"])
        for key in ("scores_computed","model_parameters_fitted","ready_for_backtest",
                    "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
            self.assertFalse(r[key])

    def test_pure_replay_and_source_fingerprint_stable(self):
        base=copy.deepcopy(self.baseline)
        streams=copy.deepcopy(self.sources)
        a=build(base,streams,as_of="2026-10-24T00:00:00Z")
        self.assertEqual(a,build(base,streams,as_of="2026-10-24T00:00:00Z"))
        self.assertEqual(base,self.baseline)
        self.assertEqual(streams,self.sources)


if __name__=="__main__":
    unittest.main()
