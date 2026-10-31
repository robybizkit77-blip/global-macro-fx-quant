#!/usr/bin/env python3
"""Adversarial CHF official same-basis source backfill, no artificial dates."""
import copy
import json
import unittest
from datetime import date
from pathlib import Path
from recover_chf_snb_paired_history_v1 import verify, KEYS, SCHEMA
ROOT=Path(__file__).resolve().parents[2]
RATES=json.loads((ROOT/'live_data/sections/NATIVE_RATES_DATA.json').read_text())
CONTEXT=json.loads((ROOT/'live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json').read_text())
BASE={
 'timeseries':[
  {'metadata':{'key':KEYS['2Y'],'unit':'In percent','frequency':'P1D_L'},
   'values':[{'date':'2026-09-30','value':0.287},
             {'date':'2026-10-29','value':0.144},
             {'date':'2026-10-30','value':0.130}]},
  {'metadata':{'key':KEYS['10Y'],'unit':'In percent','frequency':'P1D_L'},
   'values':[{'date':'2026-09-30','value':0.586},
             {'date':'2026-10-28','value':0.495},
             {'date':'2026-10-29','value':0.536},
             {'date':'2026-10-30','value':0.505}]}
 ]}
class PairedRecovery(unittest.TestCase):
 def audit(self,source=BASE,rates=RATES,context=CONTEXT):
  return verify(copy.deepcopy(source),copy.deepcopy(rates),
                copy.deepcopy(context),asof=date(2026,10,31),
                source_hash='a'*64)
 def test_real_anchor_synthetic_intervening_dates_not_fabricated(self):
  result=self.audit()
  self.assertEqual(result['schema'],SCHEMA)
  self.assertEqual(result['status'],'PAIRED_OFFICIAL_HISTORY_READY_FOR_REVIEW')
  self.assertEqual(result['matched_paired_rows'],3)
  self.assertEqual(result['new_paired_rows'],2)
  self.assertEqual([r['date'] for r in result['paired_source_rows']],
                   ['2026-09-30','2026-10-29','2026-10-30'])
  self.assertTrue(result['separately_published_snb_10y_matches_same_date'])
  self.assertFalse(result['eligible_for_automatic_promotion'])
  self.assertFalse(result['writes_operational_rates'])
  self.assertTrue(result['historic_gap_backfilled_from_observations_not_interpolated'])
  self.assertFalse(result['unmatched_or_weekend_dates_fabricated'])
  self.assertEqual(result['source_response_sha256'],'a'*64)
 def test_missing_latest_2y_never_joins_old_2y_to_new_10y(self):
  b=copy.deepcopy(BASE);b['timeseries'][0]['values'].pop()
  result=self.audit(b)
  self.assertEqual(result['last_common_date'],'2026-10-29')
  self.assertFalse(result['separately_published_snb_10y_matches_same_date'])
  self.assertFalse(any(r['date']=='2026-10-30' for r in result['paired_source_rows']))
 def test_official_webpage_10y_revision_is_not_marked_confirmed(self):
  c=copy.deepcopy(CONTEXT);c['value_percent']+=.02
  self.assertFalse(self.audit(context=c)[
      'separately_published_snb_10y_matches_same_date'])
 def test_invalid_source_unit_frequency_duplicate_and_tenor(self):
  bads=[
   lambda p:p['timeseries'][0]['metadata'].__setitem__('unit','CHF'),
   lambda p:p['timeseries'][1]['metadata'].__setitem__('frequency','P1M'),
   lambda p:p['timeseries'][1]['metadata'].__setitem__('key','FAKE'),
   lambda p:p['timeseries'][0]['values'].append(copy.deepcopy(
       p['timeseries'][0]['values'][0])),
   lambda p:p['timeseries'][0]['values'][2].__setitem__('date','2026-11-02'),
   lambda p:p['timeseries'][0]['values'][1].__setitem__('value',True),
  ]
  for modify in bads:
   with self.subTest(change=repr(modify)):
    p=copy.deepcopy(BASE);modify(p)
    with self.assertRaises((ValueError,TypeError)):
     self.audit(p)
 def test_anchor_changed_fails_closed(self):
  b=copy.deepcopy(BASE);b['timeseries'][0]['values'][0]['value']=.286
  self.assertEqual(self.audit(b)['status'],'SOURCE_BASIS_NOT_RECONCILED')
 def test_live_rate_tamper_fails(self):
  a=copy.deepcopy(RATES);a['CHF']['2Y']+=.01
  with self.assertRaises(ValueError):
   self.audit(rates=a)
 def test_expired_source_no_current_promotion(self):
  b=copy.deepcopy(BASE)
  for row in b['timeseries']:row['values']=row['values'][:1]
  self.assertEqual(self.audit(b)['status'],'OFFICIAL_PAIRED_HISTORY_NOT_CURRENT')
if __name__=='__main__':unittest.main(verbosity=2)
