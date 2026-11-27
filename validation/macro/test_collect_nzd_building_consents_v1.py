import unittest
from datetime import date
from validation.macro.collect_nzd_building_consents_v1 import parse,BASE
class TestNZHousing(unittest.TestCase):
    def raw(self,heading="Category",anchor=3218):
        dates=[f"{y}-{m:02d}-01" for y in range(2020,2027) for m in range(1,13) if f"{y}-{m:02d}"<="2026-09"]
        rows="".join(f"<tr><td>{d}</td><td>3570</td><td>{anchor if d=='2026-09-01' else 3495 if d=='2026-08-01' else 3000}</td><td>3350</td></tr>" for d in dates)
        return ("<html><h1>Building consents issued: September 2026</h1><p>03 November 2026, 10:45am</p><h2>New dwellings consented, monthly, January 1995–September 2026</h2><table><tr><th>"+heading+"</th><th>Actual</th><th>Seasonally adjusted</th><th>Trend</th></tr>"+rows+"</table></html>").encode()
    def test_sa_not_actual(self):
        r=parse(self.raw(),"2026-09",date(2026,11,27),BASE+"september-2026/")
        self.assertEqual(r["values"][-2:],[3495,3218])
        self.assertFalse(r["source_series_first_release_PIT_certified"])
    def test_wrong_header_and_anchor(self):
        for raw in (self.raw("Wrong"),self.raw(anchor=3570)):
            with self.assertRaises(ValueError):parse(raw,"2026-09",date(2026,11,27),BASE+"september-2026/")
