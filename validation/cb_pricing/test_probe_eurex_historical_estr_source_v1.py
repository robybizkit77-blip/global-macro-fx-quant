#!/usr/bin/env python3
"""No fabricating past source URLs or claiming historical OIS skill."""
import unittest
from unittest.mock import MagicMock
import urllib.error
from validation.cb_pricing.probe_eurex_historical_estr_source_v1 import (
    SOURCES, audit, probe, source_shape
)

class Response:
    status=200
    headers={"content-type":"text/csv"}
    def __init__(self, text, url):
        self.text=text.encode("utf-8"); self.url=url
    def read(self,n): return self.text[:n]
    def geturl(self): return self.url
    def __enter__(self): return self
    def __exit__(self,*_): pass

class HistoricSourceTests(unittest.TestCase):
    def test_exact_known_links_and_hypothesis_qualifier(self):
        self.assertEqual(len(SOURCES),3)
        self.assertEqual([x["date"] for x in SOURCES],
                         ["2026-10-21","2026-10-21","2026-10-29"])
        self.assertTrue(SOURCES[0]["source_url_is_site_observed"])
        self.assertFalse(SOURCES[1]["source_url_is_site_observed"])
        self.assertTrue(SOURCES[2]["source_url_is_site_observed"])
        self.assertEqual(SOURCES[0]["kind"],"SOURCE_PAGE_LINK_CACHED")
        self.assertTrue(all(x["url"].startswith("https://") for x in SOURCES))
        self.assertNotEqual(SOURCES[0]["url"],SOURCES[2]["url"])

    def test_realistic_csv_shape_and_html_login_are_distinguished(self):
        self.assertTrue(source_shape(b"Value DateTime,Curve ID,Maturity Offset,Maturity Date,Value Type,Value\n2026-10-29"))
        self.assertFalse(source_shape(b"<html><body>Log in</body></html>"))
        self.assertFalse(source_shape(b"Period,Rate,Open Interest\n"))
        a=SOURCES[0]
        csv=b"Value DateTime;Curve ID;Maturity Offset;Maturity Date;Value Type;Value\n"
        def op(req,timeout):
            return Response(csv.decode(),req.full_url)
        r=probe(a,op)
        self.assertEqual(r["status"],"PUBLIC_DATED_CURVE_CSV_HEADER_VERIFIED")
        self.assertEqual(r["http_status"],200)
        self.assertFalse(r["downloaded_vendor_curve_values"])
        self.assertFalse(r["used_as_actual_independent_OIS_quote"])

    def test_bad_historical_endpoint_stays_unverified(self):
        def op(req,timeout):
            if "20261021" in req.full_url:
                raise urllib.error.HTTPError(req.full_url,404,"Not found",{},None)
            return Response("Value DateTime,Curve ID,Maturity Date,Value Type,Value\n",req.full_url)
        out=audit(allow_network=True,opener=op)
        self.assertFalse(out["historic_21oct_public_source_verified"])
        self.assertTrue(out["29oct_positive_control_currently_accessible"])
        self.assertEqual(out["different_dates_verified"],1)
        self.assertIsNone(out["EUR_OIS_MAE_bp"])
        self.assertFalse(out["multi_date_OIS_spread_statistics_allowed"])
        self.assertFalse(out["changes_live_OIS_or_FX"])
        self.assertTrue(out["no_generated_untested_historical_url"])

    def test_21oct_potential_access_does_not_make_prices_certified(self):
        def op(req,timeout):
            return Response("Value DateTime,Curve ID,Maturity Date,Value Type,Value\n",req.full_url)
        out=audit(allow_network=True,opener=op)
        self.assertEqual(out["different_dates_verified"],2)
        self.assertTrue(out["historic_21oct_public_source_verified"])
        self.assertIsNone(out["EUR_OIS_MAE_bp"])
        self.assertIsNone(out["EUR_OIS_hit_rate"])
        self.assertFalse(out["same_market_time_and_instrument_proven"])
        self.assertTrue(out["no_source_curve_values_persisted"])

    def test_cannot_probe_forged_date(self):
        bad={**SOURCES[0],"url":SOURCES[0]["url"].replace("20261021","20261020")}
        with self.assertRaises(ValueError):
            probe(bad)

if __name__=="__main__":
    unittest.main()
