#!/usr/bin/env python3
"""Prevent 29-Oct 08:00 source-vintage regressions in prebrief and Pages CI.

This is *not* a synthetic market-data generator, timing guarantee, or a
replacement for source/PIT gates. It protects two already-fixed regressions:
(1) synthetic morning data must not demand an old AUD live publication month;
(2) Pages must source-verify official future events instead of pinning 8
macro currency schedules when the published calendar has partial coverage.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MORNING_TEST = ROOT / "validation/orchestration/test_check_morning_readiness_v1.py"
ORCHESTRATOR = ROOT / ".github/workflows/daily-data-orchestrator-v2.yml"
PAGES = ROOT / ".github/workflows/publish-dashboard-pages-v1.yml"
VERIFIER = ROOT / "validation/calendar/verify_future_macro_coverage_v1.py"


def enforce(morning: str, pages: str, orchestration: str, verifier: str) -> None:
    def require(ok: bool, msg: str) -> None:
        if not ok:
            raise ValueError("MORNING_0800_SOURCE_REGRESSION: " + msg)

    require("MACRO_FIXTURE_PERIODS" in morning
            and 'data["MACRO_THERMOMETER_DATA.json"]["currencies"][ccy][pillar]' in morning,
            "fixed October-23 synthetic scenario must set its own observed months")
    require('live_thermometer = read_feeds()["MACRO_THERMOMETER_DATA.json"]' in morning
            and 'live_evidence = inspect(live_probe, live_now)' in morning
            and 'live_evidence["rows"]["AUD.inflation"]["reference_period"] == (' in morning
            and 'live_thermometer["currencies"]["AUD"]["inflation"]["as_of"]' in morning,
            "live Australian CPI period must be verified against live source, never last month's fixture")
    # An old inline assertion on the *real* source blocked every scheduled
    # child on 29-Oct, despite a successful newer official ABS release.
    require(not re.search(
        r'live_evidence\["rows"\]\["AUD\.inflation"\]\["reference_period"\]\s*==\s*["\']20\d\d-\d\d',
        morning),
        "real AUD monthly source is frozen to obsolete reference period")
    require('Test morning freshness and DST-aware source windows' in orchestration
            and 'python validation/orchestration/test_check_morning_readiness_v1.py' in orchestration
            and 'Certify 08:00 morning delivery deadline' in orchestration,
            "orchestrator must retain source-aware tests and actual 08:00 SLA check")
    require('from validation.calendar.verify_future_macro_coverage_v1 import verify as verify_future' in pages
            and 'future=verify_future(cal,seed,cb_source,datetime.now(timezone.utc))' in pages
            and 'print(\'CALENDAR_FUTURE_COVERAGE_SOURCE_PARITY\',future)' in pages,
            "Pages must validate event dates from the approved official future registry")
    # The earlier exact '8' bound failed when the official calendar was
    # genuinely partial; retaining coverage as information is not permission
    # to invent missing publisher schedules.
    require(not re.search(r"cal\s*\[\s*['\"]coverage['\"]\s*\]\s*\[\s*['\"]macro_ccy_coverage['\"]\s*\]\s*==\s*8", pages)
            and not re.search(r"cal\s*\[\s*['\"]coverage['\"]\s*\]\s*\[\s*['\"]upcoming_macro_events['\"]\s*\]\s*>=\s*8", pages),
            "Pages falsely insists all eight economies have source-backed scheduled macro events")
    require("no_core" in verifier or "source" in verifier.lower(),
            "official future coverage must remain backed by source checks")
    require('PAGES_PUBLIC_HTTP_PROOF' in pages
            and 'PAGES_INDEPENDENT_0800_SLA' in pages,
            "do not mistake a green runner for public HTTP/08:00 proof")


class MorningSourceDriftContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.morning = MORNING_TEST.read_text(encoding="utf-8")
        cls.pages = PAGES.read_text(encoding="utf-8")
        cls.orchestration = ORCHESTRATOR.read_text(encoding="utf-8")
        cls.verifier = VERIFIER.read_text(encoding="utf-8")

    def check(self, morning=None, pages=None, orchestration=None):
        enforce(morning if morning is not None else self.morning,
                pages if pages is not None else self.pages,
                orchestration if orchestration is not None else self.orchestration,
                self.verifier)

    def test_actual_two_production_paths_are_source_dynamic(self):
        self.check()

    def test_regression_old_pages_exact_8_currency_assertion_rejected(self):
        with self.assertRaisesRegex(ValueError, "falsely insists"):
            self.check(pages=self.pages +
                       "\nassert cal['coverage']['macro_ccy_coverage']==8\n")

    def test_regression_old_pages_event_count_floor_rejected(self):
        with self.assertRaisesRegex(ValueError, "falsely insists"):
            self.check(pages=self.pages +
                       "\nassert cal['coverage']['upcoming_macro_events']>=8\n")

    def test_regression_old_aud_live_month_rejected(self):
        with self.assertRaisesRegex(ValueError, "frozen to obsolete"):
            self.check(morning=self.morning +
                       '\nassert live_evidence["rows"]["AUD.inflation"]["reference_period"] == "2026-06"\n')

    def test_regression_missing_source_coverage_verification_rejected(self):
        with self.assertRaisesRegex(ValueError, "validate event dates"):
            self.check(pages=self.pages.replace(
                "future=verify_future(cal,seed,cb_source,datetime.now(timezone.utc))",
                "future={'status':'SKIPPED'}"))

    def test_regression_missing_real_delivery_proof_rejected(self):
        with self.assertRaisesRegex(ValueError, "public HTTP"):
            self.check(pages=self.pages.replace("PAGES_PUBLIC_HTTP_PROOF",
                                                "HTTP_CHECK_REMOVED"))


if __name__ == "__main__":
    unittest.main()
