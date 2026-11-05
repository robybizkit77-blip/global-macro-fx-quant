#!/usr/bin/env python3
"""Adversarial checks that the new descriptive 8x3 candidate never becomes FX Core."""
import copy,datetime as dt,json,unittest
from pathlib import Path
from validation.macro.build_fxv2_candidate_baseline_v1 import build,ROOT
SRC=json.loads((ROOT/"site/control-room-preview/macro-v3-current-evidence.json").read_text())
NOW=dt.date.fromisoformat(SRC['generated_europe_rome_day'])
# Fixture date follows the observed evidence; never freeze current data to 4 Nov.
class TestCandidate(unittest.TestCase):
 def test_24_features_28_relative_contexts_no_fx_signal(self):
  out=build(SRC,NOW)
  self.assertEqual((out["summary"]["currencies"],out["summary"]["features"],out["summary"]["pairs"]),(8,24,28))
  # Values/periods are derived from the publication being tested,
  # not from a historical Nov 4 snapshot of evolving MACRO_V3 inputs.
  expected_growth={}
  for c,row in SRC["countries"].items():
   current=row["growth"]
   prior=current.get("prior_documented_quarter")
   expected_growth[c]=(round(
      current["nonannualized_qoq_descriptive_pct"]-
      prior["nonannualized_qoq_descriptive_pct"],6) if prior else None)
   self.assertEqual(
      out["features"][c]["growth_qoq_pct"]["gdp_acceleration_pp"],
      expected_growth[c])
  self.assertEqual(
   out["summary"]["gdp_accelerations_calculable"],
   sum(x is not None for x in expected_growth.values()))
  expected_pair_growth=0
  for name,pair in out["pairs"].items():
   a,b=name.split("/")
   ga,gb=expected_growth[a],expected_growth[b]
   aligned=(ga is not None and gb is not None and
            SRC["countries"][a]["growth"]["reference_quarter"]==
            SRC["countries"][b]["growth"]["reference_quarter"])
   contrast=pair["contrasts"]["growth_acceleration_pp"]
   self.assertEqual(contrast["same_quarter_and_historical_depth"],aligned)
   self.assertEqual(contrast["delta_base_minus_quote_pp"],
                    round(ga-gb,6) if aligned else None)
   expected_pair_growth+=int(aligned)
  self.assertEqual(out["summary"]["pair_gdp_acceleration_contrasts"],
                   expected_pair_growth)
  for name,pair in out["pairs"].items():
   a,b=name.split("/")
   for key,source_key in (("inflation_change_pp","inflation"),
                          ("unemployment_change_pp","labour")):
    xa=SRC["countries"][a][source_key]
    xb=SRC["countries"][b][source_key]
    matched=(xa["observation_period"]==xb["observation_period"] and
             ("Q" in xa["observation_period"])==("Q" in xb["observation_period"]))
    comparison=pair["contrasts"][key]
    self.assertEqual(comparison["same_period"],matched)
    self.assertEqual(comparison["delta_base_minus_quote_pp"],
      round(xa["change_over_three_observation_intervals_pp"]-
            xb["change_over_three_observation_intervals_pp"],6)
       if matched else None)
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
  for day in (NOW-dt.timedelta(days=1),NOW+dt.timedelta(days=11)):
   with self.assertRaisesRegex(ValueError,"source publication date future or too old"):
    build(SRC,day)
 def test_new_observation_source_date_is_not_a_test_failure(self):
  # A real upstream Macro V3 refresh can legitimately roll the generation
  # date. Keep chronological guards; do not pretend a new date is synthetic.
  advanced=copy.deepcopy(SRC)
  advanced["generated_europe_rome_day"]=(NOW+dt.timedelta(days=1)).isoformat()
  out=build(advanced,NOW+dt.timedelta(days=1))
  self.assertEqual(out["as_of_research"],advanced["generated_europe_rome_day"])
  self.assertFalse(out["eligible_for_live_fx_signals"])
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
  qualified=sum(
   p["contrasts"]["growth_acceleration_pp"]["delta_base_minus_quote_pp"] is not None
   for p in y["pairs"].values())
  self.assertEqual(qualified,y["summary"]["pair_gdp_acceleration_contrasts"])
  self.assertEqual(qualified,sum(
   p["contrasts"]["growth_acceleration_pp"]["same_quarter_and_historical_depth"]
   for p in y["pairs"].values()))

if __name__=="__main__":unittest.main()
