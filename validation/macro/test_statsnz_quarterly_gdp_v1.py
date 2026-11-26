from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import json
import unittest
from validation.macro.statsnz_quarterly_gdp_v1 import (
    SCHEMA, UNIT, Pending, collect, latest_growth, parse_bulletin, edition_url, official_edition,
)


def fixture(headline="GDP rose 0.2 percent", rows="Mar 2026 0.9 0.9 Jun 2026 0.2 1.7", narrative="Economic activity rose 0.2 percent in the June 2026 quarter as measured by gross domestic product. This follows a 0.9 percent rise in the March 2026 quarter."):
    return f"""<html><h1>Gross domestic product: June 2026 quarter</h1>
    <p>17 September 2026, 10:45am</p><p>All movements are in seasonally adjusted chain-volume terms.</p>
    <p>In the June 2026 quarter, compared with the March 2026 quarter:</p><p>{headline}</p>
    <p>{narrative}</p><h2>Gross domestic product, quarterly and annual growth rates, chain volume, December 2022–June 2026</h2>
    <p>Quarter Quarterly growth (%) Annual growth (%) {rows}</p></html>""".encode()


class StatsNZTests(unittest.TestCase):
    def test_exact_edition(self):
        row=parse_bulletin(fixture(),"2026Q2",date(2026,9,17))
        self.assertEqual((row["reported_value"],row["prior_qoq"]),(0.2,0.9))
        for raw in (fixture(headline="GDP rose 0.3 percent"),fixture(narrative="Expenditure on GDP rose 0.4 percent.")):
            with self.assertRaises(Pending):
                parse_bulletin(raw,"2026Q2",date(2026,9,17))
        with self.assertRaises(Pending):
            parse_bulletin(fixture(),"2026Q2",date(2026,9,16))

    def test_browser_fallback_keeps_all_source_guards(self):
        shell = b"<html><title>Gross domestic product: June 2026 quarter | Stats NZ</title></html>"
        day = date(2026,9,17)
        fetch = lambda u,h: (shell,u)
        row, raw = official_edition("2026Q2",day,fetch,lambda u: fixture())
        self.assertEqual((row["reported_value"],row["prior_qoq"]),(0.2,0.9))
        self.assertEqual(raw,fixture())
        with self.assertRaises(Pending):
            official_edition("2026Q2",day,fetch,lambda u: fixture(headline="GDP rose 0.3 percent"))
        with self.assertRaises(Pending):
            official_edition("2026Q2",date(2026,9,16),fetch,lambda u: fixture())

    def test_archive_and_no_future_release(self):
        # Synthetic September-quarter values exercise the parser; not actual GDP.
        raw=fixture().decode().replace("June 2026","September 2026").replace("March 2026","June 2026").replace("17 September 2026","17 December 2026").replace("Mar 2026","Jun 2026").replace("Jun 2026 0.2","Sep 2026 0.2").encode()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"archive.json"
            path.write_text(json.dumps({"schema":SCHEMA,"editions":[]}))
            now=datetime(2026,12,17,12,tzinfo=timezone.utc)
            self.assertEqual(collect(now,path=path,fetch=lambda u,h:(raw,u),apply=True)["status"],"ARCHIVED")
            self.assertIsNone(latest_growth("2026-12-17",path=path))
            g=latest_growth("2026-12-18",path=path)
            self.assertEqual(g["reference_quarter"],"2026Q3")
            self.assertEqual(g["reported_unit"],UNIT)
            self.assertEqual(g["prior_documented_quarter"]["reported_unit"],UNIT)
            before=path.read_bytes()
            self.assertEqual(collect(now,path=path,fetch=lambda u,h:(raw,u),apply=True)["status"],"AWAITING_STATSNZ_QUARTER_CLOSE")
            self.assertEqual(before,path.read_bytes())


if __name__ == "__main__":
    unittest.main()
