"""Four canonical vs publisher candidate source identity conflicts: fail closed."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from validation.macro.v2_g8_source_semantic_reconciliation_v1 import (
    ROOT, SCHEMA, STRICT_PINS, reconcile,
)
from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import (
    run as timeline_run,
)


class G8SourceSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = timeline_run(start="2026-10-26", end="2026-10-27")
        cls.cat = cls.timeline["source_catalogue"]

    def test_12_exact_2_economic_aliases_2_genuine_non_equivalences(self):
        r = reconcile(self.cat)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["summary"]["slots"], 16)
        self.assertEqual(r["summary"]["exact_series_ID_and_frequency"], 12)
        self.assertEqual(
            r["summary"]["source_lineage_aliases_documented_not_production_approved"], 2)
        self.assertEqual(r["summary"]["genuine_measurement_mismatches_to_replace"], 2)
        self.assertEqual(r["summary"]["macro_model_scores_approved"], 0)
        self.assertEqual(r["summary"]["fx_ranking_score_replacements"], 0)
        self.assertTrue(r["research_aliases_are_not_source_bytes_or_release_vintages"])
        self.assertFalse(r["safe_to_publish_new_D"])
        self.assertFalse(r["safe_to_change_28_pairs"])
        self.assertFalse(r["safe_for_beta"])
        self.assertFalse(r["safe_for_forward"])
        self.assertFalse(r["writes_live_data"])
        for record in r["verdicts"].values():
            self.assertFalse(record["mapping_independently_certified_for_production"])
            self.assertFalse(record["complete_joint_historical_PIT_replay_certified"])
            self.assertFalse(record["ready_to_modify_live_core_D"])
            self.assertFalse(record["eligible_for_currency_strength_ranking"])
            self.assertFalse(record["candidate_can_replace_canonical_historical_vintages"])

    def test_us_bls_lineage_is_not_2025_shutdown_missing_month_backfill(self):
        r = reconcile(self.cat)["verdicts"]["USD.labour"]
        self.assertEqual(r["registered_series_id"], "UNRATE")
        self.assertEqual(r["web_candidate_series_id"], "LNS14000000")
        self.assertTrue(r["conceptual_source_lineage_documented"])
        self.assertEqual(r["fred_unrate_BLS_source_code"], "LNS14000000")
        self.assertTrue(r["bls_web_first_release_pilot_not_full_current_chain"])
        self.assertTrue(r["missing_october_2025_unemployment_not_imputed"])
        self.assertTrue(r["source_lineage_confident_not_replay_ready"])

    def test_eurostat_semantic_alias_retains_105_month_strict_evidence_receipt(self):
        r = reconcile(self.cat)["verdicts"]["EUR.inflation"]
        self.assertTrue(r["conceptual_source_lineage_documented"])
        self.assertEqual(r["registered_series_id"], "EA_HICP_HEADLINE_YOY")
        self.assertEqual(r["web_candidate_series_id"],
                         "EA_HICP_HEADLINE_YOY_history_value")
        self.assertEqual(r["archival_documented_first_release_periods"], 105)
        self.assertFalse(r["archival_source_events_materialized_in_this_timeline"])
        self.assertIn("EA20", r["source_definition_limitation"])
        self.assertIn("EA21", r["source_definition_limitation"])
        self.assertEqual(r["archival_receipt_status"], "PASS")

    def test_aud_monthly_candidate_cannot_replace_34_quarterly_archived_periods(self):
        r = reconcile(self.cat)["verdicts"]["AUD.inflation"]
        self.assertEqual(r["registered_frequency"], "Q")
        self.assertEqual(r["web_candidate_frequency"], "M")
        self.assertFalse(r["conceptual_source_lineage_documented"])
        self.assertEqual(r["archival_documented_first_release_periods"], 34)
        self.assertEqual(r["archival_receipt_status"], "PASS")
        self.assertTrue(r["decision"].startswith("CANDIDATE_NOT_EQUIVALENT"))
        self.assertTrue(reconcile(self.cat)["quarterly_AUD_receipt_not_monthly_CPI_source_substitution"])

    def test_chf_seco_one_decimal_cannot_certify_snb_precision_or_utc(self):
        r = reconcile(self.cat)["verdicts"]["CHF.labour"]
        self.assertEqual(r["registered_series_id"], "CH_UNEMP_RATE")
        self.assertEqual(r["web_candidate_series_id"],
                         "CH_SECO_SA_REGISTERED_UNEMP_RATE_ONE_DECIMAL")
        self.assertTrue(r["rounding_information_loss_not_recoverable"])
        self.assertTrue(r["original_precise_first_release_timestamp_unknown"])
        self.assertFalse(r["conceptual_source_lineage_documented"])
        self.assertTrue(r["decision"].startswith("CANDIDATE_NOT_EQUIVALENT"))

    def test_unreviewed_fifth_mismatch_or_alias_source_spoofing_rejected(self):
        fake = copy.deepcopy(self.cat)
        fake["GBP.labour"]["candidate_series_id"] = "WRONG_ID"
        fake["GBP.labour"]["series_and_frequency_match"] = False
        with self.assertRaisesRegex(ValueError, "unreviewed mismatch"):
            reconcile(fake)
        for key, field, value in (
            ("USD.labour", "candidate_series_id", "LNS14000001"),
            ("EUR.inflation", "official_publisher", "Fake Eurostat"),
            ("AUD.inflation", "candidate_frequency", "Q"),
            ("CHF.labour", "candidate_series_id", "CH_UNEMP_RATE"),
        ):
            fake = copy.deepcopy(self.cat)
            fake[key][field] = value
            with self.subTest(key=key, field=field), self.assertRaises(ValueError):
                reconcile(fake)

    def test_unapproved_prod_promotion_flag_rejected(self):
        fake = copy.deepcopy(self.cat)
        fake["USD.labour"]["candidate_source_canonical_mapping_certified"] = True
        with self.assertRaisesRegex(ValueError, "unapproved mapping"):
            reconcile(fake)
        fake = copy.deepcopy(self.cat)
        fake["JPY.labour"]["eligible_for_live_macro_score"] = True
        with self.assertRaisesRegex(ValueError, "unapproved mapping"):
            reconcile(fake)

    def test_quarterly_archival_receipt_cannot_be_replaced_by_false_35_quarters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for key, pin in STRICT_PINS.items():
                target = root / pin["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / pin["path"]).read_bytes())
            pin = STRICT_PINS["AUD.inflation"]
            path = root / pin["path"]
            bad = json.loads(path.read_text(encoding="utf-8"))
            bad["coverage"]["materialized_quarters"] = 35
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "receipt series identity"):
                reconcile(self.cat, root=root)

    def test_timeline_outputs_reconciled_identity_and_keeps_mismatch_count(self):
        r = self.timeline
        self.assertEqual(
            r["source_semantic_reconciliation"]["summary"]["genuine_measurement_mismatches_to_replace"],
            2)
        self.assertEqual(r["summary"]["series_frequency_exact_candidate_matches"], 12)
        self.assertEqual(r["summary"]["candidate_source_mismatches_or_frequency_mismatches"], 4)
        self.assertFalse(r["safe_to_publish_new_D"])
        self.assertEqual(r["summary"]["joint_PIT_training_histories_certified"], 0)

    def test_read_only_guarantee_live_core_and_pair_file_unchanged(self):
        files = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        folder = ROOT / "live_data/sections"
        before = {k: (folder / k).read_bytes() for k in files}
        reconcile(self.cat)
        after = {k: (folder / k).read_bytes() for k in files}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
