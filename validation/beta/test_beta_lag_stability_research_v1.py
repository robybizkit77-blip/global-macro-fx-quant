import datetime as dt
import math
import unittest
from validation.beta.beta_lag_stability_research_v1 import (
    historical_dimson_52w,rolling_52w_stability,diagnose)

class LagAndStabilityTest(unittest.TestCase):
    def panel(self,n=60):
        base=dt.date(2025,1,3)
        x=[(((i*11)%37)-18)*.009+math.sin(i*.29)*.017 for i in range(n)]
        rows=[]
        for i in range(n):
            # Lead/lag relationships exist only in synthetic historical observations.
            y=.03+.8*x[i]+(.23*x[i-1] if i>0 else 0)+(
                -.1*x[i+1] if i+1<n else 0)+math.sin(i*1.4)*.0001
            rows.append((base+dt.timedelta(weeks=i),y,x[i]))
        return rows
    def test_in_sample_lag_lead_and_sum(self):
        result=historical_dimson_52w(self.panel()[:52])
        self.assertEqual(result["status"],"DESCRIPTIVE_ONLY")
        self.assertAlmostEqual(result["dimson_lag_beta"],.23,delta=.02)
        self.assertAlmostEqual(result["dimson_contemporaneous_beta"],.8,delta=.02)
        self.assertAlmostEqual(result["dimson_lead_beta"],-.1,delta=.02)
        self.assertTrue(result["no_future_observation_beyond_training_cutoff"])
        self.assertFalse(result["pit_first_release_certified"])
    def test_rolling_exact_past_sample(self):
        whole=self.panel()
        a=rolling_52w_stability(whole)
        self.assertEqual(a["status"],"DESCRIPTIVE_ONLY")
        self.assertEqual(a["windows_observed"],4)
        self.assertTrue(a["four_windows_available"])
        self.assertEqual(len(a["betas"]),4)
        self.assertGreaterEqual(a["beta_range"],0)
        self.assertFalse(a["first_release_pit_certified"])
        self.assertEqual(diagnose(whole)["beta_promoted"],False)
    def test_52_first_beta_not_four_samples(self):
        result=rolling_52w_stability(self.panel()[:52])
        self.assertEqual(result["windows_observed"],1)
        self.assertFalse(result["four_windows_available"])
    def test_missing_week_fail_closed(self):
        rows=self.panel()
        d,y,x=rows[17]
        rows[17]=(d+dt.timedelta(days=1),y,x)
        with self.assertRaisesRegex(ValueError,"continuous"):diagnose(rows)
    def test_nonfinite_and_constant_spread(self):
        rows=self.panel()[:52]
        d,y,x=rows[5]
        rows[5]=(d,float("nan"),x)
        with self.assertRaisesRegex(ValueError,"nonfinite"):diagnose(rows)
        rows=self.panel()[:52]
        rows=[(d,y,1.) for d,y,x in rows]
        self.assertEqual(historical_dimson_52w(rows)["status"],"SINGULAR_DESIGN_NO_DIAGNOSTIC")
        self.assertEqual(rolling_52w_stability(rows)["status"],"ZERO_VARIANCE")
    def test_rolls_do_not_see_later_week(self):
        a=rolling_52w_stability(self.panel(58)[:55])
        altered=self.panel(58)
        d,y,x=altered[57]
        altered[57]=(d,1000.,x)
        self.assertEqual(a,rolling_52w_stability(altered[:55]))
    def test_insufficient_window(self):
        self.assertEqual(diagnose(self.panel()[:51])["status"],"INSUFFICIENT_HISTORY")

if __name__=="__main__":unittest.main()
