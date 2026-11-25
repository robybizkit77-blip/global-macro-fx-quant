import unittest
from datetime import datetime, timezone
from validation.macro.recurring_official_actuals_v1 import build, metrics, identity

NOW=datetime(2026,11,25,15,33,tzinfo=timezone.utc)
ABS={"ccy":"AUD","source_family":"ABS","title":"Consumer Price Index, Australia","event_type":"INFLATION","reference_period":"October 2026","date":"2026-11-25","time_local":"11:30","timezone":"Australia/Sydney"}
GDP={"ccy":"USD","source_family":"BEA","title":"GDP (Second Estimate) and Corporate Profits","event_type":"GROWTH","reference_period":"Q3 2026","date":"2026-11-25","time_local":"08:30","timezone":"America/New_York"}
PCE={**GDP,"title":"Personal Income and Outlays","event_type":"INFLATION","reference_period":"October 2026"}
HTML_ABS="<h2>Reference period</h2>October 2026 <h2>Released</h2>25/11/2026 <h2>Key statistics</h2> The Consumer Price Index (CPI) rose 4.9%, up from 4.3%. Trimmed mean inflation was 3.8%, up from 3.6%. <h2>Important release updates</h2>"
HTML_GDP="November 25, 2026 <h1>GDP (Second Estimate) and Corporate Profits, 3rd Quarter 2026</h1> Real gross domestic product (GDP) increased at an annual rate of 4.3 percent in the third quarter of 2026. In the second quarter, real GDP increased 2.2 percent."
HTML_PCE="November 25, 2026 <h1>Personal Income and Outlays, October 2026</h1> <a>From the preceding month, the PCE price index for October increased 0.3 percent</a>. Excluding food and energy, the PCE price index also increased 0.3 percent. <a>From the same month one year ago, the PCE price index for October increased 3.8 percent</a>. Excluding food and energy, the PCE price index increased 3.3 percent."

class Tests(unittest.TestCase):
    def test_exact_metrics(self):
        self.assertEqual([m[2] for m in metrics(ABS,HTML_ABS)],[4.9,3.8])
        self.assertEqual(metrics(GDP,HTML_GDP)[0][2:],(4.3,2.2))
        self.assertEqual(metrics(GDP,HTML_GDP.replace('product (GDP)','product (<b>GDP</b>)'))[0][2:],(4.3,2.2))
        self.assertEqual([m[2] for m in metrics(PCE,HTML_PCE)],[.3,.3,3.8,3.3])
        self.assertEqual(metrics(GDP,HTML_GDP.replace("increased at an annual rate","decreased at an annual rate"))[0][2],-4.3)
    def test_next_period_url_and_wrong_identity(self):
        next_event={**ABS,"reference_period":"November 2026","date":"2027-01-06"}
        self.assertTrue(identity(next_event)[1].endswith("nov-2026"))
        with self.assertRaises(ValueError): metrics(next_event,HTML_ABS)
        with self.assertRaises(ValueError): metrics(GDP,HTML_GDP.replace("November 25","November 24"))
    def test_no_future_or_unverified_results(self):
        before=datetime(2026,11,25,12,tzinfo=timezone.utc)
        items,checks=build({"events":[GDP]},before,fetch=lambda u:HTML_GDP,clock=lambda:before)
        self.assertEqual((items,checks),([],[]))
        items,checks=build({"events":[PCE]},NOW,fetch=lambda u:"wrong page",clock=lambda:NOW)
        self.assertEqual(items,[])
        self.assertEqual(checks[0]["status"],"SOURCE_UNVERIFIED")
    def test_same_release_retains_original_clock(self):
        items,checks=build({"events":[ABS]},NOW,fetch=lambda u:HTML_ABS,clock=lambda:NOW)
        self.assertEqual(checks[0]["status"],"VERIFIED")
        later=NOW.replace(minute=40)
        again,checks=build({"events":[ABS]},later,previous=items,fetch=lambda u:self.fail("already verified"),clock=lambda:later)
        self.assertEqual(checks[0]["status"],"VERIFIED")
        self.assertEqual(again[0]["first_runner_observed_at_utc"],items[0]["first_runner_observed_at_utc"])
        rolled,_=build({"events":[]},later,previous=items,clock=lambda:later)
        self.assertEqual(len(rolled),1)

if __name__=="__main__": unittest.main()
