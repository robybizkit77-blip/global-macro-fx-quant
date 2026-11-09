"""No live writes / no PIT claims: test daily US/NZ issuer research intake."""
from __future__ import annotations
import copy
import csv
from datetime import datetime,timezone
from io import StringIO
import unittest

from validation.macro import collect_us_nz_household_firm_sources_v1 as mod

NOW=datetime(2026,11,9,20,0,tzinfo=timezone.utc)
SERIES={
 "USD":[
  {"id":"US_PCEC96_history_value","unit":"Billions of Chained 2017 Dollars SAAR",
   "dates":["2026-06-01","2026-07-01"],
   "values":[16900.0,16901.3],"last_date":"2026-07-01","last_value":16901.3},
  {"id":"US_DSPIC96_history_DSPIC96","unit":"Billions of Chained 2017 Dollars SAAR",
   "dates":["2026-06-01","2026-07-01"],
   "values":[18100.0,18122.5],"last_date":"2026-07-01","last_value":18122.5},
 ]
}
BEA=b"""<html><h2>Releases</h2>
<a href="/news/2026/personal-income-and-outlays-august-2026">
Personal Income and Outlays, August 2026</a>
<a href="/news/2026/personal-income-and-outlays-september-2026">
Personal Income and Outlays, September 2026</a></html>"""
NZ=b"""<html><h1>Electronic card transactions: September 2026</h1>
<p>16 October 2026, 10:45am</p>
<p>Values are at the national level and are not adjusted for price changes.</p>
<p>spending in the retail industries increased $14 million (0.1 percent).</p>
</html>"""


def fred(id,last="2026-09-01",val=17500.0):
    yy,mm=map(int,last[:7].split("-"))
    p=[]
    for i in range(28):
        index=yy*12+mm-1-(27-i)
        y,m=divmod(index,12)
        stamp=f"{y:04d}-{m+1:02d}-01"
        p.append((stamp,round(val-27+i,4)))
    io=StringIO()
    w=csv.writer(io)
    w.writerow(["observation_date",id])
    w.writerows(p)
    return io.getvalue().encode()


