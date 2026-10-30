"""Regression: JPY TONA may change OIS without changing already-current native pricing."""
from __future__ import annotations
import copy
import unittest
from validation.cb_pricing.apply_jpy_tfx_tona_candidate import assert_jpy_only_deltas

class ApplyJpyTonaOnlyDeltaTests(unittest.TestCase):
    def setUp(self):
        self.ois={'currencies':{'JPY':{'as_of':'2026-10-28'},'AUD':{'as_of':'2026-10-28'}}}
        self.native={'JPY':{'market_3m':'1.4680%'},'AUD':{'market_3m':'5.00%'}}

    def run_case(self, update_ois, update_native):
        o=copy.deepcopy(self.ois)
        n=copy.deepcopy(self.native)
        if update_ois:
            o['currencies']['JPY']['as_of']='2026-10-29'
        if update_native:
            n['JPY']['market_3m']='1.5000%'
        return assert_jpy_only_deltas(self.ois,o,self.native,n)

    def test_ois_only_reproduces_morning_failure(self):
        self.assertEqual(self.run_case(True,False),(['JPY'],[]))

    def test_native_only(self):
        self.assertEqual(self.run_case(False,True),([],['JPY']))

    def test_both_layers(self):
        self.assertEqual(self.run_case(True,True),(['JPY'],['JPY']))

    def test_noop_remains_idempotent(self):
        self.assertEqual(self.run_case(False,False),([],[]))

    def test_cross_currency_mutation_still_fails_closed(self):
        o=copy.deepcopy(self.ois); n=copy.deepcopy(self.native)
        o['currencies']['AUD']['as_of']='2026-10-29'
        with self.assertRaisesRegex(SystemExit,'non-JPY semantic delta'):
            assert_jpy_only_deltas(self.ois,o,self.native,n)
        o=copy.deepcopy(self.ois)
        n['AUD']['market_3m']='5.15%'
        with self.assertRaisesRegex(SystemExit,'non-JPY semantic delta'):
            assert_jpy_only_deltas(self.ois,o,self.native,n)

if __name__=='__main__': unittest.main()
