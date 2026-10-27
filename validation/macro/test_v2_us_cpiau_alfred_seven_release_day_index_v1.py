"""Adversarial tests of the Fed ALFRED release-day SA CPI index mirror."""
from __future__ import annotations

import copy
import json
import unittest

from validation.macro.v2_us_cpiau_alfred_seven_release_day_index_v1 import (
    ASOF, FIXED_ANCHORS, PATH, SCHEMA, audit
)
from validation.macro.v2_shadow_features_v1 import ROOT


class ALFREDSevenReleaseDayCPIResearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(PATH.read_text(encoding="utf-8"))
        cls.verified = audit()

    def mutate(self, fn):
        source = copy.deepcopy(self.source)
        fn(source)
        with self.assertRaises(ValueError):
            audit(fixture=source)

    def test_seven_exact_release_day_index_levels_but_not_original_BLS(self):
        x = self.verified
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["source_page_count"], 7)
        self.assertEqual(x["source_economic_months"], list(FIXED_ANCHORS))
        self.assertTrue(x["BLS_2025_10_original_all_items_absent"])
        self.assertTrue(x["not_24_prior_consecutive_months"])
        self.assertTrue(x["cannot_establish_original_BLS_issuer_SA_vintage_from_FED_mirror_alone"])
        self.assertEqual(x["BLS_original_issue_day_bytes_sha256_captured"], 0)
        self.assertEqual(x["ALFRED_historical_full_vintage_CSVs_acquired"], 0)
        self.assertEqual(x["canonical_CPIAUCSL_first_releases_source_day_certified"], 0)
        for forbidden in ("safe_to_publish_new_D", "safe_to_recalculate_28_pairs",
                          "safe_for_beta", "safe_for_forward", "writes_live_data"):
            self.assertIs(x[forbidden], False)

    def test_2025_11_original_mirror_level_is_not_2026_revision(self):
        by_month = {r["economic_month"]:r for r in self.source["records"]}
        self.assertEqual(by_month["2025-11"]["bls_release_date"], "2025-12-18")
        self.assertEqual(by_month["2025-11"]["alfred_release_page_last_observation_SA_CPIAUCSL_index"], 325.031)
        self.assertNotIn("2025-10", by_month)
        self.mutate(lambda d: d["records"][4].update(
            alfred_release_page_last_observation_SA_CPIAUCSL_index=325.063))
        self.mutate(lambda d: d["records"][4].update(economic_month="2025-10"))
        self.mutate(lambda d: d["records"][4].update(
            bls_release_date="2025-11-12"))

    def test_mislabelled_NSA_or_unverified_BLS_source_denied(self):
        self.mutate(lambda d: d.update(canonical_core_target="CPIAUCNS"))
        self.mutate(lambda d: d.update(origin="BLS_ORIGINAL_HISTORIC_SHA_CERTIFIED"))
        self.mutate(lambda d: d.update(source_original_BLS_bytes_captured=True))
        self.mutate(lambda d: d.update(
            capture_includes_original_publisher_PIT_full_history=True))
        self.mutate(lambda d: d.update(ALFRED_HTML_raw_download_sha256="x"*64))
        self.mutate(lambda d: d["records"][0].update(
            bls_original_issuer_SA_index_level_independently_certified=True))
        self.mutate(lambda d: d["records"][0].update(
            alfred_release_date_page_url="https://fred.stlouisfed.org/series/CPIAUCSL"))

    def test_bad_precision_duplicate_source_and_future_training_cutoff(self):
        self.mutate(lambda d: d["records"][0].update(
            alfred_release_page_last_observation_SA_CPIAUCSL_index=315.4549))
        self.mutate(lambda d: d["records"][1].update(observed_last_month="2024-11"))
        self.mutate(lambda d: d["records"].append(copy.deepcopy(d["records"][0])))
        self.mutate(lambda d: d["records"].reverse())
        self.mutate(lambda d: d.update(oct_2025_official_all_items_observation_missing=False))
        with self.assertRaises(ValueError):
            audit(as_of="2025-12-18T23:59:59Z")

    def test_no_production_mutation_and_deterministic_receipt(self):
        base = ROOT / "live_data/sections"
        names = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {name: (base/name).read_bytes() for name in names}
        again = audit()
        after = {name: (base/name).read_bytes() for name in names}
        self.assertEqual(before, after)
        self.assertEqual(self.verified["receipt_sha256"], again["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
