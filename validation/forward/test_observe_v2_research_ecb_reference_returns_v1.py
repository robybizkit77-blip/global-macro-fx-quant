"""Test purely synthetic future ECB prices; NEVER write them to production."""
import copy
from datetime import datetime, timedelta
import unittest

from validation.forward import capture_v2_research_prospective_evidence_v1 as cap
from validation.forward import observe_v2_research_ecb_reference_returns_v1 as obs


class V2ECBMaturedReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cut=datetime.fromisoformat("2026-10-27T19:31:00+01:00")
        fx=cap.read_live("ECB_G8_PRICE_HISTORY")
        pair=cap.read_live("PAIR_SETUP_OPERATIONAL_VIEW")
        core=cap.read_live("D")
        candidate=cap.domestic_run(as_of="2026-10-27")
        cb=cap.read_live("NATIVE_CB_DATA")
        ois=cap.read_live("OIS_OPERATIONAL_VIEW")
        rates=cap.read_live("NATIVE_RATES_DATA")
        hashes={
            "ecb":cap.file_sha("live_data/sections/ECB_G8_PRICE_HISTORY.json"),
            "pair_setup":cap.file_sha("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"),
            "legacy_core":cap.file_sha("live_data/sections/D.json"),
            "candidate":cap.sha(candidate),
            "native_cb":cap.file_sha("live_data/sections/NATIVE_CB_DATA.json"),
            "ois_view":cap.file_sha("live_data/sections/OIS_OPERATIONAL_VIEW.json"),
            "native_rates":cap.file_sha("live_data/sections/NATIVE_RATES_DATA.json"),
        }
        cls.snap=cap.make(cls.cut,cls.cut+timedelta(seconds=8),
            fx=fx,pair_setup=pair,legacy=core,candidate=candidate,
            banks=cb,ois=ois,rates=rates,source_hashes=hashes)
        # Synthetic future price only in test RAM; mark it unambiguously.
        future=copy.deepcopy(fx)
        fake=copy.deepcopy(future["rows"][-1])
        fake["Date"]="2026-10-29"
        fake["USD"]=round(float(fake["USD"])*1.01,8)
        future["rows"].append(fake)
        future["last_as_of"]="2026-10-29"
        future["row_count"]=len(future["rows"])
        cls.synthetic_future_fx=future

    def test_time_horizons_have_strict_post_maturity_fixing(self):
        before=datetime.fromisoformat("2026-10-28T21:15:00+01:00")
        x=obs.compute([self.snap],self.synthetic_future_fx,before)
        self.assertEqual(x["new_matured_reference_rows"],0)
        self.assertGreater(x["waiting"]["not_matured"]+
                           x["waiting"]["missing_reference_after_maturity"],0)
        after=datetime.fromisoformat("2026-10-30T21:15:00+01:00")
        done=obs.compute([self.snap],self.synthetic_future_fx,after)
        self.assertEqual(done["new_matured_reference_rows"],28)
        self.assertEqual({r["horizon"] for r in done["new_rows"]},{"1D"})
        self.assertTrue(all(r["maturity_date"]=="2026-10-28" and
                            r["first_observed_ecb_date_strictly_after_maturity"]=="2026-10-29"
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
        now=datetime.fromisoformat("2026-10-30T21:15:00+01:00")
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
        now=datetime.fromisoformat("2026-10-30T21:15:00+01:00")
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
            obs.compute([self.snap],self.synthetic_future_fx,
                        datetime.fromisoformat("2026-10-27T12:00:00+01:00"))

    def test_no_source_after_due_is_not_interpolated(self):
        future=copy.deepcopy(self.synthetic_future_fx)
        future["rows"][-1]["Date"]="2026-11-05"
        future["last_as_of"]="2026-11-05"
        now=datetime.fromisoformat("2026-11-05T21:15:00+01:00")
        report=obs.compute([self.snap],future,now)
        self.assertFalse(any(r["horizon"]=="1D" for r in report["new_rows"]))
        self.assertGreater(report["waiting"]["source_gap"],0)

    def test_existing_repository_ledgers_remain_unchanged(self):
        files=[cap.JOURNAL,obs.OUTCOMES,
               cap.ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl"]
        original={str(p):p.read_bytes() if p.exists() else None for p in files}
        _=obs.compute([self.snap],self.synthetic_future_fx,
                      datetime.fromisoformat("2026-10-30T21:15:00+01:00"))
        self.assertEqual(original,{str(p):p.read_bytes() if p.exists() else None
                                   for p in files})


if __name__=="__main__":
    unittest.main()
