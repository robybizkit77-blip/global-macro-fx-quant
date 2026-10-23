import unittest
from validation.macro.v2_usd_labour_research_desk_brief_v1 import build
class USDLabourDeskTests(unittest.TestCase):
 def test_real_research_summary_is_descriptive_not_macro_score(self):
  a=build();b=build()
  self.assertEqual(a,b)
  self.assertEqual(a["what_happened"]["u3_percent"],4.2)
  self.assertEqual(a["what_happened"]["prior_median_u3_percent"],4.2)
  self.assertEqual(a["what_changed"]["change_percentage_points"],0.1)
  self.assertEqual(a["what_changed"]["prior_u3_2026_08_percent"],4.1)
  self.assertEqual(a["market_response_evidence"]["bls_events"],9)
  self.assertEqual(a["market_response_evidence"]["event_aligned_usd_ois_windows"],0)
  self.assertEqual(a["market_response_evidence"]["pre_release_consensus_windows"],0)
  self.assertIsNone(a["what_changed"]["monthly_velocity_signal"])
  self.assertTrue(a["market_response_evidence"]["rates_fx_association_not_causation"])
  for key in ["full_PIT_vintage_certified","eligible_for_live_macro_score",
              "eligible_for_backtest","safe_to_publish_new_D",
              "safe_to_update_pair_theses","writes_live_data"]:
   self.assertFalse(a[key],key)
  self.assertEqual(len(a["inferences_withheld"]),5)
if __name__=="__main__":unittest.main()
