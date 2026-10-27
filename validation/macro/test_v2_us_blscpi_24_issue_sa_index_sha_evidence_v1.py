"""Adversarial tests: late captured BLS issue-month CPI SA index and 12m base."""
from __future__ import annotations
import copy
import json
import unittest
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_us_blscpi_24_issue_sa_index_sha_evidence_v1 import (
    PATH, SCHEMA, audit
)

class BLSExactSAIndexSourceQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(PATH.read_text(encoding="utf-8"))
        cls.baseline=audit()

    def mutate(self,change):
        source=copy.deepcopy(self.doc)
        change(source)
        with self.assertRaises(ValueError):
            audit(fixture=source)

    def test_24_real_issuer_month_sa_indices_bases_and_missing_october(self):
        d=self.baseline
        self.assertEqual(d["schema"],SCHEMA)
        self.assertEqual(len(d["records"]),25)
        self.assertEqual(d["summary"]["published_month_workbooks_captured"],24)
        self.assertEqual(d["summary"]["exact_SA_index_and_12m_base_candidates"],24)
        self.assertEqual(d["summary"]["ALFRED_release_date_anchor_matches"],7)
        self.assertEqual(d["summary"]["original_issuer_day_byte_certifications"],0)
        self.assertTrue(d["cannot_claim_strict_consecutive_24m_training"])
        self.assertTrue(d["2025_10_unpublished_BLS_all_items_index_still_missing"])
        october=d["records"][13]
        self.assertEqual(october["economic_month"],"2025-10")
        self.assertIsNone(october["SA_index_at_issue"])
        self.assertIsNone(october["raw_xlsx_sha256"])
        self.assertEqual(d["records"][14]["economic_month"],"2025-11")
        self.assertEqual(d["records"][-1]["SA_index_at_issue"],"336.298")
        self.assertEqual(d["records"][-1]["same_issue_SA_12m_base"],"324.245")
        for field in ("safe_to_publish_new_D","safe_to_change_28_pairs",
                      "safe_for_beta","safe_for_forward","writes_live_data"):
            self.assertFalse(d[field])

    def test_2025_gap_cannot_be_imputed_or_forged_as_publication(self):
        self.mutate(lambda d:d["records"][13].update(SA_index_at_issue="324.500"))
        self.mutate(lambda d:d["records"][13].update(raw_xlsx_sha256="a"*64))
        self.mutate(lambda d:d["records"][13].update(
            evidence_quality="ORIGINAL_PUBLISHER_ISSUE_MONTH_FILENAME_BINARY_CAPTURED_2026_10_27_NOT_ON_RELEASE_DAY"))
        self.mutate(lambda d:d["records"].pop(13))
        self.mutate(lambda d:d["records"].reverse())

    def test_sa_index_and_same_issuer_vintage_basis_required(self):
        self.mutate(lambda d:d["records"][14].update(SA_index_at_issue="324.122"))
        self.mutate(lambda d:d["records"][14].update(same_issue_SA_12m_base="316.000"))
        self.mutate(lambda d:d["records"][14].update(SA_index_yoy_pct_same_issue="2.700000"))
        self.mutate(lambda d:d["records"][14].update(SA_index_at_issue="325.0317"))
        self.mutate(lambda d:d["records"][14].update(SA_index_at_issue=325.031))
        self.mutate(lambda d:d["records"][14].update(source_url="https://fred.stlouisfed.org/series/CPIAUCSL"))
        self.mutate(lambda d:d["records"][14].update(raw_xlsx_sha256="bad-hash"))
        self.mutate(lambda d:d["records"][14].update(publisher_release_day="2025-11-01"))

    def test_later_revised_archive_never_claimed_historically_captured_pit(self):
        self.mutate(lambda d:d.update(original_issuer_day_HTTP_capture_not_proven=False))
        self.mutate(lambda d:d.update(prior_24_calendar_first_release_contiguous_PIT_ready=True))
        self.mutate(lambda d:d.update(pit_backtest_or_live_score_approved=True))
        self.mutate(lambda d:d["records"][14].update(evidence_quality="CERTIFIED_PIT"))
        self.mutate(lambda d:d.update(safe_to_publish_new_D=True))
        self.mutate(lambda d:d.update(run_url="https://example.com/fake"))

    def test_fed_mirror_cannot_be_relabelled_original_or_changed(self):
        self.mutate(lambda d:d["ALFRED_7_independent_same_release_page_anchor_checks"][0].update(
            bls_index_SA="315.455"))
        self.mutate(lambda d:d["ALFRED_7_independent_same_release_page_anchor_checks"][0].update(match=False))
        self.mutate(lambda d:d["ALFRED_7_independent_same_release_page_anchor_checks"].pop())
        self.mutate(lambda d:d["records"][1].update(SA_index_at_issue="315.455"))

    def test_deterministic_read_only_guard(self):
        files=ROOT/"live_data/sections"
        names=["D.json","PAIR_SETUP_OPERATIONAL_VIEW.json"]
        before={n:(files/n).read_bytes() for n in names}
        again=audit()
        after={n:(files/n).read_bytes() for n in names}
        self.assertEqual(self.baseline["receipt_sha256"],again["receipt_sha256"])
        self.assertEqual(before,after)

if __name__=="__main__":
    unittest.main()
