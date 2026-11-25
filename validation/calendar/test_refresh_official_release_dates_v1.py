import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from validation.calendar.refresh_official_release_dates_v1 import (
    ABS, BEA, BEA_NEXT, FSO_CPI, ROME, SECO_FLASH, SECO_GDP,
    apply_rows, parse_abs, parse_bea, parse_fso, parse_seco, refresh, scheduled,
    ONS_CPI, JP_CPI, eurostat_urls, parse_ons_cpi, parse_jp_cpi, parse_eurostat_flash,
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
FSO_AGENDA = '''<rss version="2.0"><channel><language>en</language>
<item><title>Swiss Consumer Price Index in March 2027</title>
<link>https://statistik.admin.ch/en/agenda/2027-639</link>
<pubDate>Fri, 02 Apr 2027 08:30:00 +0200</pubDate></item>
<item><title>Swiss Consumer Price Index in December and annual inflation 2027</title>
<link>https://statistik.admin.ch/en/agenda/2028-7</link>
<pubDate>Tue, 04 Jan 2028 08:30:00 +0100</pubDate></item>
<item><title>Swiss Producer and Import Price Index in March 2027</title></item>
</channel></rss>'''


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

    def test_fso_agenda_distinguishes_coverage_month_from_release_day(self):
        march, december = parse_fso(FSO_AGENDA)
        self.assertEqual((march["ccy"], march["reference_period"]), ("CHF", "March 2027"))
        self.assertEqual(scheduled(march).isoformat(), "2027-04-02T08:30:00+02:00")
        self.assertEqual((december["reference_period"], december["date"]), ("December 2027", "2028-01-04"))
        prior = dict(march, source_url="https://dam-api.bfs.admin.ch/calendar.pdf")
        self.assertEqual(apply_rows([prior], [march], NOW), ([march], 1))
        with self.assertRaisesRegex(ValueError, "Zurich"):
            parse_fso(FSO_AGENDA.replace("08:30:00 +0200", "08:30:00 +0100"))
        with self.assertRaisesRegex(ValueError, "official agenda link"):
            parse_fso(FSO_AGENDA.replace("statistik.admin.ch", "example.org"))
        with self.assertRaisesRegex(ValueError, "valid XML"):
            parse_fso("<rss>")

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
                   SECO_GDP: SECO_DATES, SECO_FLASH: "<html>Maintenance</html>",
                   FSO_CPI: "<rss>", ONS_CPI: "<html>Maintenance</html>",
                   JP_CPI: "<html>Maintenance</html>",
                   **{url: "<html>Maintenance</html>" for url in eurostat_urls(NOW)}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seed.json"
            path.write_text(json.dumps({"schema": "GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1",
                                        "status": "ACTIVE_VERIFIED_SEED", "events": []}))
            verified, wrong_year, abs_result, seco_result, seco_flash, fso, *new_sources = refresh(
                path, NOW, read=sources.__getitem__)
            self.assertEqual(verified["changed"], 1)
            self.assertEqual(wrong_year["status"], "SOURCE_BLOCKED_RETAINED")
            self.assertEqual(abs_result["changed"], 1)
            self.assertEqual(seco_result["changed"], 1)
            self.assertEqual(seco_flash["status"], "SOURCE_BLOCKED_RETAINED")
            self.assertEqual(fso["status"], "SOURCE_BLOCKED_RETAINED")
            self.assertEqual(len(new_sources), 4)
            self.assertTrue(all(x["status"] == "SOURCE_BLOCKED_RETAINED" for x in new_sources))
            saved = path.read_bytes()
            events = json.loads(saved)["events"]
            self.assertEqual({row["ccy"] for row in events}, {"USD", "AUD", "CHF"})
            self.assertTrue(all(not ({"actual", "consensus"} & row.keys()) for row in events))
            result = refresh(path, NOW, read=lambda _: "<html>Maintenance</html>")
            self.assertTrue(all(row["status"] == "SOURCE_BLOCKED_RETAINED" for row in result))
            self.assertEqual(path.read_bytes(), saved)


    def test_ons_confirmed_cpi_and_no_time_series_or_provisional(self):
        html = """<a>Consumer price inflation, UK: November 2026 time series</a>
        <p>Release date: 16 December 2026 7:00am | Confirmed</p>
        <a>Consumer price inflation, UK: November 2026</a>
        <p>Release date: 16 December 2026 7:00am | Confirmed</p>
        <a>Consumer price inflation, UK: December 2026</a>
        <p>Release date: 20 January 2027 7:00am | Provisional</p>"""
        row, = parse_ons_cpi(html)
        self.assertEqual(row["reference_period"], "November 2026")
        self.assertEqual(scheduled(row).astimezone(ROME).isoformat(), "2026-12-16T08:00:00+01:00")
        with self.assertRaises(ValueError):
            parse_ons_cpi(html.replace("| Confirmed", "| Provisional"))

    def test_japan_national_cpi_and_explicit_year_rollover(self):
        html = """<table><tr><th>Japan</th><th>Tokyo</th></tr>
        <tr><th>Survey month</th><th>Date of release</th><th>Survey month</th><th>Date of release</th></tr>
        <tr><td>November, 2026</td><td>December 18, 2026</td><td>December</td><td>December 25</td></tr>
        <tr><td>December</td><td>January 22, 2027</td><td>January, 2027</td><td>January 29</td></tr>
        <tr><td>January, 2027</td><td>February 19</td><td>February</td><td>February 26</td></tr></table>"""
        rows = parse_jp_cpi(html)
        self.assertEqual([x["reference_period"] for x in rows], ["November 2026", "December 2026", "January 2027"])
        self.assertEqual([x["date"] for x in rows], ["2026-12-18", "2027-01-22", "2027-02-19"])
        self.assertTrue(all(x["time_local"] == "08:30" for x in rows))
        with self.assertRaises(ValueError):
            parse_jp_cpi(html.replace("January 22, 2027", "January 22, 2026"))

    def test_eurostat_date_only_and_retain_last_verified(self):
        url = eurostat_urls(NOW)[1]
        html = """<h3>Flash estimate inflation euro area, November 2026</h3>
        <p>01 December 2026 ECFIN Data release Euro indicators release</p>"""
        row, = parse_eurostat_flash(html, url)
        self.assertEqual((row["date"], row["reference_period"], row["time_local"]),
                         ("2026-12-01", "November 2026", None))
        self.assertEqual(apply_rows([], [row], NOW), ([row], 1))
        self.assertEqual(apply_rows([row], [row], NOW), ([row], 0))
        with self.assertRaises(ValueError):
            parse_eurostat_flash("<html>Loading calendar...</html>", url)
