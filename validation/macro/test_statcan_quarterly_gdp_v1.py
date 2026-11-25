from datetime import date
import unittest

from validation.macro.statcan_quarterly_gdp_v1 import (
    Pending, SEED_URL, bulletin, parse_table,
)


def table(title="Real gross domestic product by expenditure account, quarterly change – Seasonally adjusted at annual rates, chained (2017) dollars"):
    return f"""<html><h1>{title}</h1><p>First quarter 2025 Second quarter 2025 Third quarter 2025 Fourth quarter 2025 First quarter 2026 Second quarter 2026 First quarter 2026 Second quarter 2026</p><p>quarter-to-quarter % change</p><p>Final consumption expenditure</p><p>Gross domestic product at market prices 0.7 -0.2 0.5 -0.2 0.1 0.8 2,503,604 2,524,127</p><p>Final domestic demand</p></html>""".encode()


class StatCanTests(unittest.TestCase):
    def test_q2_real_table(self):
        self.assertEqual(parse_table(table(),"2026Q2"),(0.8,0.1))
        with self.assertRaises(Pending):
            parse_table(table(),"2026Q3")
        with self.assertRaises(Pending):
            parse_table(table("Nominal GDP"),"2026Q2")

    def test_bulletin_and_next_date(self):
        raw=b'<html><h1>Gross domestic product, income and expenditure, second quarter 2026</h1><p>Released: 2026-08-28</p><a href="t002a-eng.htm">Table 2</a><p>Data on GDP by income and expenditure for the third quarter of 2026 will be released on November 30.</p></html>'
        day,url,nxt=bulletin(raw,SEED_URL,"2026Q2",date(2026,11,25))
        self.assertEqual(day,date(2026,8,28))
        self.assertTrue(url.endswith("/260828/t002a-eng.htm"))
        self.assertEqual(nxt,date(2026,11,30))
        with self.assertRaises(Pending):
            bulletin(raw,SEED_URL,"2026Q2",date(2026,8,27))


if __name__ == "__main__":
    unittest.main()
