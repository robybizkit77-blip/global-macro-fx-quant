from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import unittest

from validation.macro.esri_quarterly_gdp_v1 import (
    CSV_TITLE, HOST, Pending, archive_for, collect, edition_urls, latest_growth,
    parse_csv, release_date,
)


def index(quarter, released, stage="The First preliminary Estimates"):
    _, edition, _ = edition_urls(quarter)
    return (f'<table><tr><td>{released}</td><td><a href="{edition.removeprefix("https://" + HOST)}">'
            f'Quarterly Estimates of GDP ({stage})</a></td></tr></table>').encode()


def table(periods, title=CSV_TITLE, metric="GDP(Expenditure Approach)"):
    return ('"' + title + '"\n,' + metric + '\n' + periods).encode("cp932")


Q3 = table("2026/ 4- 6.,0.4\n7- 9.,-0.0\n")
Q4 = table("2026/ 7- 9.,0.1\n10-12.,-0.2\n")
NOV = datetime(2026,11,20,12,tzinfo=timezone.utc)
FEBRUARY = datetime(2027,2,15,12,tzinfo=timezone.utc)


class ESRIQuarterlyGDPTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.archive = Path(tmp.name) / "archive.json"
        self.archive.write_text('{"schema":"GMFQ_ESRI_FIRST_QUARTERLY_GDP_V1","editions":[]}')

    def capture(self, quarter, released, now, csv_bytes):
        index_url, edition, csv_url = edition_urls(quarter)
        page = f'<h1>The 1st preliminary</h1><a href="{csv_url.removeprefix("https://" + HOST)}">Real GDP</a>'
        pages = {index_url: index(quarter,released), edition: page.encode()}
        return collect(now, path=self.archive, apply=True,
                       fetch=lambda url,host: (pages[url],url),
                       csv_fetch=lambda url: {csv_url: csv_bytes}[url])

    def test_current_exact_table_and_release_date(self):
        self.assertEqual(release_date(index("2026Q3","Nov  16, 2026"),"2026Q3"), date(2026,11,16))
        self.assertEqual(parse_csv(Q3,"2026Q3"), (-0.0,0.4))

    def test_wrong_table_wrong_component_and_dates_are_refused(self):
        for invalid in (table("2026/ 4- 6.,1.2\n7- 9.,-0.1\n", title="Annualized"),
                        table("2026/ 4- 6.,0.4\n7- 9.,-0.0\n", metric="PrivateConsumption"),
                        Q3+b"10-12.,1.0\n", Q3+b"7- 9.,1.0\n",
                        table("2026/ 1- 3.,0.5\n7- 9.,-0.0\n")):
            with self.subTest(raw=invalid),self.assertRaises(Pending):
                parse_csv(invalid,"2026Q3")
        with self.assertRaises(Pending):
            release_date(index("2026Q3","Dec  8, 2026","The Second preliminary Estimates"),"2026Q3")

    def test_rollover_retains_frozen_earlier_edition_and_uses_current_vintage(self):
        self.assertEqual(self.capture("2026Q3","Nov 16, 2026",NOV,Q3)["status"],"ARCHIVED")
        self.assertIsNone(latest_growth("2026-11-19",path=self.archive))
        self.assertEqual(collect(NOV,path=self.archive,apply=True)["status"],"AWAITING_ESRI_FIRST_ESTIMATE")
        self.assertEqual(self.capture("2026Q4","Feb 15, 2027",FEBRUARY,Q4)["status"],"ARCHIVED")
        self.assertEqual(latest_growth("2027-02-15",path=self.archive)["reference_quarter"],"2026Q3")
        g = latest_growth("2027-02-16",path=self.archive)
        self.assertEqual(g["reference_quarter"],"2026Q4")
        self.assertEqual(g["reported_value"],-0.2)
        self.assertEqual(g["prior_documented_quarter"]["reported_value"],0.1)
        self.assertTrue(g["prior_value_from_same_esri_edition"])
        self.assertEqual(archive_for(self.archive)["editions"][0]["reported_value"],-0.0)

    def test_transport_failure_preserves_archive(self):
        self.capture("2026Q3","Nov 16, 2026",NOV,Q3)
        original = self.archive.read_bytes()
        def unavailable(*_):
            raise OSError("Official source unavailable")
        receipt = collect(FEBRUARY,path=self.archive,fetch=unavailable,apply=True)
        self.assertEqual(receipt["status"],"SOURCE_UNAVAILABLE_ARCHIVE_RETAINED")
        self.assertEqual(receipt["last_archived_quarter"],"2026Q3")
        self.assertEqual(self.archive.read_bytes(),original)


if __name__ == "__main__":
    unittest.main()
