import unittest
from validation.macro.v2_sector_financial_dynamics_v1 import parse,calculate,run,nzd_rows
class TestSectorFinancialDynamics(unittest.TestCase):
    def test_period_aliases(self):
        self.assertEqual(parse("2026Q3","Q"),parse("2026-07-01","Q"))
        self.assertEqual(parse("30/09/2026","M"),parse("30 Sep 2026","M"))
        self.assertEqual(parse("2026-10-01T00:00:00Z","M"),parse("2026-10","M"))
    def test_stock_not_flow(self):
        r=calculate({i:(str(i),100+i*10) for i in range(1,7)},"M","STOCK")
        self.assertAlmostEqual(r["momentum_pct"],100*(160/130-1))
        self.assertEqual(r["horizon"],"STOCK_3M_ENDPOINT")
    def test_survey_can_be_negative(self):
        r=calculate({1:("a",-5),2:("b",-3),3:("c",-4)},"M","BALANCE")
        self.assertEqual(r["velocity_pp"],-1)
        self.assertEqual(r["acceleration_pp"],-3)
    def test_exact_daily_and_weekly_stock_acceleration(self):
        for freq,step in (("D",1),("W",7)):
            with self.subTest(freq=freq):
                data={i*step:(str(i),value) for i,value in enumerate((100,110,132,145.2))}
                r=calculate(data,freq,"STOCK")
                self.assertAlmostEqual(r["momentum_pct"],10)
                self.assertAlmostEqual(r["velocity_pp"],-10)
                self.assertAlmostEqual(r["acceleration_pp"],-20)
                # Without the oldest exact endpoint, no invented acceleration.
                del data[0]
                partial=calculate(data,freq,"STOCK")
                self.assertAlmostEqual(partial["velocity_pp"],-10)
                self.assertIsNone(partial["acceleration_pp"])
                # An adjacent but off-grid observation cannot replace it.
                if step==7:
                    data[1]=("off-grid",100)
                    self.assertIsNone(calculate(data,freq,"STOCK")["acceleration_pp"])
                data[0]=("invalid",0)
                self.assertIsNone(calculate(data,freq,"STOCK")["acceleration_pp"])
    def test_daily_gap(self):
        r=calculate({1:("a",100),4:("b",110)},"D","STOCK")
        self.assertIsNone(r["momentum_pct"])
    def test_archive(self):
        d=run()
        self.assertEqual(len(d["countries"]),8)
        self.assertEqual(sum(map(len,d["countries"].values())),64)
        self.assertEqual(len(d["countries"]["NZD"]),8)
        self.assertEqual(len(nzd_rows("",__import__("datetime").date(2026,11,27))),7)
        self.assertTrue(all(r["measurement"]=="WITHHELD" for r in nzd_rows("",__import__("datetime").date(2026,11,27))))
        self.assertFalse(d["safe_to_publish_D"])
        print("SECTOR_VALIDATED", {c:sum(r["measurement"]!="WITHHELD" for r in rs) for c,rs in d["countries"].items()})
