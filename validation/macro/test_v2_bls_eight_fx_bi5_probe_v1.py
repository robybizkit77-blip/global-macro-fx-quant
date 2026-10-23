import hashlib,lzma,unittest
from validation.macro.v2_bls_eight_fx_bi5_probe_v1 import event_url,run
from validation.macro.v2_dukascopy_bi5_hour_probe_v1 import FMT
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence
class EightWindowTests(unittest.TestCase):
 def test_dst_month_zero_and_utc_hours(self):
  ev=evidence()["first_release_values"]
  expected=["2026/01/11/13","2026/02/06/13","2026/03/03/12",
   "2026/04/08/12","2026/05/05/12","2026/06/02/12",
   "2026/07/07/12","2026/08/04/12"]
  self.assertEqual([event_url(x["released_at"]).split("EURUSD/")[1][:13] for x in ev[:-1]],expected)
 def test_provenance_and_all_eight_synthetic_windows(self):
  payload=lzma.compress(FMT.pack(25*60000,112260,112250,1.,1.)+
                        FMT.pack(35*60000,112280,112270,1.,1.))
  def mock(url,timeout):
   return payload,{"http_status":200,"content_length":len(payload)}
  r=run(downloader=mock,max_attempts=1)
  self.assertEqual(r["attempted_events"],8)
  self.assertEqual(r["validated_source_hours"],8)
  self.assertEqual(r["unavailable_hours"],0)
  for item in r["events"]:
   self.assertEqual(item["status"],"ACQUIRED_VALIDATED")
   self.assertEqual(item["receipt"]["source_sha256"],hashlib.sha256(payload).hexdigest())
   self.assertTrue(item["receipt"]["fx_window_complete"])
   self.assertEqual(item["receipt"]["release_at"],item["release_at"])
  for key in ("license_independently_certified","causality_claimed",
              "eligible_for_backtest","safe_to_publish_new_D",
              "safe_to_update_pair_theses","writes_live_data"):
   self.assertFalse(r[key])
 def test_failure_is_not_falsely_successful(self):
  def fail(url,timeout):raise TimeoutError("network unreachable")
  r=run(downloader=fail,max_attempts=1)
  self.assertEqual(r["validated_source_hours"],0)
  self.assertEqual(r["unavailable_hours"],8)
  self.assertTrue(all(x["receipt"] is None and
      x["error_type"]=="TimeoutError" for x in r["events"]))
if __name__=="__main__":unittest.main()
