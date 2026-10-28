"""Synthetic future ECB fixings ONLY in test memory, no prospective backfill.

The fixture day follows the Rome business clock, even when live source files
advance beyond the original Oct-27 development date. Every synthetic ECB
quote/date is tagged test-only and never persisted to any real ledger.
"""
import copy
from datetime import datetime, timedelta
import unittest

from validation.forward import capture_v2_research_prospective_evidence_v1 as cap
from validation.forward import observe_v2_research_ecb_reference_returns_v1 as obs
from validation.forward.test_capture_v2_research_prospective_evidence_v1 import (
    V2ProspectiveResearchCapture as IsolatedFixture
)


class V2ECBMaturedReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        IsolatedFixture.setUpClass()
        cls.cut=IsolatedFixture.cut
        cls.day=IsolatedFixture.day
        fx=copy.deepcopy(IsolatedFixture.fx)
        cls.snap=cap.make(cls.cut,cls.cut+timedelta(seconds=8),
            fx=fx,pair_setup=copy.deepcopy(IsolatedFixture.pairs),
            legacy=copy.deepcopy(IsolatedFixture.legacy),
            candidate=copy.deepcopy(IsolatedFixture.candidate),
            banks=copy.deepcopy(IsolatedFixture.cb),
            ois=copy.deepcopy(IsolatedFixture.ois),
            rates=copy.deepcopy(IsolatedFixture.rates),
            source_hashes=copy.deepcopy(IsolatedFixture.hashes))
        # Future OBSERVATIONS only inside these synthetic unit-test dicts.
        future=copy.deepcopy(fx)
        fake=copy.deepcopy(future["rows"][-1])
        cls.synthetic_future_day=(cls.cut.date()+timedelta(days=2)).isoformat()
        fake["Date"]=cls.synthetic_future_day
        fake["USD"]=round(float(fake["USD"])*1.01,8)
        future["rows"].append(fake)
        future["last_as_of"]=cls.synthetic_future_day
        future["row_count"]=len(future["rows"])
        cls.synthetic_future_fx=future

    def evening(self,days):
        return (self.cut+timedelta(days=days)).replace(
            hour=21,minute=15,second=0,microsecond=0)

    def test_time_horizons_have_strict_post_maturity_fixing(self):
        before=self.evening(1)
        x=obs.compute([self.snap],self.synthetic_future_fx,before)
        self.assertEqual(x["new_matured_reference_rows"],0)
        self.assertGreater(x["waiting"]["not_matured"]+
                           x["waiting"]["missing_reference_after_maturity"],0)
        after=self.evening(3)
        done=obs.compute([self.snap],self.synthetic_future_fx,after)
        self.assertEqual(done["new_matured_reference_rows"],28)
        self.assertEqual({r["horizon"] for r in done["new_rows"]},{"1D"})
        self.assertTrue(all(
            r["maturity_date"]==(self.cut.date()+timedelta(days=1)).isoformat() and
            r["first_observed_ecb_date_strictly_after_maturity"]==self.synthetic_future_day
            for r in done["new_rows"]))
        self.assertTrue(all(r["reference_source"]==obs.SOURCE_URL for r in done["new_rows"]))
        self.assertTrue(all(r["trade_net_return"] is None and
                            r["trade_direction"] is None and
                            r["beta_predictive_accuracy"] is None and
                            r["model_alpha_claim"] is False for r in done["new_rows"]))
        self.assertEqual(len({(r["shadow_snapshot_id"],r["pair"],r["horizon"])
                              for r in done["new_rows"]}),28)
        for r in done["new_rows"]:
            self.assertEqual(r["reference_return_sha256"],obs.sha(
                {k:v for k,v in r.items() if k!="reference_return_sha256"}))

    def test_already_observed_is_idempotent_and_tampering_fails(self):
        now=self.evening(3)
        first=obs.compute([self.snap],self.synthetic_future_fx,now)["new_rows"]
        again=obs.compute([self.snap],self.synthetic_future_fx,now,first)
        self.assertEqual(again["new_matured_reference_rows"],0)
        self.assertEqual(again["waiting"]["already_recorded"],28)
        with self.assertRaises(ValueError):
            obs.compute([self.snap],self.synthetic_future_fx,now,first+first)
        broken=copy.deepcopy(first)
        broken[0]["trade_net_return"]=0.95
        with self.assertRaises(ValueError):
            obs.compute([self.snap],self.synthetic_future_fx,now,broken)

    def test_no_fake_t0_recalibration_and_no_ex_post_snapshots(self):
        now=self.evening(3)
        altered=copy.deepcopy(self.snap)
        altered["observed_t0_ref"]["EUR/USD"]["rate"]*=1.3
        altered["snapshot_sha256"]=obs.sha({
            k:v for k,v in altered.items() if k!="snapshot_sha256"})
        with self.assertRaises(ValueError):
            obs.compute([altered],self.synthetic_future_fx,now)
        past=copy.deepcopy(self.snap)
        past["future_outcomes_observed_at_capture"]=True
        past["snapshot_sha256"]=obs.sha({
            k:v for k,v in past.items() if k!="snapshot_sha256"})
        with self.assertRaises(ValueError):
            obs.compute([past],self.synthetic_future_fx,now)
        with self.assertRaises(ValueError):
            obs.compute([self.snap,self.snap],self.synthetic_future_fx,now)
        with self.assertRaises(ValueError):
            obs.compute([self.snap],self.synthetic_future_fx,self.evening(0).replace(hour=12))

    def test_no_source_after_due_is_not_interpolated(self):
        future=copy.deepcopy(self.synthetic_future_fx)
        gap_day=(self.cut.date()+timedelta(days=9)).isoformat()
        future["rows"][-1]["Date"]=gap_day
        future["last_as_of"]=gap_day
        now=self.evening(9)
        report=obs.compute([self.snap],future,now)
        self.assertFalse(any(r["horizon"]=="1D" for r in report["new_rows"]))
        self.assertGreater(report["waiting"]["source_gap"],0)

    def test_existing_repository_ledgers_remain_unchanged(self):
        files=[cap.JOURNAL,obs.OUTCOMES,
               cap.ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"]
        original={str(p):p.read_bytes() if p.exists() else None for p in files}
        _=obs.compute([self.snap],self.synthetic_future_fx,self.evening(3))
        self.assertEqual(original,{str(p):p.read_bytes() if p.exists() else None
                                   for p in files})


if __name__=="__main__":
    unittest.main()
