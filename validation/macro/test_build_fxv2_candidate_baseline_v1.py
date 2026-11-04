#!/usr/bin/env python3
"""Adversarial checks that the new descriptive 8x3 candidate never becomes FX Core."""
import copy,datetime as dt,json,unittest
from pathlib import Path
from validation.macro.build_fxv2_candidate_baseline_v1 import build,ROOT
SRC=json.loads((ROOT/"site/control-room-preview/macro-v3-current-evidence.json").read_text())
NOW=dt.date(2026,11,4)
class TestCandidate(unittest.TestCase):
 def test_24_features_28_relative_contexts_no_fx_signal(self):
  out=build(SRC,NOW)
  self.assertEqual((out["summary"]["currencies"],out["summary"]["features"],out["summary"]["pairs"]),(8,24,28))
  self.assertEqual(out["summary"]["gdp_accelerations_calculable"],2)
  self.assertEqual(out["summary"]["pair_gdp_acceleration_contrasts"],1)
  self.assertEqual(out["features"]["USD"]["growth_qoq_pct"]["gdp_acceleration_pp"],.466464)
  self.assertEqual(out["features"]["EUR"]["growth_qoq_pct"]["gdp_acceleration_pp"],-.2)
  self.assertEqual(out["pairs"]["EUR/USD"]["contrasts"]["growth_acceleration_pp"]["delta_base_minus_quote_pp"],-.666464)
  self.assertIsNone(out["pairs"]["AUD/CAD"]["contrasts"]["growth_acceleration_pp"]["delta_base_minus_quote_pp"])
  self.assertFalse(out["pairs"]["AUD/CAD"]["contrasts"]["inflation_change_pp"]["same_period"])
  self.assertIsNone(out["pairs"]["AUD/CAD"]["contrasts"]["inflation_change_pp"]["delta_base_minus_quote_pp"])
  self.assertTrue(out["pairs"]["AUD/NZD"]["contrasts"]["inflation_change_pp"]["same_period"])
  self.assertIsNone(out["features"]["JPY"]["growth_qoq_pct"]["gdp_acceleration_pp"])
  for pair in out["pairs"].values():
   self.assertIsNone(pair["macro_fx_signal"])
   self.assertIsNone(pair["expected_return"])
   self.assertFalse(pair["eligible_for_core"])
  self.assertFalse(out["eligible_for_live_fx_signals"])
  self.assertFalse(out["eligible_for_backtests"])
  self.assertFalse(out["eligible_for_automatic_core_rebase"])
 def test_deterministic_and_canonical_untouched(self):
  core=(ROOT/"live_data/sections/D.json").read_bytes()
  pairs=(ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json").read_bytes()
  self.assertEqual(build(SRC,NOW),build(SRC,NOW))
  self.assertEqual(core,(ROOT/"live_data/sections/D.json").read_bytes())
  self.assertEqual(pairs,(ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json").read_bytes())
 def test_future_and_stale(self):
  for day in (dt.date(2026,11,3),dt.date(2026,11,20)):
   with self.assertRaises(ValueError):build(SRC,day)
 def test_fake_score_or_policy(self):
  for mutate in (
     lambda x:x["countries"]["USD"].update(macro_score=2.4),
     lambda x:x.update(safe_to_recompute_structural_pair_theses=True),
     lambda x:x["pair_context"]["EUR/USD"].update(pair_trade_bias="LONG"),
     lambda x:x["countries"]["NZD"]["inflation"].update(change_over_three_observation_intervals_pp=None),
     lambda x:x["countries"]["USD"]["growth"]["prior_documented_quarter"].update(reported_unit="NOT_SAAR"),
  ):
   bad=copy.deepcopy(SRC);mutate(bad)
   with self.assertRaises(ValueError):build(bad,NOW)
 def test_missing_or_unaligned_gdp_is_null(self):
  y=build(SRC,NOW)
  self.assertEqual(y["summary"]["pair_gdp_acceleration_contrasts"],1)
  self.assertEqual(sum(1 for p in y["pairs"].values() if p["contrasts"]["growth_acceleration_pp"]["delta_base_minus_quote_pp"] is not None),1)

if __name__=="__main__":unittest.main()
