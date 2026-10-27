"""Adversarial coverage for BLS archival web CPI first news-release research."""
from __future__ import annotations

import copy
import json
import unittest

from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_bls_cpi_first_news_archive_v1 import (
    ASOF, PATH, SCHEMA, audit
)


class BLSFirstNewsArchiveResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(PATH.read_text(encoding="utf-8"))
        cls.result = audit()

    def mutate(self, change):
        data = copy.deepcopy(self.raw)
        change(data)
        with self.assertRaises(ValueError):
            audit(fixture=data)

    def test_source_confidence_and_pit_blockers(self):
        out = self.result
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["cutoff"], ASOF)
        stat = out["summary"]
        self.assertEqual((stat["calendar_periods"],
                          stat["official_issuer_archive_links_documented"],
                          stat["official_BLS_HTML_news_releases_opened_and_read"],
                          stat["archive_index_only_unreadable_HTML_links"]), (25, 24, 24, 0))
        self.assertEqual(stat["BLS_2025_10_all_items_officially_unpublished"], 1)
        self.assertEqual(stat["one_month_rounded_SA_rate_readings"], 23)
        self.assertEqual(stat["2025_11_two_month_rounded_SA_change_not_MOM"], 1)
        self.assertEqual(stat["prior_24_calendar_months_with_issuer_archive_link"], 23)
        self.assertEqual(stat["new_exact_CPIAUCSL_first_vintage_index_levels"], 0)
        self.assertFalse(stat["source_slot_USD_inflation_first_release_training_approved"])
        self.assertTrue(out["reported_SA_rounded_changes_not_exact_CPIAUCSL_vintages"])
        self.assertTrue(out["2025_11_change_is_two_month_not_November_MOM"])
        self.assertTrue(out["news_archive_index_link_NOT_source_original_bytes"])
        for flag in ("safe_to_publish_new_D", "safe_to_recalculate_28_pairs",
                     "safe_for_beta", "safe_for_forward", "writes_live_data"):
            self.assertFalse(out[flag])

    def test_2025_11_is_two_month_bridge_not_monthly_rate(self):
        rows = {r["reference_month"]: r for r in self.raw["records"]}
        self.assertEqual(rows["2025-11"]["sa_change_horizon_months"], 2)
        self.assertEqual(rows["2025-11"]["first_issuer_reported_sa_all_items_change_pct_rounded_1dp"], 0.2)
        self.assertIsNone(rows["2025-10"]["publisher_release_day"])
        self.assertIsNone(rows["2025-10"]["first_issuer_reported_sa_all_items_change_pct_rounded_1dp"])
        self.mutate(lambda d: d["records"][14].update(sa_change_horizon_months=1))
        self.mutate(lambda d: d["records"][13].update(
            first_issuer_reported_sa_all_items_change_pct_rounded_1dp=0.0))

    def test_all_three_recovered_original_BLS_HTML_anchors(self):
        recovered={"2024-11":0.3,"2024-12":0.4,"2025-07":0.2}
        rows={r["reference_month"]:r for r in self.raw["records"]}
        for month, expected in recovered.items():
            self.assertEqual(rows[month]["source_evidence_level"], "HTML_OPENED")
            self.assertEqual(rows[month]["first_issuer_reported_sa_all_items_change_pct_rounded_1dp"], expected)
            self.assertEqual(rows[month]["sa_change_horizon_months"], 1)
        self.mutate(lambda d: d["records"][2].update(
            source_evidence_level="ARCHIVE_INDEX_LINK_ONLY_TIMEOUT"))
        self.mutate(lambda d: d["records"][3].update(
            first_issuer_reported_sa_all_items_change_pct_rounded_1dp=0.3))
        self.mutate(lambda d: d["records"][10].update(
            first_issuer_reported_sa_all_items_change_pct_rounded_1dp=0.3))

    def test_no_unverified_number_or_forged_source_hash(self):
        self.mutate(lambda d: d["records"][3].update(original_html_raw_sha256="a" * 64))
        self.mutate(lambda d: d["records"][10].update(
            first_issuer_sa_index_level_CUSR0000SA0=315.22))

    def test_incomplete_24_prior_calendar_periods_never_closed_with_proxy(self):
        self.mutate(lambda d: d["records"][13].update(
            source_evidence_level="HTML_OPENED", publisher_release_day="2025-11-13",
            issuer_archived_html_url="https://www.bls.gov/news.release/archives/cpi_11132025.htm",
            first_issuer_reported_sa_all_items_change_pct_rounded_1dp=0.2,
            sa_change_horizon_months=1))
        self.mutate(lambda d: d["records"].append(copy.deepcopy(d["records"][-1])))
        self.mutate(lambda d: d["records"].reverse())

    def test_metric_identity_and_dates_cannot_be_relabelled(self):
        self.mutate(lambda d: d.update(bls_sa_issuer_series="CUUR0000SA0"))
        self.mutate(lambda d: d.update(intended_canonical_series="CPILFESL"))
        self.mutate(lambda d: d["records"][0].update(
            issuer_archived_html_url="https://www.bls.gov/news.release/cpi.htm"))
        self.mutate(lambda d: d["records"][0].update(publisher_release_day="2024-09-10"))
        self.mutate(lambda d: d["records"][1].update(
            first_issuer_reported_sa_all_items_change_pct_rounded_1dp=0.24))
        with self.assertRaises(ValueError):
            audit(cutoff="2025-11-01T23:59:59Z")

    def test_strict_read_only_and_deterministic_receipt(self):
        base = ROOT / "live_data/sections"
        protected = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {f: (base / f).read_bytes() for f in protected}
        other = audit()
        self.assertEqual(other["receipt_sha256"], self.result["receipt_sha256"])
        after = {f: (base / f).read_bytes() for f in protected}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
