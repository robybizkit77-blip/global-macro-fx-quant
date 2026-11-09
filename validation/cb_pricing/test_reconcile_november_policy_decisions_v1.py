#!/usr/bin/env python3
"""Prove that policy changes never turn pre-decision quotes into post-event pricing."""
import copy,unittest
from validation.cb_pricing.reconcile_november_policy_decisions_v1 import reconcile,DECISIONS
class PolicyReconciliationTest(unittest.TestCase):
 def setUp(self):
  self.canonical={}
  for c,p in DECISIONS.items():
   date="2026-11-05" if c=="AUD" else "2026-11-04"
   qs=[4.855,4.92,4.765] if c=="AUD" else [4.137,4.4049,4.6805]
   self.canonical[c]={"status":"ACTIVE","as_of":date,"policy_rate":p["old_rate"],
    "meetings":[{"date":p["date"],"status":"mapped"}],"direction":"UP",
    "horizons":{k:{"rate":v,"policy_delta_bp":round((v-p["old_rate"])*100,1)} for k,v in zip(("3m","6m","12m"),qs)},
    "cuts_hikes_priced":{}}
  self.canonical["CAD"]={"status":"ACTIVE","as_of":"2026-11-05"}
  self.o={"currencies":copy.deepcopy(self.canonical)}
  self.n={c:{"rate":p["old_rate"],"market_pricing":{"as_of":self.canonical[c]["as_of"]}} for c,p in DECISIONS.items()}
  self.n["CAD"]={"rate":2.5}
 def test_mixed_timing_and_no_cross_currency_effect(self):
  before=copy.deepcopy((self.o,self.n))
  o,n,receipt=reconcile(self.o,self.n)
  self.assertEqual((self.o,self.n),before)
  self.assertEqual(o["currencies"]["AUD"]["policy_rate"],4.85)
  self.assertEqual(n["GBP"]["rate"],4.0)
  self.assertAlmostEqual(o["currencies"]["AUD"]["horizons"]["6m"]["policy_delta_bp"],7.0)
  self.assertEqual(o["currencies"]["GBP"]["direction"],"PRE_DECISION_NO_POST_EVENT_PRICING")
  self.assertIsNone(o["currencies"]["GBP"]["horizons"]["6m"]["policy_delta_bp"])
  self.assertFalse(receipt["GBP"]["policy_comparison_aligned"])
  self.assertEqual(o["currencies"]["CAD"],self.o["currencies"]["CAD"])
  self.assertEqual(n["CAD"],self.n["CAD"])
  again,nn,_=reconcile(o,n)
  self.assertEqual(o,again)
  self.assertEqual(n,nn)
 def test_on_decision_day_without_timestamp_never_promotes_policy_delta(self):
  self.o["currencies"]["GBP"]["as_of"]=DECISIONS["GBP"]["date"]
  o,n,receipt=reconcile(self.o,self.n)
  g=o["currencies"]["GBP"]
  self.assertFalse(g["policy_comparison_temporally_aligned"])
  self.assertTrue(receipt["GBP"]["decision_day_timing_unverified"])
  self.assertEqual(g["direction"],"DECISION_DAY_TIMESTAMP_UNVERIFIED_NO_POLICY_REPRICING")
  self.assertIn("WITHHELD",g["policy_reference_note"])
  self.assertEqual(n["GBP"]["market_pricing"]["freshness_status"],"DECISION_DAY_TIMING_UNVERIFIED")
  for t in ("3m","6m","12m"):
   self.assertIsNone(g["horizons"][t]["policy_delta_bp"])
   self.assertFalse(g["horizons"][t]["policy_comparison_temporally_aligned"])
   self.assertIsNone(g["cuts_hikes_priced"][t+"_bp"])
  again,nn,_=reconcile(o,n)
  self.assertEqual(o,again)
  self.assertEqual(n,nn)
 def test_next_day_after_event_day_restores_only_descriptive_deltas(self):
  self.o["currencies"]["GBP"]["as_of"]=DECISIONS["GBP"]["date"]
  o,n,_=reconcile(self.o,self.n)
  o["currencies"]["GBP"]["as_of"]="2026-11-06"
  after,native,receipt=reconcile(o,n)
  self.assertTrue(receipt["GBP"]["policy_comparison_aligned"])
  self.assertFalse(receipt["GBP"]["decision_day_timing_unverified"])
  self.assertTrue(after["currencies"]["GBP"]["policy_comparison_temporally_aligned"])
  self.assertEqual(native["GBP"]["market_pricing"]["freshness_status"],"CURRENT_VALIDATED")
  self.assertIsNotNone(after["currencies"]["GBP"]["horizons"]["6m"]["policy_delta_bp"])
 def test_unexpected_policy_baseline_fails(self):
  self.o["currencies"]["AUD"]["policy_rate"]=4.0
  with self.assertRaisesRegex(ValueError,"unexpected policy baseline"):
   reconcile(self.o,self.n)
 def test_new_post_event_quotes_are_aligned(self):
  self.o["currencies"]["GBP"]["as_of"]="2026-11-06"
  o,_,d=reconcile(self.o,self.n)
  self.assertTrue(d["GBP"]["policy_comparison_aligned"])
  self.assertAlmostEqual(o["currencies"]["GBP"]["horizons"]["3m"]["policy_delta_bp"],13.7)
if __name__=="__main__": unittest.main()
