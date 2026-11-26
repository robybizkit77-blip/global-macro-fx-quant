import io,unittest
from datetime import datetime
from openpyxl import Workbook
from validation.macro.prepare_aud_abs_activity_revised_v1 import parse_book,locate
def fixture(duplicate=False):
    w=Workbook();s=w.active;s.title="Data1"
    s.append(["","Employed ; Persons ;","Employed ; Persons ;"])
    s.append(["Unit","'000","'000"])
    s.append(["Series Type","Seasonally Adjusted","Seasonally Adjusted" if duplicate else "Trend"])
    s.append(["Series ID","A123","A456"])
    for n in range(30):s.append([datetime(2024+n//12,n%12+1,1),14000+n,14000+n])
    f=io.BytesIO();w.save(f);return f.getvalue()
class Tests(unittest.TestCase):
    def test_exact_column(self):
        old={f"{2024+n//12}-{n%12+1:02d}":14000+n for n in range(27)}
        ident,title,unit,ds,vs,med,mx=parse_book(fixture(),"employment",old,"2026-06")
        self.assertEqual(ident,"A123");self.assertEqual(vs[-1],14029);self.assertEqual(mx,0)
        with self.assertRaises(ValueError):parse_book(fixture(True),"employment",old,"2026-06")
    def test_locate(self):
        html='<h4>Table 1</h4><a href="/file.xlsx">Download xlsx</a><h4>Next</h4><a href="/other.xlsx">Download</a>'
        self.assertEqual(locate(html,"https://www.abs.gov.au/statistics/","Table 1"),"https://www.abs.gov.au/file.xlsx")
        with self.assertRaises(ValueError):locate(html.replace("/file.xlsx","https://example.com/file.xlsx"),"https://www.abs.gov.au/","Table 1")
if __name__=="__main__":unittest.main()
