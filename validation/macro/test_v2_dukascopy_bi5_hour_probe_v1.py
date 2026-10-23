import lzma,struct,unittest
from unittest.mock import patch
from validation.macro.v2_dukascopy_bi5_hour_probe_v1 import summarize,FMT,URL,fetch,source_clock
class DukascopyBI5Tests(unittest.TestCase):
 def test_known_encoded_ticks_no_market_claim(self):
  rows=[(25*60000,116500,116490,1.,1.),(35*60000,116530,116520,1.,1.)]
  raw=b"".join(FMT.pack(*v) for v in rows)
  v=summarize(lzma.compress(raw))
  self.assertEqual(v["tick_count"],2)
  self.assertEqual(v["mid_move_pips"],3.0)
  self.assertTrue(v["fx_window_complete"])
  self.assertEqual(v["source_path_calendar_utc"],"2026-10-02T12:00:00+00:00")
  self.assertEqual(v["bi5_month_index_zero_based"],9)
  self.assertEqual(v["pre_0825_new_york"]["observed_at_utc"],"2026-10-02T12:25:00+00:00")
  self.assertFalse(v["source_bytes_externally_retrieved"])
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
 def test_url_requires_canonical_zero_based_month_path(self):
  base,parts=source_clock(URL)
  self.assertEqual(base.isoformat(),"2026-10-02T12:00:00+00:00")
  self.assertEqual(parts["month0"],9)
  for bad in (URL.replace("/09/","/12/"),URL.replace("12h_ticks.bi5","ticks.bi5"),URL.replace("https:","http:")):
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):source_clock(bad)
 def test_transport_receipt_must_match_exact_bytes(self):
  data=lzma.compress(FMT.pack(25*60000,116500,116490,1.,1.))
  with self.assertRaisesRegex(ValueError,"content length"):summarize(data,transport_receipt={"content_length":len(data)-1})
  r=summarize(data,transport_receipt={"content_length":len(data),"http_status":200})
  self.assertTrue(r["source_bytes_externally_retrieved"])
  self.assertEqual(r["transport_receipt"]["http_status"],200)
 def test_fetch_rejects_mismatched_http_response(self):
  class Response:
   status=200
   headers={"Content-Length":"4","Content-Type":"application/octet-stream"}
   def read(self,_):return b"abc"
   def geturl(self):return URL
   def __enter__(self):return self
   def __exit__(self,*_):return False
  with patch("urllib.request.urlopen",return_value=Response()):
   with self.assertRaisesRegex(ValueError,"byte count"):fetch(URL,10)
if __name__=="__main__":unittest.main()
