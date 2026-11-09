"""Reconciliation tests: revised vintages, BEA exact m/m, no backtest contamination."""
from __future__ import annotations

import copy
import csv
from datetime import date,datetime,timezone
from io import StringIO
import unittest

from validation.macro import reconcile_us_real_households_countrybook_v2 as m
from validation.macro import collect_us_nz_household_firm_sources_v1 as old

NOW=datetime(2026,11,9,20,15,tzinfo=timezone.utc)
BEA_URL="https://www.bea.gov/news/2026/personal-income-and-outlays-september-2026"
BEA_HTML=b"""<html><h1>Personal Income and Outlays, September 2026</h1>
<p>Personal Income and Related Measures</p>
<table><thead><tr><th>Measure</th><th>August</th><th>September</th></tr></thead>
<tbody><tr><td>Real DPI</td><td>0.0</td><td>-0.3</td></tr>
<tr><td>Current-dollar PCE</td><td>0.9</td><td>0.5</td></tr>
<tr><td>Real PCE</td><td>0.5</td><td>0.0</td></tr></tbody></table></html>"""
BEA_INDEX=b"""<html>
<a href="/news/2026/personal-income-and-outlays-september-2026">
Personal Income and Outlays, September 2026</a></html>"""
NZ_HTML=b"""<html><h1>Electronic card transactions: September 2026</h1>
<p>16 October 2026</p><p>Values are not adjusted for price changes</p></html>"""


def dates():
    for i in range(84):
        month=2019*12+9+i
        yy,mm=divmod(month,12)
        yield f"{yy:04d}-{mm+1:02d}-01"


def make_values(fred):
    d=list(dates())
    if fred=="PCEC96":
        vals=[round(16400+i*5,1) for i in range(84)]
        vals[-2:]=[16960.0,16962.0]  # 0.01179% -> 0.0%, BEA
    else:
        vals=[round(18000+i*3,1) for i in range(84)]
        vals[-2:]=[18416.2,18366.1]  # -0.272% -> -0.3%, BEA
    return list(zip(d,vals))


def fred_csv(fred):
    io=StringIO()
    writer=csv.writer(io)
    writer.writerow(["observation_date",fred])
    writer.writerows(make_values(fred))
    return io.getvalue().encode()


def fake_canonical():
    records=[]
    for fred,ident in old.FRED_IDS.items():
        prev=make_values(fred)[:-2]
        dates=[x[0] for x in prev]
        vals=[round(x[1]-100,1) for x in prev]
        records.append({
            "id":ident,"dates":dates,"values":vals,
            "last_date":dates[-1],"last_value":vals[-1],
            "source_file":"US_"+fred+"_history.csv",
            "unit":(m.SAAR_UNIT if fred=="PCEC96" else ""),
            "frequency":"M",
        })
    return {"USD":records}


