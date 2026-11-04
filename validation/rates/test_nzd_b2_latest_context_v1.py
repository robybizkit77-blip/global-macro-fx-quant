"""Fail-closed source/read-only boundary for latest NZD B2 web context."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "live_data/sections/NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json"

class TestNZDWebContext(unittest.TestCase):
    def test_latest_is_visible_as_context_only(self):
        d = json.loads(PATH.read_text(encoding="utf-8"))
        self.assertEqual(d["schema"], "GMFQ_NZD_B2_GOVT_WEB_REVIEW_CONTEXT_V1")
        self.assertEqual(d["as_of"], "2026-10-22")
        self.assertEqual(d["status"], "TWO_WEB_READS_MATCH__UNAPPROVED_RESEARCH_ONLY")
        x=d["latest_official_web_context"]
        self.assertEqual(x["as_of"], "2026-11-02")
        self.assertEqual((x["government_bond_2y_pct"],x["government_bond_10y_pct"]),(3.97,4.91))
        self.assertEqual(x["quoted_curve_bp"],round((4.91-3.97)*100))
        self.assertEqual(x["benchmarks"]["roll_date"],"2026-10-30")
        self.assertNotEqual(x["benchmarks"]["two_year_before"],x["benchmarks"]["two_year_from"])
        self.assertNotEqual(x["benchmarks"]["ten_year_before"],x["benchmarks"]["ten_year_from"])
        self.assertTrue(x["guards"]["official_canonical_untouched"])
        for k in ("same_instrument_weekly_change_allowed","cross_roll_bp_change_allowed",
                  "eligible_for_rate_spreads","eligible_for_OIS","eligible_for_live_pair_signals",
                  "eligible_for_backtests","independent_xlsx_review_completed"):
            self.assertFalse(x["guards"][k],k)
        for k in ("eligible_for_rate_spreads","eligible_for_automatic_promotion",
                  "live_data_promotion_allowed"):
            self.assertFalse(d["governance"][k],k)

if __name__=="__main__":
    unittest.main()
