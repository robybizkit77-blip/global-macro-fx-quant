"""Offline tests: future official actuals vs exact pre-announcement frozen consensus."""
from __future__ import annotations
import copy
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from validation.macro.capture_official_postrelease_actuals_v1 import (
    ECI,GDP,LEDGER,OUT,TARGETS,capture,parse_issuer_page,run,
    validate_actual_log,Pending
)
from validation.macro.freeze_pre_release_consensus_v1 import read_existing

AFTER=datetime(2026,10,30,12,35,tzinfo=timezone.utc)
BEFORE=datetime(2026,10,28,9,0,tzinfo=timezone.utc)
BLS_NEW=b"""<html><h1>Employment Cost Index News Release</h1>
Transmission of material in this release is embargoed until
8:30 a.m. (ET) Friday, October 30, 2026
<h2>EMPLOYMENT COST INDEX - SEPTEMBER 2026</h2>
<p>Compensation costs for civilian workers increased 0.7 percent,
seasonally adjusted, for the 3-month period ending in September 2026.</p>
<p>Wages and salaries increased 0.9 percent.</p></html>"""
BLS_OLD=BLS_NEW.replace(b"October 30, 2026",b"July 31, 2026")
CAD_NEW=b"""<html><h1>Gross domestic product by industry, August 2026</h1>
<p>Released: 2026-10-30</p><h2>Real GDP by industry</h2><p>August 2026</p>
<p>0.3% (monthly change)</p>
<p>Real gross domestic product (GDP) grew 0.3% in August, driven by services.</p>
<p>September advance estimate: 0.9% change, not a release for September.</p></html>"""
CAD_OLD=CAD_NEW.replace(b"August 2026",b"July 2026")
def fake_fetch(url,host):
    assert url.startswith("https://") and host in url
    return (BLS_NEW if host=="www.bls.gov" else CAD_NEW),url

class OfficialActualAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen=read_existing(LEDGER)
        assert set(x["event_key"] for x in cls.frozen) >= {ECI,GDP}

    def test_pre_release_never_fetches_or_infers_actual(self):
        calls=[]
        def monitor(*args):
            calls.append(args);raise AssertionError("network forbidden before release")
        rows,receipt=capture(self.frozen,[],BEFORE,monitor)
        self.assertEqual(rows,[])
        self.assertEqual(calls,[])
        self.assertEqual(receipt["new_actuals"],0)
        self.assertEqual(receipt["states"][ECI],"BEFORE_RELEASE_NO_FETCH")
        self.assertEqual(receipt["states"][GDP],"BEFORE_RELEASE_NO_FETCH")

    def test_post_release_exact_publisher_series_and_signed_prior_consensus(self):
        rows,receipt=capture(self.frozen,[],AFTER,fake_fetch)
        self.assertEqual(len(rows),2)
        self.assertEqual(receipt["new_actuals"],2)
        r={x["event_key"]:x for x in rows}
        self.assertEqual(r[ECI]["actual_percent"],0.7)
        self.assertEqual(r[GDP]["actual_percent"],0.3)
        self.assertAlmostEqual(r[ECI]["actual_minus_frozen_consensus_pp"],-0.1)
        self.assertAlmostEqual(r[GDP]["actual_minus_frozen_consensus_pp"],0.1)
        self.assertEqual(r[ECI]["forecast_receipt_sha256"],
                         next(x["record_sha256"] for x in self.frozen if x["event_key"]==ECI))
        self.assertTrue(all(x["fx_reaction"] is None and
                            x["CB_Want_Can"] is None and
                            x["publisher_first_release_PIT_verified"] is False
                            and x["eligible_for_Core_Beta_Forward"] is False
                            for x in rows))
        validate_actual_log(rows,self.frozen)
        twice,after=capture(self.frozen,rows,AFTER+timedelta(hours=1),fake_fetch)
        self.assertEqual(twice,rows)
        self.assertEqual(after["new_actuals"],0)

    def test_wrong_reference_period_or_official_source_is_not_an_actual(self):
        with self.assertRaises(Pending):parse_issuer_page(ECI,BLS_OLD)
        with self.assertRaises(Pending):parse_issuer_page(GDP,CAD_OLD)
        with self.assertRaises(Pending):parse_issuer_page(GDP,CAD_NEW.replace(b"2026-10-30",b"2026-10-29"))
        with self.assertRaises(Pending):parse_issuer_page(ECI,BLS_NEW.replace(
            b"Compensation costs for civilian workers",b"Private industry compensation"))
        with self.assertRaises(Pending):parse_issuer_page(GDP,CAD_NEW.replace(
            b"Real gross domestic product (GDP) grew",b"Advance estimate grew"))
        with self.assertRaises(Pending):parse_issuer_page(GDP,CAD_NEW.replace(
            b"Real gross domestic product (GDP) grew 0.3% in August",
            b"Real gross domestic product (GDP) grew 0.3% in September"))
        self.assertEqual(parse_issuer_page(ECI,BLS_NEW.replace(
            b"increased 0.7 percent",b"decreased 0.7 percent")),-0.7)
        self.assertEqual(parse_issuer_page(GDP,CAD_NEW.replace(
            b"grew 0.3% in August",b"fell 0.3% in August")),-0.3)

    def test_failed_official_http_is_missing_not_a_0_or_3rd_party_actual(self):
        def bad(url,host):raise OSError("source unavailable")
        rows,receipt=capture(self.frozen,[],AFTER,bad)
        self.assertEqual(len(rows),0)
        self.assertEqual(receipt["new_actuals"],0)
        self.assertEqual(receipt["states"][ECI],"ISSUER_NOT_YET_OBSERVED")
        self.assertEqual(receipt["states"][GDP],"ISSUER_NOT_YET_OBSERVED")
        def old(url,host):
            return (BLS_OLD if host=="www.bls.gov" else CAD_OLD),url
        rows,receipt=capture(self.frozen,[],AFTER,old)
        self.assertEqual(len(rows),0)
        def redirect(url,host):return BLS_NEW,"https://example.com/not-official"
        with self.assertRaises(ValueError):
            capture(self.frozen,[],AFTER,redirect)

    def test_real_canada_july_2026_unchanged_headline_is_true_numeric_zero(self):
        # Replays exact wording and prominent 0.0% month heading observed
        # on Statistics Canada's official 2026-09-29 article. Synthetic HTML
        # fixture is explicitly not a claim to cache the original site bytes.
        zero=b"""<html><h1>Gross domestic product by industry, July 2026</h1>
        <div>Released: 2026-09-29</div>
        <h2>Real GDP by industry</h2><p>July 2026</p>
        <p>0.0%</p><p>(monthly change)</p>
        <p>Real gross domestic product (GDP) was essentially unchanged in July.</p>
        <p>Advance estimate of August GDP: 0.8%, not July actual.</p></html>"""
        self.assertEqual(parse_issuer_page(
            GDP,zero,expected_release="2026-09-29",expected_period="July"),0.0)
        # The actual StatCan HTML wraps GDP in inline markup; plain-text
        # extraction then becomes "( GDP )", not "(GDP)".
        wrapped=zero.replace(b"(GDP)",b"(<span>GDP</span>)")
        self.assertEqual(parse_issuer_page(
            GDP,wrapped,expected_release="2026-09-29",expected_period="July"),0.0)
        without_headline=zero.replace(b"0.0%",b"no official numeric measure")
        with self.assertRaises(Pending):
            parse_issuer_page(GDP,without_headline,
                              expected_release="2026-09-29",expected_period="July")
        with self.assertRaises(Pending):
            parse_issuer_page(GDP,zero,expected_release="2026-10-30",
                              expected_period="August")

    def test_eci_june_2026_real_header_template_and_future_date_guard(self):
        # The BLS issued Q2 2026 version reads with the same civilian
        # compensation aggregate; not a fabricated ECI Q3 actual.
        older=b"""<html>
        Transmission of material in this release is embargoed until
        USDL-26-1270
        8:30 a.m. (ET) Friday, July 31, 2026
        EMPLOYMENT COST INDEX - JUNE 2026
        Compensation costs for civilian workers increased 0.9 percent,
        seasonally adjusted, for the 3-month period ending in June 2026.
        Wages and salaries increased 0.9 percent.</html>"""
        self.assertEqual(parse_issuer_page(
            ECI,older,expected_release="Friday, July 31, 2026",
            expected_period="June"),0.9)
        with self.assertRaises(Pending):
            parse_issuer_page(ECI,older)
        ambiguous=older.replace(
            b"Compensation costs for civilian workers increased 0.9 percent,",
            b"Compensation costs for private industry workers increased 0.9 percent,")
        with self.assertRaises(Pending):
            parse_issuer_page(ECI,ambiguous,
                              expected_release="Friday, July 31, 2026",
                              expected_period="June")

    def test_gdp_all_issuer_candidates_and_bls_secondary_page_are_allowlisted(self):
        cad=TARGETS[GDP]["url"]
        self.assertEqual(len(cad),8)
        self.assertTrue(all(x.startswith(
            "https://www150.statcan.gc.ca/n1/daily-quotidien/261030/dq261030")
            for x in cad))
        self.assertTrue(all(x.endswith("-eng.htm") for x in cad))
        self.assertEqual(TARGETS[ECI]["url"],
                         ["https://www.bls.gov/news.release/eci.htm",
                          "https://www.bls.gov/news.release/eci.nr0.htm"])

    def test_archive_cannot_be_modified_or_market_causality_synthesized(self):
        rows,_=capture(self.frozen,[],AFTER,fake_fetch)
        edits=[
            lambda v:v[0].update(actual_percent=6.2),
            lambda v:v[0].update(fx_reaction="EURUSD_DOWN"),
            lambda v:v[0].update(publisher_first_release_PIT_verified=True),
            lambda v:v[1].update(previous_record_sha256="GENESIS"),
            lambda v:v[1].update(forecast_receipt_sha256="fake"),
            lambda v:v.reverse(),
            lambda v:v.append(copy.deepcopy(v[0])),
        ]
        for change in edits:
            r=copy.deepcopy(rows);change(r)
            with self.subTest(case=str(change)),self.assertRaises(ValueError):
                validate_actual_log(r,self.frozen)

    def test_late_candidate_and_unoffset_clock_rejected(self):
        never=lambda *args: (_ for _ in ()).throw(AssertionError("must not fetch"))
        rows,receipt=capture(self.frozen,[],AFTER+timedelta(days=15),never)
        self.assertEqual(rows,[])
        self.assertEqual(receipt["new_actuals"],0)
        with self.assertRaises(ValueError):
            capture(self.frozen,[],datetime(2026,10,30,13,0),never)

    def test_run_uses_existing_forecast_and_preserves_all_live_files(self):
        old=LEDGER.read_bytes()
        old_actual=OUT.read_bytes() if OUT.exists() else None
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"actuals.jsonl"
            result=run(LEDGER,out,BEFORE)
            self.assertFalse(out.exists())
            self.assertEqual(result["new_actuals"],0)
        self.assertEqual(LEDGER.read_bytes(),old)
        self.assertEqual(OUT.read_bytes() if OUT.exists() else None,old_actual)

if __name__=="__main__":
    unittest.main()
