import lzma,struct,unittest
from validation.macro.v2_dukascopy_bi5_hour_probe_v1 import summarize,FMT
class DukascopyBI5Tests(unittest.TestCase):
 def test_known_encoded_ticks_no_market_claim(self):
  rows=[(25*60000,116500,116490,1.,1.),(35*60000,116530,116520,1.,1.)]
  raw=b"".join(FMT.pack(*v) for v in rows)
  v=summarize(lzma.compress(raw))
  self.assertEqual(v["tick_count"],2)
  self.assertEqual(v["mid_move_pips"],3.0)
  self.assertTrue(v["fx_window_complete"])
  for key in ("source_license_independently_certified","causal_attribution",
              "ois_window_available","treasury_window_available",
              "pre_release_consensus_available","eligible_for_backtest",
              "safe_to_publish_new_D","safe_to_update_pair_theses","writes_live_data"):
   self.assertFalse(v[key])
 def test_invalid_binary_fails(self):
  for raw in (b"",b"not bi5",lzma.compress(b"abc")):
   with self.assertRaises((ValueError,lzma.LZMAError)):summarize(raw)
 def test_inverted_spread_fails(self):
  raw=FMT.pack(1500000,116490,116500,1.,1.)
  with self.assertRaises(ValueError):summarize(lzma.compress(raw))
if __name__=="__main__":unittest.main()
