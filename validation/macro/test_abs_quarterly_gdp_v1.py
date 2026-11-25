import json
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import unittest

from validation.macro.abs_quarterly_gdp_v1 import (
    SCHEMA, UNIT, Pending, collect, edition_url, latest_growth, parse_bulletin,
)


def fixture(month="September", release="2/12/2026", title="Gross domestic product, chain volume measures, seasonally adjusted",
            rows="<tr><td>Jun-26</td><td>0.4</td><td>2.1</td></tr><tr><td>Sep-26</td><td>-0.2</td><td>1.5</td></tr>"):
    # Synthetic parser fixture, not a claim about the unreleased September GDP.
    return f"""<html><h1>Australian National Accounts: National Income, Expenditure and Product</h1>
    <p>Reference period</p><p>{month} 2026</p><p>Released</p><p>{release}</p>
    <h2>{title}</h2><table><tr><th></th><th>Quarterly growth (%)</th><th>Through the year (%)</th></tr>{rows}</table></html>""".encode()


class ABSTests(unittest.TestCase):
    def test_exact_quarters_and_units(self):
        r = parse_bulletin(fixture(), "2026Q3", date(2026, 12, 2))
        self.assertEqual((r["reported_value"], r["prior_qoq"]), (-0.2, 0.4))
        for bad in (fixture(month="June"), fixture(title="Nominal GDP"), fixture(rows="<tr><td>Sep-26</td><td>1.0</td><td>2.1</td></tr>")):
            with self.assertRaises(Pending):
                parse_bulletin(bad, "2026Q3", date(2026, 12, 2))
        with self.assertRaises(Pending):
            parse_bulletin(fixture(), "2026Q3", date(2026, 12, 1))

    def test_append_only_and_date_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"archive.json"
            p.write_text(json.dumps({"schema": SCHEMA, "editions": []}))
            now = datetime(2026, 12, 2, 12, tzinfo=timezone.utc)
            fetch = lambda url, host: (fixture(), url)
            self.assertEqual(collect(now, path=p, fetch=fetch, apply=True)["status"], "ARCHIVED")
            self.assertIsNone(latest_growth("2026-12-02", path=p))
            g = latest_growth("2026-12-03", path=p)
            self.assertEqual(g["reference_quarter"], "2026Q3")
            self.assertEqual(g["reported_unit"], UNIT)
            self.assertEqual(g["prior_documented_quarter"]["reported_unit"], UNIT)
            self.assertTrue(g["prior_value_from_same_publisher_edition"])
            self.assertFalse(g["is_growth_strength_score"])
            before = p.read_bytes()
            self.assertEqual(collect(now, path=p, fetch=fetch, apply=True)["status"], "AWAITING_ABS_QUARTER_CLOSE")
            self.assertEqual(p.read_bytes(), before)

    def test_source_error_retains_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"archive.json"
            p.write_text(json.dumps({"schema": SCHEMA, "editions": []}))
            before = p.read_bytes()
            now = datetime(2026, 12, 2, 12, tzinfo=timezone.utc)
            self.assertEqual(collect(now, path=p, fetch=lambda u,h:(fixture(), edition_url("2026Q2")), apply=True)["status"], "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED")
            self.assertEqual(p.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
