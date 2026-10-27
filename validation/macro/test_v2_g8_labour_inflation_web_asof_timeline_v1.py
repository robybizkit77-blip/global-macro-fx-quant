"""Adversarial source provenance, publication timing and revision tests."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timedelta, timezone

from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import (
    ROOT, COUNTRIES, PILLARS, REGISTRY, asof_source, catalogue,
    compile_timeline, daily_end, run, visible_candidates,
)
from validation.macro.v2_pit_g8_evidence_adapters_v1 import collect
from validation.macro.v2_pit_g8_control_plane_v1 import normalize
from validation.macro.v2_shadow_features_v1 import timestamp


class IssuerWebAsOfTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = collect()
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.sources = catalogue(cls.candidates, cls.registry)

    def test_all_16_issuer_web_streams_have_canonical_distinction(self):
        self.assertEqual(set(self.sources),
                         {f"{c}.{p}" for c in COUNTRIES for p in PILLARS})
        report = compile_timeline(
            self.registry, self.candidates, start="2026-10-20", end="2026-10-27")
        self.assertEqual(report["summary"]["G8_currencies"], 8)
        self.assertEqual(report["summary"]["inflation_labour_source_slots"], 16)
        self.assertEqual(report["window"]["daily_snapshots"], 8)
        self.assertGreater(report["summary"]["independent_event_boundaries_checked"], 16)
        self.assertGreater(report["summary"]["first_publisher_web_periods_in_bounded_dossiers"], 16)
        self.assertEqual(
            (report["summary"]["series_frequency_exact_candidate_matches"] +
             report["summary"]["candidate_source_mismatches_or_frequency_mismatches"]), 16)
        self.assertEqual(report["summary"]["joint_PIT_training_histories_certified"], 0)
        self.assertEqual(report["summary"]["FX_backtests_performed"], 0)
        self.assertFalse(report["safe_to_publish_new_D"])
        self.assertFalse(report["safe_to_change_28_pairs"])
        self.assertFalse(report["safe_for_beta"])
        self.assertFalse(report["safe_for_forward"])
        self.assertFalse(report["writes_live_data"])
        for row in report["source_catalogue"].values():
            self.assertFalse(row["candidate_source_canonical_mapping_certified"])
            self.assertFalse(row["eligible_for_live_macro_score"])

    def test_bls_first_statement_appears_only_after_source_gate(self):
        stream = self.sources["USD.labour"]
        e = next(e for e in stream["all_documented_publication_events"]
                 if e["stage"] == "FIRST_WEB")
        at = timestamp(e["visible_from_utc"])
        before = asof_source(stream, at - timedelta(microseconds=1))
        after = asof_source(stream, at)
        self.assertEqual(after["first_issuer_web_releases_seen"],
                         before["first_issuer_web_releases_seen"] + 1)
        self.assertFalse(after["FX_score_eligible"])
        self.assertEqual(stream["source_series_id"], "LNS14000000")
        self.assertNotEqual(stream["source_series_id"],
                            self.registry["series"]["USD.labour"]["series_id"])

    def test_nzd_earlier_first_value_survives_later_revision(self):
        stream = self.sources["NZD.labour"]
        events = stream["all_documented_publication_events"]
        # March 2026 initial 5.3, June bulletin later revised March to 5.4.
        q1 = next(e for e in events if e["reference_period"] == "2026Q1"
                  and e["stage"] == "FIRST_WEB")
        rev = next(e for e in events if e["reference_period"] == "2026Q1"
                   and e["stage"] == "REVISION_WEB")
        initial_gate = timestamp(q1["visible_from_utc"])
        revision_gate = timestamp(rev["visible_from_utc"])
        initial = asof_source(stream, initial_gate)
        self.assertEqual(initial["latest_reference_period"], "2026Q1")
        self.assertEqual(initial["first_web_value"], 5.3)
        self.assertEqual(initial["asof_known_value"], 5.3)
        self.assertEqual(initial["known_revision_count_for_latest"], 0)
        later = asof_source(stream, revision_gate)
        self.assertEqual(later["latest_reference_period"], "2026Q2")
        self.assertEqual(later["first_web_value"], 5.6)
        self.assertEqual(later["asof_known_value"], 5.6)
        prior = later["older_periods_with_revisions_visible_asof"]
        previous = next(x for x in prior if x["reference_period"] == "2026Q1")
        self.assertEqual(previous["first_web_value"], 5.3)
        self.assertEqual(previous["last_visible_value_asof"], 5.4)
        self.assertEqual(previous["last_visible_stage"], "REVISION_WEB")
        self.assertTrue(previous["revised_publication_cannot_rewrite_prior_asof"])
        self.assertTrue(initial["selected_reference_period_is_release_period_not_current_calendar"])

    def test_eurostat_flash_vs_detailed_follows_visibility(self):
        stream = self.sources["EUR.inflation"]
        events = stream["all_documented_publication_events"]
        candidates = {}
        for e in events:
            if e["reference_period"] == "2026-09":
                candidates[e["stage"]] = e
        self.assertEqual(set(candidates), {"FIRST_WEB", "DETAILED_WEB"})
        flash = timestamp(candidates["FIRST_WEB"]["visible_from_utc"])
        detailed = timestamp(candidates["DETAILED_WEB"]["visible_from_utc"])
        self.assertLess(flash, detailed)
        early = asof_source(stream, flash)
        later = asof_source(stream, detailed)
        self.assertEqual(early["latest_reference_period"], "2026-09")
        self.assertEqual(early["first_web_value"],
                         candidates["FIRST_WEB"]["reported_value"])
        self.assertEqual(early["asof_known_value"],
                         candidates["FIRST_WEB"]["reported_value"])
        self.assertEqual(later["asof_known_value"],
                         candidates["DETAILED_WEB"]["reported_value"])
        self.assertEqual(later["known_revision_count_for_latest"], 1)

    def test_ons_three_month_labour_period_not_middle_month(self):
        stream = self.sources["GBP.labour"]
        event = max((e for e in stream["all_documented_publication_events"]
                     if e["stage"] == "FIRST_WEB"),
                    key=lambda e: e["reference_period_index"])
        latest = asof_source(stream, timestamp(event["visible_from_utc"]))
        self.assertEqual(latest["latest_reference_period"], "2026-08")
        self.assertIn("THREE_MONTH_LFS_WINDOW_END_MONTH", stream["period_semantics"])
        self.assertFalse(latest["live_source_approved"])

    def test_canonical_mismatch_monthly_aud_cpi_not_quarterly_registry(self):
        stream = self.sources["AUD.inflation"]
        self.assertEqual(stream["frequency"], "M")
        self.assertEqual(self.registry["series"]["AUD.inflation"]["frequency"], "Q")
        report = compile_timeline(
            self.registry, self.candidates, start="2026-10-21", end="2026-10-22")
        audit = report["source_catalogue"]["AUD.inflation"]
        self.assertFalse(audit["frequency_matches_registry"])
        self.assertFalse(audit["series_and_frequency_match"])
        self.assertEqual(audit["source_alignment"],
                         "CANDIDATE_NOT_IDENTICAL_TO_CORE_SOURCE")

    def test_missing_events_at_past_cutoff_never_backfilled(self):
        stream = self.sources["GBP.inflation"]
        first_gate = min(timestamp(x["visible_from_utc"])
                         for x in stream["all_documented_publication_events"]
                         if x["stage"] == "FIRST_WEB")
        before = asof_source(stream, first_gate-timedelta(microseconds=1))
        self.assertEqual(before["status"],
                         "NOT_YET_VISIBLE_IN_THIS_BOUNDED_PUBLISHER_LEDGER")
        self.assertIsNone(before["asof_known_value"])
        self.assertEqual(before["first_issuer_web_releases_seen"], 0)

    def test_extra_fake_original_archive_certification_blocks_import(self):
        fake = copy.deepcopy(self.candidates)
        candidate = next(x for x in fake
                         if x["currency"] == "AUD" and x["pillar"] == "inflation")
        candidate["original_release_day_immutable_bytes_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot|verified|certified|release"):
            catalogue(fake, self.registry)

    def test_source_issuer_spoofing_and_duplicate_source_slot_rejected(self):
        fake = copy.deepcopy(self.candidates)
        target = next(x for x in fake
                      if x["currency"] == "EUR" and x["pillar"] == "labour")
        target["events"][0]["source_url"] = "https://unknown.example/false"
        with self.assertRaisesRegex(ValueError, "publisher|official|URL"):
            catalogue(fake, self.registry)
        with self.assertRaisesRegex(ValueError, "repeated"):
            catalogue(self.candidates + [self.candidates[0]], self.registry)

    def test_no_score_or_live_core_mutation_from_full_replay(self):
        root = ROOT / "live_data/sections"
        paths = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        old = {x: (root / x).read_bytes() for x in paths}
        receipt = compile_timeline(
            self.registry, self.candidates, start="2026-08-01", end="2026-10-27")
        new = {x: (root / x).read_bytes() for x in paths}
        self.assertEqual(old, new)
        self.assertEqual(receipt["summary"]["joint_PIT_training_histories_certified"], 0)
        self.assertTrue(receipt["matching_source_id_and_frequency_does_not_certify_first_release_archive"])
        self.assertFalse(receipt["safe_to_publish_new_D"])


if __name__ == "__main__":
    unittest.main()