class UsNzSourceResearchIntakeTests(unittest.TestCase):
    def fetcher(self,url):
        if "PCEC96" in url:return fred("PCEC96"),url
        if "DSPIC96" in url:return fred("DSPIC96",val=19000),url
        if "bea.gov" in url:return BEA,url
        if "stats.govt.nz" in url:return NZ,url
        raise OSError("unknown source")

    def test_collects_new_usable_level_candidates_with_no_live_writes(self):
        original=copy.deepcopy(SERIES)
        x=mod.capture(now=NOW,fetcher=self.fetcher,series=SERIES)
        self.assertEqual(x["source_count_verified"],4)
        self.assertEqual(x["usable_new_revised_monthly_candidates"],
            ["FRED_BEAMIRROR_PCEC96","FRED_BEAMIRROR_DSPIC96"])
        us=x["sources"]["FRED_BEAMIRROR_PCEC96"]["value"]
        self.assertEqual(us["last_date"],"2026-09-01")
        self.assertEqual(us["status"],"NEWER_REVISED_SOURCE_CANDIDATE_NOT_APPLIED")
        self.assertEqual(us["metric_kind"],
            "MONTHLY_SA_CHAINED_DOLLAR_REAL_LEVEL_NOT_MOM_PCT")
        self.assertFalse(x["actual_publisher_release_PIT"])
        self.assertFalse(x["source_series_modified"])
        self.assertFalse(x["fx_signal_generated"])
        self.assertFalse(x["new_scheduler_created"])
        self.assertEqual(SERIES,original)

    def test_bea_issuer_latest_reference_is_discovery_not_actual(self):
        x=mod.official_bea_release(BEA,mod.BEA_CURRENT)
        self.assertEqual(x["release_reference_period"],"2026-09")
        self.assertEqual(x["publisher"],"BEA")
        self.assertFalse(x["actual_values_validated_here"])
        self.assertTrue(x["release_url"].startswith("https://www.bea.gov/news/2026/"))

    def test_fred_header_identity_future_and_gapped_periods_rejected(self):
        with self.assertRaisesRegex(ValueError,"identity changed"):
            mod.fred_monthly_csv(fred("PCEC96").replace(b"PCEC96",b"DSPIC96"),
                                 "PCEC96",NOW.date())
        with self.assertRaisesRegex(ValueError,"future"):
            mod.fred_monthly_csv(fred("PCEC96",last="2026-12-01"),"PCEC96",NOW.date())
        with self.assertRaisesRegex(ValueError,"not contiguous"):
            bad=fred("PCEC96").decode().splitlines()
            bad.pop(-2)
            mod.fred_monthly_csv(("\n".join(bad)+"\n").encode(),"PCEC96",NOW.date())

    def test_fred_source_behind_and_same_period_revision_are_not_live(self):
        cand=mod.fred_monthly_csv(fred("PCEC96",last="2026-05-01"),"PCEC96",NOW.date())
        self.assertEqual(mod.compare_to_existing(cand,SERIES["USD"][0])["status"],
                         "SOURCE_BEHIND_CANONICAL")
        cand=mod.fred_monthly_csv(fred("PCEC96",last="2026-07-01"),"PCEC96",NOW.date())
        self.assertEqual(mod.compare_to_existing(cand,SERIES["USD"][0])["status"],
                         "SAME_PERIOD_REVISION_CANDIDATE_NOT_APPLIED")

    def test_issuer_source_failure_explicit_withheld_no_fake_numbers(self):
        def missing(url):
            if "fred" in url:raise OSError("blocked")
            return (BEA if "bea" in url else NZ),url
        x=mod.capture(now=NOW,fetcher=missing,series=SERIES)
        self.assertEqual(x["source_count_verified"],2)
        self.assertEqual(x["usable_new_revised_monthly_candidates"],[])
        for k in ("FRED_BEAMIRROR_PCEC96","FRED_BEAMIRROR_DSPIC96"):
            self.assertEqual(x["sources"][k]["status"],
                             "WITHHELD_FETCH_OR_PARSER_UNAVAILABLE")
            self.assertNotIn("value",x["sources"][k])

    def test_statsnz_known_nominal_release_cannot_claim_latest(self):
        x=mod.statsnz_known_release(NZ,mod.NZ_ECT)
        self.assertFalse(x["latest_release_certified"])
        self.assertTrue(x["not_real_retail_volumes"])
        self.assertTrue(x["release_date_verified_in_current_html"])
        partial=mod.statsnz_known_release(
            NZ.replace(b"16 October 2026",b"date loaded in client script"),mod.NZ_ECT)
        self.assertFalse(partial["release_date_verified_in_current_html"])
        self.assertEqual(partial["status"],
                         "KNOWN_STATIC_RELEASE_TITLE_ONLY_DATE_FROM_PRIOR_RESEARCH")
        with self.assertRaisesRegex(ValueError,"identity changed"):
            mod.statsnz_known_release(NZ.replace(b"September",b"October"),mod.NZ_ECT)
        with self.assertRaisesRegex(ValueError,"nominal nature"):
            mod.statsnz_known_release(NZ.replace(b"not adjusted",b"adjusted"),mod.NZ_ECT)

    def test_source_host_redirect_violation_and_no_faked_identity(self):
        def poisoned(url):
            if "fred" in url:
                return fred("PCEC96"),"https://www.evil.invalid/fake"
            return BEA if "bea.gov" in url else NZ,url
        x=mod.capture(now=NOW,fetcher=poisoned,series=SERIES)
        self.assertEqual(x["sources"]["FRED_BEAMIRROR_PCEC96"]["status"],
                         "WITHHELD_FETCH_OR_PARSER_UNAVAILABLE")
        self.assertEqual(x["sources"]["FRED_BEAMIRROR_DSPIC96"]["status"],
                         "WITHHELD_FETCH_OR_PARSER_UNAVAILABLE")
        self.assertFalse(x["source_series_modified"])

    def test_unmatched_canonical_source_fails_closed(self):
        bad=copy.deepcopy(SERIES)
        bad["USD"][0]["id"]="other"
        with self.assertRaisesRegex(ValueError,"not unique"):
            mod.capture(now=NOW,fetcher=self.fetcher,series=bad)

    def test_capture_rejects_naive_clock(self):
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            mod.capture(now=datetime(2026,11,9,20),fetcher=self.fetcher,
                        series=SERIES)


if __name__=="__main__":
    unittest.main()
