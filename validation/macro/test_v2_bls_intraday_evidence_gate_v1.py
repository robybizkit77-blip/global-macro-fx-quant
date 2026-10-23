import copy
import unittest
from validation.macro.v2_bls_intraday_evidence_gate_v1 import template,audit,FIELDS

class EvidenceGateTests(unittest.TestCase):
 def test_zero_real_event_windows_do_not_become_ois_or_fx_predictions(self):
  p=template();a=audit(p)
  self.assertEqual(a["events"],9)
  self.assertEqual(a["complete_event_windows"],0)
  self.assertEqual(a["observations_without_complete_windows"],9)
  self.assertEqual(a["research_readiness"],"DATA_GAP")
  self.assertEqual(len(p["events"]),9)
  for row in p["events"]:
   self.assertEqual(set(row["inputs"]),set(FIELDS))
   self.assertTrue(all(v is None for v in row["inputs"].values()))
  self.assertFalse(a["eligible_for_backtest"])
  self.assertFalse(a["safe_to_publish_new_D"])
  self.assertFalse(a["safe_to_update_pair_theses"])
  self.assertIsNone(a["causal_conclusion"])

 def test_fake_price_or_current_calendar_does_not_count(self):
  p=template();r=p["events"][0]
  for field in FIELDS:
   with self.subTest(field=field):
    x=copy.deepcopy(p)
    x["events"][0]["inputs"][field]={"value":4.2,"kind":"FAKE","observed_at":r["release_at"],
        "source_url":"https://example.com","license_authorized":True,"original_timestamp_verified":True,
        "source_bytes_sha256":"f"*64}
    a=audit(x)
    self.assertEqual(a["complete_event_windows"],0)
    self.assertIn(field,a["events_detail"][0]["missing_fields"])

 def test_pre_event_incorrect_claims_rejected(self):
  for edit in (
   lambda x:x["events"][0].update(actual_first_release=0),
   lambda x:x["events"][0].update(release_at="2026-02-10T13:30:00+00:00"),
   lambda x:x["events"][0]["inputs"].pop("usd_ois_before"),
   lambda x:x["events"][0].update(event_window_complete=True),
   lambda x:x["events"][0].update(causal_claim_allowed=True),
   lambda x:x["events"].pop(),
  ):
   x=template();edit(x)
   with self.assertRaises(ValueError):audit(x)

 def test_reproducible_readonly(self):
  p=template();before=copy.deepcopy(p)
  self.assertEqual(audit(p),audit(p))
  self.assertEqual(p,before)

if __name__=="__main__":
 unittest.main()
