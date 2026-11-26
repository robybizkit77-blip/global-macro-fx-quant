from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from validation.macro.ons_quarterly_gdp_v1 import (
    BASE, SCHEMA, Pending, collect, edition_url, latest_growth, load_archive, parse_bulletin,
)

Q3 = "GDP first quarterly estimate, UK: July to September 2026"
Q4 = "GDP first quarterly estimate, UK: October to December 2026"
HEADLINE = "UK real gross domestic product (GDP) is estimated to have "
Q3_MAIN = HEADLINE + "increased by 0.7% in Quarter 3 (July to Sept) 2026, following growth of 0.5% in Quarter 2 (Apr to June) 2026."
Q4_MAIN = HEADLINE + "fallen by 0.2% in Quarter 4 (Oct to Dec) 2026, following growth of 0.6% in Quarter 3 (July to Sept) 2026."


def html(title, released, headline):
    return (f"<h1>{title}</h1><p>Release date: {released}</p>"
            f"<h2>1. Main points</h2><li>{headline}</li>"
            f"<h2>2. Headline GDP figures</h2><p>{headline}</p>").encode()


CURRENT = html(Q3, "12 November 2026", Q3_MAIN)
NEXT = html(Q4, "11 February 2027", Q4_MAIN)
TODAY = datetime(2026, 11, 20, 17, 30, tzinfo=timezone.utc)
ROLLOVER = datetime(2027, 2, 11, 9, tzinfo=timezone.utc)


class OnsQuarterlyGDPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.archive = Path(temporary.name) / "ons.json"
        self.archive.write_text(json.dumps({"schema": SCHEMA, "editions": []}))

    def run_capture(self, now=TODAY, *, latest=CURRENT, dated=None):
        def issuer(url, host):
            self.assertEqual(host, "www.ons.gov.uk")
            return (latest if url == BASE + "latest" or dated is None else dated), url
        return collect(now, path=self.archive, fetch=issuer, apply=True)

    def test_current_official_structure_and_comparable_prior(self):
        result = parse_bulletin(CURRENT, TODAY.date())
        self.assertEqual(result["quarter"], "2026Q3")
        self.assertEqual(result["reported_value"], 0.7)
        self.assertEqual(result["prior_qoq"], 0.5)
        self.assertEqual(result["source_url"], edition_url("2026Q3"))

    def test_future_or_wrong_aggregate_rejected(self):
        with self.assertRaises(Pending):
            parse_bulletin(NEXT, date(2027, 2, 10))
        for invalid in (Q3_MAIN.replace("UK real", "UK nominal"),
                        Q3_MAIN.replace("UK real gross domestic product (GDP)", "Real GDP per head"),
                        Q3_MAIN.replace("Quarter 3", "Quarter 4")):
            with self.subTest(headline=invalid), self.assertRaises(Pending):
                parse_bulletin(html(Q3, "12 November 2026", invalid), TODAY.date())
        with self.assertRaises(Pending):
            parse_bulletin(html(Q3.replace("first quarterly", "monthly"), "12 November 2026", Q3_MAIN),
                           TODAY.date())

    def test_explicit_zero_and_no_inferred_previous_value(self):
        raw = html(Q4, "11 February 2027", HEADLINE + "shown no growth in Quarter 4 (Oct to Dec) 2026.")
        result = parse_bulletin(raw, ROLLOVER.date())
        self.assertEqual(result["reported_value"], 0)
        self.assertIsNone(result["prior_qoq"])

    def test_prior_from_ons_wording_in_previous_first_estimates(self):
        headline = HEADLINE + "increased by 0.1% in Quarter 4 (Oct to Dec) 2025"
        q4 = html(Q4.replace("2026", "2025"), "12 February 2026",
                  headline + ", following a 0.1% increase in the previous quarter.")
        self.assertEqual(parse_bulletin(q4, TODAY.date())["prior_qoq"], 0.1)
        q1 = html("GDP first quarterly estimate, UK: January to March 2026", "14 May 2026",
                  HEADLINE + "increased by 0.6% in Quarter 1 (Jan to Mar) 2026, "
                  "following revised growth of 0.2% in Quarter 4 (Oct to Dec) 2025.")
        self.assertEqual(parse_bulletin(q1, TODAY.date())["prior_qoq"], 0.2)

    def test_rollover_and_same_edition_revision(self):
        self.assertEqual(self.run_capture()["status"], "ARCHIVED")
        original = self.archive.read_bytes()
        self.assertEqual(self.run_capture()["status"], "VERIFIED_ALREADY_ARCHIVED")
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertIsNone(latest_growth("2026-11-19", path=self.archive))
        self.assertEqual(self.run_capture(ROLLOVER, latest=NEXT)["status"], "ARCHIVED")
        self.assertEqual(latest_growth("2027-02-11", path=self.archive)["reference_quarter"], "2026Q3")
        before_capture = latest_growth("2027-02-11", path=self.archive,
                                       live_cutoff=ROLLOVER-timedelta(seconds=1))
        self.assertEqual(before_capture["reference_quarter"],"2026Q3")
        live = latest_growth("2027-02-11", path=self.archive, live_cutoff=ROLLOVER)
        self.assertEqual(live["reference_quarter"],"2026Q4")
        self.assertEqual(live["prior_documented_quarter"]["reported_value"],0.6)
        with self.assertRaises(ValueError):
            latest_growth("2027-02-12",path=self.archive,live_cutoff=ROLLOVER)
        matured = latest_growth("2027-02-12", path=self.archive)
        self.assertEqual(matured["reference_quarter"], "2026Q4")
        self.assertEqual(matured["reported_value"], -0.2)
        self.assertEqual(matured["prior_documented_quarter"]["reported_value"], 0.6)
        self.assertTrue(matured["prior_value_from_same_ons_edition"])
        self.assertEqual(load_archive(self.archive)["editions"][0]["reported_value"], 0.7)

    def test_archive_retained_on_mismatch_regression_or_transport_failure(self):
        self.assertEqual(self.run_capture()["status"], "ARCHIVED")
        original = self.archive.read_bytes()
        mismatch = self.run_capture(ROLLOVER, latest=NEXT, dated=CURRENT)
        self.assertIn("does_not_match", mismatch["reason"].lower())
        amended = self.run_capture(latest=CURRENT.replace(b"0.7%", b"0.6%"))
        self.assertIn("archive_retained", amended["reason"].lower())
        def unavailable(*_):
            raise OSError("temporary connection failure")
        receipt = collect(TODAY, path=self.archive, fetch=unavailable, apply=True)
        self.assertEqual(receipt["status"], "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED")
        self.assertEqual(receipt["last_archived_quarter"], "2026Q3")
        self.assertEqual(self.archive.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
