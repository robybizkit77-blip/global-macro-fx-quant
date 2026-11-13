"""Hermetic final-report catalogue and byte-for-byte public delivery tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from validation.publishing.check_next_research_library_delivery_v1 import (
    DIRECTORY, ROOT, latest, parse_date, report_type, run,
)

NAMES = (
    "Briefing_Forex_Commodities_2026-11-13_V3_MORNING_RESEARCH_DESK.html",
    "Weekly_Global_Macro_Report_2026-11-06_COUNTRY_BOOK_NARRATIVO_V4_CORRETTA.html",
    "Weekly_Bank_FX_Report_2026-11-06_DARK_DESK_NARRATIVO_V5.html",
    "Weekly_CB_Sentiment_Report_2026-11-06_DARK_RESEARCH_DESK_WANT_CAN_V4_PALETTE.html",
    "Weekly_CB_Pricing_G8_2026-11-06_V7_CONFRONTO_31OTT_06NOV.html",
    "COT_FX_G8_03_NOV_2026_DARK_QUANT_DESK_v10_DEFINITIVO_LETTURA_INTEGRATA.html",
    "Weekly_Global_Macro_Strength_Cross_Asset_2026-10-17_DARK_EDITORIAL_PRO_CLEAN.html",
    "Weekly_FX_Pair_Selection_Conviction_2026-10-17.html",
)


def write(root, name, body=None):
    p = root / DIRECTORY / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body or "<!DOCTYPE html><html><head><title>Original</title></head><body>" +
                 ("macro source audit " * 125) + "</body></html>", encoding="utf-8")


class ReportDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in NAMES:
            write(self.root, name)

    def test_actual_canonical_reports_are_complete(self):
        report = latest(ROOT, "2026-11-13")
        self.assertEqual(report["canonical_categories"], 8)
        self.assertEqual(report["latest_daily"], "2026-11-13")
        self.assertEqual(len(report["latest"]), 8)
        self.assertTrue(all(x["bytes"] > 1000 for x in report["latest"]))

    def test_eight_latest_sources_and_cot_reference_date(self):
        report = latest(self.root, "2026-11-13")
        self.assertEqual(len(report["latest"]), 8)
        self.assertEqual(report["latest_daily"], "2026-11-13")
        self.assertEqual(parse_date(NAMES[5]), "2026-11-03")
        self.assertEqual(report_type(NAMES[4]), "ois")

    def test_newer_unapproved_partial_or_future_never_replaces_latest(self):
        write(self.root, "Weekly_Central_Bank_Pricing_G8_2026-11-12_V8_DATI_PARZIALI.html")
        write(self.root, "Briefing_Forex_Commodities_2026-11-14_V4_DEFINITIVO.html")
        write(self.root, "Briefing_Forex_Commodities_2026-11-13_V99_PROVA.html")
        report = latest(self.root, "2026-11-13")
        self.assertEqual(report["latest_daily"], "2026-11-13")
        self.assertEqual(next(x for x in report["latest"] if x["type"] == "ois")["reference_date"],
                         "2026-11-06")

    def test_new_valid_approved_edition_wins_without_duplicate_cards(self):
        new = "Weekly_Central_Bank_Pricing_G8_2026-11-12_V8_DEFINITIVO.html"
        write(self.root, new)
        selected = latest(self.root, "2026-11-13")["latest"]
        self.assertEqual(len(selected), 8)
        self.assertEqual(next(x for x in selected if x["type"] == "ois")["filename"], new)

    def test_invalid_html_in_new_final_is_blocked(self):
        write(self.root, "Briefing_Forex_Commodities_2026-11-13_V5_DEFINITIVO.html",
              "<html>broken")
        with self.assertRaisesRegex(ValueError, "INVALID_FINAL_HTML"):
            latest(self.root, "2026-11-13")

    def test_missing_canonical_category_is_blocked(self):
        (self.root / DIRECTORY / NAMES[-1]).unlink()
        with self.assertRaisesRegex(ValueError, "RESEARCH_LIBRARY_CATEGORIES_MISSING"):
            latest(self.root, "2026-11-13")

    def test_http_proof_is_actual_byte_comparison_not_repo_badge(self):
        proof = {"status": "PASS", "checks": [
            {"path": (DIRECTORY / name).as_posix(),
             "http_200_and_sha256_match": True} for name in NAMES]}
        with patch("validation.publishing.check_next_research_library_delivery_v1.verify",
                   return_value=proof) as check:
            result = run(self.root, http=True, today="2026-11-13")
        self.assertEqual(result["status"], "LATEST_8_PUBLIC_HTTP_EXACT_PASS")
        self.assertEqual(len(check.call_args.args[2]), 8)
        self.assertFalse(result["automatic_chatgpt_to_github_transfer_certified"])
        self.assertFalse(result["market_source_freshness_certified"])

    def test_http_mismatch_remains_a_failure(self):
        with patch("validation.publishing.check_next_research_library_delivery_v1.verify",
                   return_value={"status": "FAIL", "checks": []}):
            result = run(self.root, http=True, today="2026-11-13")
        self.assertEqual(result["status"], "LATEST_8_PUBLIC_HTTP_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
