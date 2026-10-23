import copy,csv,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from validation.macro.v2_eurusd_intraday_csv_research_v1 import import_csv,parse_utc
from validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 import evidence
from validation.macro.v2_shadow_features_v1 import timestamp

URL="https://www.dukascopy.com/swiss/english/marketwatch/historical/"
class OfflineFXGateTests(unittest.TestCase):
 def make(self,rows):
  t=tempfile.TemporaryDirectory()
  p=Path(t.name)/"eurusd.csv"
  with p.open("w") as f:
   w=csv.writer(f);w.writerow(["timestamp","bidPrice","askPrice"])
   w.writerows(rows)
  self.addCleanup(t.cleanup)
  return p
 def test_synthetic_pair_only_not_a_signal(self):
  at=timestamp(evidence()["first_release_values"][0]["released_at"])
  rows=[((at+timedelta(minutes=k)).isoformat(),b,b+.0001) for k,b in
        [(-6,1.10),(-5,1.1001),(4,1.1005),(5,1.1006)]]
  p=self.make(rows)
  o=import_csv(p,source_url=URL,usage_authorized=True,verified_original=True)
  self.assertEqual(o["FX_windows_complete"],1)
  self.assertEqual(len(o["events"]),9)
  self.assertEqual(o["events"][0]["pre"]["mid"],1.10015)
  self.assertEqual(o["events"][0]["post"]["mid"],1.10065)
  self.assertFalse(o["cross_asset_event_window_complete"])
  self.assertFalse(o["ready_for_backtest"])
  self.assertFalse(o["ready_for_FX_score"])
  self.assertFalse(o["safe_to_publish_new_D"])
  self.assertFalse(o["writes_live_data"])
  self.assertFalse(o["independent_license_or_source_attestation"])
  self.assertEqual(len(o["source_file_sha256"]),64)
 def test_pre_release_not_after_release_or_stale(self):
  at=timestamp(evidence()["first_release_values"][0]["released_at"])
  p=self.make([((at-timedelta(minutes=10)).isoformat(),1.1,1.1001),
     ((at+timedelta(minutes=6)).isoformat(),1.2,1.2001)])
  x=import_csv(p,source_url=URL,usage_authorized=True,verified_original=True)
  self.assertEqual(x["FX_windows_complete"],0)
 def test_false_source_or_permissions_fail(self):
  p=self.make([("2026-02-11T13:25:00Z",1.1,1.1001)])
  for kwargs in [
   dict(source_url=URL,usage_authorized=False,verified_original=True),
   dict(source_url=URL,usage_authorized=True,verified_original=False),
   dict(source_url="https://example.org/fake",usage_authorized=True,verified_original=True),
  ]:
   with self.assertRaises(ValueError):import_csv(p,**kwargs)
 def test_bad_timestamps_prices_order_fail(self):
  for rows in [
    [("2026-02-11T13:25:00",1.1,1.1001)],
    [("2026-02-11T13:25:00Z",1.2,1.1)],
    [("2026-02-11T13:25:00Z",1.1,1.1001),
     ("2026-02-11T13:24:00Z",1.1,1.1001)],
    [("2026-02-11T13:25:00Z",float("nan"),1.1)],
   ]:
   with self.subTest(rows=rows):
    with self.assertRaises((ValueError,TypeError)):
     import_csv(self.make(rows),source_url=URL,usage_authorized=True,verified_original=True)
 def test_epoch_millis_not_seconds(self):
  x=parse_utc("1770816300000")
  self.assertEqual(x.year,2026)
  with self.assertRaises(ValueError):parse_utc("1770816300")
if __name__=="__main__":unittest.main()
