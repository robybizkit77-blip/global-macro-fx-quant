"""Offline gate tests: Oct30 release-time retries without extra live signals."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime,timezone,timedelta

from validation.macro.one_date_oct30_official_actual_fast_poll_gate_v1 import (
    ECI,GDP,LEDGER,OUT,RELEASE_DAY,SCHEDULED_UTC,SCHEMA,gate,
)
from validation.macro.freeze_pre_release_consensus_v1 import (
    SEED,freeze,read_existing,
)
from validation.macro.capture_official_postrelease_actuals_v1 import capture

class OneDateReleasePollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=json.loads(
            (SEED.parents[2]/"validation/macro/fixtures/pre_release_oct28_usd_cad_fixture_v1.json")
            .read_text(encoding="utf-8"))
        cls.forecasts,receipt=freeze(
            fixture["official"],fixture["consensus"],[],
            "2026-10-28T08:35:00Z")
        cls.release=datetime(2026,10,30,12,30,tzinfo=timezone.utc)
        assert len(cls.forecasts)==2
        assert receipt["new_forecasts_frozen"]==2

    def test_just_before_release_does_not_poll(self):
        r=gate(self.forecasts,[],self.release-timedelta(seconds=1))
        self.assertFalse(r["should_poll"])
        self.assertEqual(r["status"],"BEFORE_RELEASE_TIME_DO_NOT_FETCH")
        self.assertTrue(r["no_pre_scheduled_issuer_fetch"])
        self.assertEqual(r["original_official_scheduled_release_utc"],SCHEDULED_UTC)

    def test_exact_release_moment_and_retry_slots_are_eligible(self):
        for minutes in (0,7,27,57,97):
            with self.subTest(minute=minutes):
                r=gate(self.forecasts,[],self.release+timedelta(minutes=minutes))
                self.assertTrue(r["should_poll"])
                self.assertEqual(r["status"],"POLL_MISSING_ISSUER_ACTUALS_NOW")
                self.assertEqual(r["missing_events"],[ECI,GDP])
                self.assertTrue(r["no_automatic_attribution_to_ois_2y_or_fx"])
                self.assertTrue(r["no_Core_Beta_Forward_or_28pair_mutation"])

    def test_scheduled_yearly_cron_cannot_poll_after_oct2026(self):
        for when in (
            "2026-10-29T13:00:00+00:00",
            "2026-10-31T13:00:00+00:00",
            "2027-10-30T13:00:00+00:00",
            "2028-10-30T13:00:00+00:00",
        ):
            r=gate(self.forecasts,[],datetime.fromisoformat(when))
            self.assertFalse(r["should_poll"])
            self.assertEqual(r["status"],"OUTSIDE_ONCE_ONLY_RELEASE_DAY")
            self.assertTrue(r["recurrent_schedule_after_2026_oct30_has_no_active_polls"])

    def test_issuer_first_actuals_mark_complete_and_preserve_first(self):
        bls=b"""<html>embargoed until 8:30 a.m. (ET) Friday, October 30, 2026
          EMPLOYMENT COST INDEX - SEPTEMBER 2026
          Compensation costs for civilian workers increased 0.7 percent,
          seasonally adjusted, for the 3-month period ending in September 2026.</html>"""
        cad=b"""<html>Gross domestic product by industry, August 2026
           Released: 2026-10-30
           Real gross domestic product (GDP) grew 0.3% in August.</html>"""
        def fake(url,host):return (bls if host=="www.bls.gov" else cad),url
        actuals,receipt=capture(self.forecasts,[],self.release+timedelta(minutes=7),fake)
        self.assertEqual(receipt["new_actuals"],2)
        r=gate(self.forecasts,actuals,self.release+timedelta(minutes=27))
        self.assertFalse(r["should_poll"])
        self.assertEqual(r["status"],"ALL_OFFICIAL_ACTUALS_ALREADY_CAPTURED")
        partial=gate(self.forecasts,actuals[:1],self.release+timedelta(minutes=57))
        self.assertTrue(partial["should_poll"])
        self.assertEqual(partial["missing_events"],[GDP])

    def test_no_missing_frozen_event_and_no_untrusted_bad_clock(self):
        one=gate(self.forecasts[:1],[],self.release+timedelta(minutes=7))
        self.assertFalse(one["should_poll"])
        self.assertEqual(one["status"],"MISSING_BOTH_OFFICIALLY_SCHEDULED_FROZEN_FORECASTS")
        corrupted=copy.deepcopy(self.forecasts)
        corrupted[0]["consensus_value_percent"]=15
        with self.assertRaises(ValueError):
            gate(corrupted,[],self.release+timedelta(minutes=7))
        with self.assertRaises(ValueError):
            gate(self.forecasts,[],datetime(2026,10,30,13,0))

    def test_current_github_snapshot_validation_is_read_only(self):
        before=(LEDGER.read_bytes(),OUT.read_bytes())
        live_forecasts=read_existing(LEDGER)
        live_actual=read_existing(OUT)
        result=gate(live_forecasts,live_actual,
                    datetime(2026,10,28,10,20,tzinfo=timezone.utc))
        self.assertEqual(result["schema"],SCHEMA)
        self.assertFalse(result["should_poll"])
        self.assertEqual(before,(LEDGER.read_bytes(),OUT.read_bytes()))

if __name__=="__main__":unittest.main()
