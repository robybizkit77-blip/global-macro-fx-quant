from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
import tempfile
import json
import unittest

from validation.macro.statcan_quarterly_gdp_v1 import (
    Pending, SEED_URL, SCHEMA, bulletin, parse_table, collect, issue_url, daily_prefix, latest_growth,
)


def table(title="Real gross domestic product by expenditure account, quarterly change – Seasonally adjusted at annual rates, chained (2017) dollars"):
    return f"""<html><h1>{title}</h1><p>First quarter 2025 Second quarter 2025 Third quarter 2025 Fourth quarter 2025 First quarter 2026 Second quarter 2026 First quarter 2026 Second quarter 2026</p><p>quarter-to-quarter % change</p><p>Final consumption expenditure</p><p>Gross domestic product at market prices 0.7 -0.2 0.5 -0.2 0.1 0.8 2,503,604 2,524,127</p><p>Final domestic demand</p></html>""".encode()


class StatCanTests(unittest.TestCase):
    def test_q2_real_table(self):
        self.assertEqual(parse_table(table(),"2026Q2"),(0.8,0.1))
        with self.assertRaises(Pending):
            parse_table(table(),"2026Q3")
        with self.assertRaises(Pending):
            parse_table(table("Nominal GDP"),"2026Q2")

    def test_bulletin_and_next_date(self):
        raw=b'<html><h1>Gross domestic product, income and expenditure, second quarter 2026</h1><p>Released: 2026-08-28</p><a href="t002a-eng.htm">Table 2</a><p>Data on GDP by income and expenditure for the third quarter of 2026 will be released on November 30.</p></html>'
        day,url,nxt=bulletin(raw,SEED_URL,"2026Q2",date(2026,11,25))
        self.assertEqual(day,date(2026,8,28))
        self.assertTrue(url.endswith("/260828/t002a-eng.htm"))
        self.assertEqual(nxt,date(2026,11,30))
        with self.assertRaises(Pending):
            bulletin(raw,SEED_URL,"2026Q2",date(2026,8,27))

    def test_delayed_release_and_source_failure(self):
        seed=b'<html><h1>Gross domestic product, income and expenditure, second quarter 2026</h1><p>Released: 2026-08-28</p><a href="t002a-eng.htm">Table 2</a><p>Data on GDP by income and expenditure for the third quarter of 2026 will be released on November 30.</p></html>'
        release=date(2026,12,3)
        source=daily_prefix(release)+"dq261203h-eng.htm"
        revised=b'<html><h1>Gross domestic product, income and expenditure, third quarter 2026</h1><p>Released: 2026-12-03</p><a href="t002h-eng.htm">Table 2</a></html>'
        revised_table=table().decode().replace("First quarter 2025 ","",1).replace("Second quarter 2026 First quarter 2026 Second quarter 2026","Second quarter 2026 Third quarter 2026 Second quarter 2026 Third quarter 2026").replace("0.1 0.8 2,503,604","0.7 0.3 2,503,604").encode()
        def fetch(url,host):
            if url==SEED_URL: return seed,url
            if url.endswith("260828/t002a-eng.htm"): return table(),url
            if url==issue_url(release):
                return b'<html><a href="dq261203h-eng.htm">GDP</a></html>',url
            if url==source: return revised,url
            if url.endswith("261203/t002h-eng.htm"): return revised_table,url
            raise HTTPError(url,404,"Not found",None,None)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"archive.json"
            path.write_text(json.dumps({"schema":SCHEMA,"editions":[]}))
            def failed(url,host):
                if url==issue_url(date(2026,12,1)):
                    raise HTTPError(url,503,"Temporary outage",None,None)
                return fetch(url,host)
            now=datetime(2026,12,6,12,tzinfo=timezone.utc)
            result=collect(now,path=path,fetch=failed,apply=True)
            self.assertEqual(result["status"],"SOURCE_UNAVAILABLE_ARCHIVE_RETAINED")
            self.assertEqual(result["checked_through"],"2026-11-30")
            result=collect(now,path=path,fetch=fetch,apply=True)
            self.assertEqual(result["status"],"ARCHIVED")
            self.assertEqual(result["publisher_release_day"],"2026-12-03")
            self.assertEqual(result["reported_value"],0.3)
            self.assertEqual(latest_growth("2026-12-07",path=path)["reported_value"],0.3)
            self.assertNotIn("discovery",json.loads(path.read_text()))


if __name__ == "__main__":
    unittest.main()
