"""Research V8: exact G8 macro series, no false candidate/actual/surprise."""
from __future__ import annotations
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import unittest

from validation.macro import g8_metric_issuer_contract_v8 as m
from validation.macro import preflight_us_cpi_official_actual_v8 as cpi
from validation.macro import build_g8_macro_event_lifecycle_v7 as v7

NOW=datetime(2026,11,9,15,10,tzinfo=timezone.utc)

def mock_bls(month,release_label,year=2026,*,hmo="increased 0.6",hyo="increased 3.7",cmo="rose 0.3",cyo="rose 2.6"):
    return f"""
    <html><body><h1>Consumer Price Index News Release</h1>
    Transmission of material in this release is embargoed until
    8:30 a.m. (ET) {release_label} USDL-26-1234
    <h2>CONSUMER PRICE INDEX - {month.upper()} {year}</h2>
    The Consumer Price Index for All Urban Consumers (CPI-U)
    {hmo} percent on a seasonally adjusted basis in {month}
    after rising 0.4 percent in the prior month. Over the last 12 months,
    the all items index {hyo} percent before seasonal adjustment.
    The index for all items less food and energy {cmo} percent in {month},
    as it did last month. The all items less food and energy index
    {cyo} percent over the year. 
    </body></html>
    """.encode("utf-8")


