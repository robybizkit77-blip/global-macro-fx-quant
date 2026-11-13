#!/usr/bin/env python3
"""Contract checks for the Morning Macro/FX reader: no hindsight or fabricated signals."""
import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from validation.morning import build_morning_fx_desk_v1 as desk
from validation.macro import capture_us_cpi_exact_actuals_v10 as v10
from validation.macro.test_capture_us_cpi_exact_actuals_v10 import PARTIAL, AFTER, SEEN
from validation.macro.freeze_exact_metric_forecasts_v9 import read_rows

from validation.morning.build_morning_fx_desk_v1 import (
    ROOT, build, validate, choose_event, fmt, signed, get_pair_price, to_date, skipped_market_sessions
)

class MorningFXDeskTests(unittest.TestCase):
    def test_event_day_before_cpi(self):
        x=build(ROOT,date(2026,11,10),datetime(2026,11,10,20,0,tzinfo=timezone.utc))
        self.assertEqual(x["schema"],"GMFQ_MORNING_MACRO_FX_V1")
        self.assertEqual(x["event_status"],"EVENT_TODAY")
        self.assertEqual(x["pair"],"EURUSD")
        self.assertIn("CPI",x["headline"])
        self.assertIn("14:30",x["catalyst"]["title"])
        self.assertEqual(x["sources"]["fx_fixing"],"2026-11-09")
        self.assertLess(x["sources"]["rates"],"2026-11-10")
        self.assertFalse(x["eligible_for_fx_signal"])
        self.assertEqual(x["edition_status"],"RECONSTRUCTION_NOT_POINT_IN_TIME")
        self.assertEqual(len(x["charts"]),2)
        self.assertTrue(len(x["paragraphs"][0])>110)
        self.assertIn("USD/JPY",x["paragraphs"][3])
        self.assertIn("stesse date",x["paragraphs"][1])
        self.assertEqual(x["relative_evidence"]["companion_pair"],"USDJPY")
        self.assertNotIn("actual +0,4", " ".join(x["paragraphs"]).lower())

    def test_day_after_cpi_without_certified_actual(self):
        x=build(ROOT,date(2026,11,11),datetime(2026,11,11,7,15,tzinfo=timezone.utc))
        self.assertIn(x["event_status"],{"AFTERMATH_UNVERIFIED","AFTERMATH_TO_VERIFY",
                                         "AFTERMATH_MONTHLY_ONLY_YOY_UNAVAILABLE"})
        self.assertIn("CPI",x["headline"])
        if x["event_status"]=="AFTERMATH_UNVERIFIED":
            self.assertIn("non sono ancora presenti misure BLS",x["catalyst"]["text"])
        elif x["event_status"]=="AFTERMATH_MONTHLY_ONLY_YOY_UNAVAILABLE":
            self.assertIn("non sono pubblicabili", x["catalyst"]["text"])
        else:
            self.assertIn("registro conserva quattro",x["catalyst"]["text"])
        self.assertEqual(x["edition_status"],"MORNING_SNAPSHOT")
        self.assertLess(x["sources"]["fx_fixing"],"2026-11-11")

    def test_real_monthly_cpi_post_release_can_be_used_without_yoy_fabrication(self):
        forecasts = read_rows(v10.FORECAST_LEDGER)
        rows, receipt = v10.capture(
            forecasts, [], AFTER, fetch=lambda url, host: (PARTIAL,url),
            observed_clock=lambda: SEEN)
        self.assertEqual(len(rows),2)
        with tempfile.TemporaryDirectory() as tmp:
            actual_path = Path(tmp)/"first_observed.jsonl"
            actual_path.write_text(
                "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),
                encoding="utf-8")
            with patch.dict(desk.FILES,{"actual":str(actual_path)}):
                report = build(ROOT,date(2026,11,11),
                               datetime(2026,11,11,7,15,tzinfo=timezone.utc))
        self.assertEqual(report["event_status"],
                         "AFTERMATH_MONTHLY_ONLY_YOY_UNAVAILABLE")
        self.assertIn("+0,4%",report["paragraphs"][2])
        self.assertIn("+0,3%",report["paragraphs"][2])
        self.assertIn("non sono pubblicabili",report["paragraphs"][2])
        self.assertFalse(report["eligible_for_fx_signal"])

    def test_upcoming_uk_growth(self):
        x=build(ROOT,date(2026,11,12),datetime(2026,11,12,7,10,tzinfo=timezone.utc))
        self.assertEqual(x["event_status"],"EVENT_TODAY")
        self.assertEqual(x["pair"],"GBPUSD")
        self.assertIn("PIL",x["headline"])
        self.assertIn("rialzo di 25 punti base",x["paragraphs"][0])
        self.assertIn("BoE",x["lead"])
        self.assertIn("GBP/USD",x["paragraphs"][3])
        self.assertIn("08:00",x["catalyst"]["title"])
        self.assertLess(x["sources"]["rates"],"2026-11-12")
        self.assertEqual(len(x["charts"]),2)

    def test_quiet_day_without_fake_calendar_catalyst(self):
        x=build(ROOT,date(2026,11,11),datetime(2026,11,11,7,0,tzinfo=timezone.utc),
                event_seed={"events":[]})
        self.assertEqual(x["event_status"],"RELATIVE_PRICING")
        self.assertIsNone(x["catalyst"]["date"])
        self.assertIn("spread",x["lead"])
        self.assertIn("EUR/USD",x["headline"])
        self.assertIn("non forziamo",x["paragraphs"][2].lower())
        self.assertLess(x["sources"]["rates"],x["edition_date"])

    def test_event_scenarios_are_distinct_and_specific(self):
        days=[((2026,11,10),None),((2026,11,11),None),
              ((2026,11,12),None),((2026,11,11),{"events":[]})]
        reports=[build(ROOT,date(*part),datetime(*part,7,0,tzinfo=timezone.utc),
                       event_seed=seed) for part,seed in days]
        titles=[tuple(s["title"] for s in r["scenarios"]) for r in reports]
        self.assertEqual(len(set(titles)),4,
                         "Two generic scenarios repeated across every macro regime")
        self.assertTrue(all(r["relative_evidence"]["aligned_from"] <
                            r["relative_evidence"]["aligned_to"] < r["edition_date"]
                            for r in reports))
        self.assertTrue(all(r["relative_evidence"]["alignment"] in
                            ("COERENTE","DIVERGENTE","NON_CONCLUSIVO")
                            for r in reports))
        self.assertTrue(all("Verifica" not in r["headline"] for r in reports))
        for r in reports:
            self.assertIn(r["pair"][:3]+"/"+r["pair"][3:],r["paragraphs"][3])
            self.assertNotEqual(r["scenarios"][0]["text"],r["scenarios"][1]["text"])

    def test_editorial_cross_regime_trace(self):
        # Short human-reviewable evidence for what the actual generator says,
        # not just green structural test counts.
        cases=[((2026,11,10),None),((2026,11,11),None),
               ((2026,11,12),None),((2026,11,11),{"events":[]})]
        for part,seed in cases:
            x=build(ROOT,date(*part),datetime(*part,7,0,tzinfo=timezone.utc),
                    event_seed=seed)
            print("MORNING_EDITORIAL_EXAMPLE "+json.dumps({
                "day":x["edition_date"],"stage":x["event_status"],
                "headline":x["headline"],"lead":x["lead"],
                "paragraphs":x["paragraphs"],"catalyst":x["catalyst"]["title"],
                "scenarios":x["scenarios"],"verdict":x["verdict"],
                "evidence":x["relative_evidence"],"sources":x["sources"]},
                ensure_ascii=False),flush=True)

    def test_13_nov_us_producer_prices_is_main_catalyst(self):
        # Regression: the source schedule must outrank an unrelated EUR/USD 2Y
        # comparison. Never publish "no official data today" with a HIGH PPI.
        x=build(ROOT,date(2026,11,13),
                datetime(2026,11,13,7,20,tzinfo=timezone.utc))
        self.assertEqual(x["event_status"],"EVENT_TODAY")
        self.assertEqual(x["catalyst"]["date"],"2026-11-13")
        self.assertEqual(x["catalyst"]["time_rome"],"14:30")
        self.assertIn("Producer Price Index",x["headline"])
        self.assertNotIn("Nessun dato domina",x["lead"])
        self.assertFalse(x["eligible_for_fx_signal"])

    def test_stale_friday_is_blocked_and_provisional_swiss_is_not_promoted(self):
        # Fixed-date arithmetic, not dependent on tomorrow's updated live JSON.
        # Tue 10 -> Fri 13 has two completed missing weekdays (Wed/Thu).
        self.assertEqual(skipped_market_sessions("2026-11-10",date(2026,11,13)),2)
        # Mon 9 -> Fri 13 has three missing weekdays (Tue/Wed/Thu).
        self.assertEqual(skipped_market_sessions("2026-11-09",date(2026,11,13)),3)
        seed={"events":[{"ccy":"CHF","date":"2026-11-16",
                         "event_type":"GROWTH","importance":"HIGH",
                         "quality":"OFFICIAL_PROVISIONAL"}]}
        self.assertEqual(choose_event(seed,date(2026,11,13))[1],"RELATIVE_PRICING")

    def test_small_spread_not_negative_zero(self):
        self.assertEqual(signed(-0.313,0," pb"),"−0,3 pb")
        self.assertEqual(signed(0,0," pb"),"0 pb")
        x=build(ROOT,date(2026,11,12),datetime(2026,11,12,7,0,tzinfo=timezone.utc))
        self.assertNotIn("−0 punti base",x["paragraphs"][1])
        self.assertIn(x["charts"][0]["precision"],(0,1))

    def test_no_forecast_promoted_to_market_surprise(self):
        x=build(ROOT,date(2026,11,10),datetime(2026,11,10,7,0,tzinfo=timezone.utc))
        t=" ".join(x["paragraphs"])
        self.assertIn("non sono un consenso da survey certificato",t)
        self.assertNotIn("sorpresa verificata",t.lower())

    def test_inconsistent_or_future_chart_rejected(self):
        x=build(ROOT,date(2026,11,10),datetime(2026,11,10,7,0,tzinfo=timezone.utc))
        y=copy.deepcopy(x)
        y["charts"][0]["points"][-1]["date"]="2026-11-10"
        with self.assertRaises(ValueError):validate(y)
        z=copy.deepcopy(x)
        z["charts"][0]["points"][-1]["value"]=float("nan")
        with self.assertRaises(ValueError):validate(z)

    def test_future_source_does_not_leak(self):
        x=build(ROOT,date(2026,11,10),datetime(2026,11,10,7,0,tzinfo=timezone.utc))
        self.assertTrue(all(row["date"]<x["edition_date"] for c in x["charts"] for row in c["points"]))
        self.assertLess(x["charts"][1]["as_of"],x["edition_date"])
        self.assertAlmostEqual(x["charts"][1]["last_value"],x["charts"][1]["points"][-1]["value"],places=6)

    def test_production_builder_cli_resolves_validation_package(self):
        # Unit imports alone missed a production-only ModuleNotFoundError.
        # Exercise the same -m entrypoint used by the publishing workflow.
        import subprocess
        import sys
        workflow = (ROOT / ".github/workflows/fxv2-morning-public-proof.yml").read_text(encoding="utf-8")
        self.assertIn("python3 -m validation.morning.build_morning_fx_desk_v1", workflow)
        self.assertNotIn("python3 validation/morning/build_morning_fx_desk_v1.py", workflow)
        proc = subprocess.run([sys.executable, "-m",
                               "validation.morning.build_morning_fx_desk_v1", "--help"],
                              cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--edition-date", proc.stdout)

    def test_time_and_pair_arithmetic(self):
        self.assertEqual(to_date("not-a-date"),None)
        self.assertEqual(fmt(162.08,0),"162")
        self.assertAlmostEqual(get_pair_price({"USD":1.2,"JPY":180},"USDJPY"),150)
        self.assertEqual(choose_event({"events":[]},date(2026,11,11))[1],"RELATIVE_PRICING")

if __name__=="__main__":
    unittest.main()
