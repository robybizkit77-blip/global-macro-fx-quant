#!/usr/bin/env python3
"""RBA F2 second official representation: strict XLSX identity and PIT gates."""
import io
import unittest
import urllib.error
from datetime import date, datetime
from unittest.mock import patch

from openpyxl import Workbook

from validation import fetch_rates_aud as aud


def workbook_bytes(*, source="RBA", unit="Per cent per annum",
                   publication="2026-11-06", two_id=aud.SERIES_2Y,
                   observations=None):
    w=Workbook()
    s=w.active
    s.title="F2 daily"
    rows=[
        ["Table F2",None,None],
        ["Title","Australian Government 2 year bond","Australian Government 10 year bond"],
        ["Description","Government bond","Government bond"],
        ["Frequency","Daily","Daily"],
        ["Type","Original","Original"],
        ["Units",unit,unit],
        ["Breaks",None,None],
        ["Research notes",None,None],
        ["Source",source,source],
        ["Publication date",publication,publication],
        ["Series ID",two_id,aud.SERIES_10Y],
    ]
    for r in rows:
        s.append(r)
    for d,y2,y10 in (observations or [
        (datetime(2026,11,3),4.6,4.8),
        (datetime(2026,11,4),4.826,5.082),
    ]):
        s.append([d,y2,y10])
    f=io.BytesIO()
    w.save(f)
    return f.getvalue()


class RbaF2StrictXlsxFallback(unittest.TestCase):
    def test_issuer_tenors_dates_and_cadence(self):
        x=aud.parse_xlsx(workbook_bytes(),asof=date(2026,11,12))
        self.assertEqual(x["source_url"],aud.XLSX_URL)
        self.assertEqual(x["source_format"],"RBA_F2_OFFICIAL_XLSX")
        self.assertEqual(x["series_2Y"],aud.SERIES_2Y)
        self.assertEqual(x["series_10Y"],aud.SERIES_10Y)
        self.assertEqual((x["date"],x["publication_date"]),
                         ("2026-11-04","2026-11-06"))
        self.assertEqual((x["2Y"],x["10Y"]),(4.826,5.082))
        self.assertIn("weekly",x["publication_cadence"])
    def test_403_uses_only_the_same_official_rba_f2_workbook(self):
        err=urllib.error.HTTPError(aud.URL,403,"Forbidden",None,None)
        with patch.object(aud,"fetch",side_effect=err):
            with patch.object(aud,"fetch_xlsx",return_value=workbook_bytes()) as x:
                a=aud.latest()
        self.assertEqual(a["date"],"2026-11-04")
        x.assert_called_once_with()
    def test_removed_csv_404_does_not_switch_source(self):
        err=urllib.error.HTTPError(aud.URL,404,"Not found",None,None)
        with patch.object(aud,"fetch",side_effect=err):
            with patch.object(aud,"fetch_xlsx") as x:
                with self.assertRaises(urllib.error.HTTPError):
                    aud.latest()
        x.assert_not_called()
    def test_bad_csv_parser_is_not_disguised_as_transport(self):
        with patch.object(aud,"fetch",return_value="Invalid schema"):
            with patch.object(aud,"fetch_xlsx") as x:
                with self.assertRaises(RuntimeError):
                    aud.latest()
        x.assert_not_called()
    def test_official_identity_and_asof_guards_fail_closed(self):
        cases=[
            dict(source="UNKNOWN"),
            dict(unit="basis points"),
            dict(two_id="FAKE_2Y"),
            dict(publication="2026-11-13"),
            dict(observations=[
                (datetime(2026,11,3),4.6,4.8),
                (datetime(2026,11,7),4.7,4.9)]),
            dict(observations=[
                (datetime(2026,11,3),4.6,4.8),
                (datetime(2026,11,3),4.7,4.9)]),
            dict(observations=[
                (datetime(2026,11,3),4.6,4.8),
                (datetime(2026,11,4),"Infinity",4.9)]),
        ]
        for kw in cases:
            with self.subTest(kw=kw):
                with self.assertRaises(RuntimeError):
                    aud.parse_xlsx(workbook_bytes(**kw),asof=date(2026,11,12))
    def test_no_fallback_to_secondary_prices_on_invalid_official_document(self):
        with self.assertRaises(Exception):
            aud.parse_xlsx(b"not-an-issuer-workbook",asof=date(2026,11,12))


if __name__=="__main__":
    unittest.main(verbosity=2)
