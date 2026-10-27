"""Regression for 1003 official first-release rows recovered from 11 prior Actions artifacts."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from validation.macro.v2_g8_11_retained_source_archives_v1 import (
    FOLDER, METRICS, PINNED, decode_slot, economic_index, run
)
from validation.macro.v2_g8_24_axis_training_history_gap_audit_v1 import (
    ASOF, evidence
)
from validation.macro.v2_shadow_features_v1 import ROOT


class ElevenPriorAuditedIssuerArchives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = run()

    def test_all_11_issuer_histories_are_pinned_and_contiguous(self):
        a = self.a
        self.assertEqual(a["summary"]["g8_histories_added"], 11)
        self.assertEqual(a["summary"]["archived_first_release_observations"], 1003)
        self.assertEqual(set(a["histories"]), set(METRICS))
        self.assertTrue(a["source_bytes_equal_to_prior_independently_audited_archives"])
        self.assertTrue(a["not_all_24_sources_joint_original_day_certified"])
        self.assertEqual(a["summary"]["PIT_24_axis_historical_model_scores_approved"], 0)
        for key in ("safe_to_publish_new_D", "safe_to_change_28_pairs",
                    "safe_for_beta", "safe_for_forward", "writes_live_data"):
            self.assertFalse(a[key])
        for key, item in a["histories"].items():
            self.assertEqual(item["first_web_release_count"], len(item["records"]))
            self.assertEqual(item["first_reference_period"],
                             item["records"][0]["reference_period"])
            self.assertEqual(item["last_reference_period"],
                             item["records"][-1]["reference_period"])
            self.assertTrue(all(r["value_as_original_reported"] is True for r in
                                item["records"]))
            self.assertTrue(all(not r["valid_source_for_PIT_FX_backtest"] for r in
                                item["records"]))
            self.assertFalse(item["full_revision_history_complete"])
            refs=[economic_index(e["reference_period"],item["frequency"])
                  for e in item["records"]]
            self.assertEqual(refs, list(range(refs[0],refs[-1]+1)))
            self.assertTrue(all(len(e["original_publisher_materialization_sha256"])==64
                                for e in item["records"]))

    def test_two_new_34_quarterly_NZD_sources_are_not_monthly_proxies(self):
        for key in ("NZD.inflation", "NZD.labour"):
            x=self.a["histories"][key]
            self.assertEqual(x["frequency"],"Q")
            self.assertEqual(x["first_web_release_count"],34)
            self.assertEqual(x["first_reference_period"],"2018-03")
            self.assertEqual(x["last_reference_period"],"2026-06")
            self.assertEqual(x["records"][-1]["metric_frequency"],"Q")

    def test_historic_rates_use_correct_issuer_utc_gate(self):
        a=self.a["histories"]
        self.assertEqual(a["JPY.labour"]["records"][0]
                         ["first_web_publisher_gate_utc"],
                         "2018-03-01T23:30:00+00:00")
        self.assertEqual(a["CAD.labour"]["records"][0]
                         ["first_web_publisher_gate_utc"],
                         "2018-02-09T13:30:00+00:00")
        self.assertEqual(a["AUD.labour"]["records"][0]
                         ["first_web_publisher_gate_utc"],
                         "2018-02-15T00:30:00+00:00")
        self.assertEqual(a["EUR.labour"]["records"][0]
                         ["first_web_publisher_gate_utc"],
                         "2018-03-02T00:00:00+00:00")
        self.assertTrue(a["CHF.inflation"]["records"][0]
                        ["first_web_publisher_gate_utc"].endswith("+00:00"))

    def test_gap_research_audit_reuses_archives_with_no_core_promotion(self):
        r=evidence(cutoff=ASOF)
        s=r["summary"]
        self.assertEqual(s["retained_official_first_release_source_archives_ingested"],11)
        self.assertEqual(s["retained_source_original_issuer_records_imported"],1003)
        self.assertTrue(r["retained_official_source_archive_original_SHA256_checked_each_run"])
        self.assertGreaterEqual(s["prior_first_web_contiguous_12Q_or_24M_slots"], 20)
        self.assertLessEqual(s["slots_missing_required_initial_release_periods"], 4)
        self.assertEqual(s["genuinely_historic_PIT_training_slots_certified"],0)
        self.assertEqual(s["currency_FX_strength_scores_approved"],0)
        self.assertFalse(r["safe_to_publish_new_D"])
        self.assertFalse(r["safe_to_recalculate_28_pairs"])
        for key in METRICS:
            item=r["slots"][key]
            self.assertEqual(
                item["training_web_data_source_type"],
                "RETAINED_OFFICIAL_STRICT_FIRST_RELEASE_ARTIFACT_HASH_PINNED")
            self.assertTrue(item["prior_initial_web_sequence_complete_mathematically"])
            self.assertEqual(item["missing_required_prior_periods"],[])
            self.assertFalse(item["model_PIT_training_approved"])
        self.assertTrue(r["slots"]["CHF.labour"]
                        ["source_measurement_alternative_not_interchangeable"])

    def test_poison_original_fixture_bytes_hard_fail(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            (folder/"G8_STRICT_SOURCE_FIRST_RELEASE_11_ARCHIVES_MANIFEST.json").write_bytes(
                (FOLDER/"G8_STRICT_SOURCE_FIRST_RELEASE_11_ARCHIVES_MANIFEST.json").read_bytes()
            )
            key="NZD.labour"
            filename=next(x["fixture"] for x in json.loads(
                (folder/"G8_STRICT_SOURCE_FIRST_RELEASE_11_ARCHIVES_MANIFEST.json").read_text()
                )["sources"] if x["slot"]==key)
            text=(FOLDER/filename).read_text()
            # A valid-looking but modified base64 string must NOT be trusted.
            (folder/filename).write_text(text[:-8]+"AAAAAAA\n")
            with self.assertRaises(Exception):
                decode_slot(key, folder=folder)

    def test_live_G8_currency_scores_and_28_pairs_untouched(self):
        root=ROOT/"live_data/sections"
        before={n:(root/n).read_bytes() for n in
                ("D.json","PAIR_SETUP_OPERATIONAL_VIEW.json")}
        r=run()
        after={n:(root/n).read_bytes() for n in before}
        self.assertEqual(before,after)
        self.assertEqual(r["summary"]["FX_rankings_updated"],0)


if __name__=="__main__":
    unittest.main()
