#!/usr/bin/env python3
"""Chapter 23.3 research-only regression sensitivity tests."""
import datetime as dt
import math
import unittest
from validation.beta.rate_beta_observational_v1 import ols_beta
from validation.beta.beta_regression_diagnostics_research_v1 import diagnose,SCHEMA

class DiagnosticsTest(unittest.TestCase):
    def rows(self):
        return [
            (dt.date(2025,1,3)+dt.timedelta(weeks=i),
             0.012+2*((i*7)%31-15)/100+0.002*math.sin(i*1.29),
             ((i*7)%31-15)/100)
            for i in range(52)
        ]
    def test_original_ols_preserved_and_no_promotion(self):
        rows=self.rows()
        a=diagnose(rows);b=diagnose(rows)
        self.assertEqual(a,b)
        self.assertEqual(a["schema"],SCHEMA)
        self.assertEqual(a["status"],"RESEARCH_DIAGNOSTIC_ONLY")
        self.assertAlmostEqual(a["beta_ols_original_contract"],ols_beta(rows),places=12)
        self.assertTrue(a["ols_hc3_standard_error"]>0)
        self.assertTrue(a["huber_converged"])
        self.assertTrue(math.isfinite(a["huber_beta"]))
        self.assertFalse(a["beta_promoted"])
        self.assertFalse(a["source_first_publication_pit_verified"])
        self.assertFalse(a["rates_instrument_comparability_verified"])
        self.assertFalse(a["performance_claim"])
        self.assertEqual(a["core_effect"],"NONE")
        self.assertEqual(a["pair_signal_effect"],"NONE")
    def test_huber_reduces_spike_sensitivity(self):
        rows=self.rows()
        d,y,x=rows[20];rows[20]=(d,y+2.5,x)
        a=diagnose(rows)
        self.assertEqual(a["status"],"RESEARCH_DIAGNOSTIC_ONLY")
        self.assertTrue(a["huber_converged"])
        self.assertLess(abs(a["huber_beta"]-2),abs(a["beta_ols_original_contract"]-2))
        self.assertGreater(a["max_single_week_leave_one_out_ols_change"],0)
    def test_constant_rate_spread_is_undefined(self):
        rows=[(d,y,0.0) for d,y,x in self.rows()]
        a=diagnose(rows)
        self.assertEqual(a["status"],"NO_VALID_VARIANCE")
        self.assertIsNone(a["beta_ols_original_contract"])
        self.assertIsNone(a["ols_hc3_standard_error"])
    def test_source_alignment_rejected(self):
        rows=self.rows()
        with self.assertRaises(ValueError):diagnose(rows[:51])
        gap=rows.copy()
        gap[19]=(gap[19][0]+dt.timedelta(days=1),gap[19][1],gap[19][2])
        with self.assertRaises(ValueError):diagnose(gap)
        rows[5]=(rows[5][0],float("nan"),rows[5][2])
        with self.assertRaises(ValueError):diagnose(rows)
    def test_no_boolean_or_non_numeric_inputs(self):
        rows=self.rows()
        rows[5]=(rows[5][0],rows[5][1],True)
        with self.assertRaises(ValueError):diagnose(rows)

if __name__=="__main__":unittest.main()
