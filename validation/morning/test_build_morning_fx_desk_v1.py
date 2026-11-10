#!/usr/bin/env python3
"""Contract checks for the Morning Macro/FX reader: no hindsight or fabricated signals."""
import copy
from datetime import date, datetime, timezone
from pathlib import Path
import unittest

from validation.morning.build_morning_fx_desk_v1 import (
    ROOT, build, validate, choose_event, fmt, get_pair_price, to_date
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
        self.assertNotIn("actual +0,4", " ".join(x["paragraphs"]).lower())

    def test_day_after_cpi_without_certified_actual(self):
        x=build(ROOT,date(2026,11,11),datetime(2026,11,11,7,15,tzinfo=timezone.utc))
        self.assertIn(x["event_status"],{"AFTERMATH_UNVERIFIED","AFTERMATH_TO_VERIFY"})
        self.assertIn("CPI",x["headline"])
        self.assertIn("verifica",x["catalyst"]["text"])
        self.assertEqual(x["edition_status"],"MORNING_SNAPSHOT")
        self.assertLess(x["sources"]["fx_fixing"],"2026-11-11")

    def test_upcoming_uk_growth(self):
        x=build(ROOT,date(2026,11,12),datetime(2026,11,12,7,10,tzinfo=timezone.utc))
        self.assertEqual(x["event_status"],"EVENT_TODAY")
        self.assertEqual(x["pair"],"GBPUSD")
        self.assertIn("GDP",x["headline"])
        self.assertIn("08:00",x["catalyst"]["title"])
        self.assertLess(x["sources"]["rates"],"2026-11-12")
        self.assertEqual(len(x["charts"]),2)

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

    def test_time_and_pair_arithmetic(self):
        self.assertEqual(to_date("not-a-date"),None)
        self.assertEqual(fmt(162.08,0),"162")
        self.assertAlmostEqual(get_pair_price({"USD":1.2,"JPY":180},"USDJPY"),150)
        self.assertEqual(choose_event({"events":[]},date(2026,11,11))[1],"RELATIVE_PRICING")

if __name__=="__main__":
    unittest.main()