class USHouseholdRevisedResearchTests(unittest.TestCase):
    def capture(self):
        def fetcher(url):
            if "id=PCEC96" in url:return fred_csv("PCEC96"),url
            if "id=DSPIC96" in url:return fred_csv("DSPIC96"),url
            if "bea.gov" in url:return BEA_INDEX,url
            if "stats.govt.nz" in url:return NZ_HTML,url
            raise OSError(url)
        return old.capture(now=NOW,fetcher=fetcher,series=fake_canonical())

    def reconciled(self):
        receipt=self.capture()
        return m.reconcile(receipt,fake_canonical(),BEA_HTML,BEA_URL,at=NOW)

    def test_full_revised_history_not_tail_only_spliced(self):
        original=fake_canonical()
        before=copy.deepcopy(original)
        note=m.reconcile(self.capture(),original,BEA_HTML,BEA_URL,at=NOW)
        self.assertEqual(note["status"],
            "TWO_REVISED_REAL_SERIES_RECONCILED_WITH_BEA_ISSUER_RESEARCH_ONLY")
        self.assertEqual(note["latest_release_month"],"2026-09")
        self.assertEqual(note["revised_series"]["PCEC96"]
                         ["historical_original_months"],82)
        self.assertEqual(note["revised_series"]["PCEC96"]
                         ["overlap_revised_observation_count"],82)
        self.assertEqual(note["revised_series"]["PCEC96"]
                         ["historical_revised_months"],84)
        self.assertEqual(note["revised_series"]["PCEC96"]
                         ["latest_mom_pct_BEA_published"],0.0)
        self.assertEqual(note["revised_series"]["DSPIC96"]
                         ["latest_mom_pct_BEA_published"],-0.3)
        self.assertFalse(note["replaces_live_macro_series"])
        self.assertFalse(note["series_pit_certified"])
        self.assertEqual(original,before)

    def test_bea_and_fred_monthly_pct_agree_on_exact_metric(self):
        note=self.reconciled()
        self.assertAlmostEqual(note["revised_series"]["DSPIC96"]
                               ["latest_mom_pct_from_revised_levels"],-0.27204,places=3)
        self.assertLess(abs(note["revised_series"]["PCEC96"]
                            ["latest_mom_pct_from_revised_levels"]),.05)
        self.assertEqual(note["bea_issuer"]["values"]["nominal_pce_mom_pct"]
                         ["current_month_pct"],.5)
        self.assertIn("spesa nominale +0.5%",note["countrybook_us_households_narrative_it"])
        self.assertIn("nessun repricing Fed",note["countrybook_us_households_narrative_it"])

    def test_broken_issuer_month_rate_or_host_rejected(self):
        cap=self.capture()
        for raw,url in [
            (BEA_HTML.replace(b"September 2026",b"August 2026"),BEA_URL),
            (BEA_HTML,BEA_URL.replace("www.bea.gov","evil.invalid")),
            (BEA_HTML.replace(b"<td>-0.3</td>",b"<td>0.4</td>"),BEA_URL),
        ]:
            with self.subTest(raw=raw[:30],url=url):
                with self.assertRaisesRegex(ValueError,"WITHHELD"):
                    m.reconcile(cap,fake_canonical(),raw,url,at=NOW)

    def test_old_canonical_history_must_have_complete_coverage(self):
        bad=fake_canonical()
        bad["USD"][0]["dates"].insert(0,"2018-01-01")
        bad["USD"][0]["values"].insert(0,16000.0)
        with self.assertRaisesRegex(ValueError,"cannot replace all canonical dates"):
            m.reconcile(self.capture(),bad,BEA_HTML,BEA_URL,at=NOW)

    def test_old_vintage_unit_is_not_silently_certified_if_blank(self):
        note=self.reconciled()
        self.assertTrue(note["revised_series"]["PCEC96"]
                        ["canonical_unit_metadata_present_and_matching"])
        self.assertFalse(note["revised_series"]["DSPIC96"]
                         ["canonical_unit_metadata_present_and_matching"])
        self.assertEqual(note["revised_series"]["DSPIC96"]["expected_unit"],
                         m.SAAR_UNIT)

    def test_current_issuer_period_must_match_both_updated_fred_series(self):
        cap=self.capture()
        cap["sources"]["FRED_BEAMIRROR_DSPIC96"]["value"]["last_date"]="2026-08-01"
        with self.assertRaisesRegex(ValueError,"not synchronized"):
            m.reconcile(cap,fake_canonical(),BEA_HTML,BEA_URL,at=NOW)

    def test_later_runner_time_not_retroactively_available(self):
        cap=self.capture()
        with self.assertRaisesRegex(ValueError,"observed after"):
            m.reconcile(cap,fake_canonical(),BEA_HTML,BEA_URL,
                        at=datetime(2026,11,8,20,tzinfo=timezone.utc))

    def test_source_probe_failure_is_not_a_successful_note(self):
        cap=self.capture()
        cap["sources"]["FRED_BEAMIRROR_PCEC96"]["status"]="WITHHELD_FETCH_OR_PARSER_UNAVAILABLE"
        with self.assertRaisesRegex(ValueError,"PCEC96 source unavailable"):
            m.reconcile(cap,fake_canonical(),BEA_HTML,BEA_URL,at=NOW)

    def test_countrybook_research_overlay_is_separate_from_original_observations(self):
        result=self.reconciled()
        book=m.research_countrybook_snapshot(result,today=date(2026,11,9))
        country=book["countries"]["USD"]
        self.assertFalse(country["safe_for_site"])
        self.assertFalse(country["safe_for_reports"])
        self.assertFalse(country["countrybook_revised_household_context"]["PIT_certified"])
        self.assertFalse(country["countrybook_revised_household_context"]
                         ["historical_series_replaced"])
        self.assertEqual(country["economic_transmission_observations"]
                         ["households"][0]["observation_period"],"2026-07-01")
        self.assertIn("spesa nominale",country["economic_transmission_narrative_it"][4])

    def test_archive_note_is_plain_readonly_and_explicit_about_revision(self):
        report=m.render_md(self.reconciled())
        self.assertIn("non snapshot point-in-time",report)
        self.assertIn("82 livelli",report)
        self.assertIn("Nessuna pubblicazione live",report)

if __name__=="__main__":
    unittest.main()
