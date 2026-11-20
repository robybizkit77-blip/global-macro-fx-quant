"""Dated SECO flash selection, release identity and archive rollover."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import unittest

from validation.macro.capture_official_postrelease_actuals_v1 import Pending
from validation.macro.seco_quarterly_gdp_v1 import (
    ARTICLE_BASE, DETAIL, FLASH, INDEX, SCHEMA, UNIT, archive_for, collect,
    discover, headline, latest_growth, parse_article, quarter_end_exclusive,
)

Q3 = ARTICLE_BASE + "/en/newnsb/eOpqmkpQhZVQ"
Q2 = ARTICLE_BASE + "/en/newnsb/xrrzuLVT1pbC"
Q4 = ARTICLE_BASE + "/en/newnsb/simulated-flash-q4"
Q3_DETAIL = ARTICLE_BASE + "/en/newnsb/simulated-detail-q3"


def link(url, quarter, stage):
    path = url.removeprefix(ARTICLE_BASE)
    return f'<a href="{path}" aria-label="More about «{headline(quarter, stage)} bulletin»"></a>'


def bulletin(quarter, stage, published, dateline, text):
    return (
        f"<html><span>Published on {published}</span><h1>{headline(quarter, stage)} bulletin</h1>"
        f"<p>Bern, {dateline} — {text}</p></html>"
    ).encode()


def flash(quarter, spoken_quarter, published, dateline, move):
    return bulletin(quarter, FLASH, published, dateline,
                    "According to the early estimate of Switzerland's quarterly real GDP "
                    "approximately 45 days after the quarter end ('GDP flash'), "
                    f"Swiss economic output is estimated to have {move} in the {spoken_quarter}. "
                    "The services sector grew by 0.9%.")


def detailed(quarter, spoken_quarter, published, dateline, move):
    return bulletin(quarter, DETAIL, published, dateline,
                    f"In the {spoken_quarter}, Switzerland’s gross domestic product (GDP) "
                    f"adjusted for sporting events {move}, following growth of 0.5% in the previous quarter. "
                    "This press release provides quarter-on-quarter growth rates in real terms, "
                    "seasonally adjusted and (where applicable) adjusted for sporting events.")


def clock(year, month, day):
    return datetime(year, month, day, 10, tzinfo=timezone.utc)


class SecoGDPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "gdp.json"
        self.path.write_text(json.dumps({"schema": SCHEMA, "editions": []}))
        self.pages = {
            INDEX: (link(Q3, "2026Q3", FLASH) + link(Q2, "2026Q2", DETAIL)).encode(),
            Q3: flash("2026Q3", "third quarter of 2026", "16 November 2026", "16.11.2026", "grown by 0.2%"),
            Q2: detailed("2026Q2", "second quarter of 2026", "3 September 2026", "03.09.2026", "grew by 1.5%"),
        }

    def fetch(self, url, host):
        self.assertTrue(url.startswith(f"https://{host}/"))
        if url not in self.pages:
            raise OSError("source unavailable")
        return self.pages[url], url

    def collect(self, now):
        return collect(now, path=self.path, fetch=self.fetch, apply=True)

    def add_q4(self, include_detail=True):
        self.pages[INDEX] += link(Q4, "2026Q4", FLASH).encode()
        self.pages[Q4] = flash("2026Q4", "fourth quarter of 2026", "16 February 2027", "16.02.2027",
                               "contracted by 0.4%")
        if include_detail:
            self.pages[INDEX] += link(Q3_DETAIL, "2026Q3", DETAIL).encode()
            self.pages[Q3_DETAIL] = detailed("2026Q3", "third quarter of 2026", "30 November 2026",
                                             "30.11.2026", "grew by 0.3%")

    def test_verified_seed_released_before_published_context_and_actual_first_seen(self):
        self.assertEqual(self.collect(clock(2026, 11, 15))["status"], "AWAITING_SECO_FLASH")
        self.assertEqual(self.collect(clock(2026, 11, 20))["status"], "ARCHIVED")
        self.assertIsNone(latest_growth("2026-11-19", path=self.path))
        gdp = latest_growth("2026-11-20", path=self.path)
        self.assertEqual((gdp["reported_value"], gdp["publisher_release_day"]), (0.2, "2026-11-16"))
        prior = gdp["prior_documented_quarter"]
        self.assertEqual((prior["reported_value"], prior["publisher_release_day"]), (1.5, "2026-09-03"))
        self.assertEqual(gdp["reported_unit"], prior["reported_unit"])
        self.assertEqual(prior["reported_unit"], UNIT)

    def test_future_rollover_uses_revision_without_overwriting_first_flash(self):
        self.collect(clock(2026, 11, 20))
        before = archive_for(self.path)["editions"][0]
        self.add_q4()
        self.assertEqual(self.collect(clock(2027, 2, 15))["status"], "AWAITING_SECO_FLASH")
        self.assertEqual(self.collect(clock(2027, 2, 16))["status"], "ARCHIVED")
        self.assertEqual(latest_growth("2027-02-16", path=self.path)["reference_quarter"], "2026Q3")
        gdp = latest_growth("2027-02-17", path=self.path)
        self.assertEqual((gdp["reference_quarter"], gdp["reported_value"]), ("2026Q4", -0.4))
        self.assertEqual(gdp["prior_documented_quarter"]["reported_value"], 0.3)
        self.assertEqual(gdp["prior_documented_quarter"]["publication_stage"], DETAIL)
        self.assertEqual(archive_for(self.path)["editions"][0], before)
        old_bytes = self.path.read_bytes()
        self.assertEqual(self.collect(clock(2027, 2, 17))["next_quarter"], "2027Q1")
        self.assertEqual(self.path.read_bytes(), old_bytes)
        self.assertEqual(quarter_end_exclusive("2027Q1"), date(2027, 4, 1))

    def test_missing_detailed_link_keeps_comparable_first_flash_tagged(self):
        self.collect(clock(2026, 11, 20))
        self.add_q4(include_detail=False)
        self.assertEqual(self.collect(clock(2027, 2, 16))["status"], "ARCHIVED")
        prior = latest_growth("2027-02-17", path=self.path)["prior_documented_quarter"]
        self.assertEqual((prior["publication_stage"], prior["reported_value"]), (FLASH, 0.2))

    def test_new_flash_survives_incompatible_detail_and_old_archive_survives_outage(self):
        self.collect(clock(2026, 11, 20))
        self.add_q4()
        old_bytes = self.path.read_bytes()
        good_flash = self.pages[Q4]
        self.pages[Q4] = good_flash.replace(b"16.02.2027", b"17.02.2027")
        self.assertEqual(self.collect(clock(2027, 2, 16))["status"], "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED")
        self.assertEqual(self.path.read_bytes(), old_bytes)
        self.pages[Q4] = good_flash
        self.pages[Q3_DETAIL] = self.pages[Q3_DETAIL].replace(b"adjusted for sporting events", b"at current prices")
        receipt = self.collect(clock(2027, 2, 16))
        self.assertEqual(receipt["status"], "ARCHIVED")
        self.assertIn("prior_fallback_reason", receipt)
        self.assertEqual(receipt["prior"]["reported_value"], 0.2)
        old_bytes = self.path.read_bytes()
        self.pages.pop(INDEX)
        self.assertEqual(self.collect(clock(2027, 4, 2))["status"], "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED")
        self.assertEqual(self.path.read_bytes(), old_bytes)

    def test_refuses_index_duplicates_and_dateline_mismatch(self):
        index = self.pages[INDEX] + link(Q4, "2026Q3", FLASH).encode()
        with self.assertRaisesRegex(Pending, "EDITION_NOT_UNIQUE"):
            discover(index, "2026Q3", FLASH)
        raw = self.pages[Q3].replace(b"16.11.2026", b"17.11.2026")
        with self.assertRaisesRegex(Pending, "DATELINE_MISMATCH"):
            parse_article(raw, "2026Q3", FLASH)
        stagnant = self.pages[Q3].replace(b"grown by 0.2%", b"stagnated")
        self.assertEqual(parse_article(stagnant, "2026Q3", FLASH)[1], 0.0)


if __name__ == "__main__":
    unittest.main()
