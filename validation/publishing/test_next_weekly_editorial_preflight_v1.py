"""Four Sunday reports: test source/date discipline, not simulated production."""
from datetime import date
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from validation.publishing.check_next_weekly_editorial_preflight_v1 import (
    ROOT, DIRECTORY, TEMPLATES, check_edition, scan,
)


class SundayEditorialPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / DIRECTORY).mkdir(parents=True)
        for _, template, _ in TEMPLATES.values():
            shutil.copyfile(ROOT / DIRECTORY / template, self.root / DIRECTORY / template)

    def candidate(self, category, *, extra=None):
        prefix, template, _ = TEMPLATES[category]
        name = {
            "bank": "Weekly_Bank_FX_Report_2026-11-13_DARK_DESK_NARRATIVO_V5.html",
            "cb": "Weekly_CB_Sentiment_Report_2026-11-13_DARK_RESEARCH_DESK_WANT_CAN_V4_PALETTE.html",
            "cross": "Weekly_Global_Macro_Strength_Cross_Asset_2026-11-13_DARK_EDITORIAL_PRO_CLEAN.html",
            "pairs": "Weekly_FX_Pair_Selection_Conviction_2026-11-13.html",
        }[category]
        src = (self.root / DIRECTORY / template).read_text(encoding="utf-8")
        src = src.replace("6 novembre 2026", "13 novembre 2026")
        src = src.replace("17 ottobre 2026", "13 novembre 2026")
        src = src.replace("6 NOVEMBRE 2026", "13 NOVEMBRE 2026")
        src = src.replace("17 OCT 2026", "13 NOV 2026")
        src = src.replace("2026-10-17", "2026-11-13")
        src = src.replace("2026-11-06", "2026-11-13")
        if extra is None:
            extra = (
                "<p>" + "Aggiornamento verificabile della seduta, "
                "driver macro, controprova, cambiamento di tassi e prezzo. " * 105
                + "</p><p>Fonti: <a href='https://www.ecb.europa.eu/'>BCE</a> "
                "<a href='https://www.federalreserve.gov/'>Fed</a>; "
                "la fonte non certifica automaticamente la relazione causale.</p>"
            )
        if category == "pairs":
            extra += "<p>EUR/GBP e AUD/CAD e CAD/JPY: view, setup, invalidazione e price trigger.</p>"
        src = re.sub(r"</body\s*>", extra + "</body>", src, flags=re.I)
        path = self.root / DIRECTORY / name
        path.write_text(src, encoding="utf-8")
        return path

    def test_current_repo_is_not_mistaken_for_four_generated_weekly_reports(self):
        result = scan(ROOT, date(2026, 11, 13))
        self.assertEqual(result["status"], "WEEKLY_STRUCTURAL_PREFLIGHT_ONLY")
        self.assertEqual(result["expected_new_types"], 4)
        self.assertEqual(result["new_files_validated"] +
                         result["new_types_not_yet_produced"], 4)
        self.assertFalse(result["report_generation_certified"])
        self.assertFalse(result["transfer_from_chatgpt_certified"])

    def test_new_sunday_reports_can_pass_structural_source_preflight(self):
        for category in TEMPLATES:
            with self.subTest(category=category):
                candidate = self.candidate(category)
                result = check_edition(self.root, category, candidate, date(2026, 11, 15))
                self.assertEqual(result["status"], "STRUCTURAL_EDITORIAL_PREFLIGHT_PASS")
                self.assertEqual(result["reference_friday"], "2026-11-13")
                self.assertFalse(result["visual_match_certified"])
                self.assertFalse(result["market_facts_verified"])

    def test_date_only_clone_cannot_be_passed_off_as_new_research(self):
        p = self.candidate("bank", extra="")
        with self.assertRaisesRegex(ValueError, "REPORT_DATE_ONLY_REPRINT"):
            check_edition(self.root, "bank", p, date(2026, 11, 15))

    def test_incorrect_title_date_is_blocked(self):
        p = self.candidate("cb")
        content = p.read_text(encoding="utf-8")
        content = content.replace("<title>Weekly Central Bank Sentiment · 13 novembre 2026",
                                  "<title>Weekly Central Bank Sentiment · 6 novembre 2026")
        p.write_text(content, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "TITLE_REFERENCE_DATE_MISMATCH"):
            check_edition(self.root, "cb", p, date(2026, 11, 15))

    def test_nonfriday_or_future_reference_date_is_blocked(self):
        p = self.candidate("cross")
        thursday = p.with_name(p.name.replace("2026-11-13", "2026-11-12"))
        shutil.copyfile(p, thursday)
        with self.assertRaisesRegex(ValueError, "NOT_A_CLOSED_FRIDAY_WEEK"):
            check_edition(self.root, "cross", thursday, date(2026, 11, 15))
        with self.assertRaisesRegex(ValueError, "WEEKLY_DATE_IN_FUTURE"):
            check_edition(self.root, "cross", p, date(2026, 11, 12))

    def test_unapproved_draft_is_rejected_before_publication(self):
        p = self.candidate("bank")
        draft = p.with_name(p.name.replace(".html", "_PROVA.html"))
        shutil.copyfile(p, draft)
        with self.assertRaisesRegex(ValueError, "UNAPPROVED_WEEKLY_FILENAME"):
            check_edition(self.root, "bank", draft, date(2026, 11, 15))

    def test_source_reference_missing_is_not_silently_accepted(self):
        p = self.candidate("cb")
        s = re.sub(r"""href\s*=\s*['"]https?://[^'"]+['"]""",
                   "href='#'", p.read_text(encoding="utf-8"), flags=re.I)
        p.write_text(s, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ATTRIBUTABLE_SOURCE_LINKS_MISSING"):
            check_edition(self.root, "cb", p, date(2026, 11, 15))

    def test_absence_remains_not_produced_even_if_schedules_exist(self):
        r = scan(self.root, date(2026, 11, 15))
        self.assertEqual(r["new_files_validated"], 0)
        self.assertEqual(r["new_types_not_yet_produced"], 4)
        p = self.candidate("pairs")
        r = scan(self.root, date(2026, 11, 15))
        self.assertEqual(r["new_files_validated"], 1)
        self.assertEqual(r["new_types_not_yet_produced"], 3)
        self.assertFalse(r["transfer_from_chatgpt_certified"])


if __name__ == "__main__":
    unittest.main()
