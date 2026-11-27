import unittest,json
from datetime import date
from validation.macro.collect_sector_output_research_v1 import collect_ons
class TestONSServiceOutput(unittest.TestCase):
    def payload(self):
        months=[dict(date=f"{y} {m}",value=str(100+i)) for i,(y,m) in enumerate((y,m) for y in range(2020,2024) for m in "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())]
        return dict(description=dict(cdid="S2KU",title="IoS: Services: Index-1dp",unit="Index, base year = 100"),months=months)
    def test_identity_and_history(self):
        p=self.payload()
        r=collect_ons(date(2026,11,27),lambda _:json.dumps(p).encode())
        self.assertEqual(len(r["dates"]),48)
        self.assertFalse(r["source_series_first_release_PIT_certified"])
    def test_missing_unit_and_conflicting_unit(self):
        p=self.payload();p["description"]["unit"]=""
        r=collect_ons(date(2026,11,27),lambda _:json.dumps(p).encode())
        self.assertEqual(r["publisher_unit_raw"],"")
        p["description"]["unit"]="Percent"
        with self.assertRaises(ValueError):collect_ons(date(2026,11,27),lambda _:json.dumps(p).encode())
    def test_wrong_id_and_gap(self):
        p=self.payload();p["description"]["cdid"]="BAD"
        with self.assertRaises(ValueError):collect_ons(date(2026,11,27),lambda _:json.dumps(p).encode())
        p=self.payload();del p["months"][10]
        with self.assertRaises(ValueError):collect_ons(date(2026,11,27),lambda _:json.dumps(p).encode())
