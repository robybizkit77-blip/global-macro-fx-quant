"""Synthetic isolated outcome tests, never written as live evidence."""
import copy
from datetime import date, timedelta
import unittest
from unittest.mock import patch
from validation.forward import capture_v2_uniform_macro_prospective_v1 as cap
from validation.forward import observe_v2_uniform_macro_ecb_reference_returns_v1 as obs
from validation.forward.test_observe_v2_quality_aware_ecb_reference_returns_v1 import QualityAwareReferenceTests as Fixture

class UniformReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass()
        anchor=Fixture.snap
        cls.cut=Fixture.cut+timedelta(seconds=15)
        cls.fx=Fixture.fx
        u,m=cap.uniform_run(),cap.momentum_run()
        day=anchor["local_date_rome"]
        u["as_of"]=m["as_of"]=day
        cls.snap={"schema":cap.SCHEMA,"policy":cap.POLICY,"local_date_rome":day,
                  "capture_at_utc":cls.cut.isoformat(),"source_git_head":"a"*40,
                  "quality_anchor":anchor,"uniform_research":u,"momentum_research":m,
                  "historical_PIT_certified":False,"prediction_made":False,
                  "eligible_for_trading":False,"can_feed_existing_H1":False,
                  "future_outcomes_observed":False}
        cls.snap["snapshot_sha256"]=cap.sha(cls.snap)

    def test_maturity_and_idempotence(self):
        with patch.object(cap,"FIRST_DAY",date.fromisoformat(self.snap["local_date_rome"])):
            before=obs.compute([self.snap],self.fx,self.cut+timedelta(hours=1))
            self.assertEqual(before["new_matured_reference_rows"],0)
            later=self.cut+timedelta(days=2,hours=1)
            r=obs.compute([self.snap],self.fx,later)
            self.assertEqual(r["new_matured_reference_rows"],28)
            self.assertTrue(r["twenty_eight_pairs_are_not_independent_trials"])
            for row in r["new_rows"]:
                self.assertEqual(row["uniform_snapshot_id"],self.snap["snapshot_sha256"])
                self.assertEqual(row["horizon"],"1D")
                self.assertIsNone(row["trade_net_return"])
                self.assertIsNone(row["predictive_accuracy"])
            self.assertEqual(obs.compute([self.snap],self.fx,later,r["new_rows"])["new_matured_reference_rows"],0)
            altered=copy.deepcopy(r["new_rows"])
            altered[0]["observed_reference_return_pct"]=999
            with self.assertRaises(ValueError):
                obs.compute([self.snap],self.fx,later,altered)
            with self.assertRaises(ValueError):
                obs.compute([],self.fx,later,r["new_rows"])

    def test_t0_and_future_capture_rejected(self):
        with patch.object(cap,"FIRST_DAY",date.fromisoformat(self.snap["local_date_rome"])):
            with self.assertRaisesRegex(ValueError,"future"):
                obs.compute([self.snap],self.fx,self.cut-timedelta(seconds=1))
            changed=copy.deepcopy(self.fx)
            for row in changed["rows"]:
                if row["Date"]==self.snap["local_date_rome"]:
                    row["USD"]*=1.02
            with self.assertRaisesRegex(ValueError,"fixing changed"):
                obs.compute([self.snap],changed,self.cut+timedelta(days=2,hours=1))

    def test_empty_cohort_no_results(self):
        r=obs.compute([],self.fx,self.cut+timedelta(days=2,hours=1))
        self.assertEqual(r["frozen_capture_dates"],0)
        self.assertEqual(r["new_rows"],[])
