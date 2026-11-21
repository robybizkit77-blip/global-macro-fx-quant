import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from validation.calendar.refresh_official_release_dates_v1 import (
    ABS, BEA, BEA_NEXT, ROME, SECO_FLASH, SECO_GDP,
    apply_rows, parse_abs, parse_bea, parse_seco, refresh, scheduled,
)

NOW = datetime.fromisoformat("2026-11-21T20:00:00+01:00")


def bea(year, title, date, extra_column=""):
    return f'''<table id="release-schedule-table">
      <thead><tr><th>Year {year}</th></tr></thead>
      <tbody><tr><td><div>{date}</div><small>8:30 AM</small></td>
      <td><span>N</span><span>ews</span></td><td>{title}</td>{extra_column}</tr></tbody>
      </table>'''


AUSTRALIA_CPI = '''<div class="views-row">Consumer Price Index, Australia, November 2026<span
class="release-date-label">Release date</span> <time datetime="2027-01-06T00:30:00Z"
class="datetime">06/01/2027 11:30am AEDT</time></div>'''
SECO_DATES = '''<h2 id="Publication-schedule">Publication schedule</h2>
<h3>Provisional dates</h3><ul><li><strong>Q3&nbsp;2026</strong><br />
Monday 30 November 2026, 9:00 a.m.</li></ul><h2>Other dates</h2>'''


class OfficialReleaseDatesTest(unittest.TestCase):
    def test_bea_next_year_uses_row_clock_and_four_column_layout(self):
        html = bea(2027, "GDP (Advance Estimate), 4th Quarter and Year 2026",
                   "January 28", "<td></td>")
        year, (row,) = parse_bea(html, BEA_NEXT)
        self.assertEqual(year, 2027)
        self.assertEqual(row["title"], "GDP (Advance Estimate)")
        self.assertEqual(row["reference_period"], "4th Quarter and Year 2026")
        self.assertEqual(scheduled(row).astimezone(ROME).isoformat(), "2027-01-28T14:30:00+01:00")
        combined = bea(2027, "GDP (Third Estimate), Industries, 2nd Quarter 2027; "
                       "State Consumer Spending, 2026", "September 30")
        _, (row,) = parse_bea(combined, BEA_NEXT)
        self.assertEqual(row["reference_period"], "2nd Quarter 2027")

    def test_abs_clock_must_match_the_timestamp(self):
        (row,) = parse_abs(AUSTRALIA_CPI)
        self.assertEqual(row["reference_period"], "November 2026")
        self.assertEqual(scheduled(row).astimezone(ROME).isoformat(), "2027-01-06T01:30:00+01:00")
        with self.assertRaisesRegex(ValueError, "disagrees"):
            parse_abs(AUSTRALIA_CPI.replace("11:30am", "10:30am"))

    def test_seco_keeps_flash_and_quarterly_schedules_distinct(self):
        quarterly, = parse_seco(SECO_DATES, SECO_GDP)
        flash, = parse_seco(SECO_DATES.replace("Monday 30 November", "Monday 16 November"), SECO_FLASH)
        self.assertEqual((quarterly["ccy"], quarterly["reference_period"]), ("CHF", "Q3 2026"))
        self.assertEqual(quarterly["quality"], "OFFICIAL_PROVISIONAL")
        self.assertEqual(scheduled(quarterly).astimezone(ROME).isoformat(), "2026-11-30T09:00:00+01:00")
        self.assertNotEqual(quarterly["title"], flash["title"])
        future, changed = apply_rows([flash], [quarterly], NOW)
        self.assertEqual((future, changed), ([flash, quarterly], 1))
        with self.assertRaisesRegex(ValueError, "weekday"):
            parse_seco(SECO_DATES.replace("Monday", "Tuesday"), SECO_GDP)

    def test_reschedule_only_the_matching_future_event(self):
        _, (row,) = parse_bea(bea(2026, "GDP (Second Estimate) and Corporate Profits, "
                                  "3rd Quarter 2026", "November 25"), BEA)
        old = dict(row, date="2026-11-26", reference_period="Q3 2026")
        unrelated = {"ccy": "AUD", "title": "PMI flash Australia", "source_family": "S&P Global"}
        history = dict(old, date="2026-11-19")
        result, changed = apply_rows([unrelated, history, old], [row], NOW)
        self.assertEqual(changed, 1)
        self.assertEqual(result, [unrelated, history, dict(old, date="2026-11-25")])
        self.assertEqual(apply_rows(result, [row], NOW), (result, 0))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            apply_rows(result, [row, dict(row, date="2026-11-27")], NOW)

    def test_unavailable_source_preserves_last_verified_rows(self):
        html = bea(2026, "Personal Income and Outlays, November 2026", "December 23")
        sources = {BEA: html, BEA_NEXT: html, ABS: AUSTRALIA_CPI,
                   SECO_GDP: SECO_DATES, SECO_FLASH: "<html>Maintenance</html>"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seed.json"
            path.write_text(json.dumps({"schema": "GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1",
                                        "status": "ACTIVE_VERIFIED_SEED", "events": []}))
            verified, wrong_year, abs_result, seco_result, seco_flash = refresh(path, NOW, read=sources.__getitem__)
            self.assertEqual(verified["changed"], 1)
            self.assertEqual(wrong_year["status"], "SOURCE_BLOCKED_RETAINED")
            self.assertEqual(abs_result["changed"], 1)
            self.assertEqual(seco_result["changed"], 1)
            self.assertEqual(seco_flash["status"], "SOURCE_BLOCKED_RETAINED")
            saved = path.read_bytes()
            events = json.loads(saved)["events"]
            self.assertEqual({row["ccy"] for row in events}, {"USD", "AUD", "CHF"})
            self.assertTrue(all(not ({"actual", "consensus"} & row.keys()) for row in events))
            result = refresh(path, NOW, read=lambda _: "<html>Maintenance</html>")
            self.assertTrue(all(row["status"] == "SOURCE_BLOCKED_RETAINED" for row in result))
            self.assertEqual(path.read_bytes(), saved)
