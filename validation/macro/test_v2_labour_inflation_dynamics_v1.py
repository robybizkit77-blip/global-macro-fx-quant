import unittest
from validation.macro.v2_labour_inflation_dynamics_v1 import rate_dynamics,run

class TestLabourInflationDynamics(unittest.TestCase):
    def test_rate_changes_are_points_not_percentage_returns(self):
        r=rate_dynamics({1:("2026-01",2.),2:("2026-02",3.),3:("2026-03",3.5)})
        self.assertEqual((r["velocity_pp"],r["acceleration_pp"]),(0.5,-0.5))
    def test_gaps_not_filled(self):
        r=rate_dynamics({1:("2026-01",2.),3:("2026-03",3.5)})
        self.assertIsNone(r["velocity_pp"])
        self.assertIsNone(r["acceleration_pp"])
    def test_actual_archive(self):
        d=run()
        self.assertEqual(len(d["countries"]),8)
        self.assertEqual(sum(map(len,d["countries"].values())),41)
        for c,rows in d["countries"].items():
            for r in rows[:2]:
                self.assertEqual(r["measurement"],"RATE")
                self.assertIsNotNone(r["level"])
            self.assertEqual({r["pillar"] for r in rows},{"labour","inflation"})
        self.assertFalse(d["safe_to_update_pairs"])
        print("DYNAMICS_ACTUAL_COVERAGE", {c:sum(r["measurement"]!="WITHHELD" for r in rows) for c,rows in d["countries"].items()})
