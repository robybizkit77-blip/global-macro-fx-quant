import json
from datetime import datetime, timedelta, timezone
import unittest

from validation.macro import capture_statcan_cpi_firstseen_v1 as cpi
from validation.macro.build_g8_official_news_items_v1 import build

SEED = json.loads(cpi.SEED.read_text(encoding="utf-8"))
RELEASE = datetime(2026, 11, 16, 13, 30, tzinfo=timezone.utc)
HTML = (
    b'<h1 property="name">Consumer Price Index, October 2026</h1>'
    b"<p>Released:&#160;2026-11-16</p>"
    b"<p>The Consumer Price Index (<a>CPI</a>) rose&#160;2.7% year over year in October."
    b" On a seasonally adjusted monthly basis, the CPI increased 0.2% in October.</p>"
)
# The 2.7% above is a parser fixture, not a real October reading.


class StatcanCpiTests(unittest.TestCase):
    def test_extracts_only_aggregate_annual_rate(self):
        self.assertEqual(cpi.parse_release(HTML, "2026-11-16", "October 2026"), 2.7)
        for bad in (
            HTML.replace(b"year over year", b"month over month"),
            HTML.replace(b"Consumer Price Index (<a>CPI</a>)", b"CPI excluding gasoline"),
            HTML.replace(b"October 2026", b"September 2026"),
            HTML.replace(b"2026-11-16", b"2026-11-15"),
            HTML + HTML[HTML.index(b"<p>The"):],
        ):
            with self.assertRaises(cpi.Pending):
                cpi.parse_release(bad, "2026-11-16", "October 2026")

    def test_official_news_only_after_observation_and_no_duplicate(self):
        def unavailable(*args):
            self.fail("Must not fetch before release or repeat the observation")

        def fetch(url, host):
            self.assertEqual(host, cpi.HOST)
            return HTML, url

        rows, _ = cpi.capture(SEED, [], RELEASE - timedelta(seconds=1), fetch=unavailable)
        self.assertEqual(rows, [])
        seen = RELEASE + timedelta(minutes=4)
        rows, state = cpi.capture(SEED, [], RELEASE, fetch=fetch, observed_clock=lambda: seen)
        self.assertEqual(state, "OFFICIAL_HEADLINE_OBSERVED")
        self.assertEqual(len(rows), 1)
        reverted, _ = cpi.capture(SEED, rows, seen, fetch=unavailable)
        self.assertEqual(reverted, rows)
        self.assertFalse(any(x["metric_id"] == cpi.METRIC for x in build(RELEASE, cad_cpi_actuals=rows)))
        item = next(x for x in build(seen, cad_cpi_actuals=rows) if x["metric_id"] == cpi.METRIC)
        self.assertEqual(item["event_key"], "CAD|2026-11-16|INFLATION|Consumer Price Index")
        self.assertIn("+2,7%", item["title"])
        self.assertIn("non disponibile", item["detail"])
        self.assertEqual(item["category"], "MACRO_OFFICIAL_ACTUAL")
        with self.assertRaises(ValueError):
            cpi.validate([{**rows[0], "actual_percent": 9.0}], SEED)

    def test_missing_press_release_stays_pending(self):
        def wrong_article(url, host):
            return HTML.replace(b"October", b"September"), url

        rows, state = cpi.capture(SEED, [], RELEASE, fetch=wrong_article)
        self.assertEqual(rows, [])
        self.assertEqual(state, "OFFICIAL_HEADLINE_NOT_YET_VERIFIED")
