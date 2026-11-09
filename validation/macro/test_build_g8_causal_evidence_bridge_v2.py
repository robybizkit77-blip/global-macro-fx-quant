"""Fail-closed V2 test suite: 8 currencies, role depth, provenance, no fake signals."""
import copy
import json
import tempfile
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import unittest

from validation.macro import build_g8_causal_evidence_bridge_v2 as m


class EvidenceBridgeV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day=datetime.now(ZoneInfo("Europe/Rome")).date()
        cls.book=m.build(today=cls.day)

    def test_24_roles_and_country_book_are_explicit(self):
        b=self.book
        self.assertEqual(tuple(b["countries"]),m.v1.FX)
        self.assertEqual(b["coverage"]["countries"],8)
        self.assertEqual(b["coverage"]["roles_possible"],24)
        self.assertEqual(b["coverage"]["causal_channels_proven"],0)
        self.assertEqual(b["coverage"]["new_fx_signals"],0)
        self.assertIn("NZD.firms",b["coverage"]["roles_missing_direct_observation"])
        self.assertIn("NZD.households",b["coverage"]["roles_without_all_recent_periods"])
        self.assertFalse(b["publication_timestamps_verified"])
        self.assertFalse(b["source_revision_vintage_verified"])
        self.assertTrue(b["no_new_fx_ranking"])
        self.assertTrue(b["no_live_site_publication"])
        self.assertTrue(b["no_report_promotion"])

    def test_all_8_country_roles_derived_from_real_selected_series(self):
        ids=set()
        for c,row in self.book["countries"].items():
            d=row["economic_transmission_observations"]
            self.assertEqual(set(d),{"firms","labor","households"})
            self.assertEqual(len(row["economic_transmission_narrative_it"]),9)
            self.assertFalse(row["safe_for_site"])
            self.assertFalse(row["safe_for_reports"])
            self.assertFalse(row["economic_evidence_summary"]["causal_chain_confirmed"])
            self.assertEqual(row["human_review_status"],"UNREVIEWED_RESEARCH_PILOT")
            for role,evidence in d.items():
                for obs in evidence:
                    self.assertEqual(obs["publisher_release_timestamp"],None)
                    self.assertEqual(obs["source_data_lineage"],"REVISED_CURRENT_VINTAGE_NOT_FIRST_RELEASE")
                    self.assertTrue(obs["observation_period_age_days"]>=0)
                    self.assertIn(obs["status"],(
                        "RECENT_PERIOD_NOT_RELEASE_VERIFIED",
                        "DATED_PERIOD_NOT_CURRENT",
                        "STALE_HISTORICAL_PERIOD"))
                    self.assertIsInstance(obs["source_file"],str)
                    self.assertIn(obs["direction_of_reported_series"],(
                        "SALITA","DISCESA","STABILE","NO_CONTIGUOUS_COMPARISON"))
                    ids.add(obs["id"])
        self.assertGreaterEqual(len(ids),30)

    def test_historical_nz_household_does_not_become_current(self):
        r=self.book["countries"]["NZD"]["economic_transmission_observations"]["households"][0]
        self.assertEqual(r["id"],"NZ_RETAIL_VOLUME_Q_history_value")
        self.assertEqual(r["status"],"STALE_HISTORICAL_PERIOD")
        self.assertNotIn("direzione recente",self.book["countries"]["NZD"]["economic_transmission_narrative_it"][4])

    def test_observation_dates_are_periods_not_publication_timestamps(self):
        self.assertEqual(m.observation_end("2026-Q3","Q"),(date(2026,9,30),"Q"))
        self.assertEqual(m.observation_end("2026Q3","Q"),(date(2026,9,30),"Q"))
        self.assertEqual(m.observation_end("2026-09-01","M"),(date(2026,9,30),"M"))
        self.assertEqual(m.observation_end("2026-09","M"),(date(2026,9,30),"M"))
        self.assertEqual(m.observation_end("31 Jul 2026","M"),(date(2026,7,31),"M"))
        self.assertEqual(m.observation_end("31/07/2026","M"),(date(2026,7,31),"M"))
        self.assertEqual(m.observation_end("Jul-26","M"),(date(2026,7,31),"M"))
        self.assertEqual(m.observation_end("2026/09","Q"),(date(2026,9,30),"Q"))

    def test_reject_future_period_and_inconsistent_latest_value(self):
        sample={"id":"example","label":"test","dates":["2026-09","2026-10"],
                "values":[10,11],"last_date":"2026-10","last_value":11,
                "frequency":"M","source_file":"test.csv"}
        with self.assertRaisesRegex(ValueError,"future observation"):
            m.evidence_row(sample,today=date(2026,9,30))
        sample["last_value"]=100
        with self.assertRaisesRegex(ValueError,"inconsistent latest observation value"):
            m.evidence_row(sample,today=date(2026,11,9))
        sample["last_value"]=11
        sample["last_date"]="2026-11"
        with self.assertRaisesRegex(ValueError,"inconsistent latest observation date"):
            m.evidence_row(sample,today=date(2026,11,9))

    def test_non_contiguous_months_cannot_claim_direction(self):
        sample={"id":"x","label":"x","dates":["2026-01","2026-09"],
                "values":[1,2],"last_date":"2026-09","last_value":2,
                "frequency":"M","source_file":"x.csv"}
        r=m.evidence_row(sample,today=date(2026,11,9))
        self.assertEqual(r["direction_of_reported_series"],"NO_CONTIGUOUS_COMPARISON")
        self.assertIsNone(r["change_raw_units"])

    def test_australian_nominal_spending_not_misread_as_real_consumption(self):
        row=self.book["countries"]["AUD"]
        obs=row["economic_transmission_observations"]["households"][0]
        self.assertEqual(obs["id"],"AU_HOUSEHOLD_SPENDING_history_value")
        self.assertEqual(obs["household_price_volume_basis"],
                         "NOMINAL_CURRENT_PRICE")
        self.assertFalse(obs["real_consumption_change_certified"])
        text=row["economic_transmission_narrative_it"][4]
        self.assertIn("prezzi correnti",text)
        self.assertIn("non dimostra maggiori volumi reali",text)

    def test_japanese_retail_index_is_not_automatically_real_consumption(self):
        row=self.book["countries"]["JPY"]
        obs=row["economic_transmission_observations"]["households"][0]
        self.assertEqual(obs["id"],"JP_RETAIL_history_value")
        self.assertEqual(obs["household_price_volume_basis"],
                         "REAL_VOLUME_BASIS_NOT_VERIFIED")
        self.assertFalse(obs["real_consumption_change_certified"])
        text=row["economic_transmission_narrative_it"][4]
        self.assertIn("non è dimostrato",text)

    def test_australian_spending_basis_change_fails_closed(self):
        from validation.macro.build_g8_causal_evidence_bridge_v2 import evidence_row
        sample={"id":"AU_HOUSEHOLD_SPENDING_history_value",
                "label":"Spesa famiglie","dates":["2026-06","2026-07"],
                "values":[100,105],"last_date":"2026-07","last_value":105,
                "frequency":"M","unit":"AUD million SA",
                "source_file":"fixture.csv"}
        with self.assertRaisesRegex(ValueError,
                                    "no longer attested as current price"):
            evidence_row(sample,today=date(2026,11,9))

    def test_us_new_bea_real_nominal_release_is_supplement_not_revised_history(self):
        row=self.book["countries"]["USD"]
        release=row["publisher_release_context"]
        self.assertIsNotNone(release)
        self.assertTrue(release["static_not_auto_refreshed"])
        self.assertFalse(release["replaces_historical_source"])
        byid={x["id"]:x for x in release["source_facts"]}
        self.assertEqual(byid["US_BEA_SEP2026_REAL_PCE_MOM"]["value"],0.0)
        self.assertEqual(byid["US_BEA_SEP2026_REAL_PCE_MOM"]["previous_value"],0.5)
        self.assertEqual(byid["US_BEA_SEP2026_NOMINAL_PCE_MOM"]["value"],0.5)
        self.assertEqual(byid["US_BEA_SEP2026_REAL_DPI_MOM"]["value"],-0.3)
        self.assertIn("NOMINALE",row["economic_transmission_narrative_it"][4])
        self.assertIn("REALE",row["economic_transmission_narrative_it"][4])
        self.assertEqual(row["economic_transmission_observations"]["households"][0]
                         ["observation_period"],"2026-07-01")
        self.assertFalse(row["safe_for_site"])
        self.assertFalse(row["safe_for_reports"])

    def test_nzd_survey_vs_volume_not_promoted_as_direct_firm_sales(self):
        row=self.book["countries"]["NZD"]
        self.assertEqual(row["economic_evidence_summary"]["missing_roles"],["firms"])
        release=row["publisher_release_context"]
        facts={x["id"]:x for x in release["source_facts"]}
        self.assertEqual(facts["NZ_NZIER_QSBO_SEP2026_GENERAL_CONFIDENCE"]["value"],40.0)
        self.assertEqual(facts["NZ_NZIER_QSBO_SEP2026_OWN_DOMESTIC_ACTIVITY"]["value"],-1.0)
        self.assertEqual(facts["NZ_STATS_JUN2026_RETAIL_REAL_QOQ"]["value"],-0.5)
        self.assertEqual(facts["NZ_STATS_JUN2026_RETAIL_NOMINAL_QOQ"]["value"],0.9)
        self.assertEqual(facts["NZ_STATS_SEP2026_ECT_RETAIL_VALUE_QOQ"]["value"],0.1)
        self.assertIn("survey non è produzione",row["economic_transmission_narrative_it"][4])
        self.assertIn("transazioni elettroniche",row["economic_transmission_narrative_it"][4])
        self.assertFalse(release["proves_causal_chain"])
        self.assertIn("NZD.firms",self.book["coverage"]["roles_missing_direct_observation"])

    def test_release_snapshot_not_visible_before_our_own_research_clock(self):
        old=m.publisher_release_facts(today=date(2026,11,8))
        self.assertEqual(old["countries"],{})
        self.assertFalse(old["publisher_release_dates_are_first_desktop_observations"])
        fresh=m.publisher_release_facts(today=date(2026,11,9))
        self.assertEqual(sorted(fresh["countries"]),["NZD","USD"])
        self.assertTrue(fresh["static_not_auto_refreshed"])

    def test_publisher_url_and_real_nominal_identity_fail_closed(self):
        src=(m.v1.ROOT / m.SOURCE_RELEASE_CONTEXT).read_text(encoding="utf-8")
        orig=json.loads(src)
        cases=[]
        broken=copy.deepcopy(orig)
        broken["countries"]["USD"]["release_facts"][0]["price_basis"]="NOMINAL_CURRENT_DOLLAR"
        cases.append(broken)
        broken=copy.deepcopy(orig)
        broken["countries"]["NZD"]["release_facts"][2]["source_url"]="https://fake.example.com"
        cases.append(broken)
        broken=copy.deepcopy(orig)
        broken["countries"]["USD"]["release_facts"][0]["release_date"]="2026-11-25"
        cases.append(broken)
        broken=copy.deepcopy(orig)
        broken["countries"]["NZD"]["release_facts"][4]["group"]="actual_firm_sales"
        cases.append(broken)
        for item in cases:
            with self.subTest(case=cases.index(item)):
                with tempfile.TemporaryDirectory() as tmp:
                    p=Path(tmp)/m.SOURCE_RELEASE_CONTEXT
                    p.parent.mkdir(parents=True)
                    p.write_text(json.dumps(item),encoding="utf-8")
                    with self.assertRaisesRegex(ValueError,"G8_EVIDENCE_V2_REJECTED"):
                        m.publisher_release_facts(today=date(2026,11,9),root=Path(tmp))

    def test_no_core_signal_and_no_external_write(self):
        b=self.book
        for c in m.v1.FX:
            r=b["countries"][c]
            self.assertIsNone(r["automatic_fx_signal"])
            self.assertIsNone(r["expected_return"])
        out=m.markdown(b)
        self.assertIn("RICERCA NON PUBBLICATA SUL SITO",out)
        self.assertNotIn("PROBABILITÀ FEDE",out)


if __name__=="__main__":
    unittest.main()
