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

class TestCADRealSectorOutput(unittest.TestCase):
    def source(self):
        import csv,io
        out=io.StringIO()
        fields=["REF_DATE","GEO","UOM","SCALAR_FACTOR","VECTOR","VALUE","Prices","Seasonal adjustment","North American Industry Classification System (NAICS)"]
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for y in range(2020,2024):
            for m in range(1,13):
                for name,vector,value in [("Manufacturing [31-33]","v1",200000),("Services-producing industries [T003]","v2",1700000)]:
                    writer.writerow(dict(zip(fields,[f"{y}-{m:02d}","Canada","Dollars","millions",vector,value,"Chained (2017) dollars","Seasonally adjusted at annual rates",name])))
        return out.getvalue()
    def test_two_exact_sectors(self):
        from validation.macro.collect_sector_output_research_v1 import collect_cad
        rows=collect_cad(self.source(),date(2026,11,27))
        self.assertEqual([(r["pillar"],len(r["dates"]),r["source_series_id"]) for r in rows],[("manufacturing",48,"v1"),("services",48,"v2")])
    def test_wrong_units_and_duplicate(self):
        from validation.macro.collect_sector_output_research_v1 import collect_cad
        raw=self.source()
        with self.assertRaises(ValueError):collect_cad(raw.replace("Chained (2017) dollars","Current dollars"),date(2026,11,27))
        with self.assertRaises(ValueError):collect_cad(raw+raw.splitlines()[1]+"\n",date(2026,11,27))