class G8MetricIssuerV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs,_=v7.load()
        cls.calendar=cls.inputs["official_calendar"]

    def event(self,ccy,date,title=None):
        return next(x for x in self.calendar["events"] if
                    x["ccy"]==ccy and x["date"]==date and
                    (title is None or x["title"]==title))

    def test_all_eight_g8_metric_contracts_and_no_spurious_actual_claim(self):
        d=m.verify_contract(self.calendar)
        self.assertEqual(d["currencies"],8)
        self.assertEqual(d["releases"],11)
        self.assertEqual(d["metrics"],16)
        self.assertEqual(d["templates_missing_in_current_seed"],[])
        keys=[]
        for country,entries in m.SPECS.items():
            for day,category,title,_ in entries:
                obj=self.event(country,day,title)
                for item in m.metrics_for(obj):
                    keys.append(item["metric_id"])
                    self.assertTrue(item["provider_alias_is_not_official_metric_proof"])
                    self.assertTrue(item["issuer_parser_status"])
                    self.assertTrue(item["unit"].startswith("PCT_"))
        self.assertEqual(len(keys),16)
        self.assertEqual(len(set(keys)),16)
        self.assertEqual(set(m.SPECS),set(m.FX))

    def test_bls_four_cpi_components_are_not_interchangeable(self):
        event=self.event("USD","2026-11-10")
        mapping={
            "CPI m/m":"US_CPI_U_HEADLINE_MOM_SA",
            "CPI y/y":"US_CPI_U_HEADLINE_YOY_NSA",
            "Core CPI m/m":"US_CPI_U_CORE_MOM_SA",
            "Core CPI y/y":"US_CPI_U_CORE_YOY_NSA",
        }
        for name,expected in mapping.items():
            with self.subTest(name=name):
                x=m.interpret_provider_label(event,name)
                self.assertEqual(x["metric_id"],expected)
        for wrong in ("CPI","CPI Flash m/m","Trimmed Mean CPI m/m",
                      "Core CPI","PPI m/m","CPI q/q","CPI mom",
                      "Core CPI y/y Europe","CPI m/m revised"):
            self.assertIsNone(m.interpret_provider_label(event,wrong))

    def test_japan_core_includes_energy_and_australia_monthly_not_quarterly(self):
        jp=self.event("JPY","2026-10-23")
        got=m.interpret_provider_label(jp,"National Core CPI y/y")
        self.assertEqual(got["metric_id"],"JP_CPI_CORE_EX_FRESH_FOOD_YOY")
        self.assertIn("energy included",got["component"])
        self.assertIsNone(m.interpret_provider_label(jp,"CPI q/q"))
        au=self.event("AUD","2026-10-28")
        metric=m.interpret_provider_label(au,"Monthly CPI Indicator y/y")
        self.assertEqual(metric["metric_id"],"AU_CPI_MONTHLY_INDICATOR_HEADLINE_YOY")
        self.assertEqual(metric["unit"],"PCT_YOY")
        self.assertIsNone(m.interpret_provider_label(au,"Trimmed Mean CPI q/q"))

    def test_provider_metric_candidate_never_becomes_frozen_consensus(self):
        official=self.calendar
        rows=[
            {"currency":"USD","event":"CPI m/m","date":"2026-11-10",
             "consensus":"0.4%"},
            {"currency":"USD","event":"Core CPI m/m","date":"2026-11-10",
             "consensus":"0.3%"},
            {"currency":"USD","event":"CPI y/y","date":"2026-11-10",
             "consensus":"3.8%"},
            {"currency":"EUR","event":"CPI m/m","date":"2026-11-10",
             "consensus":"8.0%"},
            {"currency":"GBP","event":"GDP q/q","date":"2026-11-12",
             "consensus":"1.0%"},
            {"currency":"CHF","event":"Swiss GDP q/q","date":"2026-11-16",
             "consensus":"0.2%"},
        ]
        found=m.enumerate_secondary_candidates(official,rows,now=NOW)
        self.assertEqual(len(found),4) # USD 3, CHF 1. UK generic blocked.
        self.assertEqual(
          set(x["metric_id"] for x in found),
          {"US_CPI_U_HEADLINE_MOM_SA","US_CPI_U_HEADLINE_YOY_NSA",
           "US_CPI_U_CORE_MOM_SA","CH_REAL_GDP_FLASH_QOQ"})
        self.assertTrue(all(x["eligible_for_existing_v1_freeze"] is False for x in found))
        self.assertTrue(all(x["eligible_for_macro_surprise"] is False for x in found))
        self.assertTrue(all(x["eligible_for_fx_signals"] is False for x in found))
        self.assertTrue(all(x["forecast_status"]=="LABEL_MATCHED_UNFROZEN_SECONDARY_NOT_ACCEPTED" for x in found))

    def test_duplicate_provider_metric_refused_instead_of_picking_arbitrary(self):
        rows=[
          {"currency":"USD","event":"CPI m/m","date":"2026-11-10","consensus":"0.4%"},
          {"currency":"USD","event":"Consumer Price Index m/m","date":"2026-11-10",
           "consensus":"0.6%"},
        ]
        matched=m.enumerate_secondary_candidates(self.calendar,rows,now=NOW)
        self.assertEqual(matched,[])

    def test_pre_release_us_cpi_never_calls_external_host(self):
        called=[]
        def fake(url,host):
            called.append((url,host))
            raise AssertionError("HTTP MUST NOT run before release")
        d=cpi.inspect(now=NOW,fetch=fake)
        self.assertEqual(d["status"],"BEFORE_RELEASE_NO_HTTP")
        self.assertIsNone(d["actual_pct"])
        self.assertIsNone(d["surprise_pp"])
        self.assertFalse(d["source_first_publication_PIT_verified"])
        self.assertEqual(called,[])

    def test_bls_pattern_correctly_keeps_four_distinct_release_units(self):
        raw=mock_bls("September","Wednesday, October 14, 2026")
        p=cpi.parse(raw=raw,month="September",
                    release_label="Wednesday, October 14, 2026")
        self.assertEqual(p["metric_actual_pct"],{
            "US_CPI_U_HEADLINE_MOM_SA":0.6,
            "US_CPI_U_HEADLINE_YOY_NSA":3.7,
            "US_CPI_U_CORE_MOM_SA":0.3,
            "US_CPI_U_CORE_YOY_NSA":2.6,
        })
        self.assertIsNone(p["surprise_vs_frozen_consensus_pp"])
        self.assertFalse(p["actual_is_first_publisher_delivery_PIT"])

    def test_bls_declines_are_signed_and_unchanged_is_zero_only_if_explicit(self):
        raw=mock_bls("October","Tuesday, November 10, 2026",
                    hmo="decreased 0.2",hyo="increased 2.8",
                    cmo="fell 0.1",cyo="rose 3.1")
        p=cpi.parse(raw=raw)["metric_actual_pct"]
        self.assertEqual(p["US_CPI_U_HEADLINE_MOM_SA"],-.2)
        self.assertEqual(p["US_CPI_U_CORE_MOM_SA"],-.1)
        raw=mock_bls("October","Tuesday, November 10, 2026",
                     hmo="was unchanged",cmo="was unchanged")
        p=cpi.parse(raw=raw)["metric_actual_pct"]
        self.assertEqual(p["US_CPI_U_HEADLINE_MOM_SA"],0)
        self.assertEqual(p["US_CPI_U_CORE_MOM_SA"],0)

    def test_wrong_release_month_or_embargo_or_ambiguous_core_fails_closed(self):
        sep=mock_bls("September","Wednesday, October 14, 2026")
        with self.assertRaises(cpi.Pending):
            cpi.parse(raw=sep)
        bad=mock_bls("October","Wednesday, October 14, 2026")
        with self.assertRaises(cpi.Pending):
            cpi.parse(raw=bad)
        missing=mock_bls("October","Tuesday, November 10, 2026",
                         cyo="unexpectedly")
        with self.assertRaises(cpi.Pending):
            cpi.parse(raw=missing)
        duplicated=mock_bls("October","Tuesday, November 10, 2026")
        duplicated=duplicated.replace(
            b"The all items less food and energy index rose",
            b"The all items less food and energy index rose",1) + \
            b"The all items less food and energy index rose 3.3 percent over the year."
        with self.assertRaises(cpi.Pending):
            cpi.parse(raw=duplicated)

    def test_after_release_official_parser_is_readonly_candidate_not_surprise(self):
        sample=mock_bls("October","Tuesday, November 10, 2026")
        calls=[]
        def fetch(url,host):
            calls.append((url,host))
            return sample,url
        d=cpi.inspect(now=datetime(2026,11,10,13,31,tzinfo=timezone.utc),
                      fetch=fetch)
        self.assertEqual(d["status"],"BLS_TARGET_CPI_METRICS_PARSED_RESEARCH_ONLY_NOT_PIT")
        self.assertEqual(len(calls),1)
        self.assertEqual(len(d["actual_pct"]),4)
        self.assertIsNone(d["surprise_pp"])
        self.assertIsNone(d["fx_signal"])
        self.assertFalse(d["frozen_consensus_available"])
        self.assertTrue(d["actual_not_promoted_to_live_data"])
        self.assertFalse(d["source_first_publication_PIT_verified"])

    def test_existing_countrybook_v7_still_has_exact_signed_two_historical_surprises(self):
        d=v7.build(now=NOW,inputs=copy.deepcopy(self.inputs))
        self.assertEqual(d["coverage"]["events_with_genuine_frozen_consensus_and_issuer_actual"],2)
        self.assertEqual(d["coverage"]["metric_definitions_v8"],16)
        self.assertEqual(d["coverage"]["metric_contract_releases_v8"],11)
        self.assertEqual(d["coverage"]["verified_metric_specific_surprises_v8"],0)
        usd=next(x for x in d["priority_queue"] if x["ccy"]=="USD")
        self.assertEqual(len(usd["metric_identity_v8"]),4)
        self.assertTrue(all(x["metric_specific_surprise_pp"] is None for x in usd["metric_identity_v8"]))
        self.assertTrue(all(x["frozen_metric_specific_consensus"] is None for x in usd["metric_identity_v8"]))
        self.assertIn("metric",v7.markdown(d).lower())

if __name__=="__main__":
    unittest.main()
