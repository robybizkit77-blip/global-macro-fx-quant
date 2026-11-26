from datetime import date, datetime, timezone
from urllib.error import HTTPError
from pathlib import Path
import tempfile
import json
import unittest
from validation.macro.eurostat_quarterly_gdp_v1 import (
    SCHEMA, UNIT, Pending, parse_bulletin, latest_growth, collect, edition_url,
)


def fixture(day="13 November 2026",title="GDP and employment flash estimates for the third quarter of 2026",table="Growth rates of GDP in volume(based on seasonally adjusted* data)",row="0.2 0.0 0.6 0.4 1.1 0.6 1.2 1.3"):
    return f"""<html><p>Euro indicators {day} Next release: 15 February 2027</p><h2>{title}</h2>
    <h3>{table}</h3><p>Percentage change compared with the previous quarter</p>
    <p>Percentage change compared with the same quarter of the previous year</p>
    <p>2025Q4 2026Q1 2026Q2 2026Q3 2025Q4 2026Q1 2026Q2 2026Q3 Euro area {row} EU 0.3 0.1 0.7 0.5 1.3 0.9 1.4 1.5</p></html>""".encode()


class EurostatTests(unittest.TestCase):
    def test_q3_exact_table(self):
        day=date(2026,11,13)
        r=parse_bulletin(fixture(),day,day)
        self.assertEqual((r["reported_value"],r["prior_qoq"]),(0.4,0.6))
        for bad in (fixture(table="Growth rates of employment in persons"),fixture(title="Inflation"),fixture(row="0.2 0.0 0.6 0.4")):
            with self.assertRaises(Pending):
                parse_bulletin(bad,day,day)
        with self.assertRaises(Pending):
            parse_bulletin(fixture(),day,date(2026,11,12))

    def test_revision_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"archive.json"
            p.write_text(json.dumps({"schema":SCHEMA,"editions":[]}))
            d=date(2026,11,13)
            now=datetime(2026,11,13,12,tzinfo=timezone.utc)
            self.assertEqual(collect(now,path=p,fetch=lambda u,h:(fixture(),u),apply=True)["status"],"ARCHIVED")
            self.assertIsNone(latest_growth("2026-11-13",path=p))
            r=latest_growth("2026-11-14",path=p)
            self.assertEqual(r["reported_unit"],UNIT)
            self.assertEqual(r["prior_documented_quarter"]["reported_value"],0.6)
            day=date(2026,12,7)
            revised=fixture(day="7 December 2026",title="GDP and employment estimates for the third quarter of 2026",row="0.2 0.0 0.5 0.3 1.1 0.6 1.2 1.3")
            def fetch(u,h):
                if u==edition_url(day):
                    return revised,u
                raise HTTPError(u,404,"Not found",None,None)
            now=datetime(2026,12,7,12,tzinfo=timezone.utc)
            self.assertTrue(collect(now,path=p,fetch=fetch,apply=True)["catchup_pending"])
            self.assertEqual(collect(now,path=p,fetch=fetch,apply=True)["status"],"ARCHIVED")
            self.assertEqual(latest_growth("2026-12-07",path=p)["reported_value"],0.4)
            self.assertEqual(latest_growth("2026-12-08",path=p)["reported_value"],0.3)
            self.assertEqual(latest_growth("2026-12-08",path=p)["prior_documented_quarter"]["reported_value"],0.5)

    def test_outage_and_transient_failure_never_skip_a_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"archive.json"
            p.write_text(json.dumps({"schema":SCHEMA,"editions":[]}))
            seed=date(2026,11,13)
            collect(datetime(2026,11,13,12,tzinfo=timezone.utc),path=p,
                    fetch=lambda u,h:(fixture(),u),apply=True)
            release=date(2026,12,7)
            delayed=fixture(day="7 December 2026",title="GDP and employment estimates for the third quarter of 2026",row="0.2 0.0 0.5 0.3 1.1 0.6 1.2 1.3")
            outage_day=date(2026,11,20)
            calls=[]
            def broken(u,h):
                calls.append(u)
                if u==edition_url(outage_day):
                    raise HTTPError(u,503,"Temporary outage",None,None)
                raise HTTPError(u,404,"Not found",None,None)
            now=datetime(2026,12,20,12,tzinfo=timezone.utc)
            first=collect(now,path=p,fetch=broken,apply=True)
            self.assertEqual(first["checked_through"],"2026-11-19")
            self.assertTrue(first["catchup_pending"])
            self.assertNotIn(edition_url(release),calls)
            def recovered(u,h):
                if u==edition_url(release):
                    return delayed,u
                raise HTTPError(u,404,"Not found",None,None)
            for _ in range(4):
                collect(now,path=p,fetch=recovered,apply=True)
            self.assertEqual(latest_growth("2026-12-21",path=p)["reported_value"],0.3)
            data=json.loads(p.read_text())
            self.assertEqual(len(data["editions"]),2)
            self.assertEqual(data["checked_through"],"2026-12-18")


if __name__=="__main__":
    unittest.main()
