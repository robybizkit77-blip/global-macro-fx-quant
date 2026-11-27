import unittest
from validation.fetch_rates_usd_jpy import parse_mof
class Tests(unittest.TestCase):
    def test_exact_same_day_secondary(self):
        r=parse_mof(b"Date,2Y,5Y,10Y,30Y\n2026/11/25,1.7,2.1,2.7,3.8\n2026/11/26,1.8,2.2,2.8,3.9\n")
        self.assertEqual((r["date"],r["5Y"],r["30Y"]),("2026-11-26",2.2,3.9))
    def test_missing_not_backfilled(self):
        r=parse_mof(b"Date,2Y,5Y,10Y,30Y\n2026/11/25,1.7,2.1,2.7,3.8\n2026/11/26,1.8,,2.8,nan\n")
        self.assertNotIn("5Y",r);self.assertNotIn("30Y",r)
    def test_ambiguous_header(self):
        r=parse_mof(b"Date,2Y,5Y,5 year,10Y,30Y\n2026/11/26,1.8,2.2,3.2,2.8,3.9\n")
        self.assertNotIn("5Y",r);self.assertEqual(r["30Y"],3.9)
if __name__=="__main__":unittest.main()
