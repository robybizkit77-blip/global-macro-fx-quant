"""Live-source read-only bridge tests; old numeric Macro outputs are not a fit target."""
from __future__ import annotations

import copy
import unittest

from validation.macro.legacy_v2_score_evidence_bridge_v1 import bridge, run
from validation.macro.score_formula_provenance_v1 import run as legacy_run
from validation.macro.v2_pit_g8_control_plane_v1 import run as v2_run
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


class LegacyV2ScoreEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((ROOT / "live_data/sections/D.json").read_text())
        # Use the actual Rome session date, not a past test day: the live
        # official price overlay legitimately advances after 26 October.
        # The provenance gate itself must still reject future-dated input.
        cls.legacy = legacy_run(today=datetime.now(ZoneInfo("Europe/Rome")).date())
        cls.v2 = v2_run(as_of="2026-10-26T16:00:00Z")

    def test_frozen_provenance_rejects_price_snapshot_future_to_clock(self):
        pair = json.loads((ROOT / "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json").read_text())
        observed_price_day = date.fromisoformat(pair["price_asof"])
        with self.assertRaisesRegex(ValueError, "future baseline / price snapshot"):
            legacy_run(today=observed_price_day - timedelta(days=1))

    def test_exact_24_historical_numbers_join_not_promoted(self):
        receipt = bridge(self.model, self.legacy, self.v2)
        self.assertEqual(receipt["summary"]["historical_scalar_values"], 24)
        self.assertEqual(len(receipt["rows"]), 24)
        self.assertEqual(receipt["summary"]["v2_currency_pillar_evidence_slots"], 24)
        self.assertEqual(receipt["historical_baseline_as_of"], "2026-09-25")
        self.assertTrue(receipt["no_new_scores"])
        self.assertTrue(receipt["no_bespoke_weights"])
        self.assertFalse(receipt["safe_to_publish_new_D"])
        self.assertFalse(receipt["safe_to_update_pair_theses"])
        self.assertFalse(receipt["writes_live_data"])
        self.assertEqual(receipt["summary"]["eligible_for_new_numeric_scores"], 0)
        self.assertEqual(receipt["summary"]["independent_historical_formula_replays"], 0)
        self.assertEqual(receipt["summary"]["documented_web_first_release_periods_not_archived_pit"],
                         self.v2["summary"]["candidate_first_release_reference_periods_visible"])
        self.assertEqual(set((r["currency"], r["pillar"]) for r in receipt["rows"]),
                         {(c, p) for c in
                          ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
                          for p in ("growth","labour","inflation")})
        self.assertTrue(all(r["safe_to_regenerate_pillar_score"] is False and
                            r["approved_source_to_score_formula"] is False for r in receipt["rows"]))

    def test_cannot_forge_historical_macro_value_even_if_currency_pair_unchanged(self):
        model = copy.deepcopy(self.model)
        model["macro"]["USD"]["growth"] += 0.01
        with self.assertRaisesRegex(ValueError, "frozen 24 historical output vector"):
            bridge(model, self.legacy, self.v2)

    def test_no_source_evidence_can_be_misclassified_as_approved(self):
        modified = copy.deepcopy(self.v2)
        modified["rows"][0]["eligible_for_macro_score"] = True
        with self.assertRaisesRegex(ValueError, "illegally promoted"):
            bridge(self.model, self.legacy, modified)
        modified = copy.deepcopy(self.v2)
        modified["rows"][0]["canonical_first_release_chain_certified"] = True
        with self.assertRaisesRegex(ValueError, "illegally promoted"):
            bridge(self.model, self.legacy, modified)

    def test_no_duplicate_or_missing_currency_pillar_evidence(self):
        modified = copy.deepcopy(self.v2)
        modified["rows"][0] = copy.deepcopy(modified["rows"][1])
        with self.assertRaisesRegex(ValueError, "duplicate or foreign"):
            bridge(self.model, self.legacy, modified)
        modified = copy.deepcopy(self.v2)
        modified["rows"].pop()
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            bridge(self.model, self.legacy, modified)

    def test_mismatch_groups_and_named_dossier_are_complete_without_promotion(self):
        from validation.macro.legacy_v2_score_evidence_bridge_v1 import markdown
        receipt = bridge(self.model, self.legacy, self.v2)
        stats = receipt["summary"]
        self.assertEqual(stats["unselected_growth_canonical_indicators"], 8)
        self.assertEqual(stats["source_id_and_frequency_matches"], 12)
        self.assertEqual(stats["non_growth_source_or_frequency_mismatches"], 4)
        self.assertEqual(sum(stats["source_reconciliation_classes"].values()), 24)
        growth = [r for r in receipt["rows"] if r["pillar"] == "growth"]
        self.assertEqual(len(growth), 8)
        self.assertTrue(all(r["canonical_source_id"] is None and
                            r["source_reconciliation_class"] ==
                            "GROWTH_CANONICAL_INDICATOR_NOT_SELECTED" for r in growth))
        self.assertTrue(all(r["canonical_metric_unit_or_publisher_mapping_certified"] is False
                            for r in receipt["rows"]))
        report = markdown(receipt)
        self.assertEqual(report.count("GROWTH_CANONICAL_INDICATOR_NOT_SELECTED"), 8)
        self.assertEqual(len([x for x in report.splitlines() if x.startswith("| ")]) - 2, 24)
        self.assertIn("No PIT-certified rebase", report)

    def test_upstream_parity_claim_cannot_overrule_actual_id_and_frequency(self):
        bad = copy.deepcopy(self.v2)
        candidate = next(row for row in bad["rows"]
                         if row["candidate_evidence_source_id"] is not None)
        candidate["canonical_series_id_matches_candidate"] = not (
            candidate["candidate_evidence_source_id"] ==
            candidate["canonical_series_id"])
        with self.assertRaisesRegex(ValueError, "source/frequency parity inconsistent"):
            bridge(self.model, self.legacy, bad)

    def test_four_official_semantic_relationships_do_not_approve_pit(self):
        receipt = bridge(self.model, self.legacy, self.v2)
        rows = {(r["currency"], r["pillar"]): r for r in receipt["rows"]}
        expected = {
            ("USD", "labour"): ("SOURCE_CODE_LINEAGE_DOCUMENTED_NO_PIT_VINTAGE", True),
            ("EUR", "inflation"): ("HICP_HEADLINE_FAMILY_MATCH_CANONICAL_VINTAGE_UNPROVEN", True),
            ("CHF", "labour"): ("ROUNDED_SECO_VS_EXACT_SNB_SERIES_VINTAGE_UNPROVEN", False),
            ("AUD", "inflation"): ("MONTHLY_VS_QUARTERLY_ABS_CPI_HORIZON_DIFFERENT", False),
        }
        self.assertEqual(receipt["summary"]["documented_underlying_series_code_links_not_PIT_certified"], 1)
        self.assertEqual(receipt["summary"]["source_review_cases_with_no_PIT_promotion"], 4)
        for key, (label, concept) in expected.items():
            with self.subTest(key=key):
                row = rows[key]
                self.assertEqual(row["official_source_relationship_class"], label)
                self.assertEqual(row["same_statistical_concept_externally_documented"], concept)
                self.assertTrue(row["official_source_relationship_url"].startswith("https://"))
                self.assertFalse(row["source_id_and_frequency_match"])
                self.assertFalse(row["economic_source_code_alias_certified_for_pit_score"])
                self.assertFalse(row["safe_to_regenerate_pillar_score"])
                self.assertFalse(row["candidate_history_archived_original_bytes"])

    def test_fred_underlying_bls_source_mapping_is_not_an_unverified_series_alias(self):
        modified = copy.deepcopy(self.v2)
        row = next(x for x in modified["rows"]
                   if x["currency"] == "USD" and x["pillar"] == "labour")
        row["candidate_evidence_source_id"] = "LNS14000001"
        with self.assertRaisesRegex(ValueError, "semantic crosswalk not tied"):
            bridge(self.model, self.legacy, modified)
        modified = copy.deepcopy(self.v2)
        row = next(x for x in modified["rows"]
                   if x["currency"] == "AUD" and x["pillar"] == "inflation")
        row["candidate_frequency"] = "Q"
        row["canonical_frequency_matches_candidate"] = True
        with self.assertRaisesRegex(ValueError, "semantic crosswalk not tied"):
            bridge(self.model, self.legacy, modified)

    def test_never_subtract_incompatible_frequency_from_training_requirement(self):
        modified = copy.deepcopy(self.v2)
        # Any row with a source candidate can be changed to a wrong-identity
        # research source; it is observed, but no canonical training deficit
        # may be inferred from different frequency/metric observations.
        target = next(r for r in modified["rows"]
                      if r["pillar"] != "growth"
                      and r["candidate_evidence_source_id"] is not None
                      and r["canonical_series_id_matches_candidate"] is True
                      and r["canonical_frequency_matches_candidate"] is True)
        target["candidate_evidence_source_id"] += "_DIFFERENT_SERIES"
        target["canonical_series_id_matches_candidate"] = False
        result = bridge(self.model, self.legacy, modified)
        row = next(r for r in result["rows"]
                   if r["currency"] == target["currency"] and
                   r["pillar"] == target["pillar"])
        self.assertEqual(row["open_source_gate"],
                         "INDICATOR_DIFFERS_SAME_FREQUENCY")
        self.assertIsNone(row["same_source_periods_still_needed_descriptive_only"])


if __name__ == "__main__":
    unittest.main()
