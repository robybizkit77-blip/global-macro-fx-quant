import unittest
from validation.macro.v2_current_activity_momentum_v1 import momentum, run

class ActivityMomentumTests(unittest.TestCase):
    def test_monthly_uses_six_consecutive_levels(self):
        data={i:(str(i),float(i+10)) for i in range(8)}
        r=momentum(data,"M")
        self.assertAlmostEqual(r["momentum_pct"],100*(48/39-1))
        self.assertAlmostEqual(r["previous_momentum_pct"],100*(45/36-1))
        self.assertAlmostEqual(r["velocity_pp"],100*(48/39-45/36))
        self.assertEqual(r["horizon"],"ROLLING_3M_OVER_PREVIOUS_3M")
    def test_gap_withheld(self):
        data={i:(str(i),float(i+10)) for i in range(8) if i!=4}
        self.assertIsNone(momentum(data,"M")["momentum_pct"])
    def test_quarterly_is_qoq(self):
        r=momentum({i:(str(i),v) for i,v in enumerate([100,102,101,104])},"Q")
        self.assertAlmostEqual(r["momentum_pct"],100*(104/101-1))
        self.assertEqual(r["turning_point"],"DOWN_TO_UP")
        self.assertEqual(r["change_interval"],"QUARTER")
    def test_current_source_scope(self):
        r=run()
        self.assertEqual(len(r["countries"]),8)
        self.assertTrue(r["countries"]["AUD"][0]["nominal_not_real"])
        self.assertFalse(r["safe_to_publish_D"])
        self.assertFalse(r["safe_to_update_pairs"])
        self.assertFalse(r["writes_live_data"])
